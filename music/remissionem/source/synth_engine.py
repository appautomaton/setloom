"""Oscillator/noise instruments adapted from the recovered-score production.

Original-song PCM is never an input. The new saw patch adds phrase brightness
control; the sampled grand is rendered separately by this candidate's renderer.
"""

import mido
import numpy as np
from scipy import signal
from pedalboard import Reverb


def read_midi(path):
    midi = mido.MidiFile(path)
    tempos = {m.tempo for track in midi.tracks for m in track if m.type == "set_tempo"}
    if len(tempos) != 1:
        raise ValueError("This production currently expects one explicit MIDI tempo.")
    tempo = tempos.pop()
    parts = {}
    for track in midi.tracks[1:]:
        name = next(m.name for m in track if m.type == "track_name")
        elapsed = 0.0
        active = {}
        notes = []
        cc = {}
        bends = []
        bend_range = 2
        for m in track:
            elapsed += mido.tick2second(m.time, midi.ticks_per_beat, tempo)
            if m.type == "control_change":
                if m.control == 6:
                    bend_range = m.value
                elif m.control in [11, 71, 74, 80, 91]:
                    cc.setdefault(m.control, []).append((elapsed, m.value / 127))
            elif m.type == "pitchwheel":
                bends.append((elapsed, m.pitch * bend_range / 8192))
            elif m.type == "note_on" and m.velocity:
                key = (m.channel, m.note)
                if key in active:
                    raise ValueError(f"Overlapping same-pitch MIDI note in {name}: {key}")
                active[key] = (elapsed, m.velocity / 127)
            elif m.type == "note_off" or (m.type == "note_on" and not m.velocity):
                start, velocity = active.pop((m.channel, m.note))
                notes.append(
                    {"start": start, "end": elapsed, "pitch": m.note, "velocity": velocity}
                )
        if active:
            raise ValueError(f"Unclosed notes in {name}")
        parts[name] = {"notes": sorted(notes, key=lambda n: n["start"]), "cc": cc, "bends": bends}
    return parts, tempo / 1e6


def interp(points, t, default):
    if not points:
        return np.full(len(t), default, dtype=np.float32)
    points = sorted(dict(points).items())
    return np.interp(t, *np.asarray(points).T).astype(np.float32)


def expression(part, t):
    return interp(part["cc"].get(11), t, 1.0)


def add(dest, start, a, sr):
    offset = round(start * sr)
    left = max(0, -offset)
    offset = max(0, offset)
    length = min(len(a) - left, len(dest) - offset)
    if length > 0:
        dest[offset : offset + length] += a[left : left + length]


def stereo_width(x, width):
    mid = x.mean(axis=1, keepdims=True)
    return mid + (x - mid) * width


def space(audio, sr, wet, room=0.64):
    if wet <= 0:
        return audio
    # Keep the calibrated direct level explicit. Filter only the return so
    # repeated low notes do not accumulate into a continuous C3 drone.
    return_audio = Reverb(room_size=room, damping=0.6, wet_level=wet, dry_level=0, width=1)(
        audio.T.copy(), sr
    ).T.copy()
    return_audio = signal.sosfilt(
        signal.butter(2, 380, fs=sr, btype="highpass", output="sos"), return_audio, axis=0
    )
    return (2 * audio + return_audio).astype(np.float32)


