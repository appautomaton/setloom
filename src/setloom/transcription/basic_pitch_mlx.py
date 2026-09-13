# SPDX-License-Identifier: AGPL-3.0-only
# Native reimplementation of Spotify Basic Pitch's ICASSP 2022 model architecture.
# Copyright 2022 Spotify AB, originally Apache-2.0; see LICENSES/NOTICE.
"""Fixed-window Basic Pitch inference using native MLX GPU operations.

Converted assets contain the original CQT filters and batch-normalization-fused
weights. ONNX is a conversion/reference dependency, never an inference backend.
The numerical BF16 experiments live only in scripts/validate_basic_pitch_mlx.py.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np


def _configure_fp32_precision() -> None:
    """Disable MLX's reduced-precision TF32 kernels before MLX initializes."""
    setting = os.environ.get("MLX_ENABLE_TF32")
    if setting is None and "mlx.core" in sys.modules:
        raise RuntimeError(
            "MLX is already imported without an explicit FP32 policy. "
            "Restart the process with MLX_ENABLE_TF32=0 for Basic Pitch."
        )
    if setting is not None and setting != "0":
        raise RuntimeError(
            "Basic Pitch's FP32 baseline requires MLX_ENABLE_TF32=0; set it before starting Python."
        )
    os.environ["MLX_ENABLE_TF32"] = "0"


def _load_assets(path: Path) -> tuple[dict, dict[str, np.ndarray]]:
    """Validate self-contained assets without initializing an accelerator."""
    from safetensors.numpy import load_file

    config = json.loads((path / "config.json").read_text())
    manifest = json.loads((path / "manifest.json").read_text())
    if config.get("architecture") != "basic-pitch-icassp-2022-mlx-fp32-v1":
        raise ValueError("Unsupported Basic Pitch MLX asset architecture")
    for name in ("config.json", "model.safetensors"):
        actual = hashlib.sha256((path / name).read_bytes()).hexdigest()
        if actual != manifest["files"][name]:
            raise ValueError(f"Basic Pitch MLX asset checksum mismatch: {name}")
    arrays = load_file(str(path / "model.safetensors"))
    if any(array.dtype != np.float32 for array in arrays.values()):
        raise ValueError("The FP32 baseline requires exclusively FP32 model tensors")
    return config, arrays


class MLXBasicPitchModel:
    """A reusable FP32 runner with the prediction contract of BasicPitchModel."""

    def __init__(
        self,
        model_path: str | Path = "models/basic-pitch-mlx/icassp_2022",
    ) -> None:
        _configure_fp32_precision()
        import mlx.core as mx

        if not mx.metal.is_available():
            raise RuntimeError("Basic Pitch MLX requires an available Metal GPU")
        self.mx = mx
        self.path = Path(model_path)
        self.config, arrays = _load_assets(self.path)
        with mx.stream(mx.gpu):
            self.weights = {name: mx.array(value) for name, value in arrays.items()}
            mx.eval(self.weights)

    def _conv(self, x: Any, name: str) -> Any:
        mx = self.mx
        layer = self.config["heads"][name]
        top, left, bottom, right = layer["pads"]
        x = mx.pad(x, [(0, 0), (top, bottom), (left, right), (0, 0)])
        convolved = mx.conv2d(x, self.weights[f"{name}.weight"], stride=tuple(layer["strides"]))
        return convolved + self.weights[f"{name}.bias"]

    def _cqt(self, x: Any) -> Any:
        mx, w, cfg = self.mx, self.weights, self.config["cqt"]
        octaves = []
        for octave, hop in enumerate(cfg["hops"]):
            if octave:
                x = mx.conv1d(x, w["cqt.lowpass"], stride=2, padding=cfg["downsample_pad"])
            pad = cfg["reflect_pad"]
            # MLX pad has no reflect mode. Mirror without repeating edge samples.
            centered = mx.concatenate(
                [x[:, 1 : pad + 1, :][:, ::-1, :], x, x[:, -pad - 1 : -1, :][:, ::-1, :]], axis=1
            )
            real = mx.conv1d(centered, w["cqt.real"], stride=hop)
            imag = -mx.conv1d(centered, w["cqt.imag"], stride=hop)
            octaves.append(mx.stack([real, imag], axis=-1))
        complex_cqt = mx.concatenate(octaves[::-1], axis=2)[:, :, -cfg["bins"] :, :]
        complex_cqt = complex_cqt * w["cqt.scale"]
        magnitude = mx.sqrt(mx.sum(mx.square(complex_cqt), axis=-1))
        log_power = mx.log(mx.square(magnitude) + w["normalization.epsilon"])
        log_power = log_power * w["normalization.log_multiplier"]
        log_power = log_power * w["normalization.db_multiplier"]
        offset = log_power - mx.min(log_power, axis=(1, 2), keepdims=True)
        denominator = mx.max(offset, axis=(1, 2), keepdims=True)
        normalized = mx.where(
            denominator != 0,
            offset / mx.where(denominator != 0, denominator, mx.ones_like(denominator)),
            mx.zeros_like(offset),
        )
        return normalized[..., None] * w["cqt.bn_scale"] + w["cqt.bn_bias"]

    def forward(self, audio_window: Any, *, intermediates: bool = False) -> dict[str, Any]:
        """Build a native MLX forward; caller may request stage tensors for parity."""
        mx = self.mx
        if tuple(audio_window.shape) != (1, 43844, 1):
            raise ValueError(f"Basic Pitch MLX expects (1, 43844, 1), got {audio_window.shape}")
        if audio_window.dtype != mx.float32:
            raise ValueError("Basic Pitch MLX forward requires float32 input")
        cqt = self._cqt(audio_window)
        channels = []
        for shift in self.config["harmonic_shifts"]:
            if shift < 0:
                shifted = mx.pad(cqt[:, :, :shift, :], [(0, 0), (0, 0), (-shift, 0), (0, 0)])
            elif shift > 0:
                shifted = mx.pad(cqt[:, :, shift:, :], [(0, 0), (0, 0), (0, shift), (0, 0)])
            else:
                shifted = cqt
            channels.append(shifted[:, :, :264, :])
        stacked = mx.concatenate(channels, axis=-1)
        contour_features = mx.maximum(self._conv(stacked, "contour_features"), 0)
        contour = mx.sigmoid(self._conv(contour_features, "contour"))
        note_features = mx.maximum(self._conv(contour, "note_features"), 0)
        note = mx.sigmoid(self._conv(note_features, "note"))
        onset_features = mx.maximum(self._conv(stacked, "onset_features"), 0)
        onset = mx.sigmoid(self._conv(mx.concatenate([note, onset_features], axis=-1), "onset"))
        result = {"note": note[..., 0], "onset": onset[..., 0], "contour": contour[..., 0]}
        if intermediates:
            result.update(
                cqt=cqt,
                stacked=stacked,
                contour_features=contour_features,
                note_features=note_features,
                onset_features=onset_features,
            )
        return result

    def predict(self, audio_window: np.ndarray) -> dict[str, np.ndarray]:
        """Evaluate one window on the GPU, returning FP32 NumPy activations."""
        values = np.asarray(audio_window, dtype=np.float32)
        if not np.isfinite(values).all():
            raise ValueError("Basic Pitch MLX input must contain only finite values")
        mx = self.mx
        with mx.stream(mx.gpu):
            output = self.forward(mx.array(values))
            mx.eval(output)
            return {name: np.array(value.astype(mx.float32)) for name, value in output.items()}
