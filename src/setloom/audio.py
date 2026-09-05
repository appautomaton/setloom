# SPDX-License-Identifier: AGPL-3.0-only
"""Scriptable audio utilities for Setloom render and mix stages."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy import signal

DEFAULT_SAMPLE_RATE = 44_100


def db_to_gain(db: float) -> float:
    return 10 ** (db / 20.0)


def gain_db(audio: np.ndarray, db: float) -> np.ndarray:
    return np.asarray(audio, dtype=np.float32) * db_to_gain(db)


def read_audio(path: Path, *, sample_rate: int | None = DEFAULT_SAMPLE_RATE) -> tuple[np.ndarray, int]:
    """Read audio as stereo float32, optionally resampling to ``sample_rate``."""
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    elif audio.shape[1] > 2:
        audio = audio[:, :2]

    if sample_rate is not None and sr != sample_rate:
        gcd = math.gcd(sr, sample_rate)
        audio = signal.resample_poly(audio, sample_rate // gcd, sr // gcd, axis=0).astype(np.float32)
        sr = sample_rate
    return audio.astype(np.float32, copy=False), sr


def write_audio(path: Path, audio: np.ndarray, *, sample_rate: int = DEFAULT_SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.asarray(audio, dtype=np.float32), sample_rate, subtype="PCM_24")


def match_length(audio: np.ndarray, length: int) -> np.ndarray:
    if len(audio) == length:
        return audio
    if len(audio) > length:
        return audio[:length]
    pad = np.zeros((length - len(audio), audio.shape[1]), dtype=np.float32)
    return np.vstack([audio, pad])


def peak_dbfs(audio: np.ndarray) -> float:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    return 20.0 * math.log10(max(peak, 1e-12))


def normalize_peak(audio: np.ndarray, *, target_dbfs: float = -1.0) -> np.ndarray:
    gain = db_to_gain(target_dbfs - peak_dbfs(audio))
    return np.asarray(audio, dtype=np.float32) * gain


def integrated_lufs(audio: np.ndarray, *, sample_rate: int = DEFAULT_SAMPLE_RATE) -> float:
    meter = pyln.Meter(sample_rate)
    return float(meter.integrated_loudness(np.asarray(audio, dtype=np.float32)))


def normalize_lufs(
    audio: np.ndarray,
    *,
    target_lufs: float,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    peak_ceiling_dbfs: float = -1.0,
) -> np.ndarray:
    current = integrated_lufs(audio, sample_rate=sample_rate)
    normalized = gain_db(audio, target_lufs - current)
    if peak_dbfs(normalized) > peak_ceiling_dbfs:
        normalized = normalize_peak(normalized, target_dbfs=peak_ceiling_dbfs)
    return normalized.astype(np.float32, copy=False)


def true_peak_amp(audio: np.ndarray, *, oversample: int = 4) -> np.ndarray:
    """Per-frame peak magnitude across channels, estimated by polyphase upsampling."""
    y = np.asarray(audio, dtype=np.float32)
    n = y.shape[0]
    up = signal.resample_poly(y, oversample, 1, axis=0)[: n * oversample]
    return np.abs(up).max(axis=1).reshape(n, oversample).max(axis=1)


def limit_peak(
    audio: np.ndarray,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    ceiling_dbfs: float = -1.0,
    hold_ms: float = 1.0,
    release_ms: float = 10.0,
    true_peak: bool = True,
) -> np.ndarray:
    """Smoothed brickwall limiter to a peak ceiling, true-peak aware by default.

    Holds the reduction for ``hold_ms`` then releases over ``release_ms`` so transients are
    caught without audible pumping. Unlike ``normalize_peak`` (one global gain), this rides
    the gain only where the signal exceeds the ceiling, preserving body and dynamics.
    """
    from scipy.ndimage import minimum_filter1d, uniform_filter1d

    y = np.asarray(audio, dtype=np.float32)
    ceiling = db_to_gain(ceiling_dbfs)
    amp = true_peak_amp(y) if true_peak else np.max(np.abs(y), axis=1)
    desired = np.minimum(1.0, ceiling / (amp + 1e-12))
    g = minimum_filter1d(desired, size=2 * max(1, int(sample_rate * hold_ms / 1000.0)) + 1)
    g = uniform_filter1d(g, size=2 * max(1, int(sample_rate * release_ms / 1000.0)) + 1)
    g = np.minimum(g, desired)
    limited = np.clip(y * g[:, None], -ceiling, ceiling).astype(np.float32)
    if true_peak:
        # Gain modulation can create new inter-sample peaks. Measure the actual
        # output and apply a final gain correction against the same 4x estimator.
        output_peak = float(np.max(true_peak_amp(limited)))
        if output_peak > ceiling:
            limited *= ceiling / output_peak
    return limited


def master(
    audio: np.ndarray,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    target_lufs: float,
    ceiling_dbtp: float = -1.0,
    true_peak: bool = True,
) -> np.ndarray:
    """Normalize to ``target_lufs`` (stereo BS.1770), then true-peak-aware brickwall limit.

    ``target_lufs`` stays a caller decision. Limiting can leave the output below
    that target; the peak ceiling uses a 4x polyphase estimate. Silence and audio
    below the loudness meter's gate retain their input level.
    """
    loudness = integrated_lufs(audio, sample_rate=sample_rate)
    if loudness == -math.inf:
        return np.asarray(audio, dtype=np.float32).copy()
    if not math.isfinite(loudness):
        raise ValueError("audio loudness must be finite or below the meter's gate")
    y = gain_db(audio, target_lufs - loudness)
    return limit_peak(y, sample_rate=sample_rate, ceiling_dbfs=ceiling_dbtp, true_peak=true_peak)


def butter_filter(
    audio: np.ndarray,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    cutoff_hz: float,
    kind: str,
    order: int = 4,
) -> np.ndarray:
    sos = signal.butter(order, cutoff_hz, btype=kind, fs=sample_rate, output="sos")
    if len(audio) < 128:
        return signal.sosfilt(sos, audio, axis=0).astype(np.float32)
    return signal.sosfiltfilt(sos, audio, axis=0).astype(np.float32)


def highpass(audio: np.ndarray, cutoff_hz: float, *, sample_rate: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    return butter_filter(audio, sample_rate=sample_rate, cutoff_hz=cutoff_hz, kind="highpass")


def lowpass(audio: np.ndarray, cutoff_hz: float, *, sample_rate: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    return butter_filter(audio, sample_rate=sample_rate, cutoff_hz=cutoff_hz, kind="lowpass")


def ms_width(audio: np.ndarray, width: float) -> np.ndarray:
    stereo = np.asarray(audio, dtype=np.float32)
    mid = (stereo[:, 0] + stereo[:, 1]) * 0.5
    side = (stereo[:, 0] - stereo[:, 1]) * 0.5 * width
    return np.column_stack([mid + side, mid - side]).astype(np.float32)


def mono_below(
    audio: np.ndarray,
    cutoff_hz: float,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> np.ndarray:
    low = lowpass(audio, cutoff_hz, sample_rate=sample_rate)
    high = np.asarray(audio, dtype=np.float32) - low
    mono = np.mean(low, axis=1, keepdims=True)
    return (high + np.repeat(mono, 2, axis=1)).astype(np.float32)


def beat_pump_envelope(
    length: int,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    bpm: float,
    depth_db: float,
    release_ms: float,
    attack_ms: float = 3.0,
) -> np.ndarray:
    envelope = np.ones(length, dtype=np.float32)
    samples_per_beat = sample_rate * 60.0 / bpm
    valley = db_to_gain(-abs(depth_db))
    release = max(1, int(release_ms / 1000.0 * sample_rate))
    attack = max(1, int(attack_ms / 1000.0 * sample_rate))
    for trigger in np.arange(0, length + samples_per_beat, samples_per_beat).astype(np.int64):
        if trigger >= length:
            break
        end = min(length, trigger + release)
        x = np.linspace(0.0, 1.0, end - trigger, dtype=np.float32)
        curve = valley + (1.0 - valley) * (x**1.8)
        if len(curve) > attack:
            curve[:attack] = np.minimum(curve[:attack], np.linspace(1.0, valley, attack, dtype=np.float32))
        envelope[trigger:end] = np.minimum(envelope[trigger:end], curve)
    return envelope


def apply_envelope(audio: np.ndarray, envelope: np.ndarray) -> np.ndarray:
    return np.asarray(audio, dtype=np.float32) * envelope[:, None]
