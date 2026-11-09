# SPDX-License-Identifier: AGPL-3.0-only
"""Perform the authored MIDI and physical gestures; reference audio is never opened.

Each voice owns its oscillator, excitation, articulation, spatial response and
ducking. Cached float voices allow a mix revision without replacing performances.
"""

import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import mido
import numpy as np
import soundfile as sf
from pedalboard import Reverb
from scipy import signal

from setloom.audio import integrated_lufs, write_master
from mix_dsp import polish_return, polish_voice

ROOT = Path(__file__).resolve().parents[1]
# Generated audio stays outside the tracked production.
RENDER = ROOT.parents[1] / "tmp/umklapp/render"
BEAT = 60 / 134


def read_midi(path):
    """Use the conductor tempo map for every part, including edited tempo events."""
    midi = mido.MidiFile(path)
    tempos = {0: 500000}
    for track in midi.tracks:
        tick = 0
        for message in track:
            tick += message.time
            if message.type == "set_tempo":
                tempos[tick] = message.tempo
    ticks = np.array(sorted(tempos))
    rates = np.array([tempos[tick] / 1e6 / midi.ticks_per_beat for tick in ticks])
    starts = np.r_[0, np.cumsum(np.diff(ticks) * rates[:-1])]

    def seconds(tick):
        index = int(np.searchsorted(ticks, tick, side="right") - 1)
        return float(starts[index] + (tick - ticks[index]) * rates[index])

    result = {}
    for track in midi.tracks:
        tick = 0
        name = ident = None
        opened = {}
        notes = []
        for message in track:
            tick += message.time
            if message.type == "track_name":
                name = message.name
            elif message.type == "text":
                ident = message.text
            elif message.type == "note_on" and message.velocity:
                opened.setdefault((message.channel, message.note), []).append(dict(id=ident, start=seconds(tick), pitch=message.note, velocity=message.velocity))
                ident = None
            elif message.type == "note_off" or message.type == "note_on" and not message.velocity:
                key = (message.channel, message.note)
                if not opened.get(key):
                    raise ValueError(f"Unmatched note end in {name}")
                note = opened[key].pop(0)
                note["end"] = seconds(tick)
                notes.append(note)
        if any(opened.values()):
            raise ValueError(f"Unclosed MIDI notes in {name}")
        if notes:
            result[name] = sorted(notes, key=lambda item: item["start"])
    return result


@lru_cache(maxsize=2048)
def filter_design(rate, low, high):
    if low and high:
        return signal.butter(2, [low, high], fs=rate, btype="bandpass", output="sos")
    return signal.butter(2, low or high, fs=rate, btype="highpass" if low else "lowpass", output="sos")


def filtered(audio, rate, low=0, high=0):
    return signal.sosfilt(filter_design(rate, round(low, 1), round(high, 1)), audio, axis=0).astype("float32")


def noise(rng, count, rate, low, high, channels=1):
    excitation = rng.standard_normal((count + 1024, channels), dtype="float32")
    colored = filtered(excitation, rate, low, high)[1024:]
    colored /= np.maximum(np.sqrt(np.mean(colored * colored, axis=0)), 1e-8)
    return colored[:, 0] if channels == 1 else colored


def frequency(pitch):
    return 440 * 2 ** ((pitch - 69) / 12)


def control(automation, name, time, default):
    if name not in automation:
        return np.full_like(np.asarray(time, dtype=float), default)
    return np.interp(time, automation["time_seconds"], automation[name])


def envelope(t, gate, attack, decay, sustain, release):
    body = (1 - np.exp(-t / attack)) * (sustain + (1 - sustain) * np.exp(-t / decay))
    body *= np.exp(-np.maximum(0, t - gate) / release)
    edge = np.clip((t[-1] - t) / .007, 0, 1)
    return body * edge


def stereo(mono, pan=0, width=0, side=None):
    angle = (np.clip(pan, -1, 1) + 1) * np.pi / 4
    output = np.column_stack((mono * np.cos(angle), mono * np.sin(angle))) * np.sqrt(2)
    if side is not None:
        output[:, 0] += side * width
        output[:, 1] -= side * width
    return output