def bass(part, n, sr, p, kind):
    t = np.arange(n) / sr
    frequency = np.zeros(n, dtype=np.float32)
    amplitude = np.zeros(n, dtype=np.float32)
    for index, event in enumerate(part["notes"]):
        start = round(event["start"] * sr)
        end = min(n, round(event["end"] * sr))
        frequency[start:end] = 440 * 2 ** ((event["pitch"] - 69) / 12)
        amplitude[start:end] = event["velocity"]
        legato = (
            index + 1 < len(part["notes"])
            and abs(part["notes"][index + 1]["start"] - event["end"]) < 0.003
        )
        if not legato:
            stop = min(n, end + round(5 * p["release_seconds"] * sr))
            frequency[end:stop] = frequency[max(start, end - 1)]
            amplitude[end:stop] = event["velocity"] * np.exp(
                -np.arange(stop - end) / sr / p["release_seconds"]
            )
    phase = 2 * np.pi * np.cumsum(frequency, dtype=np.float64) / sr
    gain = amplitude * expression(part, t) * p["gain"]
    if kind == "sub":
        wave = np.sin(phase) + p["warmth"] * np.sin(3 * phase)
        return np.repeat((wave * gain)[:, None], 2, axis=1).astype(np.float32)
    if kind == "formant":
        center = p["center_min_hz"] + (p["center_max_hz"] - p["center_min_hz"]) * interp(
            part["cc"].get(71), t, 0.4
        )
        voices = []
        for side in [-1, 1]:
            wave = np.zeros(n)
            for h in range(3, 37):
                hz = frequency * h
                peak = np.exp(-0.5 * ((hz - center) / p["bandwidth_hz"]) ** 2)
                upper_peak = np.exp(-0.5 * ((hz - 2 * center) / (p["bandwidth_hz"] * 1.4)) ** 2)
                shape = (0.22 + p["resonance"] * peak + p["upper_resonance"] * upper_peak) / h
                shape /= np.sqrt(1 + (hz / p["lowpass_hz"]) ** 6)
                wave += shape * np.sin(h * phase + side * 0.035 * h) * (hz < sr * 0.44)
            wave = np.tanh(wave * p["drive"]) / p["drive"]
            voices.append(wave)
        out = stereo_width(np.stack(voices, axis=1), p["width"]) * gain[:, None]
        out = signal.sosfilt(
            signal.butter(
                2, [p["highpass_hz"], p["lowpass_hz"]], fs=sr, btype="bandpass", output="sos"
            ),
            out,
            axis=0,
        )
        return out.astype(np.float32)
    brightness = interp(part["cc"].get(74), t, 0.3)
    cutoff = p["cutoff_min_hz"] * (p["cutoff_max_hz"] / p["cutoff_min_hz"]) ** brightness
    out = np.zeros((n, 2), dtype=np.float32)
    for channel, side in enumerate([-1, 1]):
        upper_phase = phase * 2 ** (side * p["detune_cents"] / 1200)
        wave = np.sin(phase)
        for harmonic in range(2, 65):
            hz = frequency * harmonic
            coefficient = (
                (1 - p["saw_blend"]) * np.sin(np.pi * harmonic * p["pulse_width"])
                + p["saw_blend"] * (-1) ** (harmonic + 1)
            ) / harmonic
            attenuation = 1 / np.sqrt(1 + (hz / np.maximum(cutoff, 1)) ** 6)
            opening = 1 + p["brightness_opening"] * brightness * (1 - np.exp(-((hz / 850) ** 4)))
            wave += (
                coefficient
                * np.sin(harmonic * upper_phase)
                * attenuation
                * opening
                * (hz < min(sr * 0.44, p["max_harmonic_hz"]))
            )
        out[:, channel] = (np.tanh(wave * p["drive"]) / p["drive"] * gain).astype(np.float32)
    return stereo_width(out, p["width"])


