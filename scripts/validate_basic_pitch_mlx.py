#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Opt-in ONNX CPU/MLX GPU parity and rejected BF16 experiments.

The production model is FP32. BF16 variants here are reproducible diagnostics,
not supported transcription modes. Strict numerical failures remain failures,
including synthetic inputs near the normalization floor with no decoded events.
"""

import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import time

import numpy as np
import onnxruntime as ort

from setloom.transcription.basic_pitch_mlx import MLXBasicPitchModel


class ExperimentalBasicPitchModel(MLXBasicPitchModel):
    """Precision experiments kept outside the supported inference runner."""

    def __init__(self, model_path, *, precision="float32"):
        super().__init__(model_path)
        self.precision = precision
        mx = self.mx
        with mx.stream(mx.gpu):
            self.weights = {
                name: value.astype(mx.bfloat16)
                if (
                    precision == "bfloat16"
                    or (
                        precision == "bfloat16-heads" and name.split(".")[0] in self.config["heads"]
                    )
                    or (precision == "bfloat16-mixed" and name.endswith(".weight"))
                    or (precision == "bfloat16-features" and name.endswith("_features.weight"))
                )
                else value
                for name, value in self.weights.items()
            }
            mx.eval(self.weights)

    def _cqt(self, x):
        return super()._cqt(x.astype(self.mx.bfloat16) if self.precision == "bfloat16" else x)

    def _conv(self, x, name):
        if self.precision == "float32":
            return super()._conv(x, name)
        mx = self.mx
        layer = self.config["heads"][name]
        top, left, bottom, right = layer["pads"]
        weight = self.weights[f"{name}.weight"]
        x = mx.pad(x, [(0, 0), (top, bottom), (left, right), (0, 0)]).astype(weight.dtype)
        convolved = mx.conv2d(x, weight, stride=tuple(layer["strides"]))
        if self.precision in ("bfloat16-mixed", "bfloat16-features"):
            convolved = convolved.astype(mx.float32)
        return convolved + self.weights[f"{name}.bias"]

    def forward(self, audio_window, *, intermediates=False):
        output = super().forward(audio_window, intermediates=intermediates)
        if intermediates and self.precision == "bfloat16-heads":
            output["stacked"] = output["stacked"].astype(self.mx.bfloat16)
        return output


def digest(path):
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def metrics(actual, expected, atol, rtol):
    diff = actual.astype(np.float64) - expected.astype(np.float64)
    return {
        "shape": list(actual.shape),
        "max_abs": float(np.abs(diff).max()),
        "rmse": float(np.sqrt(np.mean(diff**2))),
        "passed": bool(
            np.isfinite(actual).all() and np.allclose(actual, expected, atol=atol, rtol=rtol)
        ),
    }


def fixtures(full=False):
    n = 43844
    t = np.arange(n, dtype=np.float64) / 22050
    rng = np.random.default_rng(20260909)
    yield "silence", np.zeros(n)
    yield "sine440", 0.2 * np.sin(2 * np.pi * 440 * t)
    yield "noise", rng.normal(0, 0.05, n)
    impulse = np.zeros(n)
    impulse[[0, 1, 127, 128, 255, 256, n // 2, n - 2, n - 1]] = 0.5
    yield "boundary_impulses", impulse
    if full:
        for frequency in (27.5, 1760, 8000):
            yield f"sine{frequency}", 0.2 * np.sin(2 * np.pi * frequency * t)
        for amplitude in (1e-2, 1e-5, 1e-8):
            yield (
                f"chord{amplitude}",
                amplitude * (np.sin(2 * np.pi * 220 * t) + np.sin(2 * np.pi * 330 * t)),
            )
        yield "dc", np.full(n, 0.1)
        yield "tiny_dc", np.full(n, 1e-8)
        yield (
            "chirp",
            0.1
            * np.sin(2 * np.pi * 30 * ((8000 / 30) ** (t / t[-1]) - 1) * t[-1] / np.log(8000 / 30)),
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--source", default=".references/basic-pitch/basic_pitch/saved_models/icassp_2022/nmp.onnx"
    )
    p.add_argument("--model", default="models/basic-pitch-mlx/icassp_2022")
    p.add_argument(
        "--precision",
        choices=["float32", "bfloat16", "bfloat16-heads", "bfloat16-mixed", "bfloat16-features"],
        default="float32",
    )
    p.add_argument(
        "--output", type=Path, default=Path("tmp/basic-pitch-mlx-validation/report.json")
    )
    p.add_argument("--full", action="store_true")
    p.add_argument("--audio", type=Path)
    p.add_argument(
        "--max-audio-windows", type=int, help="Default: all windows, preserving full clip"
    )
    p.add_argument("--atol", type=float, default=1e-5)
    p.add_argument("--rtol", type=float, default=1e-4)
    p.add_argument("--intermediates", action="store_true")
    args = p.parse_args()
    source = args.source
    stage_names = {}
    if args.intermediates:
        import onnx

        graph = onnx.load(source)
        selectors = {
            "cqt": lambda n: (
                n.op_type == "Add" and n.name.startswith("model_1/batch_normalization/")
            ),
            "stacked": lambda n: (
                n.op_type == "Slice"
                and n.name.startswith("model_1/harmonic-stacking-diff/strided_slice_7;")
            ),
            "contour_features": lambda n: n.name == "Relu__38",
            "note_features": lambda n: n.name == "Relu__42",
            "onset_features": lambda n: n.name == "Relu__35",
        }
        for name, selector in selectors.items():
            found = [n for n in graph.graph.node if selector(n)]
            assert len(found) == 1, (name, found)
            stage_names[name] = found[0].output[0]
            graph.graph.output.append(
                onnx.helper.make_tensor_value_info(found[0].output[0], onnx.TensorProto.FLOAT, None)
            )
        source = graph.SerializeToString()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    session = ort.InferenceSession(source, sess_options=options, providers=["CPUExecutionProvider"])
    model = ExperimentalBasicPitchModel(args.model, precision=args.precision)
    outputs = [o.name for o in session.get_outputs()]
    cases = list(fixtures(args.full))
    report = {
        "reference": "ONNX Runtime CPUExecutionProvider",
        "candidate": f"native MLX GPU {args.precision}",
        "atol": args.atol,
        "rtol": args.rtol,
        "cases": {},
        "passed": True,
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "onnxruntime": ort.__version__,
            "mlx": importlib.metadata.version("mlx"),
            "MLX_ENABLE_TF32": os.environ.get("MLX_ENABLE_TF32"),
        },
        "source_sha256": digest(args.source),
        "implementation_sha256": {
            name: digest(Path(__file__).resolve().parents[1] / name)
            for name in (
                "src/setloom/transcription/basic_pitch_mlx.py",
                "scripts/validate_basic_pitch_mlx.py",
            )
        },
        "assets_sha256": {
            name: digest(Path(args.model) / name)
            for name in ("model.safetensors", "config.json", "manifest.json")
        },
    }
    for name, values in cases:
        x = np.asarray(values, dtype=np.float32).reshape(1, 43844, 1)
        start = time.perf_counter()
        raw = dict(zip(outputs, session.run(None, {session.get_inputs()[0].name: x})))
        reference = {
            key: raw[f"StatefulPartitionedCall:{i}"]
            for key, i in [("contour", 0), ("note", 1), ("onset", 2)]
        }
        reference.update(
            {
                key: raw[value].transpose(0, 2, 3, 1) if key.endswith("_features") else raw[value]
                for key, value in stage_names.items()
            }
        )
        ref_seconds = time.perf_counter() - start
        start = time.perf_counter()
        if args.intermediates:
            mx = model.mx
            with mx.stream(mx.gpu):
                native = model.forward(mx.array(x), intermediates=True)
                mx.eval(native)
                native = {key: np.array(value.astype(mx.float32)) for key, value in native.items()}
        else:
            native = model.predict(x)
        candidate_seconds = time.perf_counter() - start
        entry = {
            "reference_seconds": ref_seconds,
            "candidate_seconds": candidate_seconds,
            "outputs": {},
        }
        for key, expected in reference.items():
            actual = native[key]
            entry["outputs"][key] = metrics(
                actual,
                expected,
                args.atol if key in ("note", "onset", "contour") else 1e-4,
                args.rtol,
            )
            report["passed"] &= entry["outputs"][key]["passed"]
        from setloom.transcription.basic_pitch import _decode_notes, TranscriptionRequest

        request = TranscriptionRequest(audio="parity.wav", out_midi="parity.mid")
        events = []
        for result in (reference, native):
            notes = _decode_notes(
                {key: result[key][0] for key in ("note", "onset", "contour")}, request
            )
            events.append(
                [{k: v for k, v in asdict(note).items() if k != "confidence"} for note in notes]
            )
        entry["decoder"] = {
            "reference_events": len(events[0]),
            "candidate_events": len(events[1]),
            "pitch_timing_velocity_bends_exact": events[0] == events[1],
        }
        report["passed"] &= events[0] == events[1]
        report["cases"][name] = entry
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(name, json.dumps(entry), flush=True)
    report["synthetic_passed"] = report["passed"]
    if args.audio:
        from setloom.transcription.basic_pitch import _read_audio_windows, _unwrap_model_output

        windows, audio_length = _read_audio_windows(args.audio)
        total_windows = len(windows)
        if args.max_audio_windows is not None:
            if args.max_audio_windows < 1:
                raise ValueError("--max-audio-windows must be positive")
            windows = windows[: args.max_audio_windows]
        names = ("note", "onset", "contour")
        reference_chunks, native_chunks = [], []
        start = time.perf_counter()
        for index, window in enumerate(windows):
            raw = dict(zip(outputs, session.run(None, {session.get_inputs()[0].name: window})))
            reference_chunks.append(
                {
                    key: raw[f"StatefulPartitionedCall:{i}"]
                    for key, i in [("contour", 0), ("note", 1), ("onset", 2)]
                }
            )
            if (index + 1) % 25 == 0:
                print(f"audio reference {index + 1}/{len(windows)}", flush=True)
        reference_seconds = time.perf_counter() - start
        start = time.perf_counter()
        for index, window in enumerate(windows):
            native_chunks.append(model.predict(window))
            if (index + 1) % 25 == 0:
                print(f"audio MLX {index + 1}/{len(windows)}", flush=True)
        native_seconds = time.perf_counter() - start
        reference = {
            key: _unwrap_model_output(
                np.concatenate([chunk[key] for chunk in reference_chunks]), audio_length
            )
            for key in names
        }
        native = {
            key: _unwrap_model_output(
                np.concatenate([chunk[key] for chunk in native_chunks]), audio_length
            )
            for key in names
        }
        audio_metrics = {
            key: metrics(native[key], reference[key], args.atol, args.rtol) for key in names
        }
        window_max = {
            key: max(
                float(np.abs(a[key] - b[key]).max())
                for a, b in zip(native_chunks, reference_chunks)
            )
            for key in names
        }
        request = TranscriptionRequest(
            audio=str(args.audio),
            out_midi="parity.mid",
            onset_threshold=0.3,
            frame_threshold=0.2,
            minimum_note_length_ms=40,
            infer_onsets=False,
            energy_tol=2,
        )
        events = []
        for result in (reference, native):
            events.append(
                [
                    {k: v for k, v in asdict(note).items() if k != "confidence"}
                    for note in _decode_notes(result, request)
                ]
            )
        report["audio"] = {
            "path": str(args.audio),
            "sha256": digest(args.audio),
            "sample_count": audio_length,
            "total_windows": total_windows,
            "tested_windows": len(windows),
            "reference_seconds": reference_seconds,
            "native_seconds": native_seconds,
            "window_max_abs": window_max,
            "unwrapped_outputs": audio_metrics,
            "decoder": {
                "settings": {
                    "onset_threshold": 0.3,
                    "frame_threshold": 0.2,
                    "minimum_note_length_ms": 40,
                    "infer_onsets": False,
                    "energy_tol": 2,
                },
                "reference_events": len(events[0]),
                "candidate_events": len(events[1]),
                "pitch_timing_velocity_bends_exact": events[0] == events[1],
            },
        }
        report["audio"]["passed"] = (
            all(value["passed"] for value in audio_metrics.values()) and events[0] == events[1]
        )
        report["passed"] &= report["audio"]["passed"]
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print("audio", json.dumps(report["audio"]), flush=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if report["passed"] else 1)
