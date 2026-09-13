# SPDX-License-Identifier: AGPL-3.0-only
"""GW synthesis derived from frozen reconstruction; MIDI importer supplies every note/hit."""

from __future__ import annotations

import argparse
import copy
import json
import os
import resource
from pathlib import Path

import mido
import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import butter, lfilter, resample_poly, sosfilt, sosfiltfilt
from setloom.audio import limit_peak

ASSETS = Path(__file__).resolve().parent


def enabled(score, track):
    return track in score.get("_enabled_tracks", score["tracks"])


def hz(midi, tuning):
    return tuning * 2 ** ((midi - 69) / 12)


def pulse(time, onset, attack, decay):
    age = time - onset
    return np.where(
        age < 0,
        0,
        np.where(
            age < attack,
            0.5 - 0.5 * np.cos(np.pi * np.clip(age / attack, 0, 1)),
            np.exp(-np.maximum(age - attack, 0) / decay),
        ),
    )


def performance_curves(score, patch, time, enabled):
    brightness, upper, body = (np.zeros(len(time)) for _ in range(3))
    settings = patch["performance"]
    if enabled:
        for event in score["brightness_events"]:
            source_time, strength = event[0], event[1]
            depth_multiplier = event[2] if len(event) > 2 else 1
            amplitude_accent = event[3] if len(event) > 3 else True
            onset = source_time - score["source_start_seconds"]
            selected = slice(
                np.searchsorted(time, onset),
                np.searchsorted(time, onset + 10 * settings["filter_decay_ms"] / 1000),
            )
            brightness[selected] = np.maximum(
                brightness[selected],
                settings["depth"][strength]
                * depth_multiplier
                * pulse(
                    time[selected],
                    onset,
                    settings["attack_ms"] / 1000,
                    settings["filter_decay_ms"] / 1000,
                ),
            )
            upper[selected] = np.maximum(
                upper[selected],
                settings["upper_accent_db"][strength]
                * amplitude_accent
                * pulse(
                    time[selected],
                    onset,
                    settings["attack_ms"] / 1000,
                    settings["upper_decay_ms"] / 1000,
                ),
            )
        for source_time in score["body_accents_source_seconds"]:
            onset = source_time - score["source_start_seconds"]
            selected = slice(
                np.searchsorted(time, onset),
                np.searchsorted(time, onset + 10 * settings["body_decay_ms"] / 1000),
            )
            body[selected] = np.maximum(
                body[selected],
                settings["body_accent_db"]
                * pulse(
                    time[selected],
                    onset,
                    settings["attack_ms"] / 1000,
                    settings["body_decay_ms"] / 1000,
                ),
            )
    return brightness, upper, body


def section_control(score, time, name, default):
    """A few producer-defined section anchors, not measured per-frame curves."""
    points = score.get("section_controls", {}).get(name)
    if not points:
        return np.full(len(time), default)
    return np.interp(time + score["source_start_seconds"], *np.asarray(points).T)