def pitch_motion(t, note, descriptor, settings):
    """Perform gate-relative flex and one shared absolute-clock vibration."""
    gate = max(.005, note["end"] - note["start"])
    knots = np.asarray(descriptor["pitch_curve"], dtype=float)
    phase = np.clip(t / gate, knots[0,0], knots[-1,0])
    index = np.clip(np.searchsorted(knots[:,0],phase,side="right")-1,0,len(knots)-2)
    x = np.clip((phase-knots[index,0])/(knots[index+1,0]-knots[index,0]),0,1)
    curve = knots[index,1]+(knots[index+1,1]-knots[index,1])*(.5-.5*np.cos(np.pi*x))
    emerge = .5-.5*np.cos(np.pi*np.clip((t/gate-.18)/.40,0,1))
    decay = np.exp(-np.maximum(0,t-gate)/settings["vibrato_tail_seconds"])
    absolute_phase = 2*np.pi*settings["vibrato_cycles_per_beat"]*(note["start"]+t)/BEAT
    vibration = descriptor["vibrato_depth_cents"]/100*emerge*decay*np.sin(absolute_phase)
    # This slow shared field crosses successive cells without restarting at a
    # note. Stable landing notes carry no shear and retain their destination.
    shear_phase = 2*np.pi*(note["start"]+t)/(settings.get("phrase_shear_beats",8)*BEAT)
    window = np.sin(np.pi*np.clip(t/gate,0,1))**2
    shear = descriptor.get("phrase_shear_depth_cents",0)/100*window*np.sin(shear_phase)
    return curve+vibration+shear


def color_distortion(audio, rate, settings, amount):
    """Replace part of a filtered body with biased saturation at a declared level."""
    band = filtered(audio,rate,*settings["band_hz"])
    drive = np.asarray(np.interp(amount,[0,1],settings["drive"]),dtype="float32")
    blend = np.asarray(np.interp(amount,[0,1],settings["blend"]),dtype="float32")
    if audio.ndim==2 and drive.ndim:
        drive,blend=drive[:,None],blend[:,None]
    reference = settings["reference_level"]
    bias = settings["bias"]
    shaped = reference*(np.tanh(band/reference*drive+bias)-np.tanh(bias))/np.tanh(drive)
    # Filtering the difference suppresses DC and keeps added grain in its body band.
    residual = filtered(shaped-band,rate,*settings["band_hz"])
    return (audio+blend*residual).astype("float32")


