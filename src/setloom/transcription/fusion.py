# SPDX-License-Identifier: AGPL-3.0-only
"""Experimental fusion of two transcription note lists.

Union the candidates, merge nearby same-pitch attacks, coordinate chord onsets,
and score support using cross-engine agreement, velocity, duration, and estimated
key. Octave suppression and timing coordination can remove valid notes or change
articulation. These heuristics require listening review and remain opt-in.

The defaults came from a small local listening study. Callers may supply their
own parameters or scale; any pair of ``TranscribedNote`` sequences can be used.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from setloom.conductor import SCALES
from setloom.transcription.basic_pitch import TranscribedNote

# Defaults from one clean piano solo and three separated stems, not a general benchmark.
RECALL_FIRST: dict[str, float] = {
    "tol_support": 0.07,  # s: corroboration window in the other engine (+/- 1 semitone)
    "tol_merge": 0.05,    # s: same-pitch duplicate-merge window (onset proximity)
    "chord_win": 0.04,    # s: snap near-simultaneous attacks to a shared time
    "min_dur": 0.035,     # s: hard-drop sub-articulation blips
    "min_vel": 20,        # /127: hard-drop near-silent artifacts
    "floor": 0.40,        # keep when the support score clears this single fixed bar
    "octave_win": 0.12,   # s: octave-ghost overlap window
}

# Krumhansl-Schmuckler major/minor key profiles for duration-weighted key detection.
_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_PITCH_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def _dur(note: TranscribedNote) -> float:
    return note.end_s - note.start_s


def detect_key(notes: Sequence[TranscribedNote]) -> tuple[str, frozenset[int]]:
    """Krumhansl key estimate over duration-weighted pitch classes.

    Returns ``(label, scale_pitch_classes)`` where the label is like ``"A minor"`` and the
    scale offsets come from :data:`setloom.conductor.SCALES`. An empty note-list defaults
    to C major.
    """
    weight = np.zeros(12)
    for note in notes:
        weight[note.pitch % 12] += max(0.0, _dur(note))
    if weight.sum() <= 0:
        return "C major", frozenset(SCALES["major"])
    best = max(
        [(float(np.corrcoef(weight, np.roll(_KS_MAJOR, r))[0, 1]), r, "major") for r in range(12)]
        + [(float(np.corrcoef(weight, np.roll(_KS_MINOR, r))[0, 1]), r, "minor") for r in range(12)]
    )
    _, root, quality = best
    pcs = frozenset((root + off) % 12 for off in SCALES[quality])
    return f"{_PITCH_NAMES[root]} {quality}", pcs


def _corroborated(
    note: TranscribedNote, others: Sequence[TranscribedNote], tol_t: float, tol_p: int = 1
) -> bool:
    """True if the other engine has a note within ``tol_t`` seconds and ``tol_p`` semitones."""
    return any(
        abs(o.start_s - note.start_s) <= tol_t and abs(o.pitch - note.pitch) <= tol_p
        for o in others
    )


def fuse_recall_first(
    rhythm_notes: Sequence[TranscribedNote],
    pitch_notes: Sequence[TranscribedNote],
    *,
    scale_pcs: frozenset[int] | None = None,
    params: dict[str, float] | None = None,
) -> tuple[TranscribedNote, ...]:
    """Reconcile a rhythm-engine and a pitch-engine note-list into one note-list.

    ``rhythm_notes`` (e.g. Kong) drive timing; ``pitch_notes`` (e.g. Basic Pitch) drive
    which pitch. Returns the kept notes sorted by ``(start_s, pitch)``. ``scale_pcs``
    defaults to a Krumhansl estimate over ``pitch_notes``; ``params`` defaults to the
    :data:`RECALL_FIRST` defaults.
    """
    prm = {**RECALL_FIRST, **(params or {})}
    if scale_pcs is None:
        scale_pcs = detect_key(pitch_notes)[1]
    rhy, pit = list(rhythm_notes), list(pitch_notes)

    # 1) Union candidates, merged per pitch by ONSET proximity -- a same-pitch note within
    #    tol_merge of the anchor is the same strike seen by both engines (a duplicate), not
    #    a later re-strike, so repeated notes survive.
    tagged = [(n, "r") for n in rhy] + [(n, "p") for n in pit]
    by_pitch: dict[int, list[tuple[TranscribedNote, str]]] = {}
    for note, tag in tagged:
        by_pitch.setdefault(note.pitch, []).append((note, tag))
    merged: list[tuple[TranscribedNote, set[str]]] = []
    for pitch, group in by_pitch.items():
        group.sort(key=lambda item: item[0].start_s)
        i = 0
        while i < len(group):
            anchor, head = group[i][0].start_s, group[i][0]
            end, vel, conf, srcs = head.end_s, head.velocity, head.confidence, {group[i][1]}
            j = i + 1
            while j < len(group) and group[j][0].start_s - anchor <= prm["tol_merge"]:
                other, tag = group[j]
                end = max(end, other.end_s)
                vel = max(vel, other.velocity)
                conf = max(conf, other.confidence)
                srcs.add(tag)
                j += 1
            merged.append((TranscribedNote(anchor, end, pitch, vel, conf), srcs))
            i = j

    # 2) Cross-support flag + chord-coordination anchors (cluster on the FIRST start so a
    #    dense passage cannot chain into one giant cluster).
    scored: list[tuple[TranscribedNote, set[str], bool]] = []
    for note, srcs in merged:
        cross = ("r" in srcs and "p" in srcs) or _corroborated(
            note, pit if "p" not in srcs else rhy, prm["tol_support"]
        )
        scored.append((note, srcs, cross))
    anchors: dict[float, float] = {}
    starts = sorted({n.start_s for n, _, _ in scored})
    if starts:
        cluster = [starts[0]]
        for s in starts[1:]:
            if s - cluster[0] <= prm["chord_win"]:
                cluster.append(s)
            else:
                anchors.update({x: cluster[len(cluster) // 2] for x in cluster})
                cluster = [s]
        anchors.update({x: cluster[len(cluster) // 2] for x in cluster})

    # 3) Keep-unless-artifact: fixed hard drops, then one fixed support floor.
    kept: list[tuple[TranscribedNote, float, bool]] = []
    for note, srcs, cross in scored:
        if _dur(note) < prm["min_dur"] or note.velocity < prm["min_vel"]:
            continue
        support = (
            (1.0 if cross else 0.3)
            + 0.4 * (note.velocity / 127.0)
            + 0.2 * min(1.0, _dur(note) / 0.15)
            + (0.15 if (note.pitch % 12) in scale_pcs else -0.1)
            + (0.15 if "r" in srcs else 0.0)  # small rhythm-engine existence bias
        )
        if support < prm["floor"]:
            continue
        snapped = anchors.get(note.start_s, note.start_s)
        start = snapped if snapped < note.end_s else note.start_s
        snapped_note = TranscribedNote(start, note.end_s, note.pitch, note.velocity, note.confidence)
        kept.append((snapped_note, support, cross))

    # 4) Octave-ghost suppression: drop the UPPER note of an overlapping p / p+12 pair only
    #    when it is uncorroborated AND weaker (a likely 2nd-harmonic ghost). Cross-supported
    #    musical octaves and the lower fundamental are always kept.
    kept.sort(key=lambda item: (item[0].start_s, item[0].pitch))
    drop: set[int] = set()
    for i in range(len(kept)):
        if i in drop:
            continue
        lower, lower_support, _ = kept[i]
        for j in range(i + 1, len(kept)):
            upper, upper_support, upper_cross = kept[j]
            if upper.start_s > lower.end_s + prm["octave_win"]:
                break
            if j in drop or upper.pitch - lower.pitch != 12:
                continue
            overlaps = (
                lower.start_s < upper.end_s + prm["octave_win"]
                and upper.start_s < lower.end_s + prm["octave_win"]
            )
            if overlaps and (not upper_cross) and upper_support <= lower_support:
                drop.add(j)
    survivors = [kept[k][0] for k in range(len(kept)) if k not in drop]
    return tuple(sorted(survivors, key=lambda n: (n.start_s, n.pitch)))
