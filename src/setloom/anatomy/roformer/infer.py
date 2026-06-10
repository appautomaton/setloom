# SPDX-License-Identifier: AGPL-3.0-only
"""Config loading, checkpoint loading, and chunked inference for BS-RoFormer.

The overlap-add windowed chunking in :func:`separate` is adapted from
``demix()`` in ZFTurbo/Music-Source-Separation-Training ``utils/model_utils.py``
(MIT License): reflect-padded edges, linear fade windows, and a counter
normalization so chunk seams cancel exactly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import yaml

from setloom.anatomy.roformer.bs_roformer import BSRoformer


class _ConfigLoader(yaml.SafeLoader):
    """SafeLoader that accepts the ``!!python/tuple`` tag used by upstream configs."""


_ConfigLoader.add_constructor(
    "tag:yaml.org,2002:python/tuple",
    lambda loader, node: tuple(loader.construct_sequence(node)),
)


def load_config(path: Path | str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_ConfigLoader)


def build_model(config: dict) -> BSRoformer:
    return BSRoformer(**dict(config["model"]))


def instruments(config: dict) -> list[str]:
    training = config["training"]
    target = training.get("target_instrument")
    return [target] if target else list(training["instruments"])


def load_weights(model: torch.nn.Module, ckpt_path: Path | str) -> None:
    state = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    # Upstream checkpoints sometimes nest the state dict; unwrap the known keys.
    for key in ("state", "state_dict", "model_state_dict"):
        if key in state:
            state = state[key]
    model.load_state_dict(state)
    model.eval()


def _fade_window(window_size: int, fade_size: int) -> torch.Tensor:
    window = torch.ones(window_size)
    window[:fade_size] *= torch.linspace(0.0, 1.0, fade_size)
    window[-fade_size:] *= torch.linspace(1.0, 0.0, fade_size)
    return window


def separate(
    model: torch.nn.Module,
    mix: np.ndarray,
    names: list[str],
    *,
    chunk_size: int,
    num_overlap: int = 2,
    batch_size: int = 1,
    device: str = "cpu",
) -> dict[str, np.ndarray]:
    """Split ``mix`` (channels, time) into ``{name: (channels, time)}`` stems."""
    x = torch.tensor(mix, dtype=torch.float32)
    fade_size = chunk_size // 10
    step = chunk_size // num_overlap
    border = chunk_size - step
    length = x.shape[-1]
    window = _fade_window(chunk_size, fade_size)
    if length > 2 * border and border > 0:
        x = torch.nn.functional.pad(x, (border, border), mode="reflect")

    result = torch.zeros((len(names),) + x.shape, dtype=torch.float32)
    # The fade window is identical across stems and channels, so a 1-D counter
    # suffices — at 53 stems the full-shape counter would waste gigabytes.
    counter = torch.zeros(x.shape[-1], dtype=torch.float32)

    with torch.inference_mode():
        batch: list[torch.Tensor] = []
        locations: list[tuple[int, int]] = []
        i = 0
        while i < x.shape[-1]:
            part = x[:, i : i + chunk_size].to(device)
            seg_len = part.shape[-1]
            pad_mode = "reflect" if seg_len > chunk_size // 2 else "constant"
            part = torch.nn.functional.pad(
                part, (0, chunk_size - seg_len), mode=pad_mode, value=0
            )
            batch.append(part)
            locations.append((i, seg_len))
            i += step

            if len(batch) >= batch_size or i >= x.shape[-1]:
                out = model(torch.stack(batch, dim=0))
                win = window.clone()
                if i - step * len(batch) == 0:
                    win[:fade_size] = 1
                if i >= x.shape[-1]:
                    win[-fade_size:] = 1
                for j, (start, seg) in enumerate(locations):
                    result[..., start : start + seg] += out[j, ..., :seg].cpu() * win[:seg]
                    counter[start : start + seg] += win[:seg]
                batch.clear()
                locations.clear()

    stems = (result / counter.clamp(min=1e-8)).numpy()
    np.nan_to_num(stems, copy=False, nan=0.0)
    if length > 2 * border and border > 0:
        stems = stems[..., border:-border]
    return dict(zip(names, stems))
