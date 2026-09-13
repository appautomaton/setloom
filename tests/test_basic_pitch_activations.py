# SPDX-License-Identifier: AGPL-3.0-only

import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest

import setloom.transcription.basic_pitch as basic_pitch
from setloom.transcription import BasicPitchActivations, predict_activations
from setloom.transcription.basic_pitch_mlx import MLXBasicPitchModel


def _valid_arrays(n_frames: int = 4) -> dict[str, np.ndarray]:
    return {
        "note": np.full((n_frames, 88), 0.25, dtype=np.float32),
        "onset": np.full((n_frames, 88), 0.5, dtype=np.float32),
        "contour": np.full((n_frames, 264), 0.75, dtype=np.float32),
        "frame_times": np.arange(n_frames, dtype=np.float64) / 100.0,
    }


def test_activations_are_detached_and_genuinely_read_only() -> None:
    source = _valid_arrays()
    activations = BasicPitchActivations(**source)

    assert all(
        not array.flags.writeable
        for array in (
            activations.note,
            activations.onset,
            activations.contour,
            activations.frame_times,
        )
    )
    source["note"][0, 0] = 1.0
    assert activations.note[0, 0] == pytest.approx(0.25)
    with pytest.raises(ValueError):
        activations.note[0, 0] = 1.0
    with pytest.raises(ValueError):
        activations.note.setflags(write=True)
    with pytest.raises(FrozenInstanceError):
        activations.note = source["note"]


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("note", np.zeros((4, 87), dtype=np.float32), r"note must have shape \(T, 88\)"),
        ("onset", np.zeros((4, 89), dtype=np.float32), r"onset must have shape \(T, 88\)"),
        (
            "contour",
            np.zeros((4, 263), dtype=np.float32),
            r"contour must have shape \(T, 264\)",
        ),
        ("frame_times", np.zeros((4, 1)), r"frame_times must have shape \(T,\)"),
        (
            "onset",
            np.zeros((5, 88), dtype=np.float32),
            "must share one time dimension",
        ),
    ],
)
def test_activations_validate_exact_shapes_and_equal_time_dimension(
    field: str, replacement: np.ndarray, message: str
) -> None:
    values = _valid_arrays()
    values[field] = replacement

    with pytest.raises(ValueError, match=message):
        BasicPitchActivations(**values)


@pytest.mark.parametrize(
    ("field", "index", "value", "message"),
    [
        ("note", (0, 0), np.nan, "note must contain only finite values"),
        ("onset", (0, 0), np.inf, "onset must contain only finite values"),
        ("contour", (0, 0), -0.001, r"contour values must be within \[0, 1\]"),
        ("note", (0, 0), 1.001, r"note values must be within \[0, 1\]"),
        ("frame_times", (0,), np.inf, "frame_times must contain only finite values"),
    ],
)
def test_activations_validate_finiteness_and_unit_interval(
    field: str, index: tuple[int, ...], value: float, message: str
) -> None:
    values = _valid_arrays()
    values[field][index] = value

    with pytest.raises(ValueError, match=message):
        BasicPitchActivations(**values)


def test_predict_activations_reuses_model_and_exact_frame_time_mapping(
    tmp_path, monkeypatch
) -> None:
    audio_path = tmp_path / "bounded.wav"
    audio_path.write_bytes(b"not decoded because _run_model is stubbed")
    output = {
        "note": np.linspace(0.0, 1.0, 3 * 88, dtype=np.float32).reshape(3, 88),
        "onset": np.zeros((3, 88), dtype=np.float32),
        "contour": np.ones((3, 264), dtype=np.float32),
    }
    supplied_model = object()
    calls = []

    def fake_run_model(path, model):
        calls.append((path, model))
        return output

    monkeypatch.setattr(basic_pitch, "_run_model", fake_run_model)
    activations = predict_activations(audio_path, model=supplied_model)

    assert calls == [(audio_path, supplied_model)]
    np.testing.assert_array_equal(activations.note, output["note"])
    np.testing.assert_array_equal(activations.onset, output["onset"])
    np.testing.assert_array_equal(activations.contour, output["contour"])
    np.testing.assert_array_equal(activations.frame_times, basic_pitch._frame_times(3))
    assert activations.frame_times_s is activations.frame_times


def test_public_model_is_native_mlx_and_defaults_to_converted_directory():
    assert basic_pitch.BasicPitchModel is MLXBasicPitchModel
    expected = Path("models/basic-pitch-mlx/icassp_2022")
    assert basic_pitch.default_model_path() == expected
    assert basic_pitch.TranscriptionRequest(audio="a.wav", out_midi="a.mid").model_root == expected
    assert basic_pitch.default_model_path("custom-assets") == Path("custom-assets")