def lead(part, n, sr, p, kind, beat):
    out = np.zeros((n, 2), dtype=np.float32)
    for index, event in enumerate(part["notes"]):
        gate = event["end"] - event["start"]
        length = gate + 5 * p["release_seconds"]
        if index + 1 < len(part["notes"]):
            length = min(length, part["notes"][index + 1]["start"] - event["start"] + 0.004)
        t = np.arange(round(length * sr)) / sr
        fundamental = 440 * 2 ** ((event["pitch"] - 69) / 12)
        # A monophonic note keeps its last bend during release. Interpolating
        # across the rest to the next note's starting bend creates a false fall.
        bend_points = [
            point
            for point in part["bends"]
            if event["start"] - 0.001 <= point[0] <= event["end"] + 0.001
        ]
        bend = interp(bend_points, event["start"] + t, 0.0)
        f = fundamental * 2 ** (bend / 12)
        phase = 2 * np.pi * np.cumsum(f) / sr
        env = (1 - np.exp(-t / p["attack_seconds"])) * (
            p["sustain"] + (1 - p["sustain"]) * np.exp(-t / p["decay_seconds"])
        )
        env *= np.exp(-np.maximum(0, t - gate) / p["release_seconds"])
        env[-min(len(env), round(0.004 * sr)) :] *= np.linspace(
            1, 0, min(len(env), round(0.004 * sr))
        )
        voices = []
        for side in [-1, 1]:
            if kind == "sweep":
                ph = phase * (1 + side * 0.0007)
                wave = np.zeros(len(t))
                for h, coefficient in enumerate(p["harmonics"], start=1):
                    wave += coefficient * np.sin(h * ph + (0.3 if h == 2 else 0))
            else:
                ph = phase * 2 ** (side * p["detune_cents"] / 1200)
                brightness = interp(part["cc"].get(74), np.asarray([event["start"]]), 0.65)[0]
                cutoff = p["cutoff_end_hz"] + (p["cutoff_start_hz"] - p["cutoff_end_hz"]) * np.exp(
                    -t / p["filter_decay_seconds"]
                )
                cutoff *= 0.62 + 0.65 * brightness
                wave = np.zeros(len(t))
                for h in range(1, min(49, int(sr * 0.44 / fundamental) + 1)):
                    coeff = (
                        (1 - p["pulse_mix"]) * (-1) ** (h + 1)
                        + p["pulse_mix"] * np.sin(np.pi * h * 0.48)
                    ) / h
                    attenuation = 1 / np.sqrt(1 + (fundamental * h / cutoff) ** 4)
                    hz = fundamental * h
                    lowcut = 1 / np.sqrt(1 + (p["lowcut_hz"] / hz) ** 4)
                    emphasis = 1 + p["upper_emphasis"] * (
                        1 - np.exp(-((hz / p["emphasis_center_hz"]) ** 6))
                    )
                    transient = 1
                    if hz < 220:
                        transient = p["low_body_gain"] * (
                            0.2 + 0.8 * np.exp(-t / p["low_body_decay_seconds"])
                        )
                    wave += coeff * np.sin(h * ph) * attenuation * lowcut * emphasis * transient
                wave = np.tanh(wave * p["drive"]) / p["drive"]
            voices.append(wave)
        wave = stereo_width(np.stack(voices, axis=1), p["width"])
        add(
            out,
            event["start"],
            (wave * env[:, None] * event["velocity"] * p["gain"]).astype(np.float32),
            sr,
        )
    if kind == "arp":
        dry = out.copy()
        echoes = np.zeros_like(out)
        for beats, gain, swap in [
            (0.25, 0.055, False),
            (0.75, p["delay_gain"], True),
            (1.25, p["delay_gain"] * 0.65, False),
        ]:
            delay = round(beats * beat * sr)
            echoes[delay:] += dry[:-delay, ::-1] * gain if swap else dry[:-delay] * gain
        echoes = signal.sosfilt(
            signal.butter(2, 380, fs=sr, btype="highpass", output="sos"), echoes, axis=0
        )
        out = (dry + echoes).astype(np.float32)
    return space(out, sr, p["reverb_wet"])


