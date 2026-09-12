"""A tuned FM pluck with a resonant body, brief metallic edge and ducked space.

The oscillators are synthesized from equations. No recording, sample slice,
wavetable or external impulse response is used. MIDI CC74 controls harmonic
brightness; CC11 controls expression and CC91 the phrase-end space send.
"""

import numpy as np
from pedalboard import Reverb
from scipy import signal
from scipy.ndimage import uniform_filter1d

import synth_engine as engine
from chord_synth import bandpass, event_duck


def synthesize(part, n, sr, p, beat, kick_part, saw_audio):
    dry = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros_like(dry)
    os = p["oversampling"]
    render_sr = sr * os
    for note in part["notes"]:
        gate = note["end"] - note["start"]
        t = np.arange(round((gate + 7 * p["release_seconds"]) * render_sr)) / render_sr
        absolute = np.asarray([note["start"]])
        brightness = float(engine.interp(part["cc"].get(74), absolute, .5)[0])
        expression = float(engine.expression(part, absolute)[0])
        throw = float(engine.interp(part["cc"].get(91), absolute, .2)[0])
        velocity = note["velocity"]
        f0 = 440 * 2 ** ((note["pitch"] - 69) / 12)
        env = (1 - np.exp(-t / p["attack_seconds"])) * (
            .34 + .66 * np.exp(-t / p["decay_seconds"]))
        env *= np.exp(-np.maximum(0, t - gate) / p["release_seconds"])
        edge = min(len(t), round(.008 * render_sr))
        env[-edge:] *= np.linspace(1, 0, edge)
        index = p["fm_tail_index"] + (p["fm_index_min"] + brightness * p["fm_index_range"]) * (
            .65 + .35 * velocity) * np.exp(-t / p["fm_decay_seconds"])
        voices = []
        for side in [-1, 1]:
            phase = 2 * np.pi * f0 * 2 ** (side * p["detune_cents"] / 1200) * t
            fm = np.sin(phase + index * np.sin(2 * phase))
            # A rapidly decaying, slightly inharmonic edge adds a struck quality;
            # the stable fundamental remains the clear pitch reference.
            edge_wave = np.sin(3.006 * phase) * np.exp(-t / .022)
            body = np.sin(phase) + .16 * np.sin(2 * phase) * np.exp(-t / .10)
            sub = np.sin(phase / 2) * np.exp(-t / .15)
            wave = .54 * body + .46 * fm + p["edge_gain"] * edge_wave + p["sub_body_gain"] * sub
            wave = np.tanh(wave * p["drive"]) / p["drive"]
            voices.append(wave)
        audio = engine.stereo_width(np.stack(voices, axis=1), p["body_width"])
        audio *= (env * velocity ** .88 * expression * p["gain"])[:, None]
        audio = signal.resample_poly(audio, 1, os, axis=0).astype(np.float32)
        engine.add(dry, note["start"], audio, sr)
        engine.add(send, note["start"], audio * (.65 + 1.20 * throw), sr)
    dry = bandpass(dry, p["highpass_hz"], p["lowpass_hz"], sr)
    send = bandpass(send, p["highpass_hz"], p["lowpass_hz"], sr)

    # Reduce only the new voice's overlapping body while the reviewed saw is
    # active. The independent pulse stem and saw audio are left untouched.
    reference = bandpass(saw_audio, 650, 1900, sr)
    rms = np.sqrt(np.maximum(0, uniform_filter1d(np.mean(reference * reference, axis=1),
                                               size=round(.05 * sr))))
    activity = np.clip((rms - .01) / .055, 0, 1)
    b, a = signal.iirpeak(1100, 1.1, fs=sr)
    bell = signal.lfilter(b, a, dry, axis=0).astype(np.float32)
    dry += bell * (10 ** (-activity * p["saw_relief_db"] / 20) - 1)[:, None]
    del reference, rms, bell

    room = Reverb(room_size=.39, damping=.70, wet_level=p["room_wet"],
                  dry_level=0, width=.65)(send.T.copy(), sr).T.copy()
    hall = Reverb(room_size=.73, damping=.68, wet_level=p["hall_wet"],
                  dry_level=0, width=1.0)(send.T.copy(), sr).T.copy()
    room = bandpass(room, 430, 6100, sr)
    hall = bandpass(hall, 550, 5100, sr)
    returns = room.copy()
    shift = round(p["predelay_seconds"] * sr)
    returns[shift:] += hall[:-shift]
    feed = bandpass(send, 640, 4100, sr)
    for delay_beats, gain, flip in [(.75, 1, True), (1.5, .48, False), (2.25, .20, True)]:
        delay = round(delay_beats * beat * sr)
        echo = feed[:-delay, ::-1] if flip else feed[:-delay]
        returns[delay:] += echo * p["delay_gain"] * gain
    onsets = [note["start"] for note in part["notes"]]
    kicks = [note["start"] for note in kick_part["notes"] if note["pitch"] == 36]
    returns = event_duck(returns, onsets, sr, .50, .15)
    returns = event_duck(returns, kicks, sr, .58, .19)
    dry = event_duck(dry, kicks, sr, .22, .13)
    # Finish each phrase's space with a smooth handoff. The first following bar
    # is an existing breath; the other two introduce the approved pulse chords.
    for boundary in p["phrase_end_seconds"]:
        start, stop = round((boundary - .24) * sr), round((boundary + .10) * sr)
        fade = np.cos(np.linspace(0, np.pi / 2, stop - start)) ** 2
        returns[start:stop] *= fade[:, None]
        # There are no new Prism events until the next phrase, so remove the
        # remaining reverb tail within this explicitly scoped gap.
        next_start = min((t for t in onsets if t > boundary + 1), default=n / sr)
        returns[stop:round(next_start * sr)] = 0
    report = {"oscillator": "Tuned 2:1 FM plus sine body and a brief 3.006-ratio edge",
              "oversampling": os, "notes": len(onsets), "source_audio_inputs": [],
              "max_saw_relief_db": float(activity.max() * p["saw_relief_db"]),
              "direct_peak_dbfs": float(20 * np.log10(max(np.max(abs(dry)), 1e-12))),
              "return_peak_dbfs": float(20 * np.log10(max(np.max(abs(returns)), 1e-12)))}
    return (dry + returns).astype(np.float32), dry, returns, report
