#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-only
"""Apply targeted breath attenuation to a vocal source.

This keeps the original file intact and writes a repaired derivative. It is
meant for human-approved windows from ``detect_vocal_breaths.py`` plus listening
review, not for fully automatic vocal editing.

Example:

    uv run --no-sync python music/tracks/T04/tools/repair_vocal_breaths.py \
        local/candidates/genai/latin-vocal-clean-take6-tailfix.wav \
        local/candidates/T04/voice/source/latin-vocal-clean-take6-tailfix-breathfix.wav \
        --window 11.007:11.537 --window 18.747:19.307 --mode cut-fill
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt


@dataclass(frozen=True)
class RepairWindow:
    start_s: float
    end_s: float
    full_gain_db: float
    high_gain_db: float
    edge_s: float


def db_to_amp(db: float) -> float:
    return 10 ** (db / 20)


def parse_window(value: str) -> tuple[float, float]:
    try:
        start, end = value.split(":", 1)
        start_s = float(start)
        end_s = float(end)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("windows must be START:END seconds") from exc
    if start_s < 0 or end_s <= start_s:
        raise argparse.ArgumentTypeError("window END must be greater than START")
    return start_s, end_s


def load_audio(path: Path) -> tuple[np.ndarray, int, str]:
    info = sf.info(path)
    y, sr = sf.read(path, always_2d=True)
    if y.size == 0:
        raise ValueError(f"{path}: empty audio")
    return y.astype(np.float64), int(sr), info.subtype


def write_audio(path: Path, y: np.ndarray, sr: int, subtype: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.clip(y, -1.0, 1.0), sr, subtype=subtype or "PCM_24")


def filt(y: np.ndarray, sr: int, kind: str, cutoff: float | tuple[float, float], order: int = 3) -> np.ndarray:
    sos = butter(order, cutoff, btype=kind, fs=sr, output="sos")
    return sosfiltfilt(sos, y, axis=0)


def delay_taps(
    y: np.ndarray,
    sr: int,
    taps: list[tuple[float, float, float]],
    tail_s: float,
) -> np.ndarray:
    out = np.pad(y, ((0, int(tail_s * sr)), (0, 0)))
    dry_len = len(y)
    for delay_s, left_gain, right_gain in taps:
        delay = int(delay_s * sr)
        wet = np.zeros_like(out)
        wet[delay : delay + dry_len, 0] += y[:, 0] * left_gain
        wet[delay : delay + dry_len, 1] += y[:, 1] * right_gain
        out += wet
    return out


def stereo_halo(y: np.ndarray, sr: int, *, wet: float, tail_s: float) -> np.ndarray:
    air = filt(y, sr, "highpass", 1500, order=2)
    taps = [
        (0.188, 0.00, 0.26 * wet),
        (0.281, 0.23 * wet, 0.00),
        (0.376, 0.00, 0.16 * wet),
        (0.563, 0.13 * wet, 0.00),
    ]
    out = np.pad(y, ((0, int(tail_s * sr)), (0, 0)))
    halo = delay_taps(air, sr, taps, tail_s=tail_s)
    return out + halo[: len(out)]


def gain_env(length: int, sr: int, windows: list[RepairWindow], *, high_band: bool) -> np.ndarray:
    env = np.ones(length, dtype=np.float64)
    for window in windows:
        target = db_to_amp(window.high_gain_db if high_band else window.full_gain_db)
        edge = int(window.edge_s * sr)
        start = max(0, int(window.start_s * sr))
        end = min(length, int(window.end_s * sr))
        if end <= start:
            continue

        env[start:end] = np.minimum(env[start:end], target)

        pre0 = max(0, start - edge)
        if start > pre0:
            t = np.linspace(0, np.pi, start - pre0)
            ramp = 1.0 + (target - 1.0) * (0.5 - 0.5 * np.cos(t))
            env[pre0:start] = np.minimum(env[pre0:start], ramp)

        post1 = min(length, end + edge)
        if post1 > end:
            t = np.linspace(0, np.pi, post1 - end)
            ramp = target + (1.0 - target) * (0.5 - 0.5 * np.cos(t))
            env[end:post1] = np.minimum(env[end:post1], ramp)
    return env


def apply_attenuation(y: np.ndarray, sr: int, windows: list[RepairWindow], *, highpass_hz: float) -> np.ndarray:
    high = filt(y, sr, "highpass", highpass_hz, order=3)
    low = y - high
    full_env = gain_env(len(y), sr, windows, high_band=False)
    high_env = gain_env(len(y), sr, windows, high_band=True)
    return low * full_env[:, None] + high * high_env[:, None]


def inverse_window_env(length: int, sr: int, windows: list[RepairWindow], edge_s: float) -> np.ndarray:
    filler_windows = [
        RepairWindow(w.start_s, w.end_s, -96.0, -96.0, edge_s)
        for w in windows
    ]
    return 1.0 - gain_env(length, sr, filler_windows, high_band=False)


def repair(
    y: np.ndarray,
    sr: int,
    windows_s: list[tuple[float, float]],
    *,
    mode: str,
    highpass_hz: float,
) -> tuple[np.ndarray, list[RepairWindow]]:
    if mode == "surgical":
        windows = [RepairWindow(start, end, -14.0, -42.0, 0.070) for start, end in windows_s]
        return apply_attenuation(y, sr, windows, highpass_hz=highpass_hz), windows
    if mode == "near-remove":
        windows = [RepairWindow(start, end, -24.0, -66.0, 0.060) for start, end in windows_s]
        return apply_attenuation(y, sr, windows, highpass_hz=highpass_hz), windows
    if mode == "cut-fill":
        windows = [RepairWindow(start, end, -28.0, -72.0, 0.075) for start, end in windows_s]
        attenuated = apply_attenuation(y, sr, windows, highpass_hz=highpass_hz)
        tail = stereo_halo(attenuated, sr, wet=0.18, tail_s=1.2)[: len(attenuated)]
        fill = inverse_window_env(len(attenuated), sr, windows, edge_s=0.12)
        return attenuated + tail * fill[:, None] * db_to_amp(-12.0), windows
    raise ValueError(f"unknown mode {mode}")


def window_metrics(y: np.ndarray, sr: int, repaired: np.ndarray, windows: list[RepairWindow]) -> list[dict[str, float]]:
    high_before = filt(y, sr, "highpass", 2400, order=3)
    high_after = filt(repaired, sr, "highpass", 2400, order=3)
    rows: list[dict[str, float]] = []
    for window in windows:
        start = max(0, int(window.start_s * sr))
        end = min(len(y), int(window.end_s * sr))
        before = float(np.sqrt(np.mean(np.square(high_before[start:end])))) if end > start else 0.0
        after = float(np.sqrt(np.mean(np.square(high_after[start:end])))) if end > start else 0.0
        rows.append(
            {
                **asdict(window),
                "high_rms_before": before,
                "high_rms_after": after,
                "high_rms_ratio": after / before if before > 1e-12 else 0.0,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("input", help="source vocal to repair")
    parser.add_argument("output", help="repaired derivative output path")
    parser.add_argument(
        "--window",
        action="append",
        type=parse_window,
        required=True,
        help="approved breath window as START:END seconds; repeatable",
    )
    parser.add_argument(
        "--mode",
        choices=["surgical", "near-remove", "cut-fill"],
        default="cut-fill",
    )
    parser.add_argument("--highpass-hz", type=float, default=2400.0)
    parser.add_argument("--report", default=None, help="optional JSON report path")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    y, sr, subtype = load_audio(input_path)
    repaired, windows = repair(
        y,
        sr,
        args.window,
        mode=args.mode,
        highpass_hz=args.highpass_hz,
    )
    write_audio(output_path, repaired, sr, subtype)

    report = {
        "input": str(input_path),
        "output": str(output_path),
        "mode": args.mode,
        "sample_rate": sr,
        "windows": window_metrics(y, sr, repaired, windows),
    }
    report_path = Path(args.report) if args.report else output_path.with_suffix(".breath-repair.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"wrote repaired vocal: {output_path}")
    for row in report["windows"]:
        print(
            f"{row['start_s']:.3f}-{row['end_s']:.3f}s "
            f"high-rms {row['high_rms_before']:.6f}->{row['high_rms_after']:.6f} "
            f"ratio={row['high_rms_ratio']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
