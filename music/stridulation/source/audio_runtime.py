# SPDX-License-Identifier: AGPL-3.0-only
"""Scriptable audio utilities for Setloom render and mix stages."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
from pathlib import Path
from typing import BinaryIO

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy import signal

DEFAULT_SAMPLE_RATE = 44_100


def db_to_gain(db: float) -> float:
    return 10 ** (db / 20.0)


def gain_db(audio: np.ndarray, db: float) -> np.ndarray:
    return np.asarray(audio, dtype=np.float32) * db_to_gain(db)


def read_audio(
    path: Path, *, sample_rate: int | None = DEFAULT_SAMPLE_RATE
) -> tuple[np.ndarray, int]:
    """Read audio as stereo float32, optionally resampling to ``sample_rate``."""
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    if audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    elif audio.shape[1] > 2:
        audio = audio[:, :2]

    if sample_rate is not None and sr != sample_rate:
        gcd = math.gcd(sr, sample_rate)
        audio = signal.resample_poly(audio, sample_rate // gcd, sr // gcd, axis=0).astype(
            np.float32
        )
        sr = sample_rate
    return audio.astype(np.float32, copy=False), sr


class _SparseWavIO:
    """Let libsndfile encode WAV normally, omitting zero-byte appends on disk.

    Header rewrites always reach the file. Keeping the logical end separately
    preserves trailing holes until libsndfile has finished updating the header.
    Filesystems without sparse allocation still expose the same file contents.
    """

    _zeros = bytes(65536)

    def __init__(self, file: BinaryIO):
        self.file = file
        self.length = 0

    def tell(self) -> int:
        return self.file.tell()

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        if whence == os.SEEK_END:
            return self.file.seek(self.length + offset)
        return self.file.seek(offset, whence)

    def read(self, size: int = -1) -> bytes:
        self.file.truncate(self.length)
        return self.file.read(size)

    def write(self, data: bytes) -> int:
        position = self.tell()
        pending_zeros = 0
        for start in range(0, len(data), len(self._zeros)):
            block = data[start : start + len(self._zeros)]
            if position >= self.length and block == self._zeros[: len(block)]:
                pending_zeros += len(block)
            else:
                if pending_zeros:
                    self.file.seek(pending_zeros, os.SEEK_CUR)
                    pending_zeros = 0
                self.file.write(block)
            position += len(block)
        if pending_zeros:
            self.file.seek(pending_zeros, os.SEEK_CUR)
        self.length = max(self.length, position)
        return len(data)


def _has_silent_blocks(audio: np.ndarray) -> bool:
    """Cheaply retain native writes for dense audio; only probe possible zero runs."""
    if audio.ndim not in (1, 2):
        return False  # Let libsndfile report an invalid shape normally.
    stride = 8192
    probes = audio[::stride] == 0
    if audio.ndim == 2:
        probes = np.all(probes, axis=1)
    for index in np.flatnonzero(probes):
        block = audio[index * stride : (index + 1) * stride]
        if block.nbytes >= 32768 and not np.any(block):
            return True
    return False


def write_audio(
    path: Path,
    audio: np.ndarray,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    subtype: str = "PCM_24",
) -> None:
    """Write float32 audio; WAV zero-byte regions use sparse allocation when supported.

    ``PCM_24`` retains the existing delivery default. Use ``FLOAT`` for float32
    stems/headroom. Sparsity changes neither encoded samples nor the time axis;
    no amplitude threshold, normalization or extra codec is applied.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.asarray(audio, dtype=np.float32)
    if path.suffix.lower() != ".wav" or not _has_silent_blocks(audio):
        sf.write(path, audio, sample_rate, subtype=subtype)
        return
    with path.open("w+b") as file:
        output = _SparseWavIO(file)
        try:
            sf.write(output, audio, sample_rate, subtype=subtype, format="WAV")
        finally:
            file.truncate(output.length)


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


def measure_loudness(path: str | Path) -> dict[str, float | None]:
    """Measure a complete decoded file with FFmpeg's EBU R128 meter.

    Returns Integrated LUFS, true peak in dBTP and loudness range in LU. Only
    ``loudnorm`` input measurements are used; no normalized file is written.
    Below-gate loudness and silent peaks are ``None``, not non-finite JSON values.
    Use this same meter for reference files and encoded delivery comparisons.
    """
    path = Path(path).resolve(strict=True)
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-nostdin",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-vn",
            "-af",
            "loudnorm=print_format=json",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r'\{\s*"input_i".*?\}', result.stderr, re.DOTALL)
    if match is None:
        raise RuntimeError("FFmpeg returned no loudness measurements")
    raw = json.loads(match.group())
    fields = {
        "integrated_lufs": "input_i",
        "true_peak_dbtp": "input_tp",
        "loudness_range_lu": "input_lra",
    }
    return {
        name: value if math.isfinite(value := float(raw[key])) else None
        for name, key in fields.items()
    }


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

    Holds the reduction for ``hold_ms`` and smooths it over ``release_ms``. Unlike ``normalize_peak`` (one global gain), this rides
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


