# SPDX-License-Identifier: AGPL-3.0-only
"""Load BS-RoFormer weights from upstream PyTorch checkpoints into the MLX model.

Upstream checkpoints (the mvsep / jarredou MSST ecosystem) ship as torch ``.ckpt``
state dicts. We read one with torch a single time, rename its keys to match the
module tree in :mod:`setloom.anatomy.roformer.model`, and save the result as an MLX
``.safetensors`` model file. Inference then loads that file directly and never
imports torch.

The rename covers the small, systematic differences between the PyTorch and MLX
layouts: norm ``gamma`` -> ``weight``, ``Sequential`` index ``.N`` -> ``.layers.N``,
dotted block paths -> underscored module names. The key scheme references
ssmall256's mlx-audio-separator (MIT); see LICENSES/NOTICE.
"""

from __future__ import annotations

import re
from pathlib import Path

import mlx.core as mx
import numpy as np


def _read_torch_state_dict(ckpt_path: Path) -> dict:
    """Open a PyTorch checkpoint and return its flat parameter dict."""
    import torch

    state = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    if isinstance(state, dict):
        for key in ("state_dict", "state", "model"):
            if key in state and isinstance(state[key], dict):
                return state[key]
    return state


def _rename(key: str, has_linear: bool) -> str:
    """Map one upstream torch parameter name to its MLX-model equivalent."""
    k = key.replace(".gamma", ".weight")

    # Band split: band_split.to_features.{i}.{0,1}.* -> to_features_{i}.{norm,linear}.*
    m = re.match(r"^band_split\.to_features\.(\d+)\.([01])\.(.+)$", k)
    if m:
        part = "norm" if m.group(2) == "0" else "linear"
        k = f"band_split.to_features_{m.group(1)}.{part}.{m.group(3)}"

    # Block transformer branch: layers.{i}.{0,1,2}.* -> layers_{i}.{name}_transformer.*
    m = re.match(r"^layers\.(\d+)\.([012])\.(.+)$", k)
    if m:
        names = ("linear", "time", "freq") if has_linear else ("time", "freq")
        k = f"layers_{m.group(1)}.{names[int(m.group(2))]}_transformer.{m.group(3)}"

    # Transformer sub-layer: .layers.{j}.{0,1}. -> .layers_{j}.{attn,ff}.
    m = re.search(r"\.layers\.(\d+)\.([01])\.", k)
    if m:
        part = "attn" if m.group(2) == "0" else "ff"
        k = k[: m.start()] + f".layers_{m.group(1)}.{part}." + k[m.end():]

    # Mask estimators: mask_estimators.{i} -> mask_estimators_{i}; to_freqs.{j}.0. -> to_freqs_{j}.
    k = re.sub(r"mask_estimators\.(\d+)", r"mask_estimators_\1", k)
    k = re.sub(r"to_freqs\.(\d+)\.0\.", r"to_freqs_\1.", k)

    # Sequential indices -> .layers.N
    k = re.sub(r"\.net\.(\d+)\.", r".net.layers.\1.", k)
    k = re.sub(r"\.to_out\.(\d+)\.", r".to_out.layers.\1.", k)
    k = re.sub(r"(to_freqs_\d+)\.(\d+)\.", r"\1.layers.\2.", k)
    return k


def convert_checkpoint(ckpt_path: Path | str) -> dict[str, mx.array]:
    """Read a torch ``.ckpt`` and return MLX weights keyed for the MLX model."""
    state = _read_torch_state_dict(Path(ckpt_path))
    has_linear = any(re.match(r"^layers\.\d+\.2\.", key) for key in state)
    weights: dict[str, mx.array] = {}
    for key, value in state.items():
        if "rotary_embed.freqs" in key:  # rotary is computed on the fly, not stored
            continue
        arr = value.detach().cpu().numpy() if hasattr(value, "detach") else np.asarray(value)
        weights[_rename(key, has_linear)] = mx.array(arr)
    return weights


def load_weights(model, weights_path: Path | str) -> None:
    """Load weights into ``model`` and switch it to eval mode.

    ``weights_path`` is either an MLX ``.safetensors`` file (the at-rest format,
    loaded directly with no torch) or an upstream PyTorch ``.ckpt`` (converted in
    memory via :func:`convert_checkpoint`). Eval mode is mandatory: separation is
    inference-only and MLX modules default to training mode, where the
    architecture's dropout layers would randomly perturb the output.
    """
    weights_path = Path(weights_path)
    if weights_path.suffix == ".safetensors":
        model.load_weights(str(weights_path), strict=True)
    else:
        model.load_weights(list(convert_checkpoint(weights_path).items()), strict=True)
    model.eval()


def convert(ckpt_path: Path | str, out_path: Path | str) -> None:
    """Convert an upstream torch ``.ckpt`` to a bf16 MLX ``.safetensors`` on disk.

    Run once to populate a model folder; inference then loads the safetensors
    directly and never imports torch. Weights are stored bf16: it halves the file
    and the model runs bf16-mixed (~1.4x faster) with output indistinguishable from
    fp32 (the STFT/iSTFT stay fp32 regardless; see ``BSRoformer.neural_dtype``).
    """
    weights = convert_checkpoint(Path(ckpt_path))
    weights = {key: value.astype(mx.bfloat16) for key, value in weights.items()}
    mx.save_safetensors(str(out_path), weights)
