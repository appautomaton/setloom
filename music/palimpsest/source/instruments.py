# SPDX-License-Identifier: AGPL-3.0-only
"""Palimpsest instruments: a coherent ground with authored rhythmic, resonant and diffuse detail."""

from __future__ import annotations

import numpy as np
from scipy import signal


def finish(audio: np.ndarray, rate: int, fade_s: float = 0.025) -> np.ndarray:
    audio = audio - np.mean(audio)
    count = min(round(fade_s * rate), len(audio) // 3)
    audio[-count:] *= np.linspace(1, 0, count)
    audio[:min(40, len(audio))] *= np.linspace(0, 1, min(40, len(audio)))
    return audio.astype(np.float32)


def kick(patch: dict, rate: int, rng: np.random.Generator) -> np.ndarray:
    """Keep the reviewed kick excitation and articulation unchanged."""
    t = np.arange(round(patch["length_s"] * rate), dtype=np.float64) / rate
    phase = 2*np.pi * (patch["end_hz"]*t + patch["sweep_hz"]*patch["sweep_s"]
                       * (1 - np.exp(-t/patch["sweep_s"])))
    body = np.sin(phase)*(1-np.exp(-t/0.0008))*np.exp(-t/patch["body_decay_s"])
    body = np.tanh(patch["drive"]*body)/np.tanh(patch["drive"])
    noise = rng.normal(size=len(t))
    sos = signal.butter(2, [700, patch["contact_hz"]], btype="bandpass", fs=rate, output="sos")
    contact = signal.sosfilt(sos, noise)*np.exp(-t/0.004)
    contact *= (1-np.exp(-t/0.0003))*patch["contact"]
    mono = finish(body+contact, rate)
    return np.column_stack((mono, mono))


def note_hz(note: int) -> float:
    return 440 * 2**((note-69)/12)


def ground(note: int, patch: dict, t: np.ndarray) -> np.ndarray:
    phase = 2*np.pi*note_hz(note)*t
    mono = (np.sin(phase) + patch["second_partial"]*np.sin(2*phase)
            + patch["third_partial"]*np.sin(3*phase))*patch["level"]
    return np.column_stack((mono, mono)).astype(np.float32)


def bass_space(t: np.ndarray, beat_s: float, patch: dict, kick_beats: list) -> np.ndarray:
    """Make space for actual kick arrivals, including the sparse final gestures."""
    floor, hold, recovery = patch["duck_floor"], patch["hold_s"], patch["recover_s"]
    rate = round(1/(t[1]-t[0]))
    lookahead = patch["lookahead_s"]
    envelope = np.ones(len(t),dtype=np.float32)
    for beat in kick_beats:
        origin = beat*beat_s
        start = max(0,round((origin-lookahead)*rate))
        stop = min(len(t),round((origin+hold+recovery)*rate))
        elapsed = t[start:stop]-origin
        rise = np.clip((elapsed-hold)/recovery,0,1)
        contour = floor+(1-floor)*(.5-.5*np.cos(np.pi*rise))
        falling = np.clip((elapsed+lookahead)/lookahead,0,1)
        contour = np.where(elapsed<0,1-(1-floor)*(.5-.5*np.cos(np.pi*falling)),contour)
        envelope[start:stop] = np.minimum(envelope[start:stop],contour)
    return envelope


def held_voice(event: dict, patch: dict, rate: int, beat_s: float, colour_points: list) -> np.ndarray:
    """A voiced harmonic ensemble breathes through the form and releases across changes."""
    gate = event["gate_beats"]*beat_s
    t = np.arange(round((gate+patch["release_s"])*rate))/rate
    origin = event["beat"]*beat_s
    absolute = t+origin
    base = note_hz(event["note"])
    points = np.asarray(colour_points)
    colour = np.interp(absolute/(beat_s*4),points[:,0],points[:,1])
    colour = np.clip(colour+.065*np.sin(2*np.pi*absolute/patch["spectral_motion_period_s"]
                                      +event["note"]*.19),0,1)
    cutoff = patch["cutoff_hz"][0]+np.diff(patch["cutoff_hz"])[0]*colour
    entrance = np.clip(t/patch["attack_s"], 0, 1)
    release = np.clip((t-gate)/patch["release_s"],0,1)
    envelope = .5*(1-np.cos(np.pi*entrance)) * .5*(1+np.cos(np.pi*release))
    result = np.zeros((len(t), 2), dtype=np.float32)
    for index,(cents,weight,pan) in enumerate(patch["oscillators"]):
        frequency = base*2**(cents/1200)
        period = patch["drift_periods_s"][index]
        omega = 2*np.pi/period
        phase_offset = event["note"]*.13+index*.71
        drift_hz = frequency*(2**(patch["drift_cents"]/1200)-1)*(1 if index else .2)
        phase = (2*np.pi*frequency*t+phase_offset
                 +2*np.pi*drift_hz/omega*(np.cos(omega*origin+phase_offset)
                                        -np.cos(omega*absolute+phase_offset)))
        voice = np.zeros(len(t),dtype=np.float64)
        for harmonic,strength in patch["partials"]:
            spectral_weight = 1/np.sqrt(1+(harmonic*frequency/cutoff)**4)
            voice += np.sin(harmonic*phase)*strength*spectral_weight
        voice = signal.sosfilt(signal.butter(2,patch["highpass_hz"],btype="highpass",fs=rate,output="sos"),voice)
        voice *= envelope*patch["level"]*event["velocity"]/127*weight
        result[:,0] += (voice*np.cos((pan+1)*np.pi/4)).astype(np.float32)
        result[:,1] += (voice*np.sin((pan+1)*np.pi/4)).astype(np.float32)
    return result


def pulse(event: dict, patch: dict, rate: int, beat_s: float) -> np.ndarray:
    gate = event["gate_beats"]*beat_s
    t = np.arange(round((gate+7*patch["release_s"])*rate))/rate
    frequency = note_hz(event["note"])
    touch = patch["velocity_brightness_floor"]+(1-patch["velocity_brightness_floor"])*min(event["velocity"]/84,1)
    cutoff = patch["tail_hz"]+(patch["brightness_hz"]*event["colour"]*touch-patch["tail_hz"])*np.exp(-t/0.12)
    mono = np.zeros_like(t)
    for harmonic in range(1, 9):
        level = 1/harmonic**1.8 / np.sqrt(1+(harmonic*frequency/cutoff)**4)
        mono += level*np.sin(2*np.pi*harmonic*frequency*t)
    decay = patch["decay_s"]+gate*patch["gate_decay_scale"]
    envelope = (1-np.exp(-t/patch["attack_s"]))*np.exp(-t/decay)
    envelope *= np.exp(-np.maximum(t-gate, 0)/patch["release_s"])
    mono = np.tanh(patch["drive"]*mono)/patch["drive"]
    mono = finish(mono*envelope*patch["level"]*event["velocity"]/127, rate)
    pan = patch["pan"]
    return np.column_stack((mono*np.cos((pan+1)*np.pi/4), mono*np.sin((pan+1)*np.pi/4)))


def harmony_clearance(event: dict, patch: dict, rate: int) -> np.ndarray:
    """At a theme attack, briefly lower the backdrop by at most the stated dB depth."""
    t = np.arange(round(7*patch["clearance_release_s"]*rate))/rate
    depth = (1-10**(-patch["harmony_clearance_db"]/20))*min(event["velocity"]/84,1)
    return (depth*(1-np.exp(-t/patch["clearance_attack_s"]))
            *np.exp(-t/patch["clearance_release_s"])).astype(np.float32)


def grain(event: dict, patch: dict, rate: int, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(round(patch["length_s"]*rate))/rate
    shared = rng.normal(size=(len(t), 1))
    side = rng.normal(size=(len(t), 2))
    noise = shared+patch["width"]*side
    sos = signal.butter(2, [patch["highpass_hz"], patch["lowpass_hz"]],
                        btype="bandpass", fs=rate, output="sos")
    noise = signal.sosfilt(sos, noise, axis=0)
    envelope = (1-np.exp(-t/patch["attack_s"]))*np.exp(-t/patch["decay_s"])
    result = noise*envelope[:, None]*patch["level"]*event["velocity"]/127
    for channel in range(2): result[:, channel] = finish(result[:, channel], rate, .015)
    return result.astype(np.float32)


def percussion(event: dict, patch: dict, rate: int, rng: np.random.Generator) -> np.ndarray:
    """A short resonant strike and a softer brush occupy different parts of one cell."""
    t = np.arange(round(patch["length_s"]*rate))/rate
    brushed = event["articulation"] == 1
    frequency = patch["body_hz"]*(1.33 if brushed else 1)
    decay = patch["brush_decay_s"] if brushed else patch["body_decay_s"]
    body = (np.sin(2*np.pi*frequency*t)*np.exp(-t/decay)
            + .28*np.sin(2*np.pi*frequency*1.51*t)*np.exp(-t/(decay*.6)))
    noise = signal.sosfilt(signal.butter(
        2, [patch["highpass_hz"],patch["lowpass_hz"]], btype="bandpass", fs=rate, output="sos"),
        rng.normal(size=len(t)))
    envelope = (1-np.exp(-t/.0007))*np.exp(-t/.018)
    excitation = noise*envelope*patch["noise_amount"]*(2 if brushed else 1)
    mono = finish((body*(.45 if brushed else 1)+excitation)
                  *patch["level"]*event["velocity"]/127, rate, .018)
    pan = (event["pan"]+1)*np.pi/4
    return np.column_stack((mono*np.cos(pan),mono*np.sin(pan))).astype(np.float32)


def inner(event: dict, patch: dict, rate: int, beat_s: float) -> np.ndarray:
    """A voiced resonant arrival with a changing spectrum, rather than another lead line."""
    gate = event["gate_beats"]*beat_s
    t = np.arange(round((gate+7*patch["release_s"])*rate))/rate
    base = note_hz(event["note"])
    entrance = 1-np.exp(-t/patch["attack_s"])
    envelope = entrance*np.exp(-t/patch["decay_s"])
    envelope *= np.exp(-np.maximum(t-gate,0)/patch["release_s"])
    index = patch["fm_depth"]*event["colour"]*np.exp(-t/.11)
    result = np.zeros((len(t),2),dtype=np.float32)
    for channel, sign in [(0,-1),(1,1)]:
        frequency = base*2**(sign*patch["detune_cents"]/1200)
        modulation = index*np.sin(2*np.pi*frequency*patch["fm_ratio"]*t)
        tone = np.sin(2*np.pi*frequency*t+modulation+sign*patch["width"])
        tone += .13*np.sin(2*np.pi*frequency*2*t)*np.exp(-t/.12)
        tone = signal.sosfilt(signal.butter(
            2,[patch["highpass_hz"],patch["lowpass_hz"]],btype="bandpass",fs=rate,output="sos"),tone)
        gain = np.cos((event["pan"]+1)*np.pi/4) if channel==0 else np.sin((event["pan"]+1)*np.pi/4)
        result[:,channel] = finish(tone*envelope*patch["level"]*event["velocity"]/127*gain,rate)
    return result


def veil(event: dict, patch: dict, rate: int, beat_s: float, rng: np.random.Generator) -> np.ndarray:
    """Moving upper partials and breath sustain behind the gestures; no new melody is generated."""
    gate = event["gate_beats"]*beat_s
    t = np.arange(round(gate*rate))/rate
    absolute = t+event["beat"]*beat_s
    attack = np.clip(t/patch["attack_s"],0,1)
    release = np.clip((gate-t)/patch["release_s"],0,1)
    envelope = .5*(1-np.cos(np.pi*attack))*.5*(1-np.cos(np.pi*release))
    base = note_hz(event["note"])
    result = np.zeros((len(t),2),dtype=np.float32)
    for channel, sign in [(0,-1),(1,1)]:
        frequency = base*2**(sign*patch["detune_cents"]/1200)
        colour = .5+.5*np.sin(2*np.pi*absolute/patch["motion_periods_s"][channel]+sign*.7)
        tone = np.zeros(len(t),dtype=np.float64)
        for harmonic, level in [(2,.4),(3,.24),(4,.13),(5,.09),(6,.04)]:
            focus = np.exp(-.35*(harmonic-(2.3+colour*2.8))**2)
            tone += np.sin(2*np.pi*frequency*harmonic*t+sign*patch["width"]*harmonic)*level*focus
        noise = signal.sosfilt(signal.butter(
            2,[patch["highpass_hz"],patch["lowpass_hz"]],btype="bandpass",fs=rate,output="sos"),
            rng.normal(size=len(t)))
        motion = .72+.28*np.sin(2*np.pi*absolute/17.3+event["note"]*.13+sign*.5)
        breath = noise*patch["noise_level"]*motion
        combined = signal.sosfilt(signal.butter(2,patch["highpass_hz"],btype="highpass",fs=rate,output="sos"),
                                  tone+breath)
        result[:,channel] = combined*patch["level"]*event["velocity"]/127*envelope
    return result


def add_wrapped(target: np.ndarray, gesture: np.ndarray, start: int) -> None:
    cursor = 0
    while cursor < len(gesture):
        position = (start+cursor) % len(target)
        size = min(len(gesture)-cursor, len(target)-position)
        target[position:position+size] += gesture[cursor:cursor+size]
        cursor += size


def add_gesture(target: np.ndarray, gesture: np.ndarray, start: int) -> None:
    """A full-song performance carries tails forward without wrapping its ending."""
    size = min(len(gesture), len(target)-start)
    if size > 0:
        target[start:start+size] += gesture[:size]


def room(audio: np.ndarray, patch: dict, rate: int, rng: np.random.Generator) -> np.ndarray:
    """Early reflections locate the sound; a filtered diffuse response carries its tail."""
    count = round(patch["length_s"]*rate)
    t = np.arange(count)/rate
    start = patch["predelay_s"]
    envelope = np.where(t>=start, np.exp(-np.maximum(t-start, 0)/patch["decay_s"]), 0)
    shared = rng.normal(size=(count, 1))
    stereo = shared+patch["width"]*rng.normal(size=(count, 2))
    impulse = stereo*envelope[:, None]
    impulse *= np.minimum(np.maximum(t-start, 0)/0.012, 1)[:, None]
    impulse[-round(.015*rate):] *= np.linspace(1, 0, round(.015*rate))[:, None]
    impulse = signal.sosfilt(signal.butter(
        2, [patch["highpass_hz"], patch["lowpass_hz"]], btype="bandpass", fs=rate, output="sos"),
        impulse, axis=0)
    impulse *= patch["diffuse_level"]/np.sqrt(np.sum(impulse**2,axis=0,keepdims=True))
    for delay,gain,pan in patch["reflection_taps_s"]:
        position = round(delay*rate)
        impulse[position,0] += gain*np.cos((pan+1)*np.pi/4)
        impulse[position,1] += gain*np.sin((pan+1)*np.pi/4)
    from scipy.fft import next_fast_len, rfft, irfft
    size = next_fast_len(len(audio)+len(impulse)-1)
    transformed = rfft(audio, n=size, axis=0)*rfft(impulse, n=size, axis=0)
    return irfft(transformed, n=size, axis=0)[:len(audio)].astype(np.float32)