def bass_connected(notes, score, patch, time):
    sr = patch["sample_rate"]
    settings = patch["bass"]
    if not notes:
        return np.zeros((len(time), 2))
    frequencies = np.full(len(time), hz(notes[0]["midi"], score["tuning_a4_hz"]))
    previous = frequencies[0]
    for note in notes[1:]:
        target = hz(note["midi"], score["tuning_a4_hz"])
        amount = np.clip((time - note["start_seconds"]) / (settings["glide_ms"] / 1000), 0, 1)
        select = time >= note["start_seconds"]
        frequencies[select] = previous * (target / previous) ** amount[select]
        previous = target
    frequencies *= 2 ** (midi_bend(notes[0], time + score["source_start_seconds"]) / 12)
    phase = 2 * np.pi * np.cumsum(frequencies) / sr
    wave = sum(
        10 ** (level / 20) * np.sin((i + 1) * phase)
        for i, level in enumerate(settings["harmonic_db"])
    )
    wave = np.tanh(wave * settings["drive"]) / settings["drive"]
    wave = sosfilt(butter(2, settings["lowpass_hz"], fs=sr, output="sos"), wave)
    envelope = 0.5 - 0.5 * np.cos(
        np.pi * np.clip((time - notes[0]["start_seconds"]) / (settings["pickup_ms"] / 1000), 0, 1)
    )
    if notes[0]["carry_in"]:
        envelope[:] = 1
    envelope *= np.clip(
        (notes[-1]["end_seconds"] + settings["release_ms"] / 1000 - time)
        / (settings["release_ms"] / 1000),
        0,
        1,
    )
    slow_db = (
        -settings["movement_db"] / 2 * (1 - np.cos(2 * np.pi * settings["movement_hz"] * time))
    )
    beat_phase = (
        2
        * np.pi
        * score["tempo_context_bpm"]
        / 60
        * (time + score["source_start_seconds"] - score["bass_motion_origin_source_seconds"])
    )
    beat_db = 0.5 * settings["beat_depth_db"] * np.cos(beat_phase)
    beat_db += 0.5 * settings["eighth_depth_db"] * np.cos(2 * beat_phase + 0.4)
    velocity = np.full(len(time), notes[0]["velocity"] / score["velocity_reference"]["bass"])
    for note in notes:
        velocity[time >= note["start_seconds"]] = note["velocity"] / score["velocity_reference"]["bass"]
    wave *= envelope * velocity * 10 ** ((settings["gain_db"] + slow_db + beat_db) / 20)
    return np.tile(wave[:, None], (1, 2))


def bass_voice(score, patch, time):
    """Separate connected spans so a later entry cannot fill an intentional bass gap."""
    groups = []
    for note in sorted(
        [n for n in score["notes"] if n["part"] == "bass"], key=lambda n: n["start_seconds"]
    ):
        if not groups or note["start_seconds"] > groups[-1][-1]["end_seconds"] + 0.02:
            groups.append([])
        groups[-1].append(note)
    result = np.zeros((len(time), 2))
    for group in groups:
        begin = max(0, np.searchsorted(time, group[0]["start_seconds"] - 0.25))
        end = min(
            len(time),
            np.searchsorted(time, group[-1]["end_seconds"] + patch["bass"]["release_ms"] / 1000),
        )
        if begin < end:
            result[begin:end] += bass_connected(group, score, patch, time[begin:end])
    result *= 10 ** (section_control(score, time, "bass_gain_db", 0)[:, None] / 20)
    return result


def hat_voice(score, patch, time):
    settings, sr = patch["hat"], patch["sample_rate"]
    output = np.zeros((len(time), 2))
    for i, event in enumerate(score.get("hats", [])):
        onset = event["source_seconds"] - score["source_start_seconds"]
        begin = np.searchsorted(time, onset)
        end = min(len(time), begin + round(0.2 * sr))
        if begin >= end:
            continue
        local = np.arange(end - begin) / sr
        rng = np.random.default_rng(settings["seed"] + round(event["source_seconds"] * 1000))
        common = rng.normal(size=len(local))
        noise = np.column_stack(
            [common * 0.85 + rng.normal(size=len(local)) * 0.53 for _ in range(2)]
        )
        noise = sosfilt(
            butter(
                2,
                [settings["highpass_hz"], settings["lowpass_hz"]],
                btype="bandpass",
                fs=sr,
                output="sos",
            ),
            noise,
            axis=0,
        )
        metal = sum(np.sin(2 * np.pi * f * local) for f in settings["metal_hz"]) / len(
            settings["metal_hz"]
        )
        wave = noise * 0.8 + metal[:, None] * 0.2
        attack = settings["attack_ms"] / 1000
        envelope = np.where(
            local < attack,
            np.sin(np.pi / 2 * np.clip(local / attack, 0, 1)) ** 2,
            0.94 * np.exp(-np.maximum(local - attack, 0) / (settings["decay_ms"] / 1000))
            + 0.06 * np.exp(-np.maximum(local - attack, 0) / 0.08),
        )
        envelope *= np.clip((0.2 - local) / 0.01, 0, 1)
        level = (
            settings["gain_db"]
            + event["gain_db"]
            + float(section_control(score, np.array([onset]), "hat_gain_db", 0)[0])
        )
        output[begin:end] += wave * envelope[:, None] * 10 ** (level / 20)
    return output