def synthesize(ident, note, descriptor, settings, automation, rate, seed):
    gate = max(.005, note["end"] - note["start"])
    original_gate = max(.005, descriptor["duration_beats"] * BEAT)
    rng = np.random.default_rng(seed)
    oversample = 4 if ident in ("bend","lattice") else 2 if ident in ("kick","engine","relay") else 1
    work_rate = rate * oversample
    span = gate + {"kick": .07, "engine": .16, "bend": .22, "lattice": .58, "drums": .32, "hats": .10, "pressure": .25, "field": 4.0, "relay": .25, "veil": descriptor.get("release_beats", 3) * BEAT}[ident]
    t = np.arange(max(8, round(span * work_rate)), dtype="float64") / work_rate
    touch = (note["velocity"] / 110) ** 1.15
    brightness = float(control(automation, ident + "_brightness", note["start"], .5))
    level = float(control(automation, ident + "_level", note["start"], 1))
    pan = float(control(automation, ident + "_pan", note["start"], 0))
    grit = float(control(automation, ident + "_grit", note["start"], .5))
    f0 = frequency(note["pitch"])
    if ident == "kick":
        stretch = np.clip(gate / original_gate, .25, 4)
        tau = settings["fall_seconds"] * stretch
        pitch = settings["tail_hz"] * 2 ** ((note["pitch"] - descriptor["pitch"]) / 12)
        freq = pitch + (settings["start_hz"] - settings["tail_hz"]) * np.exp(-t / tau)
        phase = np.cumsum(freq) * 2 * np.pi / work_rate
        decay = descriptor.get("tail_seconds", .39) * stretch
        body = (1 - np.exp(-t / settings["attack_seconds"])) * (.86 * np.exp(-t / (decay * .31)) + .14 * np.exp(-t / (decay * .63)))
        body *= np.clip((decay - t) / .025, 0, 1)
        mono = (np.sin(phase) + .075 * np.sin(2 * phase) + .023 * np.sin(3 * phase)) * body
        mono += .034 * noise(rng, len(t), work_rate, 1500, 7500) * np.exp(-t / .004) * np.clip(t / .0006, 0, 1)
        output = stereo(mono)
    elif ident == "engine":
        glide = descriptor.get("glide_semitones", .35) * np.exp(-t / .025)
        phase = np.cumsum(f0 * 2 ** (glide / 12)) * 2 * np.pi / work_rate
        index = np.interp(brightness, [0, 1], settings["fm_index"]) * (.72 + .28 * np.exp(-t / .13)) * descriptor.get("bite", 1)
        throat = np.sin(settings["carrier_ratio"] * phase + index * np.sin(settings["modulator_ratio"] * phase) + .18 * np.sin(settings["secondary_modulator_ratio"] * phase))
        modes = sum(weight * np.sin(ratio * phase + index * .21 * np.sin(phase * .5)) for ratio, weight in zip(settings["modal_ratios"][1:], [.20, .115, .085, .045]))
        core = descriptor.get("core_weight", .48) * np.sin(phase) + .24 * np.sin(2 * phase)
        texture = filtered((settings["texture_amount"] * throat + modes) * descriptor.get("texture_weight", 1), work_rate, 90, np.interp(brightness, [0, 1], settings["cutoff_hz"]))
        env = envelope(t, gate, descriptor.get("attack_seconds", .003), .15, .48, descriptor.get("release_seconds", .034))
        mono = np.tanh((core + texture) * 1.65) / 1.65 * env
        grain = noise(rng, len(t), work_rate, 170, 1400) * env * settings["grain_amount"] * descriptor.get("grain_scale", 1) * (.35 + .65 * np.exp(-t / .09))
        output = stereo(mono + grain, 0, settings["width"], np.sin(phase * 6 + .35) * env * .10)
    elif ident == "bend":
        motion = pitch_motion(t,note,descriptor,settings)
        phase = np.cumsum(f0 * 2 ** (motion / 12)) * 2 * np.pi / work_rate
        index = np.interp(brightness, [0, 1], settings["fm_index"]) * (.60 + .40 * np.exp(-t / .08))
        mono = .54 * np.sin(phase + index * np.sin(phase * settings["fm_ratio"])) + .24 * np.sin(2 * phase + .4 * index * np.sin(settings["secondary_ratio"] * phase)) + .11 * np.sin(3 * phase)
        mono = filtered(mono, work_rate, 160, np.interp(brightness, [0, 1], settings["cutoff_hz"]) * descriptor.get("shade", 1))
        env = envelope(t, gate, .0025, .095, .29 if gate < .5 else .61, .045 * descriptor.get("release_scale", 1))
        air = noise(rng, len(t), work_rate, 1600, 9000) * .025 * env
        output = stereo(np.tanh(mono * 1.25) / 1.25 * env + air, pan, settings["width"], np.sin(phase * settings["side_ratio"] + .53) * env * .19)
    elif ident == "lattice":
        output = np.zeros((len(t), 2))
        motion = pitch_motion(t,note,descriptor,settings)
        open_value = descriptor.get("openness", .45)
        strike = (1 - np.exp(-t / descriptor.get("strike_seconds", .0024)))
        for mode, (ratio, weight) in enumerate(zip(settings["modal_ratios"], settings["modal_weights"])):
            ratio += descriptor.get("metal_ratio_shift", 0) * mode
            flutter = descriptor["surface_flutter_cents"]/100*(mode/6)**1.5*np.exp(-t/.22)*np.sin(2*np.pi*3*(note["start"]+t)/BEAT+.4*mode)
            phase = np.cumsum(f0*ratio*2**((motion+flutter)/12))*2*np.pi/work_rate+.31*mode
            lifetime = (gate * (settings["body_decay_scale"] if mode < 2 else settings["body_decay_scale"] * .55) + .035 + .17 * open_value) * descriptor.get("body_decay_multiplier",1)
            env = strike * np.exp(-t / lifetime) * np.clip((t[-1] - t) / .015, 0, 1)
            transient_index = settings["metal_fm_index"] * brightness * np.exp(-t / settings["metal_fm_decay_seconds"])
            ringing = np.sin(phase + transient_index * np.sin(2 * np.pi * f0 * settings["metal_fm_ratio"] * t))
            gain = weight * (.72 + brightness * .28 if mode > 2 else 1)
            output += stereo(ringing * env * gain, np.clip(pan + settings["width"] * np.sin(mode * 2.37), -.70, .70))
        output += stereo(noise(rng, len(t), work_rate, 2500, 13500) * strike * np.exp(-t / .042) * .039, pan)
        output = np.tanh(output * 1.12) / 1.12
    elif ident == "drums":
        tone = descriptor["tone_hz"] * 2 ** ((note["pitch"] - descriptor["pitch"]) / 12)
        kind = descriptor["kind"]
        if kind == "tom":
            phase = np.cumsum(tone * (1 + .20 * np.exp(-t / .018))) * 2 * np.pi / rate
            mono = (.58 * np.sin(phase) + .24 * np.sin(phase * 1.483) + .11 * np.sin(phase * 2.079)) * envelope(t, gate, .001, .058 * descriptor.get("damping_scale", 1), .03, .04)
            mono += (.07 + .09 * brightness) * noise(rng, len(t), rate, 650, 1800 + 3400 * brightness) * np.exp(-t / .024) * np.clip(t / .0007, 0, 1)
        elif kind == "rim":
            mono = sum(g * np.sin(2 * np.pi * tone * ratio * t) for ratio, g in [(1, .39), (1.67, .23), (2.41, .15)]) * envelope(t, gate, .0006, .017 * descriptor.get("damping_scale", 1), 0, .01)
            mono += noise(rng, len(t), rate, 1100, 10000) * .12 * np.exp(-t / .008) * np.clip(t / .0005, 0, 1)
        else:
            colored = noise(rng, len(t), rate, 700, 8500)
            strikes = np.exp(-t / .039) + .36 * np.exp(-np.maximum(0, t - .010) / .032) * (t >= .010) + .18 * np.exp(-np.maximum(0, t - .021) / .025) * (t >= .021)
            mono = .44 * colored * strikes + .28 * np.sin(2 * np.pi * tone * t) * np.exp(-t / .055)
            mono *= np.clip(t / .0006, 0, 1) * np.clip((t[-1] - t) / .006, 0, 1)
        output = stereo(mono, .15 * np.sin(note["start"] / BEAT * np.pi / 8))
    elif ident == "hats":
        openness = descriptor["openness"]
        high = np.interp(brightness, [0, 1], settings["maximum_band_hz"])
        grain = noise(rng, len(t), rate, 4300, high)
        metal = sum(np.sin(2 * np.pi * f * t + i * .47) for i, f in enumerate(settings["modes_hz"])) / np.sqrt(2.5)
        env = (1 - np.exp(-t / .00055)) * np.exp(-t / (.009 + .069 * openness))
        env *= np.clip((t[-1] - t) / .004, 0, 1)
        mono = (.60 * grain + settings["metal_amount"] * metal) * env
        side = noise(rng, len(t), rate, 6000, high) * env * .23
        output = stereo(mono, .10 * np.sin(note["start"] / BEAT * np.pi / 5), settings["width"], side)
    elif ident == "pressure":
        x = np.clip(t / gate, 0, 1)
        kind = descriptor["kind"]
        envelope_value = np.sin(x * np.pi / 2) ** 4 if kind == "resonant-reverse" else np.sin(x * np.pi / 2) ** 2 if kind in ("rise", "reverse") else np.exp(-t / .28) + .18 * np.exp(-t / .95)
        envelope_value *= np.clip(t / .007, 0, 1) * np.clip((gate - t) / .025, 0, 1)
        output = np.zeros((len(t), 2))
        movement = x if kind != "fall" else 1 - x
        for index, band in enumerate([(260, 1000), (1000, 4000), (4000, 11000)]):
            grain = noise(rng, len(t), rate, *band, channels=2)
            grain[:, 1] = .68 * grain[:, 0] + .733 * grain[:, 1]
            weight = [.43 * (1 - .5 * movement), .32 + .20 * movement, .08 * movement][index]
            output += grain * (envelope_value * weight * (.42 if kind == "resonant-reverse" else 1))[:, None]
        phases = 2 * np.pi * f0 * 3 * t
        output += stereo(np.sin(phases + .08 * np.sin(phases * 2)) * envelope_value * .10, 0)
        if kind == "resonant-reverse":
            memory = .38 * np.sin(2 * np.pi * f0 * t) + .16 * np.sin(2 * np.pi * f0 * 2 * t + .4) + .06 * np.sin(2 * np.pi * f0 * 3 * t)
            output += stereo(memory * envelope_value, -.13, .15, np.sin(phases + .7) * envelope_value * .10)
        output *= (.55 + .45 * np.sin(t / BEAT * np.pi * 2 + np.pi / 2) ** 2)[:, None]
    elif ident == "relay":
        phase = 2 * np.pi * f0 * t
        index = settings["fm_index"] * (.4 + brightness) * np.exp(-t / .045)
        mono = sum(weight * np.sin(ratio * phase + index * np.sin(2 * phase)) for ratio, weight in zip(settings["mode_ratios"], settings["mode_weights"]))
        lifetime = settings["body_decay_seconds"] * descriptor.get("decay_scale", 1)
        env = (1 - np.exp(-t / .0035)) * np.exp(-t / lifetime)
        env *= np.exp(-np.maximum(0, t - gate) / .045) * np.clip((t[-1] - t) / .012, 0, 1)
        mono = filtered(mono, work_rate, 150, np.interp(brightness, [0, 1], settings["cutoff_hz"]) * descriptor.get("shade", 1)) * env
        mono += noise(rng, len(t), work_rate, 800, 3800) * .022 * env * np.exp(-t / .018)
        output = stereo(mono, descriptor.get("pan_hint", 0), settings["width"], .12 * np.sin(2 * phase + .7) * env)
    elif ident == "veil":
        timeline = note["start"] + t
        color = control(automation, "veil_brightness", timeline, .3)
        level = control(automation, "veil_level", timeline, 1)
        pan = control(automation, "veil_pan", timeline, 0)
        attack = max(.04, descriptor["attack_beats"] * BEAT)
        release = max(.04, descriptor["release_beats"] * BEAT)
        env = .5 - .5 * np.cos(np.pi * np.clip(t / attack, 0, 1))
        env *= .5 + .5 * np.cos(np.pi * np.clip((t - gate) / release, 0, 1))
        env *= .93 + .07 * np.sin(2 * np.pi * t / (BEAT * 16) + descriptor["breath_phase"])
        mono, side = np.zeros(len(t)), np.zeros(len(t))
        for index, (ratio, weight) in enumerate(zip(settings["mode_ratios"], settings["mode_weights"])):
            phase = 2 * np.pi * f0 * ratio * t
            gain = weight * np.exp(-index * (.36 - .27 * color))
            mono += gain * np.sin(phase + index * .19)
            if index:
                motion = settings["phase_motion_radians"] * np.sin(2 * np.pi * t / (BEAT * (19 + index * 3)) + index)
                side += gain * np.sin(phase + index * .81 + motion)
        output = stereo(mono * env, pan, settings["width"], side * env)
        output = filtered(output, rate, settings["highpass_hz"], settings["cutoff_hz"][1])
    elif ident == "field":
        gate_env = envelope(t, gate, descriptor["attack_beats"] * BEAT / 3, 4, .83, 1.05)
        slow = .84 + .16 * np.sin(2 * np.pi * t / (BEAT * 11))
        left = np.zeros(len(t))
        right = np.zeros(len(t))
        for index, (ratio, weight) in enumerate(zip(settings["mode_ratios"], settings["mode_weights"])):
            drift = descriptor["drift_cents"] * np.sin(2 * np.pi * t / (BEAT * (17 + index * 3)))
            phase = np.cumsum(f0 * ratio * 2 ** (drift / 1200)) * 2 * np.pi / rate
            left += weight * np.sin(phase + .23 * index)
            right += weight * np.sin(phase + .23 * index + settings["phase_motion_radians"] * np.sin(t / 3 + index))
        output = np.column_stack((left, right)) * (gate_env * slow)[:, None]
        output += noise(rng, len(t), rate, 350, 2800, channels=2) * (gate_env * .036)[:, None]
    else:
        raise ValueError(f"No instrument exists for {ident}")
    if settings.get("distortion"):
        output = color_distortion(output,work_rate,settings["distortion"],grit)
    gain = settings["amplitude"] * touch * level
    output = (output * (gain[:, None] if np.ndim(gain) else gain)).astype("float32")
    if oversample != 1:
        output = signal.resample_poly(output, 1, oversample, axis=0).astype("float32")
    return output


