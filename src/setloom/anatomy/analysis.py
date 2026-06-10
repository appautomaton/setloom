# SPDX-License-Identifier: AGPL-3.0-only
"""Pure per-track anatomy math.

Functions operate on arrays, times, and grids supplied by the caller so unit
tests can feed synthetic data. No audio I/O, no librosa, no torch here.
"""

from __future__ import annotations

import unicodedata

import numpy as np

PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

KRUMHANSL_MAJOR = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
KRUMHANSL_MINOR = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)

MAJOR_TRIAD = np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0], dtype=float)
MINOR_TRIAD = np.array([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0], dtype=float)

# Plausible club-tempo band; folding cannot rescue 3:2 metrical-level errors
# (e.g. 80.7 for a true 123), so those land outside and read as suspect.
TEMPO_BAND = (100.0, 160.0)

BAND_EDGES_HZ = {"low": (0.0, 120.0), "mid": (120.0, 4000.0), "high": (4000.0, None)}


def nfc(s: str) -> str:
    """NFC-normalize so macOS NFD filenames compare equal to composed text."""
    return unicodedata.normalize("NFC", s)


def fold_tempo(bpm: float, band: tuple[float, float] = TEMPO_BAND) -> float:
    lo, hi = band
    while bpm < lo:
        bpm *= 2.0
    while bpm > hi:
        bpm /= 2.0
    return bpm


def tempo_suspect(bpm: float, band: tuple[float, float] = TEMPO_BAND) -> bool:
    """True when octave folding cannot place the estimate inside the band."""
    lo, hi = band
    folded = fold_tempo(bpm, band)
    return not (lo <= folded <= hi)


def estimate_key(chroma_mean: np.ndarray) -> tuple[str, float]:
    best_key, best_r = "?", -2.0
    for i in range(12):
        rolled = np.roll(chroma_mean, -i)
        for profile, mode in ((KRUMHANSL_MAJOR, "major"), (KRUMHANSL_MINOR, "minor")):
            r = float(np.corrcoef(rolled, profile)[0, 1])
            if r > best_r:
                best_key, best_r = f"{PITCHES[i]} {mode}", r
    return best_key, round(best_r, 3)


def bar_grid(t0: float, bar_dur: float, n_bars: int) -> np.ndarray:
    return t0 + bar_dur * np.arange(n_bars + 1)


def band_energy_per_bar(
    power: np.ndarray, freqs: np.ndarray, frame_times: np.ndarray, grid: np.ndarray
) -> dict[str, np.ndarray]:
    """Per-bar RMS in low/mid/high bands, each normalized to its own max."""
    out: dict[str, np.ndarray] = {}
    for name, (lo, hi) in BAND_EDGES_HZ.items():
        mask = freqs >= lo if hi is None else (freqs >= lo) & (freqs < hi)
        band = np.sqrt(power[mask].mean(axis=0) + 1e-12)
        bars = np.zeros(len(grid) - 1)
        for b, (start, end) in enumerate(zip(grid[:-1], grid[1:])):
            sel = (frame_times >= start) & (frame_times < end)
            bars[b] = float(band[sel].mean()) if sel.any() else 0.0
        out[name] = bars / (bars.max() + 1e-12)
    return out


def bar_feature_matrix(
    chroma: np.ndarray, mfcc: np.ndarray, frame_times: np.ndarray, grid: np.ndarray
) -> np.ndarray:
    """Per-bar unit-normalized chroma+mfcc features for novelty segmentation."""
    feats = []
    dim = chroma.shape[0] + mfcc.shape[0]
    for start, end in zip(grid[:-1], grid[1:]):
        sel = (frame_times >= start) & (frame_times < end)
        if not sel.any():
            feats.append(np.zeros(dim))
            continue
        c = chroma[:, sel].mean(axis=1)
        m = mfcc[:, sel].mean(axis=1)
        c = c / (np.linalg.norm(c) + 1e-12)
        m = m / (np.linalg.norm(m) + 1e-12)
        feats.append(np.concatenate([c, m]))
    return np.array(feats)


def section_boundaries(
    feats: np.ndarray, window: int = 8, snap: int = 4, min_gap: int = 8
) -> list[int]:
    """Novelty peaks between bar-window means, snapped to phrase multiples."""
    n = len(feats)
    novelty = np.zeros(n)
    for b in range(window, n - window):
        before = feats[b - window : b].mean(axis=0)
        after = feats[b : b + window].mean(axis=0)
        novelty[b] = float(np.linalg.norm(after - before))
    thresh = novelty.mean() + 0.8 * novelty.std()
    bounds: list[int] = []
    for b in range(window, n - window):
        if novelty[b] >= thresh and novelty[b] == novelty[max(0, b - 4) : b + 5].max():
            snapped = int(round(b / snap) * snap)
            if not bounds or snapped - bounds[-1] >= min_gap:
                bounds.append(snapped)
    return bounds


