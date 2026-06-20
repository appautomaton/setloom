# SPDX-License-Identifier: AGPL-3.0-only
"""Shared deterministic DSP helpers."""

from __future__ import annotations

import math

import numpy as np
from scipy import signal

from .context import BAR_S, BPM, PPQ, SR, TOTAL_N


def fit(audio: np.ndarray, length: int = TOTAL_N) -> np.ndarray:
    out = np.zeros((length, 2), dtype=np.float32)
    out[: min(length, len(audio))] = audio[:length]
    return out


def bar_n(bar: float) -> int:
    return int(round(bar * BAR_S * SR))


def loop8(audio: np.ndarray, length: int = TOTAL_N) -> np.ndarray:
    eight_n = bar_n(8.0)
    src = fit(audio, eight_n)
    out = np.zeros((length, 2), dtype=np.float32)
    for start in range(0, length, eight_n):
        end = min(length, start + eight_n)
        out[start:end] = src[: end - start]
    return out


def filt(audio: np.ndarray, cutoff, kind: str, order: int = 2) -> np.ndarray:
    sos = signal.butter(order, cutoff, kind, fs=SR, output="sos")
    return signal.sosfilt(sos, audio, axis=0).astype(np.float32)


def band(audio: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return filt(audio, [lo, hi], "bandpass", order=3)


def cap(audio: np.ndarray, peak: float = 0.88) -> np.ndarray:
    current = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if current > peak:
        audio = audio * (peak / current)
    return audio.astype(np.float32)


def fade(audio: np.ndarray, seconds: float = 0.8) -> np.ndarray:
    out = audio.copy()
    n = min(len(out) // 2, int(round(seconds * SR)))
    if n:
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)[:, None]
        out[:n] *= ramp
        out[-n:] *= ramp[::-1]
    return out


def midi_to_hz(pitch: int) -> float:
    return 440.0 * (2.0 ** ((pitch - 69) / 12.0))


def env_adsr(n: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    n = max(1, n)
    a = max(1, int(attack * SR))
    d = max(1, int(decay * SR))
    r = max(1, int(release * SR))
    body = max(0, n - a - d - r)
    parts = [
        np.linspace(0.0, 1.0, a, endpoint=False),
        np.linspace(1.0, sustain, d, endpoint=False),
        np.full(body, sustain),
        np.linspace(sustain, 0.0, r, endpoint=True),
    ]
    out = np.concatenate(parts)
    return np.pad(out, (0, max(0, n - len(out))))[:n].astype(np.float32)


def additive_saw(freq: float, n: int, harmonics: int = 18, phase: float = 0.0) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / SR
    max_h = max(1, min(harmonics, int((SR * 0.46) // max(freq, 1.0))))
    x = np.zeros(n, dtype=np.float64)
    for k in range(1, max_h + 1):
        x += ((-1.0) ** (k + 1)) * np.sin(2.0 * np.pi * freq * k * t + phase) / k
    return (x * 2.0 / np.pi).astype(np.float32)


def lowpass(audio: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    cutoff = float(np.clip(cutoff, 30.0, SR * 0.45))
    return filt(audio, cutoff, "lowpass", order=order)


def highpass(audio: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    cutoff = float(np.clip(cutoff, 20.0, SR * 0.45))
    return filt(audio, cutoff, "highpass", order=order)


def bandpass(audio: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    return filt(audio, [lo, hi], "bandpass", order=order)


def mono_below(audio: np.ndarray, cutoff: float = 150.0) -> np.ndarray:
    lows = lowpass(audio, cutoff, order=4)
    highs = highpass(audio, cutoff, order=4)
    low_mono = np.mean(lows, axis=1, keepdims=True)
    return (np.repeat(low_mono, 2, axis=1) + highs).astype(np.float32)


def harmonic_presence(audio: np.ndarray, lo: float = 120.0, hi: float = 350.0, amount: float = 0.16) -> np.ndarray:
    body = bandpass(audio, lo, hi, order=2)
    excited = np.tanh(body * 2.0) / np.tanh(2.0)
    return (excited * amount).astype(np.float32)


def stereo_tap_return(
    audio: np.ndarray,
    *,
    hp: float = 180.0,
    lp: float = 2200.0,
    taps: tuple[tuple[float, float, float], ...] = ((17.0, 0.22, 0.20), (29.0, 0.20, 0.80)),
    drive: float = 1.15,
) -> np.ndarray:
    src = lowpass(highpass(audio, hp, order=4), lp, order=2)
    mono = np.mean(src, axis=1).astype(np.float32)
    out = np.zeros_like(audio, dtype=np.float32)
    for delay_ms, gain, pan in taps:
        delay = int(round(delay_ms * 0.001 * SR))
        if delay <= 0 or delay >= len(mono):
            continue
        angle = float(np.clip(pan, 0.0, 1.0)) * np.pi / 2.0
        tap = mono[:-delay] * float(gain)
        out[delay:, 0] += tap * np.cos(angle)
        out[delay:, 1] += tap * np.sin(angle)
    out = highpass(out, hp, order=4)
    return soft_limit(out, drive=drive, peak=0.72)


def split_low_high(audio: np.ndarray, cutoff: float) -> tuple[np.ndarray, np.ndarray]:
    low = lowpass(audio, cutoff, order=4)
    high = highpass(audio, cutoff, order=4)
    return low, high


def soft_limit(audio: np.ndarray, drive: float = 1.0, peak: float = 0.88) -> np.ndarray:
    y = np.tanh(audio * drive) / np.tanh(drive)
    current = float(np.max(np.abs(y))) if y.size else 0.0
    if current > peak:
        y *= peak / current
    return y.astype(np.float32)


def section_env(points: list[tuple[float, float]]) -> np.ndarray:
    env = np.zeros(TOTAL_N, dtype=np.float32)
    pts = sorted((bar_n(bar), float(value)) for bar, value in points)
    if not pts:
        return env
    for (i0, v0), (i1, v1) in zip(pts, pts[1:]):
        i0 = max(0, min(TOTAL_N, i0))
        i1 = max(0, min(TOTAL_N, i1))
        if i1 <= i0:
            continue
        env[i0:i1] = np.linspace(v0, v1, i1 - i0, endpoint=False, dtype=np.float32)
    last_i, last_v = pts[-1]
    if last_i < TOTAL_N:
        env[max(0, last_i):] = last_v
    first_i, first_v = pts[0]
    if first_i > 0:
        env[:first_i] = first_v
    return env[:, None]


def band_stats(audio: np.ndarray) -> str:
    vals = []
    for lo, hi in [(20, 55), (55, 90), (90, 150), (150, 350), (350, 1000), (1000, 8000)]:
        part = band(audio, lo, hi)
        vals.append(float(np.sqrt(np.mean(part * part))))
    return " ".join(f"{v:.4f}" for v in vals)


def stats(name: str, audio: np.ndarray) -> str:
    return (
        f"{name}: duration={len(audio) / SR:.2f}s "
        f"peak={float(np.max(np.abs(audio))):.3f} "
        f"rms={float(np.sqrt(np.mean(audio * audio))):.4f} "
        f"bands={band_stats(audio)}"
    )


def normalize(audio: np.ndarray, peak: float) -> np.ndarray:
    current = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if current > 1e-8:
        audio = audio * (peak / current)
    return audio.astype(np.float32)


def scale_if_needed(audio: np.ndarray, peak: float) -> np.ndarray:
    current = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if current > peak:
        audio = audio * (peak / current)
    return audio.astype(np.float32)


def pcm16_roundtrip(audio: np.ndarray) -> np.ndarray:
    clipped = np.clip(audio, -1.0, 1.0)
    quantized = np.clip(np.floor(clipped * 32768.0), -32768.0, 32767.0) / 32768.0
    return quantized.astype(np.float32)


def add_stereo(buf: np.ndarray, audio: np.ndarray, start_s: float, gain: float = 1.0, pan: float = 0.5) -> None:
    start = int(round(start_s * SR))
    end = min(len(buf), start + len(audio))
    if end <= start:
        return
    x = audio[: end - start]
    if x.ndim == 1:
        angle = float(np.clip(pan, 0.0, 1.0)) * math.pi / 2.0
        buf[start:end, 0] += x * gain * math.cos(angle)
        buf[start:end, 1] += x * gain * math.sin(angle)
    else:
        buf[start:end] += x[:, :2] * gain


def tick_to_s(tick: int) -> float:
    return tick * 60.0 / (BPM * PPQ)