def snare_voice(score, patch, time):
    settings, sr = patch["snare"], patch["sample_rate"]
    output = np.zeros((len(time), 2))
    for index, event in enumerate(score.get("snares", [])):
        onset = event[0] - score["source_start_seconds"]
        begin = np.searchsorted(time, onset)
        end = min(len(time), np.searchsorted(time, onset + 0.32))
        if begin >= end or onset < time[0] - 0.32:
            continue
        local = time[begin:end] - onset
        level = float(section_control(score, np.array([onset]), "snare_gain_db", 0)[0])
        if event[1] == "ghost":
            level += float(section_control(score, np.array([onset]), "snare_ghost_db", -36)[0])
        level += event[2]
        cutoff = float(section_control(score, np.array([onset]), "snare_lowpass_hz", 11000)[0])
        tail = float(section_control(score, np.array([onset]), "snare_tail_mix", 0.08)[0])
        rng = np.random.default_rng(settings["seed"] + round(event[0] * 1000))
        common = rng.normal(size=len(local))
        noise = np.column_stack(
            [common * 0.78 + rng.normal(size=len(local)) * 0.70 for _ in range(2)]
        )
        noise = sosfilt(
            butter(2, [settings["highpass_hz"], cutoff], fs=sr, btype="bandpass", output="sos"),
            noise,
            axis=0,
        )
        noise = (
            np.tanh(noise * settings["noise_drive"])
            * settings["noise_makeup"]
            / settings["noise_drive"]
        )
        attack = settings["attack_ms"] / 1000
        envelope = np.minimum(local / attack, 1) * (
            (1 - tail) * np.exp(-local / (settings["decay_ms"] / 1000))
            + tail * np.exp(-local / (settings["tail_ms"] / 1000))
        )
        body = (
            np.sin(2 * np.pi * settings["body_hz"] * local)
            * np.exp(-local / 0.035)
            * 10 ** (settings["body_db"] / 20)
        )
        voice = (noise + body[:, None]) * envelope[:, None]
        voice *= np.clip((0.32 - local) / 0.015, 0, 1)[:, None]
        output[begin:end] += voice * 10 ** ((settings["gain_db"] + level) / 20)
    # Deliberate release into the drop, not a long residual wash under the kick.
    # Full-song non-build snare events continue later; each event has its own release.
    return output


