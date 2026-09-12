"""Band-limited pulse chords with intentional articulation and separate depth returns."""

import numpy as np
from pedalboard import Reverb
from scipy import signal
from scipy.ndimage import uniform_filter1d

import synth_engine as engine


def bandpass(y, lo, hi, sr):
    return signal.sosfilt(signal.butter(2, [lo, hi], fs=sr, btype="bandpass", output="sos"),
                          y, axis=0).astype(np.float32)


def event_duck(audio, onsets, sr, depth, duration=.16):
    gain = np.ones(len(audio), dtype=np.float32)
    for start_seconds in sorted(set(round(t, 6) for t in onsets)):
        start = max(0, round(start_seconds * sr))
        stop = min(len(audio), start + round(duration * sr))
        t = np.arange(stop - start) / sr
        dip = np.interp(t, [0, .007, .034, duration], [0, depth, depth*.9, 0])
        gain[start:stop] = np.minimum(gain[start:stop], 1-dip)
    return audio * gain[:, None]


def synthesize(part, n, sr, p, beat, kick_part, saw_audio):
    dry = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros_like(dry)
    oversampling = p["oversampling"]
    render_sr = sr * oversampling
    for index, note in enumerate(part["notes"]):
        gate = note["end"] - note["start"]
        length = gate + 5*p["release_seconds"]
        t = np.arange(round(length*render_sr)) / render_sr
        f0 = 440 * 2 ** ((note["pitch"]-69)/12)
        control_t = np.asarray([note["start"]])
        brightness = float(engine.interp(part["cc"].get(74), control_t, .5)[0])
        expression = float(engine.expression(part, control_t)[0])
        space_send = float(engine.interp(part["cc"].get(91), control_t, .26)[0])
        cutoff_start = p["cutoff_closed_hz"] * (p["cutoff_open_hz"]/p["cutoff_closed_hz"])**brightness
        cutoff = cutoff_start * (p["cutoff_tail_ratio"] +
                                 (1-p["cutoff_tail_ratio"])*np.exp(-t/p["filter_decay_seconds"]))
        env = (1-np.exp(-t/p["attack_seconds"])) * (p["sustain"] +
               (1-p["sustain"])*np.exp(-t/p["decay_seconds"]))
        env *= np.exp(-np.maximum(0, t-gate)/p["release_seconds"])
        env[-round(.006*render_sr):] *= np.linspace(1, 0, round(.006*render_sr))
        voices = []
        for side in [-1, 1]:
            f = f0 * 2**(side*p["detune_cents"]/1200)
            phase = 2*np.pi*f*t + .07*index + side*.16
            duty = p["pulse_width"] + p["pulse_width_motion"]*np.sin(
                2*np.pi*.19*(note["start"]+t)+side*.2)
            wave = np.zeros(len(t))
            for h in range(1, min(65, int(sr*.43/f)+1)):
                # Pulse and triangle Fourier coefficients. No saw oscillator,
                # source recording, sampled waveform, or original impulse response.
                pulse = 2*np.sin(np.pi*h*duty)/(np.pi*h)
                triangle = (8/np.pi**2)*(-1)**((h-1)//2)/h**2 if h % 2 else 0
                attenuation = 1/np.sqrt(1+(h*f/cutoff)**4)
                # A centered rectangular pulse has cosine-series coefficients;
                # the triangle component uses its separate sine series.
                harmonic = ((1-p["triangle_mix"])*pulse*np.cos(h*phase) +
                            p["triangle_mix"]*triangle*np.sin(h*phase))
                wave += harmonic*attenuation
            wave = np.tanh(wave*p["drive"])/np.tanh(p["drive"])
            voices.append(wave)
        y = engine.stereo_width(np.stack(voices, axis=1), p["body_width"])
        y *= (env * note["velocity"] * expression * p["gain"])[:, None]
        y = signal.resample_poly(y, 1, oversampling, axis=0).astype(np.float32)
        engine.add(dry, note["start"], y, sr)
        engine.add(send, note["start"], y*(.65+1.45*space_send), sr)
    dry = signal.sosfilt(signal.butter(2, p["highpass_hz"], fs=sr, btype="highpass", output="sos"),
                          dry, axis=0).astype(np.float32)
    send = signal.sosfilt(signal.butter(2, p["highpass_hz"], fs=sr, btype="highpass", output="sos"),
                           send, axis=0).astype(np.float32)

    # A keyed midrange bell gives the already-liked saw precedence only while
    # it is sounding. The saw itself is not retuned, filtered, or revoiced here.
    low, high = p["saw_mask_band_hz"]
    reference_band = bandpass(saw_audio, low, high, sr)
    power = np.mean(reference_band*reference_band, axis=1)
    envelope = np.sqrt(np.maximum(0, uniform_filter1d(power, size=round(.09*sr))))
    activity = np.clip((envelope-.014)/.05, 0, 1)
    cut = 10**(-activity*p["saw_mask_relief_db"]/20)-1
    center = np.sqrt(low*high)
    b, a = signal.iirpeak(center, center/(high-low), fs=sr)
    bell = signal.lfilter(b, a, dry, axis=0).astype(np.float32)
    dry += bell*cut[:, None]

    room = Reverb(room_size=p["room_size"], damping=.67, wet_level=p["room_wet"],
                  dry_level=0, width=.65)(send.T.copy(), sr).T.copy()
    room = bandpass(room, 380, 6500, sr)
    air = Reverb(room_size=p["air_room_size"], damping=p["air_damping"], wet_level=p["air_wet"],
                 dry_level=0, width=1.0)(send.T.copy(), sr).T.copy()
    air = bandpass(air, p["return_lowcut_hz"], p["return_highcut_hz"], sr)
    delayed_air = np.zeros_like(air)
    predelay = round(p["air_predelay_seconds"]*sr)
    delayed_air[predelay:] = air[:-predelay]
    del air

    filtered_send = bandpass(send, p["delay_lowcut_hz"], p["delay_highcut_hz"], sr)
    echoes = np.zeros_like(dry)
    for beats, level, swap in [(.75, p["delay_gain"], True),
                                (1.5, p["delay_gain"]*.57, False),
                                (2.25, p["delay_gain"]*.24, True)]:
        delay = round(beats*beat*sr)
        feed = filtered_send[:-delay, ::-1] if swap else filtered_send[:-delay]
        echoes[delay:] += feed*level

    onsets = [note["start"] for note in part["notes"]]
    kick_onsets = [note["start"] for note in kick_part["notes"] if note["pitch"] == 36]
    returns = (room+delayed_air+echoes).astype(np.float32)
    returns = event_duck(returns, onsets, sr, 1-10**(-p["self_return_duck_db"]/20), .17)
    returns = event_duck(returns, kick_onsets, sr, p["return_kick_duck_depth"], .20)
    dry = event_duck(dry, kick_onsets, sr, p["kick_duck_depth"], .15)
    stats = {"unique_chord_attacks": len(set(round(t, 5) for t in onsets)),
             "max_saw_keyed_mid_cut_db": float(np.max(activity)*p["saw_mask_relief_db"]),
             "direct_rms_dbfs": float(20*np.log10(max(float(np.sqrt(np.mean(dry*dry))), 1e-12))),
             "return_rms_dbfs": float(20*np.log10(max(float(np.sqrt(np.mean(returns*returns))), 1e-12))),
             "source_audio_inputs": [], "oscillator": "Band-limited pulse plus triangle; 2x nonlinear oversampling"}
    return (dry+returns).astype(np.float32), dry, returns, stats
