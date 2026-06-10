# SPDX-License-Identifier: AGPL-3.0-only
"""Hermetic tests for the vendored BS-RoFormer core (change: anatomy-layer-lens).

No model weights, no network, no audio files: a tiny randomly initialized
model proves the vendored architecture and the chunked separate() path.
"""

import numpy as np
import pytest
import torch
import yaml

from setloom.anatomy.roformer import infer

TINY = dict(
    dim=32,
    depth=1,
    stereo=True,
    num_stems=2,
    time_transformer_depth=1,
    freq_transformer_depth=1,
)


@pytest.fixture(scope="module")
def tiny_model():
    torch.manual_seed(0)
    model = infer.build_model({"model": TINY})
    model.eval()
    return model


def test_tiny_model_forward_shape(tiny_model) -> None:
    audio = torch.randn(1, 2, 8000)
    with torch.inference_mode():
        out = tiny_model(audio)
    assert out.shape == (1, 2, 2, 8000)
    assert torch.isfinite(out).all()


def test_separate_preserves_length_and_names(tiny_model) -> None:
    rng = np.random.default_rng(0)
    mix = rng.standard_normal((2, 12000)).astype(np.float32) * 0.1
    stems = infer.separate(
        tiny_model, mix, ["a", "b"], chunk_size=4096, num_overlap=2
    )
    assert sorted(stems) == ["a", "b"]
    for stem in stems.values():
        assert stem.shape == (2, 12000)
        assert np.isfinite(stem).all()


def test_config_loader_accepts_python_tuple(tmp_path) -> None:
    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text(
        "model:\n  freqs_per_bands: !!python/tuple\n    - 2\n    - 2\n", encoding="utf-8"
    )
    cfg = infer.load_config(cfg_file)
    assert cfg["model"]["freqs_per_bands"] == (2, 2)
    assert isinstance(cfg["model"]["freqs_per_bands"], tuple)
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(cfg_file.read_text(encoding="utf-8"))  # proves the tag needs our loader


def test_load_weights_unwraps_nested_state_dict(tiny_model, tmp_path) -> None:
    ckpt = tmp_path / "w.ckpt"
    torch.save({"state_dict": tiny_model.state_dict()}, ckpt)
    torch.manual_seed(1)
    fresh = infer.build_model({"model": TINY})

    # The first parameters are deterministic rotary tables; compare a weight
    # matrix that is actually randomly initialized.
    def first_matrix(model):
        return next(p for p in model.parameters() if p.ndim >= 2)

    before = first_matrix(fresh).clone()
    infer.load_weights(fresh, ckpt)
    assert torch.equal(first_matrix(fresh), first_matrix(tiny_model))
    assert not torch.equal(before, first_matrix(fresh))


def test_instruments_prefers_target() -> None:
    cfg = {"training": {"instruments": ["x", "y"], "target_instrument": None}}
    assert infer.instruments(cfg) == ["x", "y"]
    cfg["training"]["target_instrument"] = "x"
    assert infer.instruments(cfg) == ["x"]
