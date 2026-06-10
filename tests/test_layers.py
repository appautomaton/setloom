# SPDX-License-Identifier: AGPL-3.0-only
"""Hermetic tests for the vendored BS-RoFormer core (change: anatomy-layer-lens).

No model weights, no network, no audio files: a tiny randomly initialized
model proves the vendored architecture and the chunked separate() path.
"""

import numpy as np
import pytest
import torch
import yaml

from setloom.anatomy import layers as ll
from setloom.anatomy.pipeline import Grid
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


# --- layer pass (slice 2) ---



def _sine(freq, dur, sr, amp=0.3):
    t = np.arange(int(dur * sr)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_keep_threshold_on_stats() -> None:
    sr = 22050
    loud = _sine(220, 2.0, sr)  # ~ -13 dBFS
    quiet = _sine(220, 2.0, sr, amp=0.001)  # ~ -63 dBFS
    loud_db, loud_active = ll._stem_stats(np.stack([loud, loud]), sr)
    quiet_db, _ = ll._stem_stats(np.stack([quiet, quiet]), sr)
    assert ll._keep(loud_db) and loud_active == 1.0
    assert not ll._keep(quiet_db)


def test_prep_melodic_strips_bassline_and_clamps() -> None:
    sr = 22050
    y = _sine(60, 2.0, sr, amp=0.9) + _sine(880, 2.0, sr, amp=0.9)  # sums past 1.0
    out = ll._prep_melodic(y, sr, "synth")
    assert np.max(np.abs(out)) <= 1.0
    spec = np.abs(np.fft.rfft(out)) ** 2
    freqs = np.fft.rfftfreq(len(out), 1 / sr)
    low_frac = spec[freqs < 100].sum() / spec.sum()
    assert low_frac < 0.05
    # keys layer is not high-passed, only normalized
    keys = ll._prep_melodic(_sine(60, 1.0, sr), sr, "keys")
    spec_k = np.abs(np.fft.rfft(keys)) ** 2
    assert spec_k[np.fft.rfftfreq(len(keys), 1 / sr) < 100].sum() / spec_k.sum() > 0.9


def test_f0_steps_quantizes_to_grid() -> None:
    grid = Grid(bpm=120.0, t0=0.0, n_bars=1)  # 2 s bar, 16 steps of 0.125 s
    f0 = np.full(200, 220.0)  # constant A3 over 2 s
    steps = ll._f0_steps(f0, 2.0, grid)
    assert (steps == 57).all()
    notes = [(s, ln, p) for s, ln, p in __import__("setloom.anatomy.analysis", fromlist=["x"]).segment_notes(steps)]
    assert notes == [(0, 16, 57)]


def test_layer_pass_writes_keeps_and_caches(tmp_path, monkeypatch) -> None:
    sr = 44100
    synth = np.stack([_sine(440, 3.0, sr), _sine(440, 3.0, sr)])
    keys = np.stack([_sine(660, 3.0, sr), _sine(660, 3.0, sr)])
    bleed = np.stack([_sine(500, 3.0, sr, amp=0.002)] * 2)
    monkeypatch.setattr(ll, "_extract_stems", lambda *_a, **_k: {"synth": synth, "keys": keys, "clarinet": bleed})
    monkeypatch.setattr(ll, "_f0_track", lambda y, s: np.full(300, 440.0))

    out_dir = tmp_path / "dossiers"
    out_dir.mkdir()
    grid = Grid(bpm=120.0, t0=0.0, n_bars=1)
    audio = tmp_path / "fake.mp3"
    audio.touch()

    status = ll.layer_pass(audio, "fake", grid, out_dir, tmp_path / "stems53", tmp_path / "models")
    assert status == ["layers:analyzed"]
    layer_dir = tmp_path / "stems53" / "fake"
    assert (layer_dir / "synth.wav").is_file() and (layer_dir / "keys.wav").is_file()
    assert not (layer_dir / "clarinet.wav").exists()
    import yaml

    manifest = yaml.safe_load((layer_dir / "manifest.yml").read_text(encoding="utf-8"))
    flags = {e["layer"]: e["kept"] for e in manifest["stems"]}
    assert flags == {"synth": True, "keys": True, "clarinet": False}
    dossier = yaml.safe_load((out_dir / "fake.layers.yml").read_text(encoding="utf-8"))
    assert dossier["kept_layers"] == ["synth", "keys"]
    assert set(dossier["melodic"]) == {"synth", "keys"}
    assert (out_dir / "fake.synth.mid").is_file() and (out_dir / "fake.keys.mid").is_file()

    before = {p: p.stat().st_mtime for p in layer_dir.iterdir()}
    status2 = ll.layer_pass(audio, "fake", grid, out_dir, tmp_path / "stems53", tmp_path / "models")
    assert status2 == ["layers:cached"]
    assert {p: p.stat().st_mtime for p in layer_dir.iterdir()} == before
