#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-only
"""Find likely breath/gasp windows in a vocal audio file.

This is an analysis helper, not a mastering decision. It ranks short windows
whose spectrum looks like broadband high-frequency inhale noise so the human
listener can audit fewer places.

Run from the repo root:

    uv run --no-sync python scripts/detect_vocal_breaths.py path/to/vocal.wav \
        --csv local/candidates/T04/motif-auditions/voice-repair/breath-candidates.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt


@dataclass(frozen=True)
class Candidate:
    start_s: float
    end_s: float
    duration_s: float
    score: float
    peak_score: float
    high_rms: float
    high_ratio: float
    flatness: float
    zcr: float


def load_mono(path: Path) -> tuple[np.ndarray, int]:
    y, sr = sf.read(path, always_2d=True)
    if y.size == 0:
        raise ValueError(f"{path}: empty audio")
    mono = y.astype(np.float64).mean(axis=1)
    peak = float(np.max(np.abs(mono)))
    if peak > 0:
        mono = mono / peak
    return mono, int(sr)


def highpass(y: np.ndarray, sr: int, hz: float) -> np.ndarray:
    if hz <= 0 or hz >= sr / 2:
        return y
    sos = butter(3, hz, btype="highpass", fs=sr, output="sos")
    return sosfiltfilt(sos, y)


def frame_audio(y: np.ndarray, frame: int, hop: int) -> np.ndarray:
    if len(y) < frame:
        y = np.pad(y, (0, frame - len(y)))
    n = 1 + (len(y) - frame) // hop
    starts = np.arange(n) * hop
    return np.stack([y[start : start + frame] for start in starts])


def robust_z(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    source = values[mask] if np.any(mask) else values
    med = float(np.median(source))
    q25, q75 = np.percentile(source, [25, 75])
    scale = float(q75 - q25)
    if scale <= 1e-9:
        scale = float(np.std(source)) or 1.0
    return (values - med) / scale


def spectral_features(frames: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    window = np.hanning(frames.shape[1])[None, :]
    mag = np.abs(np.fft.rfft(frames * window, axis=1)) + 1e-12
    freqs = np.fft.rfftfreq(frames.shape[1], d=1.0 / sr)
    flatness = np.exp(np.mean(np.log(mag), axis=1)) / np.mean(mag, axis=1)
    centroid = np.sum(mag * freqs[None, :], axis=1) / np.sum(mag, axis=1)
    centroid = centroid / (sr / 2)
    return flatness, centroid


def zero_crossing_rate(frames: np.ndarray) -> np.ndarray:
    return np.mean(np.diff(np.signbit(frames), axis=1), axis=1)


def smooth(values: np.ndarray, frames: int) -> np.ndarray:
    if frames <= 1:
        return values
    kernel = np.ones(frames, dtype=np.float64) / frames
    return np.convolve(values, kernel, mode="same")


def contiguous_regions(mask: np.ndarray) -> list[tuple[int, int]]:
    regions: list[tuple[int, int]] = []
    start: int | None = None
    for index, enabled in enumerate(mask):
        if enabled and start is None:
            start = index
        elif not enabled and start is not None:
            regions.append((start, index))
            start = None
    if start is not None:
        regions.append((start, len(mask)))
    return regions


def merge_regions(regions: list[tuple[int, int]], max_gap_frames: int) -> list[tuple[int, int]]:
    if not regions:
        return []
    merged = [regions[0]]
    for start, end in regions[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= max_gap_frames:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def detect_breaths(
    y: np.ndarray,
    sr: int,
    *,
    frame_ms: float,
    hop_ms: float,
    highpass_hz: float,
    threshold_percentile: float,
    min_duration_s: float,
    max_duration_s: float,
    merge_gap_s: float,
    expand_s: float,
    top: int,
) -> list[Candidate]:
    frame = max(64, int(sr * frame_ms / 1000))
    hop = max(1, int(sr * hop_ms / 1000))
    frames = frame_audio(y, frame, hop)
    high = highpass(y, sr, highpass_hz)
    high_frames = frame_audio(high, frame, hop)

    eps = 1e-10
    rms = np.sqrt(np.mean(np.square(frames), axis=1) + eps)
    high_rms = np.sqrt(np.mean(np.square(high_frames), axis=1) + eps)
    high_ratio = high_rms / (rms + eps)
    flatness, centroid = spectral_features(frames, sr)
    zcr = zero_crossing_rate(frames)

    active = (rms > np.percentile(rms, 35)) & (high_rms > np.percentile(high_rms, 45))
    score = (
        1.35 * robust_z(np.log(high_rms + eps), active)
        + 0.90 * robust_z(high_ratio, active)
        + 0.70 * robust_z(flatness, active)
        + 0.45 * robust_z(zcr, active)
        + 0.30 * robust_z(centroid, active)
    )
    score = smooth(score, max(1, int(round(0.05 * sr / hop))))
    active_scores = score[active]
    if len(active_scores) == 0:
        return []
    threshold = float(np.percentile(active_scores, threshold_percentile))
    hot = active & (score >= threshold)

    expand_frames = int(round(expand_s * sr / hop))
    regions = []
    for start, end in contiguous_regions(hot):
        regions.append((max(0, start - expand_frames), min(len(hot), end + expand_frames)))
    regions = merge_regions(regions, max_gap_frames=int(round(merge_gap_s * sr / hop)))

    candidates: list[Candidate] = []
    for start, end in regions:
        start_s = start * hop / sr
        end_s = min(len(y) / sr, (end * hop + frame) / sr)
        duration = end_s - start_s
        if duration < min_duration_s or duration > max_duration_s:
            continue
        span = slice(start, end)
        candidates.append(
            Candidate(
                start_s=start_s,
                end_s=end_s,
                duration_s=duration,
                score=float(np.mean(score[span])),
                peak_score=float(np.max(score[span])),
                high_rms=float(np.mean(high_rms[span])),
                high_ratio=float(np.mean(high_ratio[span])),
                flatness=float(np.mean(flatness[span])),
                zcr=float(np.mean(zcr[span])),
            )
        )
    candidates.sort(key=lambda item: (item.score, item.peak_score), reverse=True)
    return candidates[:top]


def write_csv(path: Path, candidates: list[Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(asdict(candidates[0]).keys()) if candidates else [field.name for field in Candidate.__dataclass_fields__.values()]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(asdict(candidate))


def write_json(path: Path, input_path: Path, candidates: list[Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "input": str(input_path),
        "candidates": [asdict(candidate) for candidate in candidates],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("audio", help="vocal audio file to inspect")
    parser.add_argument("--csv", default=None, help="optional CSV output path")
    parser.add_argument("--json", default=None, help="optional JSON output path")
    parser.add_argument("--top", type=int, default=12, help="maximum candidates to print")
    parser.add_argument("--frame-ms", type=float, default=28.0)
    parser.add_argument("--hop-ms", type=float, default=10.0)
    parser.add_argument("--highpass-hz", type=float, default=2400.0)
    parser.add_argument("--threshold-percentile", type=float, default=90.0)
    parser.add_argument("--min-duration-s", type=float, default=0.12)
    parser.add_argument("--max-duration-s", type=float, default=0.95)
    parser.add_argument("--merge-gap-s", type=float, default=0.13)
    parser.add_argument("--expand-s", type=float, default=0.05)
    args = parser.parse_args()

    audio = Path(args.audio)
    y, sr = load_mono(audio)
    candidates = detect_breaths(
        y,
        sr,
        frame_ms=args.frame_ms,
        hop_ms=args.hop_ms,
        highpass_hz=args.highpass_hz,
        threshold_percentile=args.threshold_percentile,
        min_duration_s=args.min_duration_s,
        max_duration_s=args.max_duration_s,
        merge_gap_s=args.merge_gap_s,
        expand_s=args.expand_s,
        top=args.top,
    )

    print(f"input: {audio}")
    print("rank,start_s,end_s,duration_s,score,high_ratio,flatness,zcr")
    for index, candidate in enumerate(candidates, start=1):
        print(
            f"{index},{candidate.start_s:.3f},{candidate.end_s:.3f},"
            f"{candidate.duration_s:.3f},{candidate.score:.3f},"
            f"{candidate.high_ratio:.3f},{candidate.flatness:.3f},{candidate.zcr:.3f}"
        )

    if args.csv:
        write_csv(Path(args.csv), candidates)
    if args.json:
        write_json(Path(args.json), audio, candidates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
