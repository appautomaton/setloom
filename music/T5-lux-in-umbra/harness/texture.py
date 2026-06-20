# SPDX-License-Identifier: AGPL-3.0-only
"""Support pad and space return lanes."""

from __future__ import annotations

import numpy as np
import soundfile as sf

from .context import BAR_S, BEAT_S, MIX_PLAN, NOTE, OUT, SCORE, SR, TOTAL_N
from .dsp import add_stereo, highpass, lowpass, midi_to_hz, normalize, scale_if_needed, section_env


def pad_note(pitch: int, duration_s: float, gain: float, phase: float) -> np.ndarray:
    n_samp = int(round(duration_s * SR))
    t = np.arange(n_samp, dtype=np.float64) / SR
    f = midi_to_hz(pitch)
    left = np.zeros(n_samp, dtype=np.float64)
    right = np.zeros(n_samp, dtype=np.float64)
    for k in range(1, 10):
        if f * k > SR * 0.42:
            break
        amp = 1.0 / (k * 1.35)
        slow = 1.0 + 0.004 * np.sin(2 * np.pi * (0.035 + k * 0.003) * t + phase)
        left += amp * np.sin(2 * np.pi * f * k * slow * t + phase + k * 0.11)
        right += amp * np.sin(2 * np.pi * f * k * (2.0 - slow) * t + phase + k * 0.29)
    env = np.ones(n_samp, dtype=np.float64)
    fade_n = min(n_samp // 3, int(1.2 * SR))
    if fade_n:
        env[:fade_n] *= np.linspace(0.0, 1.0, fade_n, dtype=np.float64)
        env[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float64)
    return np.column_stack([left, right]).astype(np.float32) * env[:, None].astype(np.float32) * gain


def render_support() -> np.ndarray:
    buf = np.zeros((TOTAL_N, 2), dtype=np.float32)
    for event in SCORE["support_notes"]:
        layer = pad_note(
            NOTE[str(event["pitch"])],
            float(event["duration_seconds"]),
            float(event["gain"]),
            phase=float(event["phase"]),
        )
        add_stereo(buf, layer, int(event["bar"]) * BAR_S)
    cfg = MIX_PLAN["support"]
    env = section_env([tuple(point) for point in cfg["env"]])
    support = normalize(lowpass(highpass(buf, cfg["highpass_hz"]), cfg["lowpass_hz"]) * env, peak=cfg["output_peak"])
    sf.write(OUT / "stem-support.wav", support, SR)
    return support


def render_space(piano: np.ndarray, pluck: np.ndarray) -> np.ndarray:
    cfg = MIX_PLAN["space"]
    source = highpass((piano * cfg["source_piano_gain"]) + (pluck * cfg["source_pluck_gain"]), cfg["source_highpass_hz"])
    wet = np.zeros_like(source)
    for delay_beats, gain, cross in cfg["taps"]:
        delay_s = BEAT_S * delay_beats
        delay = int(round(delay_s * SR))
        if delay >= len(source):
            continue
        delayed = np.zeros_like(source)
        delayed[delay:] = source[:-delay]
        delayed = np.column_stack(
            [
                delayed[:, 0] * (1.0 - cross) + delayed[:, 1] * cross,
                delayed[:, 1] * (1.0 - cross) + delayed[:, 0] * cross,
            ]
        )
        wet += delayed.astype(np.float32) * gain
    env = section_env([tuple(point) for point in cfg["env"]])
    space = lowpass(highpass(wet, cfg["return_highpass_hz"]), cfg["return_lowpass_hz"]) * env
    space = scale_if_needed(space, peak=cfg["peak_limit"])
    sf.write(OUT / "stem-space.wav", space, SR)
    return space
