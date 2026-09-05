# SPDX-License-Identifier: AGPL-3.0-only

import os
import sys
import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import setloom.transcription.basic_pitch as basic_pitch
from setloom.transcription import BasicPitchActivations, predict_activations


def _valid_arrays(n_frames: int = 4) -> dict[str, np.ndarray]:
    return {
        "note": np.full((n_frames, 88), 0.25, dtype=np.float32),
        "onset": np.full((n_frames, 88), 0.5, dtype=np.float32),
        "contour": np.full((n_frames, 264), 0.75, dtype=np.float32),
        "frame_times": np.arange(n_frames, dtype=np.float64) / 100.0,
    }


def _fake_coreml(monkeypatch, calls: list[dict[str, object]]) -> object:
    cpu_only = object()

    class FakeMLModel:
        def __init__(self, path, *, compute_units) -> None:
            scratch = Path(tempfile.gettempdir())
            scratch.joinpath("coreml-load-scratch").write_text("load")
            calls.append(
                {
                    "operation": "load",
                    "path": path,
                    "compute_units": compute_units,
                    "environment_tmpdir": os.environ.get("TMPDIR"),
                    "python_tempdir": tempfile.gettempdir(),
                }
            )

        def predict(self, inputs):
            scratch = Path(tempfile.gettempdir())
            scratch.joinpath("coreml-predict-scratch").write_text("predict")
            calls.append(
                {
                    "operation": "predict",
                    "input_dtype": inputs["input_2"].dtype,
                    "environment_tmpdir": os.environ.get("TMPDIR"),
                    "python_tempdir": tempfile.gettempdir(),
                }
            )
            return {
                "Identity_1": np.zeros((1, 1, 88), dtype=np.float32),
                "Identity_2": np.zeros((1, 1, 88), dtype=np.float32),
                "Identity": np.zeros((1, 1, 264), dtype=np.float32),
            }

    fake = SimpleNamespace(
        ComputeUnit=SimpleNamespace(CPU_ONLY=cpu_only),
        models=SimpleNamespace(MLModel=FakeMLModel),
    )
    monkeypatch.setitem(sys.modules, "coremltools", fake)
    return cpu_only


def test_model_explicit_temp_root_contains_load_and_predict_scratch(
    tmp_path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    model_path = tmp_path / "model.mlpackage"
    model_path.mkdir()
    caller_root = tmp_path / "system-temp" / "setloom" / "gravitational-wave" / "run"
    outer_temp = tmp_path / "outer-temp"
    outer_temp.mkdir()
    monkeypatch.setenv("TMPDIR", str(outer_temp))
    monkeypatch.setattr(tempfile, "tempdir", str(outer_temp))
    calls: list[dict[str, object]] = []
    cpu_only = _fake_coreml(monkeypatch, calls)

    model = basic_pitch.BasicPitchModel(model_path, temp_root=caller_root)

    assert calls == [
        {
            "operation": "load",
            "path": str(model_path),
            "compute_units": cpu_only,
            "environment_tmpdir": str(caller_root),
            "python_tempdir": str(caller_root),
        }
    ]
    assert os.environ["TMPDIR"] == str(outer_temp)
    assert tempfile.gettempdir() == str(outer_temp)
    assert not (workspace / "tmp" / "transcription").exists()

    result = model.predict(np.zeros((1, 8, 1), dtype=np.float64))

    assert calls[1] == {
        "operation": "predict",
        "input_dtype": np.dtype(np.float32),
        "environment_tmpdir": str(caller_root),
        "python_tempdir": str(caller_root),
    }
    assert set(result) == {"note", "onset", "contour"}
    assert os.environ["TMPDIR"] == str(outer_temp)
    assert tempfile.gettempdir() == str(outer_temp)
    assert caller_root.joinpath("coreml-load-scratch").is_file()
    assert caller_root.joinpath("coreml-predict-scratch").is_file()

    del model
    assert caller_root.is_dir()


def test_model_default_temp_behavior_and_cpu_only_identity_remain_unchanged(
    tmp_path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    model_path = tmp_path / "model.mlpackage"
    model_path.mkdir()
    monkeypatch.delenv("TMPDIR", raising=False)
    monkeypatch.setattr(tempfile, "tempdir", None)
    calls: list[dict[str, object]] = []
    cpu_only = _fake_coreml(monkeypatch, calls)

    model = basic_pitch.BasicPitchModel(model_path)
    default_root = (workspace / "tmp" / "transcription").resolve()

    assert default_root.is_dir()
    assert os.environ["TMPDIR"] == str(default_root)
    assert calls[0] == {
        "operation": "load",
        "path": str(model_path),
        "compute_units": cpu_only,
        "environment_tmpdir": str(default_root),
        "python_tempdir": str(default_root),
    }

    model.predict(np.zeros((1, 8, 1), dtype=np.float32))

    assert calls[1]["environment_tmpdir"] == str(default_root)
    assert calls[1]["python_tempdir"] == str(default_root)
    assert default_root.joinpath("coreml-load-scratch").is_file()
    assert default_root.joinpath("coreml-predict-scratch").is_file()


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


def test_predict_activations_resolves_model_path_without_real_inference(
    tmp_path, monkeypatch
) -> None:
    audio_path = tmp_path / "bounded.wav"
    audio_path.write_bytes(b"fixture")
    model_path = tmp_path / "model.mlpackage"
    constructed = []

    class FakeModel:
        def __init__(self, path) -> None:
            constructed.append(path)

    monkeypatch.setattr(basic_pitch, "BasicPitchModel", FakeModel)
    monkeypatch.setattr(
        basic_pitch,
        "_run_model",
        lambda _path, _model: {
            "note": np.zeros((2, 88), dtype=np.float32),
            "onset": np.zeros((2, 88), dtype=np.float32),
            "contour": np.zeros((2, 264), dtype=np.float32),
        },
    )

    predict_activations(audio_path, model_path=model_path)

    assert constructed == [model_path]
