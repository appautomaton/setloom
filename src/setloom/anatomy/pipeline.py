# SPDX-License-Identifier: AGPL-3.0-only
"""Anatomy pipeline: full-mix pass, optional 53-stem layer lens, corpus roll-up.

Owns all audio I/O and librosa feature extraction; the math lives in
`analysis` and `corpus`. The 53-stem layer lens is imported lazily so
analysis-only runs never load torch.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

import mido
import numpy as np
import soundfile as sf
import yaml

from setloom.anatomy import analysis as an
from setloom.anatomy import corpus as co

SR = 22050
HOP = 512
AUDIO_SUFFIXES = {".mp3", ".wav", ".flac", ".aiff", ".aif", ".m4a"}
START_BPM = 124.0

DEFAULT_OUT = Path("local/corpus/dossiers")


@dataclass
class Grid:
    bpm: float
    t0: float
    n_bars: int

    @property
    def bar_dur(self) -> float:
        return 4.0 * 60.0 / self.bpm


def _load_mono(path: Path) -> np.ndarray:
    import librosa

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        y, _ = librosa.load(path, sr=SR, mono=True)
    return y


def _beat_grid(y: np.ndarray, duration: float) -> tuple[Grid, bool]:
    import librosa

    tempo, beats = librosa.beat.beat_track(y=y, sr=SR, start_bpm=START_BPM, units="time")
    raw = float(np.atleast_1d(tempo)[0])
    bpm = an.fold_tempo(raw)
    suspect = an.tempo_suspect(raw)
    t0 = float(beats[0]) if len(beats) else 0.0
    bar_dur = 4.0 * 60.0 / bpm
    n_bars = max(1, int((duration - t0) / bar_dur))
    return Grid(round(bpm, 1), round(t0, 2), n_bars), suspect


def _integrated_lufs(path: Path) -> float:
    import pyloudnorm as pyln

    data, sr = sf.read(path, always_2d=True)
    return round(float(pyln.Meter(sr).integrated_loudness(data)), 2)


def fullmix_pass(path: Path) -> dict:
    """Whole-mix dossier: grid, key, loudness, energy curve, section map."""
    import librosa

    y = _load_mono(path)
    duration = float(len(y) / SR)
    grid, suspect = _beat_grid(y, duration)
    grid_times = an.bar_grid(grid.t0, grid.bar_dur, grid.n_bars)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        chroma = librosa.feature.chroma_stft(y=y, sr=SR, hop_length=HOP)
        chroma_key = librosa.feature.chroma_cqt(y=y, sr=SR).mean(axis=1)
        mfcc = librosa.feature.mfcc(y=y, sr=SR, n_mfcc=12, hop_length=HOP)
        stft_power = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP)) ** 2
    freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)
    frame_times = librosa.frames_to_time(np.arange(stft_power.shape[1]), sr=SR, hop_length=HOP)

    key, key_conf = an.estimate_key(chroma_key)
    energy = an.band_energy_per_bar(stft_power, freqs, frame_times, grid_times)
    feats = an.bar_feature_matrix(chroma, mfcc, frame_times, grid_times)
    bounds = an.section_boundaries(feats)

    edges = [0, *bounds, grid.n_bars]
    sections = []
    for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
        if b <= a:
            continue
        low = float(energy["low"][a:b].mean())
        mid = float(energy["mid"][a:b].mean())
        high = float(energy["high"][a:b].mean())
        sections.append(
            {
                "bars": f"{a + 1}-{b}",
                "length_bars": b - a,
                "label_guess": an.label_section(low, mid, high, i, len(edges) - 1),
                "energy": {"low": round(low, 2), "mid": round(mid, 2), "high": round(high, 2)},
            }
        )

    phrase = 16
    energy_curve = [
        {
            "bars": f"{a + 1}-{min(a + phrase, grid.n_bars)}",
            "low": round(float(energy["low"][a : a + phrase].mean()), 2),
            "mid": round(float(energy["mid"][a : a + phrase].mean()), 2),
            "high": round(float(energy["high"][a : a + phrase].mean()), 2),
        }
        for a in range(0, grid.n_bars, phrase)
    ]

    return {
        "file": path.name,
        "artist_dir": path.parent.name,
        "duration_s": round(duration, 1),
        "bpm_estimate": grid.bpm,
        "tempo_suspect": suspect,
        "key_estimate": key,
        "key_confidence": key_conf,
        "integrated_lufs": _integrated_lufs(path),
        "bars_estimated": grid.n_bars,
        "first_beat_s": grid.t0,
        "sections": sections,
        "energy_curve_16bar": energy_curve,
    }


def write_bass_midi(notes: list[tuple[int, int, int]], out_path: Path, bpm: float) -> None:
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    events = []
    for start, length, pitch in notes:
        events.append((start * 120, "on", pitch))
        events.append(((start + length) * 120 - 10, "off", pitch))
    events.sort(key=lambda e: (e[0], e[1] == "on"))
    now = 0
    for tick, kind, pitch in events:
        msg = "note_on" if kind == "on" else "note_off"
        track.append(mido.Message(msg, note=pitch, velocity=96, time=max(0, tick - now)))
        now = tick
    mid.save(out_path)


def collect_audio(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if target.suffix.lower() in AUDIO_SUFFIXES else []
    skip = {"stems", "stems53", "dossiers", "candidates", "_stems", "_stems53", "_dossiers", "_candidates"}
    return sorted(
        p
        for p in target.rglob("*")
        if p.suffix.lower() in AUDIO_SUFFIXES and not p.name.startswith(".")
        and not skip & set(p.parts)
    )


def _write_yaml_if_changed(path: Path, data: dict) -> bool:
    text = yaml.safe_dump(data, sort_keys=False, width=100, allow_unicode=True)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def _write_summary(out_dir: Path, rows: list[dict]) -> bool:
    """Merge this run's rows into the corpus summary and write if changed."""
    path = out_dir / "corpus-summary.yml"
    if path.is_file():
        existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        rows = co.merge_rows(existing.get("tracks") or [], rows)
    return _write_yaml_if_changed(path, {"tracks": rows, "corpus": co.corpus_stats(rows)})


def run(
    target: Path,
    out_dir: Path = DEFAULT_OUT,
    layers: bool = False,
    layer_stems_dir: Path = Path("local/corpus/stems53"),
    models_dir: Path = Path("models/roformer"),
    summary: bool = True,
) -> dict:
    """Run the pipeline over a file or directory. Returns a per-track status map."""
    out_dir.mkdir(parents=True, exist_ok=True)
    statuses: dict[str, list[str]] = {}
    rows = []

    for audio in collect_audio(target):
        track = an.nfc(audio.stem)
        status: list[str] = []
        quick_path = out_dir / f"{track}.quick.yml"

        if quick_path.is_file():
            quick = yaml.safe_load(quick_path.read_text(encoding="utf-8"))
            status.append("quick:cached")
        else:
            quick = fullmix_pass(audio)
            status.append("quick:analyzed")

        if layers:
            # Lazy import: the layer lens is torch-heavy and opt-in.
            from setloom.anatomy import layers as layer_lens

            grid_l = Grid(quick["bpm_estimate"], quick["first_beat_s"], quick["bars_estimated"])
            status += layer_lens.layer_pass(
                audio, track, grid_l, out_dir, layer_stems_dir, models_dir
            )

        _write_yaml_if_changed(quick_path, quick)
        rows.append(co.quick_row(track, quick))
        statuses[track] = status

    if rows and summary:
        changed = _write_summary(out_dir, rows)
        statuses["corpus-summary"] = ["written" if changed else "unchanged"]
    return statuses
