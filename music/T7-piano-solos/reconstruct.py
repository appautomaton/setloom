# SPDX-License-Identifier: AGPL-3.0-only
"""T7 piano-solos: end-to-end solo-piano reconstruction. Raw piano audio in, our piano out.

One self-contained pipeline, no notation, no quantization, expressive timing preserved:

  1. transcribe   Kong -> raw MIDI with pedal (CC64).  GPU mps->cpu.
  2. clean        drop sub-30ms note blips; debounce sub-60ms pedal flutter. Keeps rubato,
                  dynamics, and the pedal contour intact.
  3. render       cleaned MIDI -> Salamander grand (fluidsynth):
                    faithful   = fluidsynth's own room.
                    expressive = effects off, then a tasteful room + top tame (pedalboard).
  4. master       LUFS-normalize (stereo BS.1770) + true-peak limit, via setloom.audio.master.

Seams: setloom.audio owns loudness (the harness's job). Kong is called directly because
setloom.transcription drops pedal; mido is used directly because setloom.midi is 4/4-grid
only. Heavy ML lives in the shared uv env via the `kong` group; weights stay in models/.

Run (from repo root):
  uv run --group kong python music/T7-piano-solos/reconstruct.py \
      "local/corpus/audio/piano/classical/Clair de lune.mp3"
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

import mido
import numpy as np

from setloom import audio as sa

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CKPT = REPO / "models/piano-transcription/note_F1=0.9677_pedal_F1=0.8658.pth"
SF2 = REPO / "models/soundfonts/SalamanderGrandPiano-V3.sf2"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# --- 1. transcribe -----------------------------------------------------------------------
def transcribe(src: Path, midi_out: Path, ckpt: Path) -> None:
    """Kong audio -> raw MIDI (notes + pedal). Cached: skipped if midi_out already exists."""
    if midi_out.exists() and midi_out.stat().st_size > 0:
        print(f"  1. transcribe: cached {midi_out.name} (delete to redo)")
        return
    import librosa
    import torch
    from piano_transcription_inference import PianoTranscription, sample_rate

    audio = librosa.load(str(src), sr=sample_rate, mono=True)[0].astype(np.float32)
    last = None
    for dev in ("mps", "cpu"):
        if dev == "mps" and not torch.backends.mps.is_available():
            continue
        try:
            engine = PianoTranscription(device=dev, checkpoint_path=str(ckpt))
            t0 = time.time()
            out = engine.transcribe(audio, str(midi_out))
            secs = len(audio) / sample_rate
            print(f"  1. transcribe: {secs:.0f}s on {dev} in {time.time()-t0:.0f}s "
                  f"-> {len(out['est_note_events'])} notes")
            return
        except Exception as exc:  # noqa: BLE001 -- fall through to next device
            last = exc
            print(f"  1. transcribe: {dev} failed ({type(exc).__name__}: {str(exc)[:70]})")
    raise SystemExit(f"transcription failed on every device: {last}")


# --- 2. clean ----------------------------------------------------------------------------
def load_midi(path: Path) -> tuple[list[list], list[tuple[float, int]]]:
    """Parse to (notes [onset_s, offset_s, pitch, vel], sustain CC64 [(time_s, value)])."""
    notes: list[list] = []
    open_n: dict[int, list[tuple[float, int]]] = {}
    cc: list[tuple[float, int]] = []
    t = 0.0
    for m in mido.MidiFile(str(path)):
        t += m.time
        if m.type == "note_on" and m.velocity > 0:
            open_n.setdefault(m.note, []).append((t, m.velocity))
        elif m.type == "note_off" or (m.type == "note_on" and m.velocity == 0):
            if open_n.get(m.note):
                on, vel = open_n[m.note].pop(0)
                notes.append([on, t, m.note, vel])
        elif m.type == "control_change" and m.control == 64:
            cc.append((t, m.value))
    notes.sort()
    return notes, cc


def clean_notes(notes: list[list], min_dur: float) -> list[list]:
    """Drop transcription blips shorter than min_dur. Everything else is kept verbatim."""
    return [n for n in notes if (n[1] - n[0]) >= min_dur]


def clean_pedal(cc: list[tuple[float, int]], min_seg: float) -> list[tuple[float, int]]:
    """Binarize CC64 at 64, drop on/off segments shorter than min_seg (flutter), re-emit."""
    trans: list[list] = []
    cur = 0
    for t, v in cc:
        s = 1 if v >= 64 else 0
        if s != cur:
            trans.append([t, s])
            cur = s
    cleaned: list[list] = []
    for tr in trans:
        if cleaned and (tr[0] - cleaned[-1][0]) < min_seg:
            cleaned.pop()  # this toggle reverts within min_seg -> cancel the flutter
        else:
            cleaned.append(tr)
    return [(t, 127 if s else 0) for t, s in cleaned]


def write_midi(path: Path, notes: list[list], cc: list[tuple[float, int]],
               ppq: int = 480, bpm: float = 120.0) -> None:
    """Write cleaned notes + pedal as a format-1 file, absolute timing preserved."""
    tempo = mido.bpm2tempo(bpm)
    tick = lambda s: int(round(mido.second2tick(s, ppq, tempo)))  # noqa: E731
    timed: list[tuple[int, int, mido.Message]] = []
    for on, off, pitch, vel in notes:
        timed.append((tick(on), 1, mido.Message("note_on", note=pitch, velocity=vel)))
        timed.append((tick(off), 0, mido.Message("note_off", note=pitch, velocity=0)))
    for t, v in cc:
        timed.append((tick(t), 2, mido.Message("control_change", control=64, value=v)))
    timed.sort(key=lambda x: (x[0], x[1]))

    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    cursor = 0
    for tk, _, msg in timed:
        msg.time = tk - cursor
        cursor = tk
        track.append(msg)
    mf = mido.MidiFile(type=1, ticks_per_beat=ppq)
    mf.tracks.append(track)
    mf.save(str(path))


# --- 3. render + 4. master ---------------------------------------------------------------
def render(midi: Path, sf2: Path, wav: Path, gain: float = 0.6, effects: bool = True) -> None:
    cmd = ["fluidsynth", "-ni", "-F", str(wav), "-r", "44100", "-g", f"{gain}"]
    if not effects:
        cmd += ["-o", "synth.reverb.active=0", "-o", "synth.chorus.active=0"]
    cmd += [str(sf2), str(midi)]
    subprocess.run(cmd, check=True, capture_output=True)


def voice(dry_wav: Path, wet_wav: Path) -> None:
    """Tasteful room + gentle top tame: a piano in a room, not a cathedral."""
    from pedalboard import HighShelfFilter, Pedalboard, Reverb
    from pedalboard.io import AudioFile

    board = Pedalboard([
        HighShelfFilter(cutoff_frequency_hz=7500, gain_db=-2.0),
        Reverb(room_size=0.42, damping=0.55, wet_level=0.16, dry_level=0.86, width=0.9),
    ])
    with AudioFile(str(dry_wav)) as f:
        sig, sr = f.read(f.frames), f.samplerate
    out = board(sig, sr)
    with AudioFile(str(wet_wav), "w", sr, out.shape[0]) as f:
        f.write(out)


def master(in_wav: Path, out_wav: Path, target_lufs: float, ceiling_dbtp: float = -1.0) -> None:
    """Normalize to target LUFS and true-peak-limit, via the setloom.audio primitive.

    The harness now owns the meter and limiter (setloom.audio.master): stereo BS.1770 plus a
    true-peak-aware brickwall limiter. We hand it the target and the ceiling; solo piano sits
    at a quiet, dynamics-first level without clipping the transient cadenza peaks.
    """
    y, sr = sa.read_audio(in_wav, sample_rate=None)
    out = sa.master(y, sample_rate=sr, target_lufs=target_lufs, ceiling_dbtp=ceiling_dbtp)
    sa.write_audio(out_wav, out, sample_rate=sr)
    print(f"       master {out_wav.name}: {sa.integrated_lufs(out, sample_rate=sr):.1f} LUFS, "
          f"peak {sa.peak_dbfs(out):.1f} dBFS")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="End-to-end solo-piano reconstruction.")
    ap.add_argument("audio", help="raw solo-piano recording")
    ap.add_argument("--lufs", type=float, default=-16.0, help="solo-piano target (dynamics-first)")
    ap.add_argument("--min-note-ms", type=float, default=30.0, help="drop note blips shorter than this")
    ap.add_argument("--min-pedal-ms", type=float, default=60.0, help="drop pedal flutter shorter than this")
    args = ap.parse_args(argv)

    src = Path(args.audio)
    missing = [str(p) for p in (src, CKPT, SF2) if not p.exists()]
    if missing:
        print("missing input(s):", *(f"\n  {m}" for m in missing), file=sys.stderr)
        return 1

    slug = slugify(src.stem)
    out = REPO / "tmp/t7-piano-solos" / slug
    out.mkdir(parents=True, exist_ok=True)
    raw_mid, clean_mid = out / "notes.raw.mid", out / "notes.clean.mid"
    retained_raw = HERE / "performances" / slug / "notes.raw.mid"
    if not raw_mid.exists() and retained_raw.exists():
        raw_mid.write_bytes(retained_raw.read_bytes())
    faithful = out / f"{slug}.faithful.piano.wav"
    expressive = out / f"{slug}.expressive.piano.wav"
    scratch = [out / "_fa.wav", out / "_ex.dry.wav", out / "_ex.wet.wav"]

    print(f"{src.name} -> {out}/")
    transcribe(src, raw_mid, CKPT)

    notes, cc = load_midi(raw_mid)
    cn = clean_notes(notes, args.min_note_ms / 1000.0)
    cp = clean_pedal(cc, args.min_pedal_ms / 1000.0)
    write_midi(clean_mid, cn, cp)
    print(f"  2. clean: notes {len(notes)}->{len(cn)} (-{len(notes)-len(cn)} blips), "
          f"pedal events {len(cc)}->{len(cp)} (debounced flutter)")

    render(clean_mid, SF2, scratch[0], effects=True)
    master(scratch[0], faithful, args.lufs)

    render(clean_mid, SF2, scratch[1], effects=False)
    voice(scratch[1], scratch[2])
    master(scratch[2], expressive, args.lufs)

    for s in scratch:
        s.unlink(missing_ok=True)
    print(f"  3-4. render+master: {faithful.name}, {expressive.name}")
    print(f"\ndone. setloom play {expressive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
