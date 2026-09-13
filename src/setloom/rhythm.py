# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded, CPU-only rhythm evidence. Peaks and grid samples are not notes.

Analyze the original mix and any separated estimates independently. This module
measures band energy; it neither assigns instruments nor quantizes a performance.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, find_peaks, sosfilt


@dataclass(frozen=True)
class FrequencyBand:
    name: str
    low_hz: float
    high_hz: float


def default_bands(sample_rate: int) -> tuple[FrequencyBand, ...]:
    """Broad observation bands, truncated/omitted above 95% of Nyquist."""
    ceiling = 0.95 * sample_rate / 2
    return tuple(
        FrequencyBand(name, low, min(high, ceiling))
        for name, low, high in (
            ("low", 30, 150), ("low-mid", 150, 700),
            ("mid", 700, 6000), ("high", 6500, 14000),
        )
        if low < ceiling
    )


def grid_positions(
    start: float, end: float, bpm: float, *, origin: float = 0, subdivisions: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """Integer grid indices and absolute seconds within [start, end).

    Origin is an explicitly supplied beat-zero time. Subdivisions divide one
    quarter-note beat; they do not infer meter, swing, tempo, or note attacks.
    """
    if not all(np.isfinite(v) for v in (start, end, bpm, origin)) or bpm <= 0:
        raise ValueError("grid times must be finite and bpm must be positive")
    if not isinstance(subdivisions, int) or subdivisions < 1:
        raise ValueError("subdivisions must be a positive integer")
    if end <= start:
        raise ValueError("grid end must be after start")
    step = 60 / bpm / subdivisions
    first = int(np.ceil((start - origin) / step - 1e-9))
    last = int(np.ceil((end - origin) / step - 1e-9))
    indices = np.arange(first, last, dtype=np.int64)
    return indices, origin + indices * step


def _db(power: float | np.ndarray):
    return 10 * np.log10(np.maximum(power, 1e-20))


def _interval_db(power: np.ndarray, sr: int, start_frame: int, lo: float, hi: float):
    i, j = round(lo * sr) - start_frame, round(hi * sr) - start_frame
    # Do not pad or average truncated measurement windows at the selected edges.
    if i < 0 or j > len(power) or j <= i:
        return None
    return float(_db(np.mean(power[i:j])))


def analyze_rhythm(
    audio: str | Path,
    *,
    start: float = 0,
    end: float | None = None,
    bpm: float | None = None,
    grid_origin: float = 0,
    subdivisions: int = 4,
    bands: tuple[FrequencyBand, ...] | None = None,
    envelope_ms: float = 8,
    hop_ms: float = 2,
    peak_distance_ms: float = 30,
) -> dict:
    """Return JSON-ready measurements with absolute file times and PCM provenance.

    Channels are averaged in *power*, preserving anti-phase energy. A causal
    order-3 Butterworth bandpass precedes a centered RMS envelope. Bounded
    pre-roll warms the filters; their frequency-dependent delay is not corrected.
    Maxima are therefore acoustic landmarks, not exact onsets. Grid timing is
    optional and supplied by the caller, never estimated here.
    """
    path = Path(audio)
    info = sf.info(path)
    sr = info.samplerate
    end = info.frames / sr if end is None else end
    if not all(np.isfinite(v) for v in (start, end)) or start < 0 or end <= start:
        raise ValueError("require finite window bounds with 0 <= start < end")
    start_frame, end_frame = round(start * sr), min(round(end * sr), info.frames)
    if end_frame <= start_frame:
        raise ValueError("selected window is empty")
    start, end = start_frame / sr, end_frame / sr
    if not all(np.isfinite(v) and v > 0 for v in (envelope_ms, hop_ms, peak_distance_ms)):
        raise ValueError("envelope-ms, envelope-hop-ms, and peak-distance-ms must be positive")
    if not np.isfinite(grid_origin) or not isinstance(subdivisions, int) or subdivisions < 1:
        raise ValueError("grid origin must be finite and subdivisions must be a positive integer")
    grid_indices, grid_times = (
        grid_positions(start, end, bpm, origin=grid_origin, subdivisions=subdivisions)
        if bpm is not None else ([], [])
    )
    bands = default_bands(sr) if bands is None else bands
    if not bands or len({band.name for band in bands}) != len(bands):
        raise ValueError("require at least one band, with unique names")
    for band in bands:
        if not band.name or not (np.isfinite(band.low_hz) and np.isfinite(band.high_hz)
                                and 0 < band.low_hz < band.high_hz < sr / 2):
            raise ValueError(f"invalid band {band}; require 0 < low < high < Nyquist")

    # Odd smoothing windows have an unambiguous sample center. Five cycles of
    # the lowest cutoff (at least 250 ms) provide bounded filter warm-up.
    envelope_frames = max(1, round(envelope_ms * sr / 1000))
    envelope_frames += 1 - envelope_frames % 2
    half = envelope_frames // 2
    hop_frames = max(1, round(hop_ms * sr / 1000))
    pre_roll = max(round(sr * max(0.25, 5 / min(b.low_hz for b in bands))), half)
    read_start = max(0, start_frame - pre_roll)
    read_end = min(info.frames, end_frame + half)
    pcm, _ = sf.read(path, start=read_start, stop=read_end, dtype="float32", always_2d=True)
    if not np.isfinite(pcm).all():
        raise ValueError("audio contains non-finite samples")
    left = start_frame - read_start
    right = end_frame - read_start
    # Anchor envelope sampling to file zero so adjacent inspections use the same
    # sample centers. Only complete RMS windows contribute envelope evidence.
    centers = np.arange(
        int(np.ceil(start_frame / hop_frames)) * hop_frames, end_frame, hop_frames,
    )
    centers = centers[(centers - half >= read_start) & (centers + half < read_end)]
    local_centers = centers - read_start
    times = centers / sr
    report = {
        "schema_version": 1,
        "kind": "rhythm-evidence",
        "source": {
            "path": str(path.resolve()), "sample_rate": sr, "channels": info.channels,
            "total_frames": info.frames,
            "analysis_frames": [start_frame, end_frame],
            "read_frames": [read_start, read_end],
            "decoded_read_sha256": hashlib.sha256(pcm.astype("<f4").tobytes()).hexdigest(),
        },
        "window_seconds": [start, end],
        "method": {
            "filter": "causal Butterworth bandpass, order 3; delay is not corrected",
            "channel_reduction": "mean power across file channels, not mono fold-down",
            "level_unit": "RMS dBFS, floor -200 dBFS; no gain normalization",
            "envelope_frames": envelope_frames, "hop_frames": hop_frames,
            "requested_envelope_ms": envelope_ms, "requested_hop_ms": hop_ms,
            "peak_distance_ms": peak_distance_ms,
            "peak_prominence_fraction_of_p95_amplitude": 0.03,
            "peak_floor_fraction_of_p95_amplitude": 0.04,
            "grid_windows_ms": {"pre": [-30, -8], "attack": [0, 40],
                                "tail": [40, 90], "local_peak": [-20, 45]},
            "edge_policy": "incomplete grid windows are null; envelope needs full RMS support",
            "interpretation": "maxima and grid samples are evidence, not notes or instrument labels",
        },
        "grid": None if bpm is None else {
            "bpm": bpm, "origin_seconds": grid_origin, "subdivisions_per_beat": subdivisions,
            "provenance": "caller-supplied timing context; not detected or quantized",
        },
        "bands": [],
    }
    for band in bands:
        filtered = sosfilt(
            butter(3, [band.low_hz, band.high_hz], fs=sr, btype="bandpass", output="sos"),
            pcm, axis=0,
        )
        full_power = np.mean(filtered * filtered, axis=1)
        power = full_power[left:right]
        envelope = np.sqrt(np.maximum(
            uniform_filter1d(full_power, size=envelope_frames, mode="constant")[local_centers],
            0,
        ))
        p95 = float(np.quantile(envelope, 0.95)) if len(envelope) else 0
        peaks, _ = find_peaks(
            envelope,
            distance=max(1, int(np.ceil(peak_distance_ms * sr / 1000 / hop_frames))),
            prominence=p95 * 0.03,
        )
        peaks = peaks[envelope[peaks] > max(p95 * 0.04, 1e-10)]
        measurements = []
        for index, when in zip(grid_indices, grid_times):
            pre = _interval_db(power, sr, start_frame, when - 0.030, when - 0.008)
            attack = _interval_db(power, sr, start_frame, when, when + 0.040)
            tail = _interval_db(power, sr, start_frame, when + 0.040, when + 0.090)
            candidates = np.flatnonzero((times >= when - 0.020) & (times < when + 0.045))
            complete_peak_window = (
                len(times) and when - 0.020 >= times[0]
                and when + 0.045 <= times[-1] + hop_frames / sr
            )
            peak = None
            if complete_peak_window and len(candidates):
                strongest = candidates[np.argmax(envelope[candidates])]
                if envelope[strongest] > 1e-10:
                    peak = float(times[strongest])
            measurements.append({
                "grid_index": int(index), "grid_seconds": float(when),
                "pre_rms_dbfs": pre, "attack_rms_dbfs": attack, "tail_rms_dbfs": tail,
                "attack_vs_pre_db": None if pre is None or attack is None else attack - pre,
                "tail_vs_attack_db": None if tail is None or attack is None else tail - attack,
                "local_peak_seconds": peak,
                "local_peak_lag_ms": None if peak is None else (peak - when) * 1000,
            })
        report["bands"].append({
            "name": band.name, "low_hz": band.low_hz, "high_hz": band.high_hz,
            "rms_dbfs": float(_db(np.mean(power))),
            "envelope": {"seconds": times.tolist(), "rms_dbfs": _db(envelope ** 2).tolist()},
            "landmarks": [{"peak_seconds": float(times[i]),
                           "rms_dbfs": float(_db(envelope[i] ** 2))} for i in peaks],
            "grid_measurements": measurements,
        })
    return report
