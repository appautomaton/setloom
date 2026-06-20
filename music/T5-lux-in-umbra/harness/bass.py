# SPDX-License-Identifier: AGPL-3.0-only
"""Remapped bass rhythm rendering."""

from __future__ import annotations

import math

import numpy as np

from .context import BAR_S, SR, TOTAL_BARS, load_source_json
from .dsp import (
    additive_saw,
    bandpass,
    env_adsr,
    fit,
    lowpass,
    midi_to_hz,
    soft_limit,
    tick_to_s,
)


def bass_voice(pitch: int, velocity: int, dur_s: float) -> np.ndarray:
    dur = dur_s + 0.12
    n = int(dur * SR)
    f = midi_to_hz(pitch)
    v = (velocity / 127.0) ** 0.8
    x = 0.78 * additive_saw(f, n, 28)
    x += 0.30 * additive_saw(f * 0.997, n, 18, phase=0.4)
    x += 0.20 * additive_saw(f * 2.0, n, 12, phase=0.2)
    x = lowpass(x, min(1150.0, 7.8 * f + 280.0), order=3)
    body = bandpass(additive_saw(f, n, 12), max(45.0, f * 0.7), min(190.0, f * 2.2), order=2)
    punch = bandpass(additive_saw(max(f * 2.0, 120.0), n, 10), 95.0, 170.0, order=2)
    env = env_adsr(n, 0.004, 0.11, 0.62, 0.08)
    return soft_limit((x + 0.42 * body + 0.25 * punch) * env * v, drive=1.45, peak=0.92)


def add_at(buf: np.ndarray, start_s: float, mono: np.ndarray, pan: float = 0.5, gain: float = 1.0) -> None:
    start = int(round(start_s * SR))
    if start >= len(buf):
        return
    mono = np.asarray(mono, dtype=np.float32)
    end = min(len(buf), start + len(mono))
    if end <= start:
        return
    x = mono[: end - start] * gain
    angle = float(np.clip(pan, 0.0, 1.0)) * np.pi / 2.0
    buf[start:end, 0] += x * np.cos(angle)
    buf[start:end, 1] += x * np.sin(angle)


def render_bass_stem(events: list[dict], duration_s: float, gain: float = 1.10, pan_seed: int = 1) -> np.ndarray:
    buf = np.zeros((int(math.ceil(duration_s * SR)), 2), dtype=np.float32)
    for i, event in enumerate(events):
        start_s = tick_to_s(int(event["start_tick"]))
        dur_s = tick_to_s(int(event["duration_ticks"]))
        note = int(event["note"])
        velocity = int(event["velocity"])
        pan = 0.5 + 0.08 * math.sin((note * 0.37) + (i + pan_seed) * 0.113)
        add_at(buf, start_s, bass_voice(note, velocity, dur_s), pan=pan, gain=gain)
    return soft_limit(buf, drive=1.0, peak=0.88)


def remapped_bass_events() -> list[dict]:
    payload = load_source_json("remapped-bass-events.json")
    return [dict(event) for event in payload["events"]]


def render_remapped_bass(mix_plan: dict) -> tuple[np.ndarray, list[dict]]:
    events = remapped_bass_events()
    duration_s = TOTAL_BARS * BAR_S + 1.0
    bass_cfg = mix_plan["bass_render"]
    bass = render_bass_stem(events, duration_s, gain=bass_cfg["gain"], pan_seed=bass_cfg["pan_seed"])
    return fit(bass), events