def label_section(low: float, mid: float, high: float, idx: int, total: int) -> str:
    if idx == 0:
        return "intro"
    if idx == total - 1:
        return "outro"
    if low < 0.35:
        return "break"
    if low > 0.75 and mid > 0.6:
        return "peak"
    return "groove"


def events_per_bar(times: np.ndarray, t0: float, bar_dur: float, n_bars: int) -> np.ndarray:
    counts = np.zeros(n_bars, dtype=int)
    for t in np.asarray(times, dtype=float):
        bar = int((t - t0) / bar_dur)
        if 0 <= bar < n_bars:
            counts[bar] += 1
    return counts


def presence_gaps(present: np.ndarray, min_len: int = 2) -> list[tuple[int, int]]:
    """Absent spans as 1-indexed inclusive (start, end) bars, short gaps dropped."""
    gaps: list[tuple[int, int]] = []
    start: int | None = None
    present = np.asarray(present, dtype=bool)
    for i, p in enumerate(present):
        if not p and start is None:
            start = i
        elif p and start is not None:
            if i - start >= min_len:
                gaps.append((start + 1, i))
            start = None
    if start is not None and len(present) - start >= min_len:
        gaps.append((start + 1, len(present)))
    return gaps


def segment_notes(step_pitch: np.ndarray) -> list[tuple[int, int, int]]:
    """Merge consecutive equal step pitches into (start_step, length, midi) notes.

    Steps with pitch < 0 are unvoiced.
    """
    notes: list[tuple[int, int, int]] = []
    step_pitch = np.asarray(step_pitch, dtype=int)
    s, n = 0, len(step_pitch)
    while s < n:
        if step_pitch[s] < 0:
            s += 1
            continue
        pitch, start = int(step_pitch[s]), s
        while s < n and step_pitch[s] == pitch:
            s += 1
        notes.append((start, s - start, pitch))
    return notes


def note_stats(notes: list[tuple[int, int, int]], n_steps: int) -> dict:
    pcs = np.zeros(12)
    for _, length, pitch in notes:
        pcs[pitch % 12] += length
    lengths = np.array([n[1] for n in notes]) if notes else np.array([0])
    voiced_steps = int(sum(n[1] for n in notes))
    midis = [n[2] for n in notes]
    share = {}
    if pcs.sum():
        for i in np.argsort(pcs)[::-1][:4]:
            share[PITCHES[int(i)]] = round(float(pcs[i] / pcs.sum()), 2)
    return {
        "tonic_candidate": PITCHES[int(pcs.argmax())] if pcs.sum() else "?",
        "pitch_class_share": share,
        "step_occupancy": round(voiced_steps / max(1, n_steps), 2),
        "note_len_16ths_median": float(np.median(lengths)),
        "share_one_step_notes": round(float((lengths == 1).mean()), 2),
        "midi_range": [int(min(midis)), int(max(midis))] if midis else None,
        "note_count": len(notes),
    }


def match_triad(chroma_vec: np.ndarray) -> tuple[str, float]:
    c = chroma_vec / (np.linalg.norm(chroma_vec) + 1e-12)
    best, best_score = "?", -1.0
    for i in range(12):
        for tpl, suffix in ((MAJOR_TRIAD, ""), (MINOR_TRIAD, "m")):
            score = float(np.dot(c, np.roll(tpl / np.linalg.norm(tpl), i)))
            if score > best_score:
                best, best_score = f"{PITCHES[i]}{suffix}", score
    return best, round(best_score, 3)


def active_ranges(
    per_bar: np.ndarray, thresh: float = 0.3, min_len: int = 2
) -> list[tuple[int, int]]:
    """1-indexed inclusive bar ranges where normalized activity exceeds thresh."""
    values = np.asarray(per_bar, dtype=float)
    values = values / (values.max() + 1e-12)
    return [
        (a, b)
        for a, b in _runs(values > thresh)
        if b - a + 1 >= min_len
    ]


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    start: int | None = None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        elif not m and start is not None:
            out.append((start + 1, i))
            start = None
    if start is not None:
        out.append((start + 1, len(mask)))
    return out
