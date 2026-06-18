# SPDX-License-Identifier: AGPL-3.0-only
"""Create a clean T04 vocal audit folder.

This packages the full source vocal, dry slices, processed slices, and
placement-gain clips so the human listener can audit the vocal pipeline before
melody/orchestration changes.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
ASSEMBLE_PATH = ROOT / "music/tracks/T04/assemble.py"
OUT = ROOT / "local/candidates/T04/vocal-audit"
SR = 44100
ORDER = {"tease": 1, "fullverse": 2, "hook1": 3, "hook2": 4}


def load_assemble_module() -> Any:
    spec = importlib.util.spec_from_file_location("t04_assemble_audit", ASSEMBLE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {ASSEMBLE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_stereo(path: Path) -> np.ndarray:
    y, sr = sf.read(path, always_2d=True)
    if sr != SR:
        raise ValueError(f"{path}: expected {SR}, got {sr}")
    if y.shape[1] == 1:
        y = np.repeat(y, 2, axis=1)
    return y.astype(np.float64)


def write(path: Path, y: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, y, SR, subtype="PCM_24")


def dry_piece(voice: Path, piece: dict[str, Any]) -> np.ndarray:
    y = load_stereo(voice)
    start = int(float(piece["trim_start_s"]) * SR)
    length = int(float(piece["trim_len_s"]) * SR)
    out = y[start : start + length].copy()
    fade_in = min(len(out), int(0.03 * SR))
    fade_out = min(len(out), int(float(piece.get("fade_out_s", 1.2)) * SR))
    if fade_in:
        out[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    if fade_out:
        out[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]
    return out


def info(path: Path) -> tuple[float, float]:
    y, sr = sf.read(path, always_2d=True)
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    return len(y) / sr, peak


def placement_clip(piece_audio: np.ndarray, gain: float, pre_s: float = 1.0, post_s: float = 1.0) -> np.ndarray:
    pre = np.zeros((int(pre_s * SR), 2), dtype=np.float64)
    post = np.zeros((int(post_s * SR), 2), dtype=np.float64)
    return np.vstack([pre, piece_audio * gain, post])


def main() -> int:
    assemble = load_assemble_module()
    manifest = assemble.load_production()
    voice_path = assemble.repo_path(manifest["sources"]["voice"])

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "00-source").mkdir(parents=True)
    (OUT / "01-dry-pieces").mkdir()
    (OUT / "02-processed-pieces").mkdir()
    (OUT / "03-placement-clips").mkdir()
    (OUT / "04-full-timeline").mkdir()

    source_copy = OUT / "00-source" / f"{voice_path.stem}.source.wav"
    shutil.copyfile(voice_path, source_copy)

    temp_root = Path(tempfile.mkdtemp(prefix="setloom-t04-vocal-audit-"))
    try:
        runtime = assemble.with_runtime_overrides(manifest, output_root=temp_root)
        assemble.cut_voice_pieces(runtime)
        processed_dir = assemble.pieces_dir(runtime)

        repair = manifest["voice"].get("source_repair")
        lines = [
            "# T04 Vocal Audit",
            "",
            "This folder packages the current T04 vocal pipeline for listening review.",
            "Files are not peak-normalized; levels reflect their pipeline stage.",
            "",
            f"- Source vocal: `{source_copy.relative_to(OUT)}`",
            f"- Production source path: `{manifest['sources']['voice']}`",
            "",
            "Pipeline: full source vocal -> trim/fade pieces -> piece processing chain -> placement gain/timeline.",
            "",
            "## Source Breath Candidates",
            "",
            "Detector output is a candidate list, not an automatic edit decision.",
        ]
        if repair:
            windows = ", ".join(
                f"`{float(window['start']):.3f}-{float(window['end']):.3f}s`"
                for window in repair.get("breath_windows_s", [])
            )
            lines.extend(
                [
                    f"Current source repair method: `{repair.get('method')}`.",
                    f"Current source repair windows: {windows}.",
                    f"Original source: `{repair.get('original')}`.",
                    "",
                ]
            )
        else:
            lines.append("")
        lines.extend(["## Pieces", ""])

        for name, piece in manifest["voice"]["pieces"].items():
            index = ORDER.get(name, 99)
            dry_path = OUT / "01-dry-pieces" / f"{index:02d}-{name}-dry.wav"
            processed_path = OUT / "02-processed-pieces" / f"{index:02d}-{name}-processed.wav"
            write(dry_path, dry_piece(voice_path, piece))
            shutil.copyfile(processed_dir / f"{name}.wav", processed_path)

            start = float(piece["trim_start_s"])
            end = start + float(piece["trim_len_s"])
            dry_len, dry_peak = info(dry_path)
            processed_len, processed_peak = info(processed_path)
            lines.append(
                f"- `{name}` source `{start:.3f}-{end:.3f}s`: "
                f"`{dry_path.relative_to(OUT)}` ({dry_len:.2f}s peak {dry_peak:.3f}); "
                f"`{processed_path.relative_to(OUT)}` ({processed_len:.2f}s peak {processed_peak:.3f})"
            )

        lines.extend(["", "## Placement Clips", ""])
        for idx, placement in enumerate(manifest["voice"]["placements"], start=1):
            piece_name = placement["piece"]
            processed = load_stereo(processed_dir / f"{piece_name}.wav")
            out = OUT / "03-placement-clips" / (
                f"{idx:02d}-{piece_name}-bar{float(placement['bar']):05.2f}-placement-gain.wav"
            )
            write(out, placement_clip(processed, float(placement.get("gain", 1.0))))
            duration, peak = info(out)
            lines.append(
                f"- `{out.relative_to(OUT)}`: piece `{piece_name}`, bar `{placement['bar']}`, "
                f"gain `{placement.get('gain', 1.0)}`, {duration:.2f}s peak {peak:.3f}"
            )

        total = assemble.bar_to_sample(runtime, float(runtime["total_bars"]))
        voice_only = assemble.place_voice(runtime, total)
        timeline = OUT / "04-full-timeline" / "voice-only-full-arrangement.wav"
        write(timeline, voice_only)
        duration, peak = info(timeline)
        lines.extend(
            [
                "",
                "## Full Timeline",
                "",
                f"- `{timeline.relative_to(OUT)}`: all current vocal placements, {duration:.2f}s peak {peak:.3f}",
                "",
                "## Listening Order",
                "",
                "1. Listen to the full source vocal in `00-source/`.",
                "2. Listen to `01-dry-pieces/` to audit source and slicing.",
                "3. Listen to `02-processed-pieces/` to audit the current voice chain.",
                "4. Listen to `03-placement-clips/` for placement gain and tails.",
                "5. Use `04-full-timeline/` only if timing across the whole arrangement matters.",
                "",
            ]
        )
        (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")

        detector_csv = OUT / "00-source" / "source-breath-candidates.csv"
        detector_json = OUT / "00-source" / "source-breath-candidates.json"
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/detect_vocal_breaths.py",
                str(voice_path),
                "--csv",
                str(detector_csv),
                "--json",
                str(detector_json),
                "--top",
                "12",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    print(f"wrote vocal audit folder: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
