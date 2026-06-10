# SPDX-License-Identifier: AGPL-3.0-only
"""Anatomy pipeline: full-mix pass, stem separation, stem pass, corpus roll-up.

Owns all audio I/O and librosa feature extraction; the math lives in
`analysis` and `corpus`. Stem separation is imported lazily from `separate`
only when stems are missing, so analysis-only runs never load torch.
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
PYIN_VOICED_MIN = 0.4

DEFAULT_OUT = Path("anatomy/_dossiers")
DEFAULT_STEMS = Path("anatomy/_stems")


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
        "stem_model": None,
        "sections": sections,
        "energy_curve_16bar": energy_curve,
    }


def reanchor_grid(dossier: dict, drums_wav: Path) -> dict:
    """Re-estimate the grid from the drum stem when the full-mix tempo is suspect."""
    y = _load_mono(drums_wav)
    grid, still_suspect = _beat_grid(y, dossier["duration_s"])
    old = dossier["bpm_estimate"]
    dossier.update(
        bpm_estimate=grid.bpm,
        first_beat_s=grid.t0,
        bars_estimated=grid.n_bars,
        tempo_suspect=still_suspect,
        bpm_note=f"re-anchored from drum stem; full-mix pass had {old}",
    )
    return dossier


def _bandpass(y: np.ndarray, lo: float | None, hi: float | None) -> np.ndarray:
    from scipy.signal import butter, sosfiltfilt

    if lo and hi:
        sos = butter(4, [lo, hi], btype="band", fs=SR, output="sos")
    elif hi:
        sos = butter(4, hi, btype="low", fs=SR, output="sos")
    else:
        sos = butter(4, lo, btype="high", fs=SR, output="sos")
    return sosfiltfilt(sos, y)


def _onset_times(y: np.ndarray) -> np.ndarray:
    import librosa

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return librosa.onset.onset_detect(y=y, sr=SR, units="time", backtrack=False)


def _analyze_drums(y: np.ndarray, grid: Grid) -> dict:
    kicks = _onset_times(_bandpass(y, None, 100.0))
    highs = _onset_times(_bandpass(y, 5000.0, None))
    kick_count = an.events_per_bar(kicks, grid.t0, grid.bar_dur, grid.n_bars)
    high_count = an.events_per_bar(highs, grid.t0, grid.bar_dur, grid.n_bars)
    present = kick_count >= 2
    in_groove = kick_count[present]
    return {
        "kick_bars_present": int(present.sum()),
        "kick_per_bar_mode": int(np.bincount(in_groove).argmax()) if len(in_groove) else 0,
        "kick_gap_bars": [f"{a}-{b}" for a, b in an.presence_gaps(present)],
        "high_perc_onsets_per_bar_groove": round(float(high_count[present].mean()), 1)
        if present.any()
        else 0.0,
    }


def _analyze_bass(y: np.ndarray, grid: Grid) -> tuple[dict, list[tuple[int, int, int]]]:
    import librosa

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f0, voiced, _ = librosa.pyin(
            y, fmin=27.5, fmax=261.6, sr=SR, frame_length=4096, hop_length=HOP
        )
    times = librosa.times_like(f0, sr=SR, hop_length=HOP)
    step = grid.bar_dur / 16.0
    n_steps = grid.n_bars * 16

    step_pitch = np.full(n_steps, -1, dtype=int)
    for s in range(n_steps):
        t_start = grid.t0 + s * step
        sel = (times >= t_start) & (times < t_start + step)
        if not sel.any():
            continue
        v = voiced[sel] & ~np.isnan(f0[sel])
        if v.mean() < PYIN_VOICED_MIN:
            continue
        hz = np.nanmedian(f0[sel][v])
        if hz > 0:
            step_pitch[s] = int(round(librosa.hz_to_midi(hz)))

    notes = an.segment_notes(step_pitch)
    return an.note_stats(notes, n_steps), notes


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


def _analyze_other(y: np.ndarray, grid: Grid) -> dict:
    import librosa

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        chroma = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=HOP)
    times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=SR, hop_length=HOP)
    chords: list[str | None] = []
    for a in range(0, grid.n_bars - 1, 2):
        t_start = grid.t0 + a * grid.bar_dur
        t_end = grid.t0 + (a + 2) * grid.bar_dur
        sel = (times >= t_start) & (times < t_end)
        if not sel.any():
            chords.append(None)
            continue
        chords.append(an.match_triad(chroma[:, sel].mean(axis=1))[0])
    changes = sum(1 for a, b in zip(chords[:-1], chords[1:]) if a and b and a != b)
    return {
        "chords_per_2bars": chords,
        "harmonic_changes_per_16bars": round(changes / max(1, grid.n_bars / 16), 1),
        "onset_rate_per_bar": round(len(_onset_times(y)) / max(1, grid.n_bars), 1),
    }


def _analyze_vocals(y: np.ndarray, grid: Grid) -> dict:
    import librosa

    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=SR, hop_length=HOP)
    per_bar = np.zeros(grid.n_bars)
    for b in range(grid.n_bars):
        sel = (times >= grid.t0 + b * grid.bar_dur) & (times < grid.t0 + (b + 1) * grid.bar_dur)
        per_bar[b] = float(rms[sel].mean()) if sel.any() else 0.0
    ranges = an.active_ranges(per_bar)
    normalized = per_bar / (per_bar.max() + 1e-12)
    return {
        "active_share": round(float((normalized > 0.3).mean()), 2),
        "active_bar_ranges": [f"{a}-{b}" for a, b in ranges],
    }


def stem_pass(track: str, stem_dir: Path, grid: Grid, out_dir: Path) -> dict:
    """Per-stem dossier from separated stems; writes the bass MIDI transcription."""
    drums = _analyze_drums(_load_mono(stem_dir / "drums.wav"), grid)
    bass, notes = _analyze_bass(_load_mono(stem_dir / "bass.wav"), grid)
    write_bass_midi(notes, out_dir / f"{track}.bass.mid", grid.bpm)
    other = _analyze_other(_load_mono(stem_dir / "other.wav"), grid)
    vocals = _analyze_vocals(_load_mono(stem_dir / "vocals.wav"), grid)
    return {
        "track": track,
        "bpm_used": grid.bpm,
        "bars": grid.n_bars,
        "drums": drums,
        "bass": bass,
        "other": other,
        "vocals": vocals,
    }


def collect_audio(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if target.suffix.lower() in AUDIO_SUFFIXES else []
    return sorted(
        p
        for p in target.rglob("*")
        if p.suffix.lower() in AUDIO_SUFFIXES and not p.name.startswith(".")
        and "_stems" not in p.parts and "_dossiers" not in p.parts
        and "_stems53" not in p.parts
        and "_candidates" not in p.parts
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
    stems_dir: Path = DEFAULT_STEMS,
    separate: bool = True,
    layers: bool = False,
    layer_stems_dir: Path = Path("anatomy/_stems53"),
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
        stem_yml = out_dir / f"{track}.stems.yml"
        stem_dir = stems_dir / track

        if quick_path.is_file():
            quick = yaml.safe_load(quick_path.read_text(encoding="utf-8"))
            status.append("quick:cached")
        else:
            quick = fullmix_pass(audio)
            status.append("quick:analyzed")

        from setloom.anatomy.separate import MODEL_NAME, stems_present

        if not stems_present(stem_dir):
            if separate:
                from setloom.anatomy.separate import separate_track

                separate_track(audio, stem_dir)
                status.append("stems:separated")
            else:
                status.append("stems:missing")
        else:
            status.append("stems:cached")

        if stems_present(stem_dir):
            if quick.get("tempo_suspect"):
                quick = reanchor_grid(quick, stem_dir / "drums.wav")
                status.append("grid:reanchored")
            quick["stem_model"] = MODEL_NAME
            grid = Grid(quick["bpm_estimate"], quick["first_beat_s"], quick["bars_estimated"])
            if stem_yml.is_file():
                stems = yaml.safe_load(stem_yml.read_text(encoding="utf-8"))
                status.append("stempass:cached")
            else:
                stems = stem_pass(track, stem_dir, grid, out_dir)
                status.append("stempass:analyzed")
            _write_yaml_if_changed(stem_yml, stems)
            rows.append(co.track_row(quick, stems))

        if layers:
            # Lazy import: the layer lens is torch-heavy and opt-in. Runs after
            # the stem pass so heavy models never overlap (unified-memory rule).
            from setloom.anatomy import layers as layer_lens

            grid_l = Grid(quick["bpm_estimate"], quick["first_beat_s"], quick["bars_estimated"])
            status += layer_lens.layer_pass(
                audio, track, grid_l, out_dir, layer_stems_dir, models_dir
            )

        _write_yaml_if_changed(quick_path, quick)
        statuses[track] = status

    if rows and summary:
        changed = _write_summary(out_dir, rows)
        statuses["corpus-summary"] = ["written" if changed else "unchanged"]
    return statuses