def kick_voice(score, patch, time):
    settings, sr = patch["kick"], patch["sample_rate"]
    output = np.zeros((len(time), 2))
    for event in score.get("kicks", []):
        onset = event - score["source_start_seconds"]
        begin = np.searchsorted(time, onset)
        end = min(len(time), np.searchsorted(time, onset + settings["length_ms"] / 1000))
        if begin >= end or onset < time[0] - settings["length_ms"] / 1000:
            continue
        local = time[begin:end] - onset
        cycles = settings["floor_hz"] * local
        cycles += (
            settings["fast_hz"]
            * settings["fast_seconds"]
            * (1 - np.exp(-local / settings["fast_seconds"]))
        )
        cycles += (
            settings["slow_hz"]
            * settings["slow_seconds"]
            * (1 - np.exp(-local / settings["slow_seconds"]))
        )
        phase = 2 * np.pi * cycles
        envelope = (1 - np.exp(-local / (settings["rise_ms"] / 1000))) * np.exp(
            -local / (settings["decay_ms"] / 1000)
        )
        wave = np.sin(phase) + 10 ** (settings["second_db"] / 20) * np.sin(2 * phase)
        wave += (
            10 ** (settings["body_db"] / 20)
            * np.sin(2 * np.pi * settings["body_hz"] * local)
            * np.exp(-local / 0.18)
        )
        wave = np.tanh(wave * settings["drive"]) / settings["drive"]
        wave *= envelope * np.clip((settings["length_ms"] / 1000 - local) / 0.06, 0, 1)
        rng = np.random.default_rng(910 + round(event * 1000))
        click = sosfilt(
            butter(2, [2000, 12000], fs=sr, btype="bandpass", output="sos"),
            rng.normal(size=len(local)),
        )
        click *= (
            np.minimum(local / 0.0005, 1)
            * np.exp(-local / settings["click_decay_seconds"])
            * 10 ** (settings["click_db"] / 20)
        )
        level = settings["gain_db"] + float(
            section_control(score, np.array([onset]), "kick_gain_db", 0)[0]
        )
        level += score.get("kick_velocity_db", {}).get(str(event), 0)
        common = rng.normal(size=len(local))
        mid_body = np.column_stack(
            [0.87 * common + 0.5 * rng.normal(size=len(local)) for _ in range(2)]
        )
        mid_body = sosfilt(
            butter(
                2,
                [settings["mid_highpass_hz"], settings["mid_lowpass_hz"]],
                fs=sr,
                btype="bandpass",
                output="sos",
            ),
            mid_body,
            axis=0,
        )
        mid_env = np.minimum(local / 0.002, 1) * (
            0.9 * np.exp(-local / settings["mid_decay_seconds"]) + 0.1 * np.exp(-local / 0.055)
        )
        mid_body *= (mid_env * 10 ** (settings["mid_gain_db"] / 20))[:, None]
        output[begin:end] += ((wave + click)[:, None] + mid_body) * 10 ** (level / 20)
    return output


def single_wash_voice(score, patch, time):
    """Independent colored-noise bridge; sparse producer anchors, no source residual."""
    settings, sr = patch["wash"], patch["sample_rate"]
    onset = score["wash_start_source_seconds"] - score["source_start_seconds"]
    stop = score["wash_end_source_seconds"] - score["source_start_seconds"]
    begin, end = np.searchsorted(time, onset), min(len(time), np.searchsorted(time, stop))
    output = np.zeros((len(time), 2))
    if begin >= end:
        return output
    rng = np.random.default_rng(settings["seed"])
    common = rng.normal(size=end - begin)
    noise = np.column_stack(
        [
            settings["common"] * common + settings["side"] * rng.normal(size=end - begin)
            for _ in range(2)
        ]
    )
    low_color = sosfilt(
        butter(
            2,
            [settings["highpass_hz"], settings["mid_lowpass_hz"]],
            btype="bandpass",
            fs=sr,
            output="sos",
        ),
        noise,
        axis=0,
    )
    high_color = sosfilt(
        butter(3, settings["high_color_hz"], btype="bandpass", fs=sr, output="sos"), noise, axis=0
    )
    noise = low_color + settings["high_mix"] * high_color
    noise = sosfilt(butter(2, settings["lowpass_hz"], fs=sr, output="sos"), noise, axis=0)
    noise /= max(np.sqrt(np.mean(noise**2)), 1e-9)
    local = time[begin:end]
    envelope = np.minimum((local - onset) / 0.03, 1) * np.minimum((stop - local) / 0.025, 1)
    envelope *= 10 ** (section_control(score, local, "wash_gain_db", -90) / 20)
    output[begin:end] = noise * envelope[:, None]
    return output


