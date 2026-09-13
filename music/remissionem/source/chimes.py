"""Accepted Veil chimes instrument; composition and expression are in MIDI."""

import numpy as np
from scipy import signal
from pedalboard import Reverb
import synth_engine as engine

def dome(t, entrance, exit_start, exit_end):
    entry = np.sin(np.clip(t / entrance, 0, 1) * np.pi / 2) ** 2
    retreat = np.cos(np.clip((t - exit_start) / (exit_end - exit_start), 0, 1) * np.pi / 2) ** 2
    return (entry * retreat).astype(np.float32)


def bandpass(audio, low, high, sr):
    return signal.sosfilt(signal.butter(2, [low, high], fs=sr, btype="bandpass", output="sos"), audio, axis=0).astype(np.float32)


def synthesize(part, n, sr, p, beat, kicks):
    bell = np.zeros((n, 2), dtype=np.float32)
    body = np.zeros_like(bell)
    for index, note in enumerate(part["notes"]):
        t = np.arange(round(p["ring_seconds"] * sr)) / sr
        f0 = 440 * 2 ** ((note["pitch"] - 69) / 12)
        brightness = float(engine.interp(part["cc"].get(74), np.asarray([note["start"]]), .5)[0])
        strength = note["velocity"] ** p["velocity_exponent"]
        if note["velocity"] < p["soft_strike_threshold"]:
            strength *= p["soft_strike_gain"]
        pan = p["pan_width"] * np.sin(index * 2.399963)
        channels = []
        for side in [-1, 1]:
            wave = np.zeros(len(t))
            for mode, (ratio, gain, decay, attack) in enumerate(zip(
                p["partial_ratios"], p["partial_gains"], p["partial_decays_seconds"], p["partial_attacks_seconds"]
            )):
                detune = side * p["upper_detune_cents"] if mode > 0 else 0
                frequency = f0 * ratio * 2 ** (detune / 1200)
                # Slow beating in the upper modes gives a glass-like shimmer;
                # the tuned fundamental and octave keep the musical center clear.
                envelope = (1 - np.exp(-t / attack)) * np.exp(-t / decay)
                color = 1.0 if mode < 2 else .60 + .70 * brightness
                wave += gain * color * envelope * np.sin(2 * np.pi * frequency * t)
            wave *= np.sqrt(1 + side * pan)
            channels.append(wave)
        y = np.stack(channels, axis=1)
        y[-round(.08 * sr):] *= np.linspace(1, 0, round(.08 * sr))[:, None]
        y *= strength * p["gain"]
        engine.add(bell, note["start"], y.astype(np.float32), sr)
        warm = np.sin(2 * np.pi * f0 * t) * (1 - np.exp(-t / .028)) * np.exp(-t / p["body_decay_seconds"])
        warm[-round(.08 * sr):] *= np.linspace(1, 0, round(.08 * sr))
        warm *= strength * p["body_gain"] * p["gain"]
        engine.add(body, note["start"], np.repeat(warm[:, None], 2, axis=1).astype(np.float32), sr)
    excitation = bandpass(bell + body, p["highpass_hz"], p["lowpass_hz"], sr)
    room = Reverb(room_size=.52, damping=.67, wet_level=p["room_wet"], dry_level=0, width=.8)(excitation.T.copy(), sr).T.copy()
    hall = Reverb(room_size=p["hall_size"], damping=p["hall_damping"],
                  wet_level=p["hall_wet"], dry_level=0, width=1)(excitation.T.copy(), sr).T.copy()
    # A slower, dark resonance adds body behind the brighter bells rather than
    # relying on high-frequency reverb alone to create a sense of space.
    cloud_input = bandpass(excitation, 260, 1600, sr)
    cloud = Reverb(room_size=.91, damping=.77, wet_level=p["cloud_wet"],
                   dry_level=0, width=.84)(cloud_input.T.copy(), sr).T.copy()
    room = bandpass(room, 340, 6800, sr)
    hall = bandpass(hall, 550, 7200, sr)
    cloud = bandpass(cloud, 285, 2100, sr)
    returns = room + cloud
    delay = round(p["hall_predelay_seconds"] * sr)
    returns[delay:] += hall[:-delay]
    feed = bandpass(excitation, 820, 5200, sr)
    for beats, gain, flip in [(.75, 1, True), (1.5, .42, False), (2.25, .18, True)]:
        d = round(beats * beat * sr)
        returns[d:] += (feed[:-d, ::-1] if flip else feed[:-d]) * p["delay_gain"] * gain
    time = np.arange(n) / sr
    direct_envelope = engine.expression(part, time)
    space_envelope = dome(time, p["space_entrance_seconds"], p["space_exit_start"], p["space_exit_end"])
    direct = excitation * direct_envelope[:, None]
    returns *= space_envelope[:, None]
    for note in kicks:
        if note["pitch"] != 36 or note["start"] > p["space_exit_end"]:
            continue
        a = round(note["start"] * sr)
        b = min(n, a + round(.18 * sr))
        returns[a:b] *= np.interp(np.arange(b - a) / sr, [0, .015, .06, .18], [1, .76, .80, 1])[:, None]
    return (direct + returns).astype(np.float32), direct, returns, direct_envelope, space_envelope
