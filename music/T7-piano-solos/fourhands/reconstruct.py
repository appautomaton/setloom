# SPDX-License-Identifier: AGPL-3.0-only
"""T7 four-hands: end-to-end piano-duet reconstruction. Raw 4-hands audio in, our piano out.

Sibling to ../reconstruct.py (solo). A four-hands recording merges two players into one audio
stream; this pipeline recovers two coherent player strata, restores the dynamic life the
transcriber flattens, and re-performs on the Salamander grand -- while PRESERVING the real
ensemble timing (the two players' actual asynchrony), which is the four-hands feel.

  1. transcribe  Kong (ByteDance MAESTRO) -> flat MIDI (notes + pedal). cached. mps->cpu.
  2. stratify    flat MIDI -> PRIMO (upper) + SECONDO (lower) via an adaptive register seam +
                 voice continuity. Two-stratum recovery, NOT literal 4-hand staves -- per the
                 Grok+Codex consult, full per-hand labels are under-determined on dense,
                 constantly-crossing duet textures.
  3. ensemble    per-stratum three-band velocity shaping (restore the build + cell contrast) +
                 a small independent per-player jitter. Onsets preserved: the real ensemble
                 timing is already human, so the human touch goes into dynamics, not timing.
  4. render      mechanical reference + humanized + a panned aid -> Salamander -> -16 master.

Seams: setloom.audio owns loudness (the harness's job); Kong is called directly because it is
pedal-aware; mido directly because free-timing duet playing is not a 4/4 grid.

Run (repo root, kong group):
  uv run --group kong python music/T7-piano-solos/fourhands/reconstruct.py PATH/TO/duet.mp3
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from collections import deque
from pathlib import Path

import mido
import numpy as np

from setloom import audio as sa

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CKPT = REPO / "models/piano-transcription/note_F1=0.9677_pedal_F1=0.8658.pth"
SF2 = REPO / "models/soundfonts/SalamanderGrandPiano-V3.sf2"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# --- 1. transcribe -----------------------------------------------------------------------
def transcribe(src: Path, midi_out: Path, ckpt: Path) -> None:
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
            print(f"  1. transcribe: {len(audio)/sample_rate:.0f}s on {dev} in {time.time()-t0:.0f}s "
                  f"-> {len(out['est_note_events'])} notes")
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            print(f"  1. transcribe: {dev} failed ({type(exc).__name__}: {str(exc)[:70]})")
    raise SystemExit(f"transcription failed on every device: {last}")


# --- MIDI I/O (absolute timing preserved; setloom.midi is 4/4-grid only) ------------------
def load_midi(path: Path):
    notes, opn, cc, t = [], {}, [], 0.0
    for m in mido.MidiFile(str(path)):
        t += m.time
        if m.type == "note_on" and m.velocity > 0:
            opn.setdefault(m.note, []).append((t, m.velocity))
        elif m.type == "note_off" or (m.type == "note_on" and m.velocity == 0):
            if opn.get(m.note):
                on, v = opn[m.note].pop(0)
                notes.append([on, t, m.note, v])
        elif m.type == "control_change" and m.control == 64:
            cc.append((t, m.value))
    notes.sort()
    return notes, cc


def write_midi(path: Path, notes, cc, ppq: int = 480, bpm: float = 120.0) -> None:
    tempo = mido.bpm2tempo(bpm)
    tick = lambda s: int(round(mido.second2tick(s, ppq, tempo)))  # noqa: E731
    ev = []
    for on, off, p, v in notes:
        ev.append((tick(on), 1, mido.Message("note_on", note=p, velocity=int(v))))
        ev.append((tick(off), 0, mido.Message("note_off", note=p, velocity=0)))
    for t, val in cc:
        ev.append((tick(t), 2, mido.Message("control_change", control=64, value=int(val))))
    ev.sort(key=lambda x: (x[0], x[1]))
    tr = mido.MidiTrack()
    tr.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    cur = 0
    for tk, _, msg in ev:
        msg.time = tk - cur
        cur = tk
        tr.append(msg)
    mf = mido.MidiFile(type=1, ticks_per_beat=ppq)
    mf.tracks.append(tr)
    mf.save(str(path))


def _windowed(onsets, vals, W):
    o = np.asarray(onsets, float)
    order = np.argsort(o, kind="stable")
    os_, vs = o[order], np.asarray(vals, float)[order]
    pre = np.concatenate([[0.0], np.cumsum(vs)])
    lo = np.searchsorted(os_, os_ - W / 2, "left")
    hi = np.searchsorted(os_, os_ + W / 2, "right")
    out = np.empty_like(vs)
    out[order] = (pre[hi] - pre[lo]) / np.maximum(hi - lo, 1)
    return out


# --- 2. stratify: PRIMO (upper) vs SECONDO (lower) ----------------------------------------
def stratify(notes, band=(52, 80), min_gap=3, win_s=1.5, alpha=0.12, border=4, cont_s=0.40):
    on = [n[0] for n in notes]
    pit = [n[2] for n in notes]
    seam, dq, b = [], deque(), float(np.median(pit))
    for i, t in enumerate(on):
        dq.append((t, pit[i]))
        while dq and dq[0][0] < t - win_s:
            dq.popleft()
        bnd = sorted(p for _, p in dq if band[0] <= p <= band[1])
        cand = None
        if len(bnd) >= 2:
            g, mid = max((bnd[k + 1] - bnd[k], (bnd[k + 1] + bnd[k]) / 2) for k in range(len(bnd) - 1))
            if g >= min_gap:
                cand = mid
        if cand is None:
            wp = [p for _, p in dq]
            cand = float(np.median(wp)) if wp else b
        b = alpha * cand + (1 - alpha) * b
        seam.append(b)
    assign, last = [], {"P": (-1e9, 0.0), "S": (-1e9, 0.0)}
    for i, (onset, _o, p, _v) in enumerate(notes):
        base = "P" if p >= seam[i] else "S"
        a = base
        if abs(p - seam[i]) <= border:
            dp = abs(p - last["P"][1]) if onset - last["P"][0] <= cont_s else 1e9
            ds = abs(p - last["S"][1]) if onset - last["S"][0] <= cont_s else 1e9
            a = "P" if dp < ds else "S" if ds < dp else base
        assign.append(a)
        last[a] = (onset, p)
    primo = [n for n, x in zip(notes, assign) if x == "P"]
    secondo = [n for n, x in zip(notes, assign) if x == "S"]
    return primo, secondo


# --- 3. ensemble: dynamic human touch per player (onsets preserved) -----------------------
def expand_velocity(notes, k_macro, k_mid, k_micro, w_local, w_global, v_min, v_max):
    on = np.array([n[0] for n in notes])
    vel = np.array([n[3] for n in notes], float)
    gmean = vel.mean()
    glob = _windowed(on, vel, w_global)
    local = _windowed(on, vel, w_local)
    new = gmean + k_macro * (glob - gmean) + k_mid * (local - glob) + k_micro * (vel - local)
    new = np.clip(new, v_min, v_max)
    for n, nv in zip(notes, new):
        n[3] = float(nv)
    return notes


def shape(notes, rng, k=(1.4, 1.4, 1.4), win=(3.0, 25.0), vrange=(20, 125),
          blip_ms=20.0, noise=2.5):
    notes = [n for n in notes if (n[1] - n[0]) >= blip_ms / 1000.0]
    notes = expand_velocity(notes, k[0], k[1], k[2], win[0], win[1], vrange[0], vrange[1])
    for n, z in zip(notes, rng.normal(0.0, noise, size=len(notes))):
        n[3] = int(round(np.clip(n[3] + z, vrange[0], vrange[1])))
    return notes


# --- 4. render ---------------------------------------------------------------------------
def fluidsynth(mid: Path, wav: Path) -> None:
    subprocess.run(["fluidsynth", "-ni", "-F", str(wav), "-r", "44100", "-g", "0.6",
                    "-o", "synth.reverb.active=0", "-o", "synth.chorus.active=0", str(SF2), str(mid)],
                   check=True, capture_output=True)


def _room(src: Path, dst: Path, room_size=0.5, wet=0.16) -> None:
    from pedalboard import HighShelfFilter, Pedalboard, Reverb
    from pedalboard.io import AudioFile
    board = Pedalboard([HighShelfFilter(cutoff_frequency_hz=7500, gain_db=-2.0),
                        Reverb(room_size=room_size, damping=0.5, wet_level=wet,
                               dry_level=1 - wet * 0.9, width=0.9)])
    with AudioFile(str(src)) as f:
        sig, sr = f.read(f.frames), f.samplerate
    out = board(sig, sr)
    with AudioFile(str(dst), "w", sr, out.shape[0]) as f:
        f.write(out)


def _master(src: Path, dst: Path, lufs: float):
    y, sr = sa.read_audio(src, sample_rate=None)
    o = sa.master(y, sample_rate=sr, target_lufs=lufs)
    sa.write_audio(dst, o, sample_rate=sr)
    return sa.integrated_lufs(o, sample_rate=sr), sa.peak_dbfs(o)


def render_solo(mid: Path, out: Path, scratch: Path, lufs: float):
    dry, wet = scratch / "_d.wav", scratch / "_w.wav"
    fluidsynth(mid, dry)
    _room(dry, wet)
    lk = _master(wet, out, lufs)
    for f in (dry, wet):
        f.unlink(missing_ok=True)
    return lk


def render_panned(primo: Path, secondo: Path, out: Path, scratch: Path, lufs: float, pan=0.3):
    dp, ds, pan_w, wet = scratch / "_p.wav", scratch / "_s.wav", scratch / "_pan.wav", scratch / "_w.wav"
    fluidsynth(primo, dp)
    fluidsynth(secondo, ds)
    yp, sr = sa.read_audio(dp, sample_rate=None)
    ys, _ = sa.read_audio(ds, sample_rate=None)
    n = max(yp.shape[0], ys.shape[0])
    mono = lambda y: np.pad(y.mean(axis=1) if y.ndim > 1 else y, (0, n - y.shape[0]))  # noqa: E731
    mp, ms = mono(yp), mono(ys)
    glp, grp = np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)
    gls, grs = np.sqrt((1 + pan) / 2), np.sqrt((1 - pan) / 2)
    sa.write_audio(pan_w, np.stack([ms * gls + mp * glp, ms * grs + mp * grp], axis=1).astype(np.float32),
                   sample_rate=sr)
    _room(pan_w, wet)
    lk = _master(wet, out, lufs)
    for f in (dp, ds, pan_w, wet):
        f.unlink(missing_ok=True)
    return lk


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="End-to-end four-hands piano reconstruction.")
    ap.add_argument("audio", help="raw four-hands piano recording")
    ap.add_argument("--out", default=None, help="output root (default: <here>/out)")
    ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--blip-ms", type=float, default=20.0, help="drop notes shorter than this")
    ap.add_argument("--k-macro", type=float, default=1.4, help="enhance the build/accumulation")
    ap.add_argument("--k-mid", type=float, default=1.4)
    ap.add_argument("--k-micro", type=float, default=1.4)
    ap.add_argument("--noise", type=float, default=2.5, help="per-player velocity jitter sigma")
    args = ap.parse_args(argv)

    src = Path(args.audio)
    missing = [str(p) for p in (src, CKPT, SF2) if not p.exists()]
    if missing:
        print("missing input(s):", *(f"\n  {m}" for m in missing), file=sys.stderr)
        return 1

    slug = slugify(src.stem)
    out = (Path(args.out) if args.out else HERE / "out") / slug
    out.mkdir(parents=True, exist_ok=True)
    raw = out / "notes.raw.mid"

    print(f"{src.name} -> {out}/")
    transcribe(src, raw, CKPT)
    notes, cc = load_midi(raw)
    primo, secondo = stratify(notes)
    assert len(primo) + len(secondo) == len(notes), "stratify lost notes"
    print(f"  2. stratify: PRIMO {len(primo)} (upper) / SECONDO {len(secondo)} (lower)")

    rng = np.random.default_rng(args.seed)
    k, win, vr = (args.k_macro, args.k_mid, args.k_micro), (3.0, 25.0), (20, 125)
    hp = shape([list(n) for n in primo], rng, k, win, vr, args.blip_ms, args.noise)
    hs = shape([list(n) for n in secondo], rng, k, win, vr, args.blip_ms, args.noise)
    write_midi(out / "primo.mid", primo, cc)
    write_midi(out / "secondo.mid", secondo, cc)
    write_midi(out / "humanized.primo.mid", hp, cc)
    write_midi(out / "humanized.secondo.mid", hs, cc)
    write_midi(out / "humanized.mid", sorted(hp + hs, key=lambda n: n[0]), cc)
    print(f"  3. ensemble: dynamics shaped per player (seed {args.seed}), onsets preserved")

    mech = out / f"{slug}.mechanical.piano.wav"
    human = out / f"{slug}.humanized.piano.wav"
    panned = out / f"{slug}.humanized-panned.piano.wav"
    render_solo(raw, mech, out, args.lufs)
    lh, kh = render_solo(out / "humanized.mid", human, out, args.lufs)
    render_panned(out / "humanized.primo.mid", out / "humanized.secondo.mid", panned, out, args.lufs)
    print(f"  4. render: mechanical + humanized ({lh:.1f} LUFS, peak {kh:.1f}) + panned aid")
    print(f"\ndone. A/B:\n  setloom play {mech}\n  setloom play {human}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