def drums(part, n, sr, p, kind):
    out = np.zeros((n, 2), dtype=np.float32)
    low_accents = np.zeros_like(out) if kind == "kick" else None
    rng = np.random.default_rng({"kick": 913, "hat": 117, "snare": 309, "percussion": 571}[kind])
    if p["gain"] == 0:
        return out
    for index, event in enumerate(part["notes"]):
        t = np.arange(round((0.8 if kind == "kick" else 0.55) * sr)) / sr
        if kind == "kick" and event["pitch"] == 35:
            hz = 24 + 140 * np.exp(-t / 0.045) + 20 * np.exp(-t / 0.14)
            wave = np.sin(2 * np.pi * np.cumsum(hz) / sr)
            wave *= (1 - np.exp(-t / 0.003)) * np.exp(-t / 0.17)
            wave = signal.sosfilt(signal.butter(2, 24, fs=sr, btype="highpass", output="sos"), wave)
            wave[-round(0.05 * sr) :] *= np.linspace(1, 0, round(0.05 * sr))
            wave = np.repeat(wave[:, None], 2, axis=1) * p["gain"] * event["velocity"]
            add(low_accents, event["start"], wave.astype(np.float32), sr)
            continue
        if kind == "kick":
            hz = (
                p["pitch_end_hz"]
                + (p["pitch_body_hz"] - p["pitch_end_hz"]) * np.exp(-t / 0.38)
                + (p["pitch_start_hz"] - p["pitch_body_hz"]) * np.exp(-t / p["pitch_drop_seconds"])
            )
            phase = 2 * np.pi * np.cumsum(hz) / sr
            env = (1 - np.exp(-t / p["attack_seconds"])) * np.exp(
                -np.maximum(0, t - p["hold_seconds"]) / p["decay_seconds"]
            )
            wave = np.tanh(np.sin(phase) * p["drive"]) / np.tanh(p["drive"]) * env
            wave += np.sin(2 * phase) * np.exp(-t / 0.055) * p["thump_gain"]
            click = signal.sosfilt(
                signal.butter(2, [1100, 6500], fs=sr, btype="bandpass", output="sos"),
                rng.standard_normal(len(t)),
            )
            wave += click * np.exp(-t / 0.0024) * p["click_gain"]
            if index + 1 < len(part["notes"]):
                until = part["notes"][index + 1]["start"] - event["start"]
                wave *= np.clip((until + 0.004 - t) / 0.004, 0, 1)
            wave = np.repeat(wave[:, None], 2, axis=1)
        elif kind == "hat":
            noise = rng.standard_normal((len(t), 2))
            metal = (
                sum(
                    np.sin(2 * np.pi * f * t + i * 0.61)
                    for i, f in enumerate([6743, 8237, 10139, 12781])
                )
                / 2
            )
            noise = (1 - p["metal_mix"]) * noise + p["metal_mix"] * metal[:, None]
            wave = signal.sosfilt(
                signal.butter(3, p["highpass_hz"], fs=sr, btype="highpass", output="sos"),
                noise,
                axis=0,
            )
            decay = p["open_decay_seconds"] if event["pitch"] == 46 else p["closed_decay_seconds"]
            wave *= ((1 - np.exp(-t / 0.0004)) * np.exp(-t / decay))[:, None]
            wave = stereo_width(wave, p["width"])
        elif kind == "snare":
            noise = signal.sosfilt(
                signal.butter(2, [700, 9500], fs=sr, btype="bandpass", output="sos"),
                rng.standard_normal((len(t), 2)),
                axis=0,
            )
            env = np.exp(-t / p["decay_seconds"]) * (1 - np.exp(-t / 0.0007))
            body = (np.sin(2 * np.pi * 178 * t) + 0.45 * np.sin(2 * np.pi * 331 * t)) * np.exp(
                -t / 0.042
            )
            wave = noise * env[:, None] + body[:, None] * p["body_gain"]
            wave = stereo_width(wave, p["width"])
        elif kind == "percussion":
            wave = signal.sosfilt(
                signal.butter(2, [1700, 10000], fs=sr, btype="bandpass", output="sos"),
                rng.standard_normal((len(t), 2)),
                axis=0,
            )
            wave *= ((1 - np.exp(-t / 0.0006)) * np.exp(-t / p["decay_seconds"]))[:, None]
            wave = stereo_width(wave, p["width"])
        else:
            raise ValueError(f"Unknown drum instrument: {kind}")
        wave[-round(0.02 * sr) :] *= np.linspace(1, 0, round(0.02 * sr))[:, None]
        add(out, event["start"], (wave * p["gain"] * event["velocity"]).astype(np.float32), sr)
    if kind == "kick":
        out *= interp(part["cc"].get(80), np.arange(n) / sr, 1.0)[:, None]
        out += low_accents
    return out


def effects(part, n, sr, p, kind):
    out = np.zeros((n, 2), dtype=np.float32)
    rng = np.random.default_rng(981)
    for event in part["notes"]:
        length = event["end"] - event["start"]
        t = np.arange(round((length + 0.7) * sr)) / sr
        base = 440 * 2 ** ((event["pitch"] - 69) / 12)
        noise = rng.standard_normal((len(t), 2))
        if kind == "downshift":
            f = base * (0.09 + 0.41 * np.exp(-t / p["pitch_decay_seconds"]))
            ph = 2 * np.pi * np.cumsum(f) / sr
            x = np.sin(ph) * (1 - np.exp(-t / 0.004)) * np.exp(-t / p["amplitude_decay_seconds"])
            wave = np.repeat(x[:, None], 2, axis=1)
            hiss = signal.sosfilt(
                signal.butter(2, 1100, fs=sr, btype="highpass", output="sos"), noise, axis=0
            )
            wave += hiss * np.exp(-t / 0.23)[:, None] * p["noise_gain"]
        else:
            wave = signal.sosfilt(
                signal.butter(2, [1800, 12000], fs=sr, btype="bandpass", output="sos"),
                noise,
                axis=0,
            )
            env = np.minimum(t / max(length, 1e-3), 1) ** 2 * np.exp(
                -np.maximum(0, t - length) / 0.16
            )
            wave *= env[:, None]
            wave = stereo_width(wave, p["width"])
        wave[-round(0.1 * sr) :] *= np.linspace(1, 0, round(0.1 * sr))[:, None]
        add(out, event["start"], (wave * p["gain"] * event["velocity"]).astype(np.float32), sr)
    return out
