# SPDX-License-Identifier: AGPL-3.0-only
"""Music-theory helpers: key/scale parsing, scale-degree and chord-tone math.

Unopinionated primitives for per-track composition code. No energy curves,
progressions, harmonic-rhythm tables, or arrangement defaults live here — those
are musical decisions that belong to a track's own code and spec, not the
harness. These functions only translate a key and a scale degree into pitches.
"""

from __future__ import annotations

PITCH_CLASSES = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}

SCALES = {
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "major": (0, 2, 4, 5, 7, 9, 11),
}


def parse_key(key: str) -> tuple[int, str]:
    """Parse a key string like 'D minor' into (pitch_class, quality)."""
    tonic, _, quality = key.strip().partition(" ")
    quality = quality.strip().lower()
    pitch_class = PITCH_CLASSES.get(tonic)
    if pitch_class is None or quality not in SCALES:
        raise ValueError(f"unsupported key: {key!r} (expected e.g. 'D minor')")
    return pitch_class, quality


def scale_offset(scale: tuple[int, ...], degree: int) -> int:
    """Semitone offset of a (possibly multi-octave) scale degree from the tonic."""
    return scale[degree % len(scale)] + 12 * (degree // len(scale))


def degree_note(pitch_class: int, scale: tuple[int, ...], degree: int, octave: int) -> int:
    """MIDI note number for a scale degree in a given key and octave."""
    return 12 * (octave + 1) + pitch_class + scale_offset(scale, degree)


def chord_tones(scale: tuple[int, ...], degree: int, color: str = "triad") -> tuple[int, ...]:
    """Semitone offsets (from the tonic) of a diatonic chord on ``degree``.

    ``color`` selects the voicing: triad (default), sus2, sus4, or add9. The
    choice of color per chord is a musical decision for the caller, not a
    harness default.
    """
    root = scale_offset(scale, degree)
    fifth = scale_offset(scale, degree + 4)
    if color == "sus2":
        return (root, scale_offset(scale, degree + 1), fifth)
    if color == "sus4":
        return (root, scale_offset(scale, degree + 3), fifth)
    third = scale_offset(scale, degree + 2)
    if color == "add9":
        return (root, third, fifth, scale_offset(scale, degree + 8))
    return (root, third, fifth)
