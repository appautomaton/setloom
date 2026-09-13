# SPDX-License-Identifier: AGPL-3.0-only
"""Hermetic tests for the MLX BS-RoFormer core and the layer-lens logic.

No model weights, no network, no audio files: a tiny randomly initialized MLX
model proves the architecture and the chunked separate() path, the torch->MLX
key rename is checked against the known module tree, and load_weights is proven
to leave the model in eval mode (dropout off) so inference is deterministic.
"""

import numpy as np
import pytest
import yaml

mx = pytest.importorskip("mlx.core", reason="requires the optional anatomy group")
if not mx.metal.is_available():
    pytest.skip("MLX separation tests require an accessible Metal device", allow_module_level=True)
pytest.importorskip("mlx_spectro", reason="requires the optional anatomy group")

from mlx.utils import tree_flatten  # noqa: E402 -- load only after the optional backend checks

from setloom.anatomy import layers as ll  # noqa: E402
from setloom.anatomy.roformer import separate as separation  # noqa: E402
from setloom.anatomy.roformer import weights as rfw  # noqa: E402


def test_separate_cli_preserves_quiet_estimates_and_float_headroom(tmp_path, monkeypatch):
    import soundfile as sf
    from setloom.cli import main

    source = tmp_path / "original.wav"
    sf.write(source, np.zeros((100000, 2)), 44100)
    estimates = {"synth": np.full((2, 100000), 1.25, dtype=np.float32),
                 "quiet": np.full((2, 100000), 1e-30, dtype=np.float32),
                 "silent": np.zeros((2, 100000), dtype=np.float32)}
    monkeypatch.setattr(ll, "_extract_stems", lambda audio, models: estimates)
    out = tmp_path / "estimates"
    assert main(["separate", str(source), "--out", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["quiet.wav", "silent.wav", "synth.wav"]
    for name, expected in estimates.items():
        actual, sr = sf.read(out / f"{name}.wav", dtype="float32", always_2d=True)
        assert sr == 44100
        assert sf.info(out / f"{name}.wav").subtype == "FLOAT"
        np.testing.assert_array_equal(actual, expected.T)

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
    return separation.build_model({"model": TINY})


def test_tiny_model_forward_shape(tiny_model) -> None:
    audio = mx.array(np.random.default_rng(0).standard_normal((1, 2, 8000)).astype(np.float32))
    out = np.array(tiny_model(audio))
    assert out.shape == (1, 2, 2, 8000)
    assert np.isfinite(out).all()


def test_separate_preserves_length_and_names(tiny_model) -> None:
    rng = np.random.default_rng(0)
    mix = rng.standard_normal((2, 12000)).astype(np.float32) * 0.1
    stems = separation.separate(tiny_model, mix, ["a", "b"], chunk_size=4096, num_overlap=2)
    assert sorted(stems) == ["a", "b"]
    for stem in stems.values():
        assert stem.shape == (2, 12000)
        assert np.isfinite(stem).all()


def test_config_loader_accepts_python_tuple(tmp_path) -> None:
    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text(
        "model:\n  freqs_per_bands: !!python/tuple\n    - 2\n    - 2\n", encoding="utf-8"
    )
    cfg = separation.load_config(cfg_file)
    assert cfg["model"]["freqs_per_bands"] == (2, 2)
    assert isinstance(cfg["model"]["freqs_per_bands"], tuple)
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(cfg_file.read_text(encoding="utf-8"))  # proves the tag needs our loader


def test_instruments_prefers_target() -> None:
    cfg = {"training": {"instruments": ["x", "y"], "target_instrument": None}}
    assert separation.instruments(cfg) == ["x", "y"]
    cfg["training"]["target_instrument"] = "x"
    assert separation.instruments(cfg) == ["x"]


# The torch->MLX key rename is the load-bearing bridge between upstream checkpoints
# and the MLX module tree. These cases are verified to land in a real model's
# parameter set; the mask-estimator MLP carries three torch indices
# (band . wrapper . sequential) that collapse to one underscore index + layers.N.
@pytest.mark.parametrize(
    "torch_key, has_linear, mlx_key",
    [
        ("band_split.to_features.0.0.gamma", False, "band_split.to_features_0.norm.weight"),
        ("band_split.to_features.0.1.bias", False, "band_split.to_features_0.linear.bias"),
        (
            "layers.0.0.layers.0.0.to_out.0.weight", False,
            "layers_0.time_transformer.layers_0.attn.to_out.layers.0.weight",
        ),
        (
            "layers.0.1.layers.0.1.net.4.weight", False,
            "layers_0.freq_transformer.layers_0.ff.net.layers.4.weight",
        ),
        (
            "mask_estimators.0.to_freqs.0.0.0.weight", False,
            "mask_estimators_0.to_freqs_0.layers.0.weight",
        ),
        (
            "mask_estimators.0.to_freqs.1.0.2.bias", False,
            "mask_estimators_0.to_freqs_1.layers.2.bias",
        ),
        ("final_norm.gamma", False, "final_norm.weight"),
        # has_linear=True names the three block branches (linear, time, freq).
        (
            "layers.2.0.layers.0.0.norm.gamma", True,
            "layers_2.linear_transformer.layers_0.attn.norm.weight",
        ),
    ],
)
def test_weight_key_rename(torch_key, has_linear, mlx_key) -> None:
    assert rfw._rename(torch_key, has_linear) == mlx_key


def test_read_torch_state_dict_unwraps_nested(tmp_path) -> None:
    torch = pytest.importorskip("torch")
    inner = {"a": torch.zeros(2), "b": torch.ones(3)}
    ckpt = tmp_path / "w.ckpt"
    torch.save({"state_dict": inner}, ckpt)
    got = rfw._read_torch_state_dict(ckpt)
    assert set(got) == {"a", "b"}


def test_load_weights_sets_eval_mode_so_dropout_is_disabled(tmp_path) -> None:
    # Regression: MLX modules default to training mode; the architecture's dropout
    # would then randomly perturb inference. load_weights must switch to eval.
    cfg = {"model": {**TINY, "attn_dropout": 0.5, "ff_dropout": 0.5}}
    model = separation.build_model(cfg)
    weights = tmp_path / "tiny.safetensors"
    mx.save_safetensors(str(weights), dict(tree_flatten(model.parameters())))
    separation.load_weights(model, weights)  # loads safetensors directly, sets eval
    audio = mx.array(np.random.default_rng(1).standard_normal((1, 2, 6000)).astype(np.float32))
    first = np.array(model(audio))
    second = np.array(model(audio))
    assert np.array_equal(first, second)  # deterministic only if dropout is off


def test_ff_mult_is_fixed_not_tied_to_mlp_expansion_factor() -> None:
    # Regression: the transformer FF expansion is a fixed 4; mlp_expansion_factor
    # sizes only the mask MLP. Conflating them broke the 53-stem checkpoint.
    model = separation.build_model({"model": {**TINY, "mlp_expansion_factor": 2}})
    first_linear = model.layers_0.time_transformer.layers_0.ff.net.layers[1]
    assert first_linear.weight.shape[0] == TINY["dim"] * 4


def test_chunk_size_prefers_inference_over_audio() -> None:
    assert separation.chunk_size({"inference": {"chunk_size": 882000}, "audio": {"chunk_size": 441000}}) == 882000
    assert separation.chunk_size({"audio": {"chunk_size": 588800}}) == 588800  # fall back


def test_load_model_and_separate_track_roundtrip(tmp_path) -> None:
    # The two-call public API: load_model resolves the sibling .yaml + bf16 weights,
    # and separate_track derives names + chunk settings from the config. bf16 weights
    # must make the model run in bf16 (the hybrid path) automatically.
    cfg = {
        "model": dict(TINY),
        "training": {"instruments": ["a", "b"], "target_instrument": None},
        "inference": {"chunk_size": 4096, "num_overlap": 2},
    }
    weights = tmp_path / "tiny.safetensors"
    (tmp_path / "tiny.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    src = separation.build_model(cfg)
    mx.save_safetensors(str(weights), {k: v.astype(mx.bfloat16) for k, v in tree_flatten(src.parameters())})

    model, loaded = separation.load_model(weights)  # config_path defaults to the sibling .yaml
    assert loaded["training"]["instruments"] == ["a", "b"]
    assert model.neural_dtype == mx.bfloat16  # precision follows the bf16 weights

    mix = np.random.default_rng(0).standard_normal((2, 12000)).astype(np.float32) * 0.1
    stems = separation.separate_track(model, loaded, mix)
    assert sorted(stems) == ["a", "b"]
    assert stems["a"].shape == (2, 12000)
    assert np.isfinite(stems["a"]).all()


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


def test_layer_pass_writes_keeps_and_caches(tmp_path, monkeypatch) -> None:
    # layer_pass is separation-only now: kept stems + manifest + kept-layers dossier.
    # Note extraction lives in the transcribe pass (see tests/test_transcribe.py).
    sr = 44100
    synth = np.stack([_sine(440, 3.0, sr), _sine(440, 3.0, sr)])
    keys = np.stack([_sine(660, 3.0, sr), _sine(660, 3.0, sr)])
    bleed = np.stack([_sine(500, 3.0, sr, amp=0.002)] * 2)
    monkeypatch.setattr(ll, "_extract_stems", lambda *_a, **_k: {"synth": synth, "keys": keys, "clarinet": bleed})

    out_dir = tmp_path / "dossiers"
    out_dir.mkdir()
    audio = tmp_path / "fake.mp3"
    audio.touch()

    status = ll.layer_pass(audio, "fake", out_dir, tmp_path / "stems53", tmp_path / "models")
    assert status == ["layers:analyzed"]
    layer_dir = tmp_path / "stems53" / "fake"
    assert (layer_dir / "synth.wav").is_file() and (layer_dir / "keys.wav").is_file()
    assert not (layer_dir / "clarinet.wav").exists()  # below the keep threshold

    manifest = yaml.safe_load((layer_dir / "manifest.yml").read_text(encoding="utf-8"))
    flags = {e["layer"]: e["kept"] for e in manifest["stems"]}
    assert flags == {"synth": True, "keys": True, "clarinet": False}
    dossier = yaml.safe_load((out_dir / "fake.layers.yml").read_text(encoding="utf-8"))
    assert dossier["kept_layers"] == ["synth", "keys"]
    assert "melodic" not in dossier  # transcription moved to the --transcribe pass

    before = {p: p.stat().st_mtime for p in layer_dir.iterdir()}
    status2 = ll.layer_pass(audio, "fake", out_dir, tmp_path / "stems53", tmp_path / "models")
    assert status2 == ["layers:cached"]
    assert {p: p.stat().st_mtime for p in layer_dir.iterdir()} == before