def texture_voice(score, patch, time):
    settings, sr = patch["texture"], patch["sample_rate"]
    output = np.zeros((len(time), 2))
    for note in score["notes"]:
        if note["part"] != "texture":
            continue
        begin = max(0, np.searchsorted(time, note["start_seconds"]))
        end = min(len(time), np.searchsorted(time, note["end_seconds"] + 0.12))
        if begin >= end:
            continue
        local = np.arange(end - begin) / sr
        frequency = hz(note["midi"], score["tuning_a4_hz"])
        voice = np.zeros((len(local), 2))
        low_body = section_control(score, time[begin:end], "texture_low_body", 0)
        for channel, cents in enumerate([-settings["detune_cents"], settings["detune_cents"]]):
            offsets = midi_bend(note, time[begin:end] + score["source_start_seconds"])
            cycles = frequency * local
            if np.any(offsets):
                instant = frequency * 2 ** (offsets / 12)
                cycles = np.r_[0, np.cumsum((instant[1:] + instant[:-1]) * 0.5) / sr]
            phase = 2 * np.pi * 2 ** (cents / 1200) * cycles
            for harmonic, gain in enumerate(settings["harmonic_gain"], start=1):
                if harmonic * frequency < sr * 0.45:
                    gain = gain + (
                        0.30 * low_body
                        if harmonic == 1
                        else 0.50 * low_body
                        if harmonic == 2
                        else 0
                    )
                    phase_used = 2 * np.pi * cycles if harmonic <= 2 else phase
                    voice[:, channel] += gain * np.sin(harmonic * phase_used + harmonic * 0.13)
        voice = np.tanh(voice * 1.1) / 1.1
        voice = sosfilt(
            butter(
                2,
                35 if np.max(low_body) > 0.5 else settings["highpass_hz"],
                fs=sr,
                btype="highpass",
                output="sos",
            ),
            voice,
            axis=0,
        )
        absolute = time[begin:end]
        voice = moving_lowpass(
            voice, section_control(score, absolute, "texture_lowpass_hz", 600), 0.72, sr
        )
        envelope = np.minimum(local / 0.04, 1) * np.clip(
            (note["end_seconds"] + 0.12 - absolute) / 0.12, 0, 1
        )
        gain = settings["gain_db"] + section_control(score, absolute, "texture_gain_db", 0)
        gain += 20 * np.log10(note["velocity"] / score["velocity_reference"]["texture"])
        duck = np.zeros(len(local))
        for event in score.get("kicks", []):
            if (
                event < score["source_start_seconds"] + absolute[0] - 0.8
                or event > score["source_start_seconds"] + absolute[-1]
            ):
                continue
            duck = np.maximum(
                duck, pulse(absolute, event - score["source_start_seconds"], 0.003, 0.10)
            )
        output[begin:end] += (
            voice * (envelope * 10 ** ((gain - settings["kick_duck_db"] * duck) / 20))[:, None]
        )
    return output


def bright_voice(score, patch, time):
    """Broad beat/offbeat percussion missing from the incomplete stem views."""
    settings, sr = patch["bright_percussion"], patch["sample_rate"]
    output = np.zeros((len(time), 2))
    for event in score.get("bright_percussion", []):
        onset = event[0] - score["source_start_seconds"]
        begin = np.searchsorted(time, onset)
        end = min(len(time), np.searchsorted(time, onset + settings["duration_ms"] / 1000))
        if begin >= end or onset < time[0] - 0.3:
            continue
        local = time[begin:end] - onset
        rng = np.random.default_rng(settings["seed"] + round(event[0] * 1000))
        common = rng.normal(size=len(local))
        noise = np.column_stack(
            [0.63 * common + 0.77 * rng.normal(size=len(local)) for _ in range(2)]
        )
        noise = sosfilt(
            butter(
                2,
                [settings["highpass_hz"], settings["lowpass_hz"]],
                fs=sr,
                btype="bandpass",
                output="sos",
            ),
            noise,
            axis=0,
        )
        metal = sum(
            np.sin(2 * np.pi * f * local + i * 0.4) for i, f in enumerate(settings["metal_hz"])
        ) / len(settings["metal_hz"])
        envelope = np.minimum(local / 0.005, 1) * (
            0.85 * np.exp(-local / (settings["decay_ms"] / 1000)) + 0.15 * np.exp(-local / 0.18)
        )
        envelope *= np.clip((settings["duration_ms"] / 1000 - local) / 0.015, 0, 1)
        level = (
            settings["gain_db"]
            + event[1]
            + float(section_control(score, np.array([onset]), "bright_gain_db", 0)[0])
        )
        output[begin:end] += (
            (0.85 * noise + 0.15 * metal[:, None]) * envelope[:, None] * 10 ** (level / 20)
        )
    return output