def limit_peak_lookahead(
    audio: np.ndarray,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    ceiling_dbtp: float = -1.0,
    lookahead_ms: float = 3.0,
    release_ms: float = 60.0,
) -> np.ndarray:
    """Stereo-linked FFmpeg lookahead limiting at 4x sample rate.

    Input drive is a production decision: this does not chase a LUFS target.
    Auto makeup is disabled, filter delay is compensated, and decoded length
    must be preserved. A post-resampling true-peak check catches overshoot.
    ``lookahead_ms`` is not interchangeable with the array limiter's hold window.
    """
    y = np.asarray(audio, dtype=np.float32)
    if y.ndim != 2 or y.shape[1] not in (1, 2):
        raise ValueError("Expected audio shaped (frames, one or two channels)")
    if not np.isfinite(y).all():
        raise ValueError("Audio must be finite")
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise ValueError("Sample rate must be a positive integer")
    if not (-23.9 <= ceiling_dbtp <= 0):
        raise ValueError("Lookahead ceiling must be between -23.9 and 0 dBTP")
    if not (0.1 <= lookahead_ms <= 80 and 1 <= release_ms <= 8000):
        raise ValueError("Unsupported limiter lookahead or release time")
    if len(y) == 0:
        return y.copy()
    # Small working margin; the ceiling is verified again after downsampling.
    limit = db_to_gain(ceiling_dbtp - 0.1)
    chain = (
        f"aresample={sample_rate * 4},"
        f"alimiter=limit={limit}:attack={lookahead_ms}:release={release_ms}"
        f":level=false:latency=true,aresample={sample_rate}"
    )
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-f",
            "f32le",
            "-ar",
            str(sample_rate),
            "-ac",
            str(y.shape[1]),
            "-i",
            "pipe:0",
            "-af",
            chain,
            "-f",
            "f32le",
            "-c:a",
            "pcm_f32le",
            "pipe:1",
        ],
        input=y.astype("<f4", copy=False).tobytes(),
        capture_output=True,
        check=True,
    )
    expected = y.size * 4
    if len(result.stdout) != expected:
        raise RuntimeError("Lookahead limiter changed the audio frame count")
    limited = np.frombuffer(result.stdout, dtype="<f4").reshape(y.shape).copy()
    if not np.isfinite(limited).all():
        raise RuntimeError("Lookahead limiter returned non-finite audio")
    peak = float(np.max(true_peak_amp(limited)))
    ceiling = db_to_gain(ceiling_dbtp)
    if peak > ceiling:
        limited *= ceiling / peak
    return limited


def write_master(
    path: str | Path,
    audio: np.ndarray,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    target_lufs: float,
    input_gain_db: float,
    ceiling_dbtp: float,
    lookahead_ms: float,
    release_ms: float,
    tolerance_lu: float = 0.3,
) -> dict:
    """Write a PCM24 master with explicit processing and measured delivery checks.

    The target is a check, not an automatic drive adjustment. Composition, bus
    balance and other processing remain with the production. The delivered file
    uses the same FFmpeg meter as reference comparisons.
    """
    requested = dict(
        target_lufs=target_lufs,
        input_gain_db=input_gain_db,
        ceiling_dbtp=ceiling_dbtp,
        lookahead_ms=lookahead_ms,
        release_ms=release_ms,
        tolerance_lu=tolerance_lu,
    )
    if not all(math.isfinite(value) for value in requested.values()) or tolerance_lu < 0:
        raise ValueError("Master settings must be finite and tolerance nonnegative")
    mixed = limit_peak_lookahead(
        gain_db(audio, input_gain_db),
        sample_rate=sample_rate,
        ceiling_dbtp=ceiling_dbtp,
        lookahead_ms=lookahead_ms,
        release_ms=release_ms,
    )
    write_audio(Path(path), mixed, sample_rate=sample_rate, subtype="PCM_24")
    measured = measure_loudness(path)
    if measured["true_peak_dbtp"] is not None and measured["true_peak_dbtp"] > ceiling_dbtp:
        mixed = gain_db(mixed, ceiling_dbtp - measured["true_peak_dbtp"] - 0.02)
        write_audio(Path(path), mixed, sample_rate=sample_rate, subtype="PCM_24")
        measured = measure_loudness(path)
    error = (
        measured["integrated_lufs"] - target_lufs
        if measured["integrated_lufs"] is not None
        else None
    )
    return dict(
        requested=requested,
        measured=measured,
        meter="FFmpeg loudnorm input measurements; full decoded delivery file",
        target_error_lu=error,
        within_target_tolerance=error is not None and abs(error) <= tolerance_lu,
        within_peak_ceiling=measured["true_peak_dbtp"] is None
        or measured["true_peak_dbtp"] <= ceiling_dbtp,
    )


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


def highpass(
    audio: np.ndarray, cutoff_hz: float, *, sample_rate: int = DEFAULT_SAMPLE_RATE
) -> np.ndarray:
    return butter_filter(audio, sample_rate=sample_rate, cutoff_hz=cutoff_hz, kind="highpass")


def lowpass(
    audio: np.ndarray, cutoff_hz: float, *, sample_rate: int = DEFAULT_SAMPLE_RATE
) -> np.ndarray:
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
            curve[:attack] = np.minimum(
                curve[:attack], np.linspace(1.0, valley, attack, dtype=np.float32)
            )
        envelope[trigger:end] = np.minimum(envelope[trigger:end], curve)
    return envelope


def apply_envelope(audio: np.ndarray, envelope: np.ndarray) -> np.ndarray:
    return np.asarray(audio, dtype=np.float32) * envelope[:, None]
