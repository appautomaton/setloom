# SPDX-License-Identifier: AGPL-3.0-only
"""CPU-only checks for MLX precision policy and lossless model conversion."""

import hashlib
import json
from pathlib import Path
import runpy
import sys

import numpy as np
import pytest

from setloom.transcription.basic_pitch_mlx import _configure_fp32_precision, _load_assets


def test_precision_policy_disables_tf32_before_import(monkeypatch):
    monkeypatch.delitem(sys.modules, "mlx.core", raising=False)
    monkeypatch.delenv("MLX_ENABLE_TF32", raising=False)
    _configure_fp32_precision()
    import os

    assert os.environ["MLX_ENABLE_TF32"] == "0"


def test_precision_policy_rejects_ambiguous_existing_runtime(monkeypatch):
    monkeypatch.setitem(sys.modules, "mlx.core", object())
    monkeypatch.delenv("MLX_ENABLE_TF32", raising=False)
    with pytest.raises(RuntimeError, match="Restart the process"):
        _configure_fp32_precision()
    monkeypatch.setenv("MLX_ENABLE_TF32", "0")
    _configure_fp32_precision()


@pytest.mark.parametrize("setting", ["1", "true", ""])
def test_precision_policy_rejects_reduced_or_unrecognized_precision(monkeypatch, setting):
    monkeypatch.setenv("MLX_ENABLE_TF32", setting)
    with pytest.raises(RuntimeError, match="requires MLX_ENABLE_TF32=0"):
        _configure_fp32_precision()


@pytest.fixture
def converter():
    pytest.importorskip("onnx")
    pytest.importorskip("safetensors.numpy")
    return runpy.run_path(str(Path(__file__).parents[1] / "scripts/convert_basic_pitch_mlx.py"))[
        "convert"
    ]


def test_converter_rejects_unreviewed_source_before_parsing(tmp_path, converter):
    source = tmp_path / "changed.onnx"
    source.write_bytes(b"a different model must not be silently partially converted")
    with pytest.raises(ValueError, match="Unsupported ONNX release"):
        converter(source, tmp_path / "converted")
    assert not (tmp_path / "converted").exists()


def test_canonical_conversion_preserves_fp32_bits_and_detects_corruption(tmp_path, converter):
    from onnx import load, numpy_helper

    source = Path(".references/basic-pitch/basic_pitch/saved_models/icassp_2022/nmp.onnx")
    if not source.is_file():
        pytest.skip("optional canonical Basic Pitch source is not installed")
    first, second = tmp_path / "first", tmp_path / "second"
    manifest = converter(source, first)
    converter(source, second)
    for name in ("config.json", "manifest.json", "model.safetensors"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    config, weights = _load_assets(first)
    original = {t.name: numpy_helper.to_array(t) for t in load(source).graph.initializer}
    assert config["input_shape"] == [1, 43844, 1]
    assert len(weights) == 21
    for name, converted in weights.items():
        origin = original[manifest["tensors"][name]["source_initializer"]]
        if name.endswith(".weight"):
            restored = converted.transpose(0, 3, 1, 2)
        else:
            restored = converted.reshape(origin.shape)
        assert restored.dtype == origin.dtype == np.float32
        assert restored.tobytes() == origin.tobytes()
        assert (
            hashlib.sha256(converted.tobytes()).hexdigest()
            == manifest["tensors"][name]["stored_sha256"]
        )
    config["sample_rate"] = 1
    (first / "config.json").write_text(json.dumps(config))
    with pytest.raises(ValueError, match="checksum mismatch: config.json"):
        _load_assets(first)
    data = bytearray((second / "model.safetensors").read_bytes())
    data[-1] ^= 1
    (second / "model.safetensors").write_bytes(data)
    with pytest.raises(ValueError, match="checksum mismatch: model.safetensors"):
        _load_assets(second)