def space(audio, ident, settings, automation, rate, absolute_start, space_settings, audit=None):
    count = len(audio)
    timeline = absolute_start + np.arange(count) / rate
    low = 160 if ident not in ("hats", "pressure") else 900
    high = {"engine": 1800, "field": 2400, "bend": 3300, "lattice": 4200, "drums": 2800, "hats": 6800, "pressure": 4300, "kick": 2300, "relay": 2200, "veil": 2500}[ident]
    send = control(automation, ident + "_send", timeline, .3).astype("float32")
    feed = filtered(audio, rate, low, high) * send[:, None]
    if settings.get("return_distortion"):
        up = signal.resample_poly(feed,2,1,axis=0).astype("float32")
        upper_timeline = absolute_start+np.arange(len(up))/(2*rate)
        grit = control(automation,ident+"_grit",upper_timeline,.5).astype("float32")
        feed = signal.resample_poly(color_distortion(up,2*rate,settings["return_distortion"],grit),1,2,axis=0)[:count].astype("float32")
    output = audio.copy()
    for index, (beats, gain) in enumerate(zip(settings.get("delay_beats", []), settings.get("delay_gains", []))):
        shift = round(beats * BEAT * rate)
        if shift >= count:
            continue
        echo = feed[:-shift]
        answer = stereo(echo.mean(axis=1), space_settings["echo_pan"] * (1 if index % 2 == 0 else -1))
        output[shift:] += (.72 * answer + .28 * echo[:, ::-1]) * gain
    if settings["room"]:
        room = Reverb(room_size=space_settings["room_size"], damping=space_settings["damping"], wet_level=1.0, dry_level=0.0, width=.76)
        predelay = round(settings.get("predelay_ms", 0) / 1000 * rate)
        if predelay:
            feed = np.pad(feed, ((predelay, 0), (0, 0)))[:count]
        reverberation = room(feed.T, rate).T
        output += reverberation * settings["room"]
    if ident in ("bend", "lattice") and "foreground_activity" in automation:
        activity = control(automation,"foreground_activity",timeline,0).astype("float32")
        amount = control(automation,"form_return_duck",timeline,0).astype("float32")
        output = audio + (output-audio)*(1-amount*activity)[:,None]
    output = polish_return(output, audio, settings.get("space_polish"), rate, timeline, audit)
    if ident == "engine":
        mid = output.mean(axis=1)
        side = filtered((output[:, 0] - output[:, 1]) / 2, rate, 155, 5500)
        output = np.column_stack((mid + side, mid - side))
    return output.astype("float32")


