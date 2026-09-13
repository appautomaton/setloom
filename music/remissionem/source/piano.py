"""Accepted Salamander performance and processing, with explicit render paths."""

import subprocess
import numpy as np
import soundfile as sf
from scipy import signal
from pedalboard import Reverb
import synth_engine as engine

def db(x):
    return float(20 * np.log10(max(float(x), 1e-12)))

def render(patch, n, sr, midi_path, repo, work):
    raw_path = work / "piano-engine.wav"
    soundfont = repo / patch["soundfont"]
    command = [patch["fluidsynth"], "-ni", "-r", "48000", "-g", str(patch["engine_gain"]),
               "-R", "0", "-C", "0", "-o", "synth.polyphony=256", "-T", "wav", "-O", "float",
               "-F", str(raw_path), str(soundfont), str(midi_path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    (work / "piano-engine.log").write_text(result.stdout + result.stderr)
    y, sample_rate = sf.read(raw_path, dtype="float32", always_2d=True)
    raw_peak = float(np.max(abs(y)))
    if sample_rate != 48000 or not np.isfinite(y).all():
        raise ValueError("Unexpected piano engine output")
    y = signal.resample_poly(y, 147, 160, axis=0).astype(np.float32)[:n]
    if len(y) < n:
        y = np.pad(y, ((0, n - len(y)), (0, 0)))
    y = signal.sosfilt(signal.butter(2, [patch["highpass_hz"], patch["lowpass_hz"]],
                                   fs=sr, btype="bandpass", output="sos"), y, axis=0).astype(np.float32)
    y = engine.stereo_width(y, patch["width"]) * 10 ** (patch["bus_gain_db"] / 20)
    dry = y.copy()
    predelay = round(patch["predelay_seconds"] * sr)
    wet = Reverb(room_size=patch["reverb_room"], damping=patch["reverb_damping"],
                 wet_level=patch["reverb_wet"], dry_level=0, width=0.85)(dry.T.copy(), sr).T.copy()
    wet = signal.sosfilt(signal.butter(2, [280, 6200], fs=sr, btype="bandpass", output="sos"),
                         wet, axis=0).astype(np.float32)
    y[predelay:] += wet[:-predelay]
    echo = signal.sosfilt(signal.butter(2, [450, 4700], fs=sr, btype="bandpass", output="sos"),
                          dry, axis=0).astype(np.float32)
    delay = round(.75 * 60 / 140 * sr)
    y[delay:] += echo[:-delay, ::-1] * patch["delay_gain"]
    automation = patch.get("mix_gain_automation", [])
    if automation:
        points = np.asarray([(point["seconds"], point["db"]) for point in automation])
        gain = np.interp(np.arange(n) / sr, points[:, 0], points[:, 1])
        y *= (10 ** (gain / 20))[:, None]
    raw_path.unlink()
    return y, {"command": command, "engine_peak_dbfs": db(raw_peak),
               "engine_clipped": raw_peak >= 1,
               "sample_source": patch["soundfont"], "credit": patch["credit"],
               "license": patch["license"]}
