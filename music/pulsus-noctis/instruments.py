# SPDX-License-Identifier: AGPL-3.0-only
"""Note-driven instruments; all audio inputs are independent instrument-library samples."""

from functools import lru_cache
from fractions import Fraction
from pathlib import Path
import math
import re
import subprocess

import mido
import numpy as np
import soundfile as sf
from scipy import signal
from pedalboard import Reverb


def stereo(y, pan=0):
    if y.ndim == 1:
        y = y[:, None]
    if y.shape[1] == 1:
        angle = (pan + 1) * np.pi / 4
        return (y * np.array([np.cos(angle), np.sin(angle)])).astype(np.float32)
    return (y * np.array([min(1.0, 1 - pan), min(1.0, 1 + pan)])).astype(np.float32)


def envelope(t, gate, attack, release):
    return np.minimum(t / max(attack, 1e-5), 1) * np.exp(-np.maximum(t - gate, 0) / release)


def synthesized(pitch, duration, patch, sr):
    kind = patch["instrument"]
    tail = patch.get("release", 0.08) * 7
    t = np.arange(round((duration + tail) * sr), dtype=np.float64) / sr
    hz = 440 * 2 ** ((pitch - 69) / 12)
    if kind == "bass":
        phase = 2 * np.pi * hz * t
        coefficients = patch["harmonics"]
        y = sum(a * np.sin((k + 1) * phase) for k, a in enumerate(coefficients))
        y = np.tanh(y * patch.get("drive", 1.1))
        y *= envelope(t, duration, patch["attack"], patch["release"])
    elif kind == "pluck":
        # A saw oscillator and closing low-pass envelope reproduce the retained
        # analog articulation without a Logic export or per-song wavetable.
        cutoff = patch["cutoff_floor"] + patch["cutoff_peak"] * np.exp(-t / patch["filter_decay"])
        y = np.zeros_like(t)
        for k in range(1, min(64, int(sr * 0.43 / hz)) + 1):
            gain = 1 / (k * np.sqrt(1 + (k * hz / cutoff) ** 4))
            y += np.sin(2 * np.pi * k * hz * t) * gain
        y *= envelope(t, duration, patch["attack"], patch["release"]) * (
            0.72 + 0.28 * np.exp(-t / 0.07)
        )
    elif kind == "modal":
        y = sum(
            a * np.sin(2 * np.pi * hz * ratio * t) * np.exp(-t / decay)
            for ratio, a, decay in patch["modes"]
        )
        y *= np.minimum(t / 0.0015, 1)
    elif kind in {"kick", "tom"}:
        ratio = 2 ** ((pitch - patch.get("root_note", pitch)) / 12)
        freq = ratio * (
            patch["fundamental"] + patch["sweep_hz"] * np.exp(-t / patch["sweep_seconds"])
        )
        phase = 2 * np.pi * np.cumsum(freq) / sr
        y = np.sin(phase) * np.exp(-t / patch["decay"])
        if kind == "tom":
            y += 0.22 * np.sin(phase * 1.57) * np.exp(-t / 0.065)
        else:
            y += 0.05 * np.sin(2 * np.pi * 2200 * t) * np.exp(-t / 0.003)
        y = np.tanh(y * patch.get("drive", 1.2)) * np.minimum(t / 0.0008, 1)
    else:
        raise ValueError(kind)
    y[-min(256, len(y)) :] *= np.linspace(1, 0, min(256, len(y)))
    return stereo(y, patch.get("pan", 0))