def fingerprint(score, patch):
    physical = {key: {k: v for k, v in value.items() if k != "gain_db"} for key, value in patch["voices"].items()}
    physical["space"] = patch["space"]
    result = hashlib.sha256(json.dumps(physical, sort_keys=True).encode())
    for relative in ["source/performance.json", "source/Umklapp.mid", "source/automation.npz", "source/render.py", "source/mix_dsp.py", "source/engineering.json"]:
        with (ROOT / relative).open("rb") as handle:
            result.update(handle.read())
    return result.hexdigest()


def master_signal(mix, patch, rate):
    output = filtered(mix, rate, patch["master"]["highpass_hz"], 0)
    drive = patch["master"]["saturation_drive"]
    up = signal.resample_poly(output, 2, 1, axis=0)
    up = np.tanh(up * drive) / drive
    return signal.resample_poly(up, 1, 2, axis=0)[:len(mix)].astype("float32")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mix-only", action="store_true", help="Reuse checked float performances; apply current faders and mastering")
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--end", type=float)
    parser.add_argument("--out", type=Path, help="Separate passage output; canonical full performance remains intact")
    args = parser.parse_args()
    score = json.loads((ROOT / "source/performance.json").read_text())
    patch = json.loads((ROOT / "source/patches.json").read_text())
    with np.load(ROOT / "source/automation.npz") as archive:
        automation = {key: archive[key] for key in archive.files}
    played = read_midi(ROOT / "source/Umklapp.mid")
    if max(note["end"] for notes in played.values() for note in notes) > score["duration_seconds"] + .002:
        raise ValueError("The MIDI performance exceeds the declared audio scope; extend the score duration before rendering")
    rate = patch["sample_rate"]
    start = args.start
    end = args.end or score["duration_seconds"]
    if not 0 <= start < end <= score["duration_seconds"] + .001:
        raise ValueError("Passage bounds must fit the composed duration")
    full = start == 0 and args.end is None and args.out is None
    if not full and args.out is None:
        raise ValueError("Passage renders need --out to preserve the full performance")
    folder = args.out or RENDER
    (folder / "work").mkdir(parents=True, exist_ok=True)
    (folder / "stems").mkdir(exist_ok=True)
    frames = round(end * rate) - round(start * rate)
    mix = np.zeros((frames, 2), dtype="float32")
    current_fingerprint = fingerprint(score, patch)
    cache_report = folder / "voice-cache.json"
    if args.mix_only:
        cache = json.loads(cache_report.read_text())
        if cache["fingerprint"] != current_fingerprint or cache["start"] != start or cache["end"] != end:
            raise ValueError("Changed notes, articulation, automation or instruments require a fresh performance")
    duck = np.ones(frames, dtype="float32")
    for note in played["kick"]:
        a = round(note["start"] * rate) - round(start * rate)
        decay = np.arange(round(.40 * rate)) / rate
        shape = np.exp(-decay / .095) * np.clip(decay / .0015, 0, 1)
        left, right = max(0, a), min(frames, a + len(shape))
        if right > left:
            offset = left - a
            duck[left:right] = np.minimum(duck[left:right], 1 - shape[offset:offset + right - left])
    melodic_activity = np.zeros(frames, dtype="float32")
    for ident in ("bend", "lattice"):
        for note in played[ident]:
            a = round(note["start"] * rate) - round(start * rate)
            t = np.arange(round(1.5 * rate)) / rate
            shape = np.exp(-t / .23) * np.clip(t / .008, 0, 1) * min(1, note["velocity"] / 85)
            left, right = max(0, a), min(frames, a + len(shape))
            if right > left:
                offset = left - a
                melodic_activity[left:right] = np.maximum(melodic_activity[left:right], shape[offset:offset + right - left])
    report = []
    for part_index, part in enumerate(score["parts"]):
        ident = part["id"]
        settings = patch["voices"][ident]
        raw_path = folder / "work" / f"{ident}.wav"
        engineering_report = {}
        if args.mix_only:
            audio, cache_rate = sf.read(raw_path, dtype="float32", always_2d=True)
            if cache_rate != rate or len(audio) != frames:
                raise ValueError("Cached voice dimensions changed")
        else:
            audio = np.zeros_like(mix)
            descriptors = {note["id"]: note for note in part["notes"]}
            for index, note in enumerate(played[ident]):
                # Include note and room prehistory when investigating a bounded passage.
                if note["start"] > end or note["end"] < start - 7:
                    continue
                if note["id"] not in descriptors:
                    raise ValueError(f"Missing articulation for MIDI gesture {note['id']}; keep its text ID when editing")
                event = synthesize(ident, note, descriptors[note["id"]], settings, automation, rate, patch["seed"] + part_index * 101003 + index * 37)
                origin = round(note["start"] * rate) - round(start * rate)
                a, b = max(0, origin), min(frames, origin + len(event))
                if b > a:
                    audio[a:b] += event[a - origin:b - origin]
            audio = space(audio, ident, settings, automation, rate, start, patch["space"], engineering_report)
            if settings["duck"]:
                audio *= (1 - settings["duck"] * (1 - duck))[:, None]
            if settings.get("melodic_duck"):
                audio *= (1 - settings["melodic_duck"] * melodic_activity)[:, None]
            audio, voice_report = polish_voice(audio, settings.get("mix_polish", {}), rate, 1-duck)
            engineering_report.update(voice_report)
            absolute = start + np.arange(frames) / rate
            finish = score["duration_seconds"]
            fade = .5 - .5 * np.cos(np.pi * np.clip((finish - absolute) / 2.0, 0, 1))
            audio *= fade[:, None].astype("float32")
            if not np.isfinite(audio).all():
                raise ValueError(f"Non-finite voice: {ident}")
            sf.write(raw_path, audio, rate, subtype="FLOAT")
        audio *= 10 ** (settings["gain_db"] / 20)
        sf.write(folder / "stems" / f"{ident}.wav", audio, rate, subtype="FLOAT")
        mix += audio
        report.append(dict(id=ident, gestures=len(played[ident]), peak=float(abs(audio).max()), rms=float(np.sqrt(np.mean(audio * audio))), gain_db=settings["gain_db"], engineering=engineering_report))
        print("performed", ident, report[-1], flush=True)
    cache_report.write_text(json.dumps(dict(fingerprint=current_fingerprint, start=start, end=end), indent=2) + "\n")
    sf.write(folder / "premaster.wav", mix, rate, subtype="FLOAT")
    bus = master_signal(mix, patch, rate)
    before = integrated_lufs(bus, sample_rate=rate)
    if full:
        if patch["master"]["input_gain_db"] is None:
            patch["master"]["input_gain_db"] = round(patch["master"]["target_lufs"] - before + .12, 3)
            (ROOT / "source/patches.json").write_text(json.dumps(patch, indent=2) + "\n")
        metered = write_master(folder / "Umklapp.wav", bus, sample_rate=rate, target_lufs=patch["master"]["target_lufs"], input_gain_db=patch["master"]["input_gain_db"], ceiling_dbtp=patch["master"]["ceiling_dbtp"], lookahead_ms=patch["master"]["lookahead_ms"], release_ms=patch["master"]["release_ms"], tolerance_lu=.4)
    else:
        gain = 10 ** ((patch["master"]["input_gain_db"] or 0) / 20)
        bus *= min(gain, .86 / max(float(abs(bus).max()), 1e-9))
        sf.write(folder / "passage.wav", bus, rate, subtype="PCM_24")
        metered = {"passage_only": True, "full_master_processing": False}
    report = dict(title=score["title"], edition=score["edition"], sample_rate=rate, frames=frames, start=start, end=end, duration_seconds=frames / rate, voices=report, bus_before_drive_lufs=before, master=metered, source_pcm_used=False, inputs=patch["performance_inputs"], stems="Pre-master contributions, with voice effects and ducking. The sum is premaster.wav, not the limited master.", listening="No auditory perception claimed; awaiting human listening.")
    (folder / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report["master"], indent=2), flush=True)


if __name__ == "__main__":
    main()
