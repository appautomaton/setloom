# SPDX-License-Identifier: AGPL-3.0-only
"""Harness-facing API for the MLX BS-RoFormer: load, configure, and separate.

Typical use is two calls::

    from setloom.anatomy.roformer import separate as rf

    model, config = rf.load_model("models/roformer/bs-roformer-53stem-mlx-bf16.safetensors")
    stems = rf.separate_track(model, config, mix)  # {name: (channels, time)}

``load_model`` reads the sibling ``.yaml`` and the weights; ``separate_track`` pulls
the instrument list and chunk settings from the config. The lower-level primitives
(``load_config`` / ``build_model`` / ``instruments`` / ``chunk_size`` / ``load_weights``
/ ``separate``) stay available for finer control, and ``convert`` turns an upstream
torch checkpoint into a bf16 ``.safetensors``.

Precision follows the weights: bf16 weights run bf16-mixed (~1.4x faster; STFT/iSTFT
stay fp32), fp32 weights run exact fp32. See :mod:`setloom.anatomy.roformer.weights`.

The overlap-add chunking uses reflect-padded edges, linear fade windows, and counter
normalization so chunk seams cancel exactly.
"""

from __future__ import annotations

from pathlib import Path

import mlx.core as mx
import numpy as np
import yaml

from setloom.anatomy.roformer.model import BSRoformer
from setloom.anatomy.roformer.weights import convert, load_weights  # noqa: F401  (re-exported)


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


def chunk_size(config: dict) -> int:
    """Inference chunk length. Prefer the ``inference`` section, fall back to ``audio``."""
    inference = config.get("inference", {})
    if "chunk_size" in inference:
        return int(inference["chunk_size"])
    return int(config["audio"]["chunk_size"])


def load_model(
    weights_path: Path | str, config_path: Path | str | None = None
) -> tuple[BSRoformer, dict]:
    """Load a ready-to-run separator and return ``(model, config)``.

    ``config_path`` defaults to the weights' sibling ``.yaml``. The model runs in the
    weights' precision (bf16 weights -> bf16-mixed, fp32 weights -> exact fp32).
    """
    weights_path = Path(weights_path)
    if config_path is None:
        config_path = weights_path.with_suffix(".yaml")
    config = load_config(config_path)
    model = build_model(config)
    load_weights(model, weights_path)
    return model, config


def _fade_window(size: int, fade: int) -> np.ndarray:
    window = np.ones(size, dtype=np.float32)
    window[:fade] = np.linspace(0.0, 1.0, fade, dtype=np.float32)
    window[-fade:] = np.linspace(1.0, 0.0, fade, dtype=np.float32)
    return window


def separate(
    model: BSRoformer,
    mix: np.ndarray,
    names: list[str],
    *,
    chunk_size: int,
    num_overlap: int = 2,
) -> dict[str, np.ndarray]:
    """Split ``mix`` (channels, time) into ``{name: (channels, time)}`` stems.

    The low-level primitive: callers pass the stem names and chunk settings explicitly.
    Use :func:`separate_track` to take those from a config.
    """
    n_stems = len(names)
    channels, length = mix.shape
    fade = chunk_size // 10
    step = chunk_size // num_overlap
    border = chunk_size - step

    x = mix.astype(np.float32)
    if length > 2 * border and border > 0:
        x = np.pad(x, ((0, 0), (border, border)), mode="reflect")
    total = x.shape[-1]

    out = np.zeros((n_stems, channels, total), dtype=np.float32)
    counter = np.zeros(total, dtype=np.float32)
    window = _fade_window(chunk_size, fade)

    i = 0
    while i < total:
        seg = x[:, i : i + chunk_size]
        seg_len = seg.shape[-1]
        chunk = np.zeros((channels, chunk_size), dtype=np.float32)
        chunk[:, :seg_len] = seg

        stems = model(mx.array(chunk)[None])  # (1, c, T) -> (1, [n,] c, T)
        if model.num_stems == 1:
            stems = stems[:, None]
        stems = np.array(stems[0])  # (n, c, T), forces evaluation

        win = window.copy()
        if i == 0:
            win[:fade] = 1.0
        if i + step >= total:
            win[-fade:] = 1.0
        out[:, :, i : i + seg_len] += stems[:, :, :seg_len] * win[:seg_len]
        counter[i : i + seg_len] += win[:seg_len]
        i += step

    out /= np.maximum(counter, 1e-8)
    if length > 2 * border and border > 0:
        out = out[:, :, border:-border]
    return {name: out[k] for k, name in enumerate(names)}


def separate_track(model: BSRoformer, config: dict, mix: np.ndarray) -> dict[str, np.ndarray]:
    """Split a full mix using the instrument list and chunk settings from ``config``."""
    return separate(
        model,
        mix,
        instruments(config),
        chunk_size=chunk_size(config),
        num_overlap=int(config.get("inference", {}).get("num_overlap", 2)),
    )