def single_ending_voice(score, patch, time):
    """Independent ringing modes, not sampled source audio or invented outro keys."""
    settings = patch["ending_fx"]
    event = score["ending_fx"]
    onset = event["source_seconds"] - score["source_start_seconds"]
    begin = np.searchsorted(time, onset)
    output = np.zeros((len(time), 2))
    if begin >= len(time):
        return output
    local = time[begin:] - onset
    base_hz = hz(event["root_midi"], score["tuning_a4_hz"])
    rng = np.random.default_rng(settings["noise_seed"])
    diffuse = rng.normal(size=(len(local), 2))
    diffuse = sosfilt(
        butter(
            2, settings["noise_band_hz"], fs=patch["sample_rate"], btype="bandpass", output="sos"
        ),
        diffuse,
        axis=0,
    )
    diffuse /= max(float(np.sqrt(np.mean(diffuse**2))), 1e-9)
    diffuse *= 10 ** (
        (settings["noise_relative_db"] - settings["noise_extra_decay_db_s"] * (local - 1.1))[
            :, None
        ]
        / 20
    )
    for channel in range(2):
        decay_db = settings["first_decay_db_s"] * np.minimum(local, 1.1) + settings[
            "later_decay_db_s"
        ] * np.maximum(local - 1.1, 0)
        envelope = np.minimum(local / 0.08, 1) * 10 ** ((settings["gain_db"] - decay_db) / 20)
        envelope *= (
            np.clip(
                (event["end_seconds"] - score["source_start_seconds"] - time[begin:])
                / settings["final_fade_seconds"],
                0,
                1,
            )
            ** 2
        )
        first = np.sin(2 * np.pi * base_hz * local + (channel - 0.5) * settings["phase_spread_rad"])
        second = np.sin(
            2 * np.pi * base_hz * settings["secondary_ratio"] * local
            + (channel - 0.5) * settings["secondary_phase_spread_rad"]
        ) * 10 ** ((settings["secondary_db"] - settings["secondary_extra_decay_db_s"] * local) / 20)
        output[begin:, channel] = (first + second + diffuse[:, channel]) * envelope
    return output


def waveform(frequency, time, phase_cycles, osc, sr):
    if np.ndim(frequency):
        # Integrate instantaneous frequency; f(t)*t would create the wrong bend.
        cycles = np.zeros(len(time))
        cycles[1:] = np.cumsum((frequency[1:] + frequency[:-1]) * 0.5) / sr
        maximum_frequency = float(np.max(frequency))
    else:
        cycles = frequency * time  # Preserve the unchanged opening oscillator path.
        maximum_frequency = frequency
    phase = 2 * np.pi * (cycles + phase_cycles)
    wave = np.zeros(len(time))
    # Analytic bandlimited saw/pulse coefficients; no source Fourier coefficients.
    for harmonic in range(1, min(osc["max_harmonics"], int(0.45 * sr / maximum_frequency)) + 1):
        saw = -2 * np.sin(harmonic * phase) / (np.pi * harmonic)
        duty = osc["pulse_width"]
        square = (
            4
            * np.sin(np.pi * harmonic * duty)
            * np.cos(harmonic * phase - np.pi * harmonic * duty)
            / (np.pi * harmonic)
        )
        wave += (1 - osc["pulse_mix"]) * saw + osc["pulse_mix"] * square
    return wave


