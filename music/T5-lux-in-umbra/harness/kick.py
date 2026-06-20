# SPDX-License-Identifier: AGPL-3.0-only
"""Deterministic strict four-on-floor kick rendering."""

from __future__ import annotations

import numpy as np
from scipy import signal

from .context import BEAT_S, KICK_SYNTH, SR
from .dsp import pcm16_roundtrip, soft_limit


def render_kick_hit() -> np.ndarray:
    cfg = KICK_SYNTH["kick_voice"]
    n = int(round(cfg["duration_seconds"] * SR))
    t = np.arange(n, dtype=np.float64) / SR
    freq = cfg["frequency_end_hz"] + (cfg["frequency_start_hz"] - cfg["frequency_end_hz"]) * np.exp(-t / cfg["pitch_decay_seconds"])
    phase = np.cumsum(2.0 * np.pi * freq / SR)
    sine = np.sin(phase)
    thump = signal.sosfilt(signal.butter(2, cfg["thump_lowpass_hz"], "lowpass", fs=SR, output="sos"), sine).astype(np.float32)
    click_noise = np.random.default_rng(cfg["click_seed"]).standard_normal(n).astype(np.float32)
    click = signal.sosfilt(signal.butter(2, cfg["click_bandpass_hz"], "bandpass", fs=SR, output="sos"), click_noise)
    click *= np.exp(-t / cfg["click_decay_seconds"]).astype(np.float32) * cfg["click_gain"]
    env = np.exp(-t / cfg["amp_decay_seconds"]).astype(np.float32)
    attack = np.minimum(1.0, t / cfg["attack_seconds"]).astype(np.float32)
    body = np.zeros_like(thump)
    body_cfg = cfg.get("body_layer", {})
    if body_cfg.get("enabled", False):
        body_src = np.tanh(sine * float(body_cfg["drive"]))
        body = signal.sosfilt(
            signal.butter(2, body_cfg["bandpass_hz"], "bandpass", fs=SR, output="sos"),
            body_src,
        ).astype(np.float32)
        body_env = np.exp(-t / body_cfg["decay_seconds"]).astype(np.float32)
        body_attack = np.minimum(1.0, t / body_cfg["attack_seconds"]).astype(np.float32)
        body *= body_env * body_attack * float(body_cfg["gain"])
    thump *= float(cfg.get("thump_gain", 1.0))
    return soft_limit((thump * env * attack) + body + click, drive=cfg["soft_limit_drive"], peak=cfg["soft_limit_peak"])


def render_strict_kick_8bar() -> np.ndarray:
    pattern = KICK_SYNTH["pattern"]
    compat = KICK_SYNTH["compatibility_steps"]
    duration_s = KICK_SYNTH["bars"] * 4.0 * BEAT_S + KICK_SYNTH["render_tail_seconds"]
    buf = np.zeros((int(round(duration_s * SR)), 2), dtype=np.float32)
    mono = render_kick_hit()
    for beat in range(KICK_SYNTH["beats"]):
        start = int(round(beat * BEAT_S * SR))
        end = min(len(buf), start + len(mono))
        if end > start:
            buf[start:end] += mono[: end - start, None] * pattern["gain"]
    peak = float(np.max(np.abs(buf))) if len(buf) else 0.0
    if peak > pattern["peak_cap"]:
        buf *= pattern["peak_cap"] / peak
    if compat["pcm16_roundtrip_before_trim"]:
        buf = pcm16_roundtrip(buf)
    exact_n = int(round(KICK_SYNTH["bars"] * 4.0 * BEAT_S * SR))
    if compat["trim_to_exact_bars"]:
        buf = buf[:exact_n].copy()
    if compat["edge_fade_seconds"] > 0:
        n = min(len(buf) // 2, int(round(compat["edge_fade_seconds"] * SR)))
        if n > 0:
            ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)[:, None]
            buf[:n] *= ramp
            buf[-n:] *= ramp[::-1]
    if compat["pcm16_roundtrip_after_fade"]:
        buf = pcm16_roundtrip(buf)
    return buf.astype(np.float32)
