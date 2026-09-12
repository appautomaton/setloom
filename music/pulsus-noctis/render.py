# SPDX-License-Identifier: AGPL-3.0-only
"""Perform Pulsus Noctis from its own MIDI and instrument patches."""

import argparse
import json
from pathlib import Path
import tempfile

import mido
import numpy as np

import instruments
from setloom.audio import write_audio, write_master

HERE = Path(__file__).resolve().parent


def read_part(track, ppq, tempo):
    active = {}
    tick = 0
    notes = []
    expression = []
    for e in track:
        tick += e.time
        s = tick / ppq * tempo / 1e6
        if e.type == "note_on" and e.velocity:
            active.setdefault((e.channel, e.note), []).append((s, e.velocity))
        elif e.type == "note_off" or e.type == "note_on" and not e.velocity:
            key = (e.channel, e.note)
            if not active.get(key):
                raise ValueError(f"Unpaired note in {track.name}")
            start, v = active[key].pop(0)
            notes.append((start, s - start, e.note, v))
        elif e.type == "control_change" and e.control == 11:
            expression.append((s, e.value / 127))
    if any(active.values()):
        raise ValueError(f"Unclosed notes in {track.name}")
    return sorted(notes), expression


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--assets", type=Path, default=Path("models"), help="Independent instrument libraries"
    )
    args = parser.parse_args()
    out = args.out_dir.resolve()
    assets = args.assets.resolve()
    if out == HERE or HERE in out.parents:
        raise ValueError("Output must be outside production source")
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError("Choose an empty output directory")
    cfg = json.loads((HERE / "instruments.json").read_text())
    sr = cfg["sample_rate"]
    frames = cfg["frames"]
    midi = mido.MidiFile(HERE / "Pulsus Noctis.mid")
    tempo = next(e.tempo for tr in midi.tracks for e in tr if e.type == "set_tempo")
    tracks = {int(tr.name[:2]): tr for tr in midi.tracks[1:]}
    if set(tracks) != set(range(1, 15)):
        raise ValueError("Expected all fourteen Pulsus parts")
    decoded = {i: read_part(tr, midi.ticks_per_beat, tempo) for i, tr in tracks.items()}
    mix = np.zeros((frames, 2), np.float64)
    time = np.arange(frames) / sr
    report = {"parts": [], "frames": frames, "sample_rate": sr}
    stems = out / "stems"
    stems.mkdir()
    with tempfile.TemporaryDirectory(prefix="instrument-work-", dir=out) as temporary:
        work = Path(temporary)
        for number in sorted(tracks):
            tr = tracks[number]
            patch = cfg["parts"][str(number)]
            kind = patch["instrument"]
            notes, expression = decoded[number]
            if kind == "piano":
                y = instruments.piano(
                    tr, midi.tracks[0], midi.ticks_per_beat, patch, sr, frames, assets, work
                )
            else:
                y = np.zeros((frames, 2), np.float32)
                sample = instruments.percussion_sample(patch, sr) if kind == "sample" else None
                for start, duration, pitch, velocity in notes:
                    at = round(start * sr)
                    if at >= frames:
                        continue
                    if sample is not None:
                        voice = sample
                    elif kind == "violin":
                        voice = instruments.violin(pitch, duration, patch, sr, assets)
                    else:
                        voice = instruments.synthesized(pitch, duration, patch, sr)
                    size = min(len(voice), frames - at)
                    gain = (velocity / 100) ** patch.get("velocity_power", 1.5)
                    y[at : at + size] += voice[:size] * gain
            y = instruments.finish(y, patch, sr)
            if patch.get("pulse"):
                pulse = patch["pulse"]
                phase = np.mod(time - pulse["origin_seconds"], tempo / 1e6)
                y *= (
                    pulse["floor"]
                    + (1 - pulse["floor"])
                    * np.minimum(phase / pulse["rise_seconds"], 1) ** pulse["curve"]
                )[:, None]
            if patch.get("duck", 0):
                duck = np.ones(frames, np.float32)
                for start, _, _, velocity in decoded[5][0]:
                    at = round(start * sr)
                    size = min(round(0.45 * sr), frames - at)
                    if size <= 0:
                        continue
                    duck[at : at + size] *= 1 - patch["duck"] * min(
                        1, (velocity / 100) ** 2
                    ) * np.exp(-np.arange(size) / sr / 0.10)
                y *= duck[:, None]
            if patch.get("level_curve"):
                points = np.array(patch["level_curve"])
                y *= (10 ** (np.interp(time, points[:, 0], points[:, 1]) / 20))[:, None]
            if expression:
                points = np.array(expression)
                y *= np.interp(time, points[:, 0], points[:, 1], left=1, right=points[-1, 1])[
                    :, None
                ]
            y *= 10 ** (patch["gain_db"] / 20)
            fade = round(0.08 * sr)
            y[-fade:] *= np.linspace(1, 0, fade)[:, None]
            if not np.isfinite(y).all():
                raise ValueError(f"Non-finite {tr.name}")
            filename = stems / (tr.name + ".wav")
            write_audio(filename, y, sample_rate=sr, subtype="FLOAT")
            rms = float(np.sqrt(np.mean(y.astype(np.float64) ** 2)))
            peak = float(np.max(abs(y)))
            report["parts"].append(
                {"number": number, "name": tr.name, "notes": len(notes), "rms": rms, "peak": peak}
            )
            mix += y
            print(
                tr.name,
                len(notes),
                "notes; RMS",
                round(20 * np.log10(max(rms, 1e-12)), 2),
                flush=True,
            )
    report.update(
        duration_seconds=frames / sr,
        mastering=write_master(out / "Pulsus Noctis.wav", mix, sample_rate=sr, **cfg["mastering"]),
    )
    print("Mastering:", json.dumps(report["mastering"]), flush=True)
    (out / "render.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Full song:", out / "Pulsus Noctis.wav", flush=True)


if __name__ == "__main__":
    main()
