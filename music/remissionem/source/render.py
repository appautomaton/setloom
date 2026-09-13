# SPDX-License-Identifier: AGPL-3.0-only
"""Perform all Remissionem parts from retained MIDI and instrument settings."""

import argparse
import json
from pathlib import Path
import tempfile

import mido
import numpy as np

from setloom.audio import integrated_lufs, mono_below, write_audio, write_master
import synth_engine as engine
import chord_synth
import prism_synth
import chimes
import piano

HERE = Path(__file__).resolve().parent
REPO = next(p for p in HERE.parents if (p / "pyproject.toml").exists())


def duck(audio, kicks, sr, depth):
    for note in kicks:
        if note["pitch"] != 36:
            continue
        start = round(note["start"] * sr)
        stop = min(len(audio), start + round(0.16 * sr))
        t = np.arange(stop - start) / sr
        dip = np.interp(t, [0, 0.008, 0.040, 0.16], [0, depth, depth * 0.85, 0])
        audio[start:stop] *= (1 - dip)[:, None]
    return audio


def isolated_midi(full, name, destination):
    track = next(t for t in full.tracks if t.name == name)
    result = mido.MidiFile(type=1, ticks_per_beat=full.ticks_per_beat)
    result.tracks = [full.tracks[0], track]
    result.save(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=REPO / "tmp/remissionem")
    parser.add_argument(
        "--keep-premaster",
        action="store_true",
        help="Retain the mix before mastering for level revisions.",
    )
    args = parser.parse_args()
    out = args.out_dir.resolve()
    roots = [REPO / "tmp", Path(tempfile.gettempdir()), Path("/tmp")]
    if (
        not any(out.is_relative_to(p.resolve()) for p in roots)
        or out == HERE
        or HERE in out.parents
    ):
        raise ValueError("Choose a scratch output directory outside production source.")
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError("Choose an empty output directory.")
    score = json.loads((HERE / "performance.json").read_text())
    patch = json.loads((HERE / "patch.json").read_text())
    if score.get("audio_tracks"):
        raise ValueError("Song-recording audio is not a performance input.")
    full = mido.MidiFile(HERE / "performance.mid")
    parts, beat = engine.read_midi(HERE / "performance.mid")
    sr = patch["sample_rate"]
    n = round(score["duration_seconds"] * sr)
    total = np.zeros((n, 2), np.float32)
    saw = None
    stats = {}
    descriptors = [p for p in score["tracks"] if p["name"] != "Veil chimes"]
    descriptors += [next(p for p in score["tracks"] if p["name"] == "Veil chimes")]
    if set(parts) != {p["name"] for p in descriptors}:
        raise ValueError("MIDI and instrument assignments differ.")
    with tempfile.TemporaryDirectory(prefix="render-work-", dir=out) as directory:
        work = Path(directory)
        for descriptor in descriptors:
            name, kind = descriptor["name"], descriptor["instrument"]
            part = parts[name]
            p = patch[kind]
            if kind in ["sub", "pulse", "formant"]:
                y = engine.bass(part, n, sr, p, kind)
            elif kind == "arp":
                y = engine.lead(part, n, sr, p, kind, beat)
            elif kind in ["kick", "hat", "snare", "percussion"]:
                y = engine.drums(part, n, sr, p, kind)
            elif kind in ["downshift", "riser"]:
                y = engine.effects(part, n, sr, p, kind)
            elif kind == "piano":
                midi_path = work / "grand-piano.mid"
                isolated_midi(full, name, midi_path)
                y, _ = piano.render(p, n, sr, midi_path, REPO, work)
            elif kind in ["stab", "prism"]:
                if saw is None:
                    raise ValueError("Render the saw before its complementary synth voices.")
                synth = chord_synth if kind == "stab" else prism_synth
                y, direct, returns, _ = synth.synthesize(part, n, sr, p, beat, parts["Kick"], saw)
                del direct, returns
            elif kind == "chimes":
                voice_n = round(14 * sr)
                voice, direct, returns, _, _ = chimes.synthesize(
                    part, voice_n, sr, p, beat, parts["Kick"]["notes"]
                )
                start, stop = [round(t * sr) for t in p["presence_window_seconds"]]
                gain = p["target_presence_lufs"] - integrated_lufs(
                    voice[start:stop], sample_rate=sr
                )
                voice *= 10 ** (gain / 20)
                y = np.zeros((n, 2), np.float32)
                y[:voice_n] = voice
                del voice, direct, returns
            else:
                raise ValueError(f"Unknown instrument: {kind}")
            if kind in ["arp", "piano"]:
                y = duck(y, parts["Kick"]["notes"], sr, 0.32 if kind == "arp" else 0.18)
            if kind != "chimes":
                y[: round(0.003 * sr)] *= np.linspace(0, 1, round(0.003 * sr))[:, None]
                y[-round(0.20 * sr) :] *= np.linspace(1, 0, round(0.20 * sr))[:, None]
            if y.shape != (n, 2) or not np.isfinite(y).all():
                raise ValueError(f"Invalid audio: {name}")
            if kind == "arp":
                saw = y.copy()
            total += y
            stats[name] = {
                "notes": len(part["notes"]),
                "peak_dbfs": float(20 * np.log10(max(float(abs(y).max()), 1e-12))),
            }
            print(f"{name}: performed {len(part['notes'])} notes", flush=True)
    total = mono_below(total, patch["mix"]["mono_below_hz"], sample_rate=sr)
    total[: round(0.004 * sr)] *= np.linspace(0, 1, round(0.004 * sr))[:, None]
    total[-round(0.05 * sr) :] *= np.linspace(1, 0, round(0.05 * sr))[:, None]
    if args.keep_premaster:
        write_audio(out / "premaster.wav", total, sample_rate=sr, subtype="FLOAT")
    print("Premaster LUFS:", integrated_lufs(total, sample_rate=sr), flush=True)
    report = {
        "parts": stats,
        "sample_rate": sr,
        "frames": n,
        "duration_seconds": n / sr,
        "mastering": write_master(
            out / "Remissionem (Setloom Remix).wav", total, sample_rate=sr, **patch["mastering"]
        ),
    }
    (out / "render.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["mastering"], indent=2), flush=True)


if __name__ == "__main__":
    main()