@lru_cache(maxsize=64)
def library_sample(path, sr):
    p = Path(path).expanduser()
    if p.suffix.lower() == ".caf":
        raw = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(p),
                "-t",
                "1",
                "-ar",
                str(sr),
                "-ac",
                "2",
                "-f",
                "f32le",
                "-",
            ],
            check=True,
            capture_output=True,
        ).stdout
        y = np.frombuffer(raw, dtype="<f4").reshape(-1, 2).copy()
        rate = sr
    else:
        y, rate = sf.read(p, dtype="float32", always_2d=True)
    if rate != sr:
        d = math.gcd(sr, rate)
        y = signal.resample_poly(y, sr // d, rate // d, axis=0).astype(np.float32)
    return y


def percussion_sample(patch, sr):
    y = library_sample(patch["sample"], sr).copy()
    if "crop_seconds" in patch:
        a, b = patch["crop_seconds"]
        y = y[round(a * sr) : round(b * sr)].copy()
        na, nb = round(0.001 * sr), round(0.008 * sr)
        y[:na] *= np.linspace(0, 1, na)[:, None]
        y[-nb:] *= np.linspace(1, 0, nb)[:, None]
    if patch.get("tail_fade_seconds"):
        a, b = [round(x * sr) for x in patch["tail_fade_seconds"]]
        y = y[:b]
        y[a:] *= np.linspace(1, 0, len(y) - a, dtype=np.float32)[:, None]
    return stereo(y, patch.get("pan", 0))


@lru_cache(maxsize=2)
def violin_regions(sfz):
    path = Path(sfz)
    text = path.read_text()
    default = re.search(r"default_path=([^\n]+)", text)[1].strip().replace("\\", "/")
    regions = []
    for block in text.split("<region>")[1:]:
        values = dict(
            re.findall(r"(sample|lokey|hikey|pitch_keycenter|volume|tune)=([^\n]+)", block)
        )
        if "sample" not in values:
            continue
        regions.append(
            (
                int(values["pitch_keycenter"]),
                int(values["lokey"]),
                int(values["hikey"]),
                float(values.get("tune", 0)),
                path.parent / default / values["sample"].strip(),
            )
        )
    return regions


def violin(pitch, duration, patch, sr, repo):
    regions = violin_regions(str(repo / patch["sfz"]))
    key, _, _, tune, path = next(
        (r for r in regions if r[1] <= pitch <= r[2]),
        min(regions, key=lambda item: abs(item[0] - pitch)),
    )
    sample = library_sample(str(path), sr)
    ratio = Fraction(2 ** ((key - pitch - tune / 100) / 12)).limit_denominator(2048)
    sample = signal.resample_poly(sample, ratio.numerator, ratio.denominator, axis=0).astype(
        np.float32
    )
    length = round((duration + patch["release"] * 5) * sr)
    if length > len(sample):
        # A crossfaded sustain loop is an instrument behavior, not song sampling.
        overlap = round(0.12 * sr)
        body = sample[round(0.7 * sr) : max(round(0.9 * sr), len(sample) - round(0.25 * sr))]
        while len(sample) < length:
            fade = np.linspace(0, 1, overlap, dtype=np.float32)[:, None]
            sample[-overlap:] = sample[-overlap:] * (1 - fade) + body[:overlap] * fade
            sample = np.concatenate((sample, body[overlap:]))
    sample = sample[:length]
    t = np.arange(len(sample)) / sr
    env = envelope(t, duration, patch["attack"], patch["release"])
    sample *= env[:, None]
    return stereo(sample, patch.get("pan", 0))


def piano(track, conductor, ppq, patch, sr, frames, repo, work):
    projected = mido.MidiFile(type=1, ticks_per_beat=ppq)
    projected.tracks.append(conductor.copy())
    tr = mido.MidiTrack()
    pending = 0
    for event in track:
        pending += event.time
        if event.type == "control_change" and event.control == 11:
            continue
        changes = {"time": pending}
        if hasattr(event, "channel"):
            changes["channel"] = 0
        tr.append(event.copy(**changes))
        pending = 0
    projected.tracks.append(tr)
    midi = work / f"{track.name[:2]}-piano.mid"
    wav = work / f"{track.name[:2]}-piano.wav"
    projected.save(midi)
    subprocess.run(
        [
            "fluidsynth",
            "-ni",
            "-r",
            str(sr),
            "-g",
            str(patch["engine_gain"]),
            "-R",
            "0",
            "-C",
            "0",
            "-o",
            "synth.polyphony=256",
            "-T",
            "wav",
            "-O",
            "float",
            "-F",
            str(wav),
            str(repo / patch["soundfont"]),
            str(midi),
        ],
        check=True,
        capture_output=True,
    )
    y, rate = sf.read(wav, dtype="float32", always_2d=True)
    if rate != sr:
        raise ValueError("Unexpected piano rate")
    y = np.pad(y[:frames], ((0, max(0, frames - len(y))), (0, 0)))
    midi.unlink()
    wav.unlink()
    return y


def finish(y, patch, sr):
    if patch.get("highpass", 0) > 0:
        y = signal.sosfilt(
            signal.butter(2, patch["highpass"], fs=sr, btype="highpass", output="sos"), y, axis=0
        ).astype(np.float32)
    if patch.get("lowpass", 0) > 0:
        y = signal.sosfilt(
            signal.butter(2, patch["lowpass"], fs=sr, btype="lowpass", output="sos"), y, axis=0
        ).astype(np.float32)
    wet = patch.get("reverb", 0)
    if wet:
        y = Reverb(
            room_size=patch.get("room", 0.45), damping=0.55, wet_level=wet, dry_level=1, width=0.85
        )(y.T.copy(), sr).T.copy()
    delay = patch.get("delay_seconds", 0)
    if delay:
        n = round(delay * sr)
        dry = y.copy()
        for k in [1, 2, 3]:
            y[k * n :] += dry[: -k * n, ::-1] * patch["delay_gain"] ** k
    return y
