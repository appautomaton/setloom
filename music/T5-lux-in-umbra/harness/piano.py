# SPDX-License-Identifier: AGPL-3.0-only
"""Piano lane rendering."""

from __future__ import annotations

import math

import numpy as np
import soundfile as sf
from scipy import signal

from .context import MIX_PLAN, NOTE, OUT, SR, STEINWAY, TOTAL_N
from .dsp import add_stereo, midi_to_hz, normalize
from .events import piano_events


def load_piano_note(pitch: int, duration_s: float) -> np.ndarray:
    candidates = {int(k): v for k, v in MIX_PLAN["piano_samples"].items() if k.isdigit()}
    base = min(candidates, key=lambda k: abs(k - pitch))
    path = STEINWAY / candidates[base]
    if not path.is_file():
        return fallback_piano_note(pitch, duration_s)
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    if sr != SR:
        gcd = math.gcd(sr, SR)
        mono = signal.resample_poly(mono, SR // gcd, sr // gcd).astype(np.float32)
    ratio = 2.0 ** ((pitch - base) / 12.0)
    if abs(ratio - 1.0) > 1e-6:
        mono = signal.resample(mono, max(1, int(len(mono) / ratio))).astype(np.float32)
    need = int((duration_s + 1.4) * SR)
    mono = mono[:need]
    if len(mono) < need:
        mono = np.pad(mono, (0, need - len(mono)))
    fade_n = min(len(mono), int(0.7 * SR))
    if fade_n > 0:
        mono[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)
    return mono.astype(np.float32)


def fallback_piano_note(pitch: int, duration_s: float) -> np.ndarray:
    n = max(1, int((duration_s + 1.4) * SR))
    t = np.arange(n, dtype=np.float64) / SR
    freq = midi_to_hz(pitch)
    x = np.zeros(n, dtype=np.float64)
    for h in range(1, min(8, int(SR * 0.45 // freq)) + 1):
        x += np.sin(2.0 * np.pi * freq * h * t) / (h * h)
    env = np.exp(-t / max(0.65, duration_s * 0.8))
    return (x * env * 0.18).astype(np.float32)


def render_piano() -> np.ndarray:
    piano = np.zeros((TOTAL_N, 2), dtype=np.float32)
    for event in piano_events():
        mono = load_piano_note(NOTE[event.pitch], event.duration_s)
        add_stereo(piano, mono, event.start_s, event.velocity, event.pan)
    piano = normalize(piano, peak=MIX_PLAN["piano_samples"]["output_peak"])
    sf.write(OUT / "stem-piano.wav", piano, SR)
    return piano