def unison(frequency, time, osc, sr, pan_scale):
    core = waveform(frequency, time, 0.11, osc, sr)
    result = np.tile(core[:, None], (1, 2)) * osc["center_gain"]
    for cents, phase, pan in zip(osc["detune_cents"], osc["phase_cycles"], osc["pan"]):
        wave = waveform(frequency * 2 ** (cents / 1200), time, phase, osc, sr)
        pan *= pan_scale
        result += (
            wave[:, None]
            * np.sqrt([1 - pan, 1 + pan])
            * osc["unison_gain"]
            / len(osc["detune_cents"])
        )
    return result


def moving_lowpass(audio, cutoff, q, sr):
    result = np.zeros_like(audio)
    state = np.zeros((2, 2))
    for start in range(0, len(audio), 64):
        stop = min(len(audio), start + 64)
        omega = 2 * np.pi * float(np.mean(cutoff[start:stop])) / sr
        cosine, alpha = np.cos(omega), np.sin(omega) / (2 * q)
        b = np.array([(1 - cosine) / 2, 1 - cosine, (1 - cosine) / 2]) / (1 + alpha)
        a = np.array([1 + alpha, -2 * cosine, 1 - alpha]) / (1 + alpha)
        result[start:stop], state = lfilter(b, a, audio[start:stop], axis=0, zi=state)
    return result


def presence_shelf(audio, frequency, gain_db, sr):
    """Fixed conventional high shelf, not a fitted spectral transfer function."""
    amplitude = 10 ** (gain_db / 40)
    omega = 2 * np.pi * frequency / sr
    cosine = np.cos(omega)
    beta = np.sqrt(2 * amplitude) * np.sin(omega)
    b = amplitude * np.array(
        [
            amplitude + 1 + (amplitude - 1) * cosine + beta,
            -2 * (amplitude - 1 + (amplitude + 1) * cosine),
            amplitude + 1 + (amplitude - 1) * cosine - beta,
        ]
    )
    a = np.array(
        [
            amplitude + 1 - (amplitude - 1) * cosine + beta,
            2 * (amplitude - 1 - (amplitude + 1) * cosine),
            amplitude + 1 - (amplitude - 1) * cosine - beta,
        ]
    )
    return lfilter(b / a[0], a / a[0], audio, axis=0)


