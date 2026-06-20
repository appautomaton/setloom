# SPDX-License-Identifier: AGPL-3.0-only
"""Kick/bass bed processing."""

from __future__ import annotations

import numpy as np

from .context import MIX_PLAN
from .dsp import (
    bandpass,
    cap,
    harmonic_presence,
    highpass,
    loop8,
    lowpass,
    mono_below,
    section_env,
    soft_limit,
    split_low_high,
    stereo_tap_return,
)
from .kick import render_strict_kick_8bar


def render_bed_with_bass(bass: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cfg = MIX_PLAN["bed"]
    kick_raw = loop8(render_strict_kick_8bar()) * cfg["kick_gain"]
    kick_low, kick_high = split_low_high(kick_raw, cfg["kick_split_hz"])
    kick_body = bandpass(kick_raw, cfg["kick_body_band_hz"][0], cfg["kick_body_band_hz"][1], order=2)
    kick_low_env = section_env([tuple(point) for point in cfg["kick_low_env"]])
    kick_high_env = section_env([tuple(point) for point in cfg["kick_high_env"]])
    kick_body_env = section_env([tuple(point) for point in cfg["kick_body_env"]])
    kick_core = cap(
        (kick_low * (kick_low_env * cfg["kick_low_gain"]))
        + (kick_high * (kick_high_env * cfg["kick_high_gain"]))
        + (kick_body * (kick_body_env * cfg["kick_body_gain"])),
        peak=cfg["kick_peak"],
    )
    bass_env = section_env([tuple(point) for point in cfg["bass_env"]])
    bass_mix = bass * cfg["bass_mix_gain"] * bass_env
    bass_core = mono_below(bass_mix, cutoff=cfg["bass_mono_cutoff_hz"])
    bass_sub, bass_mid = split_low_high(bass_core, cfg["bass_mono_cutoff_hz"])
    bass_mid_dark = lowpass(bass_mid, cfg["bass_mid_lowpass_hz"], order=2)
    bass_mid_bright = bass_mid
    bass_sub_env = section_env([tuple(point) for point in cfg["bass_sub_env"]])
    bass_mid_env = section_env([tuple(point) for point in cfg["bass_mid_env"]])
    bass_bright_env = section_env([tuple(point) for point in cfg["bass_bright_env"]])
    bass_presence_env = section_env([tuple(point) for point in cfg["bass_presence_env"]])
    bass_mid_phase = (bass_mid_dark * (1.0 - bass_bright_env)) + (bass_mid_bright * bass_bright_env)
    bass_presence = harmonic_presence(bass_core, amount=1.0) * bass_presence_env
    bass_phase = cap(
        (bass_sub * (bass_sub_env * cfg["bass_sub_gain"]))
        + (bass_mid_phase * (bass_mid_env * cfg["bass_mid_gain"]))
        + (bass_presence * cfg["bass_presence_gain"]),
        peak=cfg["bass_peak"],
    )
    kick_room_cfg = cfg["kick_room"]
    kick_room_source = kick_core + highpass(
        soft_limit(kick_body * kick_room_cfg["body_drive_pre_gain"], drive=kick_room_cfg["body_drive"], peak=kick_room_cfg["body_peak"]),
        kick_room_cfg["body_hpf_hz"],
        order=4,
    ) * kick_room_cfg["send_gain"]
    kick_room = stereo_tap_return(
        kick_room_source,
        hp=kick_room_cfg["hp"],
        lp=kick_room_cfg["lp"],
        taps=tuple(tuple(point) for point in kick_room_cfg["taps_ms"]),
        drive=kick_room_cfg["drive"],
    )
    bass_wide_cfg = cfg["bass_wide"]
    bass_wide = stereo_tap_return(
        bass_phase + harmonic_presence(bass_phase, amount=bass_wide_cfg["presence_amount"]),
        hp=bass_wide_cfg["hp"],
        lp=bass_wide_cfg["lp"],
        taps=tuple(tuple(point) for point in bass_wide_cfg["taps_ms"]),
        drive=bass_wide_cfg["drive"],
    )
    return_env = section_env([tuple(point) for point in cfg["return_env"]])
    kick_room *= return_env * cfg["kick_room_return_gain"]
    bass_wide *= return_env * cfg["bass_wide_return_gain"]
    bed_sum = kick_core + bass_phase + kick_room + bass_wide
    bed = soft_limit(bed_sum * cfg["bed_sum_gain"], drive=cfg["bed_soft_limit_drive"], peak=cfg["bed_peak"])
    return bed, kick_core, bass_phase