def test_public_import_does_not_initialize_inference_backends():
    code = """
import builtins
import sys
original_import = builtins.__import__
blocked = {'mlx', 'coremltools', 'tensorflow', 'torch', 'onnx', 'onnxruntime'}
def guarded_import(name, *args, **kwargs):
    if name.split('.')[0] in blocked:
        raise AssertionError('inference backend imported: ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
from setloom.transcription import BasicPitchModel, MLXBasicPitchModel, predict_activations
assert BasicPitchModel is MLXBasicPitchModel
assert not blocked.intersection(sys.modules)
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)


@pytest.mark.parametrize("path_kind", ["default", "root", "path"])
def test_raw_api_resolves_native_directory_without_real_inference(tmp_path, monkeypatch, path_kind):
    audio = tmp_path / "bounded.wav"
    audio.touch()
    constructed = []
    runner = object()
    monkeypatch.setattr(
        basic_pitch, "BasicPitchModel", lambda path: constructed.append(path) or runner
    )

    def run(path, model):
        assert path == audio and model is runner
        return {name: value for name, value in _valid_arrays().items() if name != "frame_times"}

    monkeypatch.setattr(basic_pitch, "_run_model", run)
    options = {}
    expected = basic_pitch.default_model_path()
    if path_kind == "root":
        expected = tmp_path / "root-assets"
        options["model_root"] = expected
    elif path_kind == "path":
        expected = tmp_path / "explicit-assets"
        options.update(model_path=expected, model_root=tmp_path / "unused-root")
    predict_activations(audio, **options)
    assert constructed == [expected]


@pytest.mark.parametrize("request_object", [False, True])
@pytest.mark.parametrize("path_kind", ["default", "root", "path"])
def test_transcribe_constructs_native_model_from_request_paths(
    tmp_path, monkeypatch, request_object, path_kind
):
    audio = tmp_path / "input.wav"
    audio.touch()
    constructed = []
    monkeypatch.setattr(
        basic_pitch, "BasicPitchModel", lambda path: constructed.append(path) or object()
    )
    monkeypatch.setattr(basic_pitch, "_run_model", lambda *_: {})
    monkeypatch.setattr(basic_pitch, "_decode_notes", lambda *_: ())
    options = {"out_midi": tmp_path / "notes.mid"}
    expected = basic_pitch.default_model_path()
    if path_kind == "root":
        expected = tmp_path / "root-assets"
        options["model_root"] = expected
    elif path_kind == "path":
        expected = tmp_path / "explicit-assets"
        options.update(model_path=expected, model_root=tmp_path / "unused-root")
    if request_object:
        basic_pitch.transcribe_audio(basic_pitch.TranscriptionRequest(audio=audio, **options))
    else:
        basic_pitch.transcribe_audio(audio, **options)
    assert constructed == [expected]


def test_transcribe_reuses_supplied_runner_across_calls(tmp_path, monkeypatch):
    audio = tmp_path / "input.wav"
    audio.touch()
    supplied = object()
    seen = []

    def unexpected(*args, **kwargs):
        pytest.fail("a supplied model must not be replaced")

    monkeypatch.setattr(basic_pitch, "BasicPitchModel", unexpected)
    monkeypatch.setattr(basic_pitch, "_run_model", lambda path, model: seen.append(model) or {})
    monkeypatch.setattr(basic_pitch, "_decode_notes", lambda *_: ())
    for _ in range(2):
        basic_pitch.transcribe_audio(audio, out_midi=tmp_path / "notes.mid", model=supplied)
    assert seen == [supplied, supplied]


def test_native_load_failure_is_not_retried_with_another_backend(tmp_path, monkeypatch):
    audio = tmp_path / "input.wav"
    audio.touch()
    calls = []

    def fail(path):
        calls.append(path)
        raise RuntimeError("Metal GPU unavailable")

    monkeypatch.setattr(basic_pitch, "BasicPitchModel", fail)
    with pytest.raises(RuntimeError, match="Metal GPU unavailable"):
        predict_activations(audio)
    assert calls == [basic_pitch.default_model_path()]


def test_retired_coreml_policy_is_rejected_instead_of_ignored(tmp_path):
    with pytest.raises(TypeError, match="compute_units"):
        predict_activations(tmp_path / "missing.wav", model=object(), compute_units="all")
    with pytest.raises(TypeError, match="compute_units"):
        basic_pitch.TranscriptionRequest(audio="a.wav", out_midi="a.mid", compute_units="all")
    with pytest.raises(TypeError, match="unknown transcription option"):
        basic_pitch.transcribe_audio("a.wav", out_midi="a.mid", compute_units="all")
    for name, value in (("compute_units", "all"), ("temp_root", tmp_path)):
        with pytest.raises(TypeError, match=name):
            basic_pitch.BasicPitchModel(tmp_path / "missing-assets", **{name: value})