def synthesize(score, patch, articulate=True):
    """No reads: symbolic score + sparse events + conventional patch only."""
    sr = patch["sample_rate"]
    preroll = round(0.25 * sr)
    length = round(score["duration_seconds"] * sr) + preroll
    time = (np.arange(length) - preroll) / sr
    brightness, upper_accent, body_accent = performance_curves(score, patch, time, articulate)
    output = np.zeros((length, 2))
    for part, part_patch in patch["parts"].items():
        if not enabled(score, part):
            continue
        bus = np.zeros_like(output)
        for note in score["notes"]:
            if note["part"] != part:
                continue
            start = -0.25 if note["carry_in"] else note["start_seconds"]
            release = patch["amplitude"]["release_ms"] / 1000
            begin = max(0, round(start * sr) + preroll)
            end = min(length, round((note["end_seconds"] + release) * sr) + preroll)
            local = np.arange(end - begin) / sr
            voice = np.zeros((len(local), 2))
            for octave, key in [(0, "root_gain_db"), (12, "octave_gain_db")]:
                if part_patch[key] <= -90:
                    continue
                frequency = hz(note["midi"] + octave, score["tuning_a4_hz"])
                offsets = midi_bend(note, time[begin:end] + score["source_start_seconds"])
                if np.any(offsets):
                    frequency = frequency * 2 ** (offsets / 12)
                voice += unison(
                    frequency, local, patch["oscillator"], sr, part_patch["pan_scale"]
                ) * 10 ** (part_patch[key] / 20)
            env_settings = patch["amplitude"]
            attack, decay = env_settings["attack_ms"] / 1000, env_settings["decay_ms"] / 1000
            sustain = env_settings["sustain"]
            envelope = (
                np.full(len(local), sustain)
                if note["carry_in"]
                else np.where(
                    local < attack,
                    np.clip(local / attack, 0, 1),
                    sustain + (1 - sustain) * np.exp(-np.maximum(local - attack, 0) / decay),
                )
            )
            off_age = time[begin:end] - note["end_seconds"]
            envelope *= np.where(off_age > 0, np.clip(1 - off_age / release, 0, 1) ** 2, 1)
            gain = note["velocity"] / 127 * 10 ** (part_patch["gain_db"] / 20)
            bus[begin:end] += voice * (envelope * gain)[:, None]
        accent = body_accent if part == "body" else upper_accent
        bus *= 10 ** (accent[:, None] / 20)
        drive = patch["filter"]["saturation_drive"]
        bus = np.tanh(bus * drive) / drive
        cutoff = patch["filter"]["base_hz"] * (
            patch["filter"]["peak_hz"] / patch["filter"]["base_hz"]
        ) ** (brightness * part_patch["filter_depth_scale"])
        cutoff *= section_control(score, time, "filter_scale", 1)
        bus *= 10 ** (section_control(score, time, part + "_gain_db", 0)[:, None] / 20)
        output += moving_lowpass(bus, cutoff, patch["filter"]["q"], sr)
    output = sosfilt(
        butter(2, patch["filter"]["highpass_hz"], fs=sr, btype="highpass", output="sos"),
        output,
        axis=0,
    )
    output = presence_shelf(
        output, patch["filter"]["presence_hz"], patch["filter"]["presence_db"], sr
    )
    stereo = patch["stereo"]
    result = output * (1 - stereo["wet"])
    sample = np.arange(length)
    for channel in range(2):
        delay = (
            (
                stereo["delay_ms"][channel]
                + stereo["depth_ms"][channel]
                * np.sin(2 * np.pi * stereo["rate_hz"][channel] * time + channel * 1.7)
            )
            * sr
            / 1000
        )
        result[:, channel] += stereo["wet"] * np.interp(
            sample - delay, sample, output[:, channel], left=0
        )
    result *= 10 ** (section_control(score, time, "synth_gain_db", 0)[:, None] / 20)
    for track, renderer in [
        ("bass", bass_voice),
        ("hat", hat_voice),
        ("snare", snare_voice),
        ("kick", kick_voice),
        ("texture", texture_voice),
        ("wash", wash_voice),
        ("bright_percussion", bright_voice),
        ("ending_fx", ending_voice),
    ]:
        if enabled(score, track):
            result += renderer(score, patch, time)
    return result[preroll:]



def midi_bend(note, absolute_seconds):
    """Standard MIDI pitchwheel is held until its next channel event."""
    points = note.get("midi_bend_points", [[0, 0]])
    times, values = np.asarray(points).T
    indices = np.maximum(0, np.searchsorted(times, absolute_seconds, side="right") - 1)
    return values[indices]


def wash_voice(score, patch, time):
    output = np.zeros((len(time), 2))
    for event in score.get("wash_triggers", []):
        local = dict(score, wash_start_source_seconds=event["start"], wash_end_source_seconds=event["end"])
        output += single_wash_voice(local, patch, time) * event["velocity"] / 100
    return output


def ending_voice(score, patch, time):
    output = np.zeros((len(time), 2))
    for event in score.get("ending_triggers", []):
        local = dict(score, ending_fx={"source_seconds": event["start"], "end_seconds": event["end"], "root_midi": event["midi"]})
        output += single_ending_voice(local, patch, time) * event["velocity"] / 100
    return output
