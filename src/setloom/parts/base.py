# SPDX-License-Identifier: AGPL-3.0-only
"""Part-generator Protocol, per-part RNG derivation, and shared key helpers."""

import random
from typing import Protocol

from setloom.midi import NoteEvent
from setloom.schema import TrackSpec

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

TRIADS = {"minor": (0, 3, 7), "major": (0, 4, 7)}

SCALES = {
    "minor": (0, 2, 3, 5, 7, 8, 10),  # natural minor
    "major": (0, 2, 4, 5, 7, 9, 11),
}


class PartGenerator(Protocol):
    """One musical part: a name and a deterministic event generator."""

    name: str

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]: ...


def part_rng(seed: int, variant: int, part: str) -> random.Random:
    """Derive the per-part RNG from (seed, variant, part).

    String seeding hashes via SHA-512 inside ``random.seed``, so streams are
    stable across processes and platforms. Variant plumbing arrives with the
    generate CLI; variant 0 is the default for direct use.
    """
    return random.Random(f"{seed}:{variant}:{part}")


def parse_key(key: str) -> tuple[int, str]:
    """Parse a key like ``"D minor"`` into (pitch_class, quality)."""
    tonic, _, quality = key.strip().partition(" ")
    quality = quality.strip().lower()
    pitch_class = PITCH_CLASSES.get(tonic)
    if pitch_class is None or quality not in TRIADS:
        raise ValueError(f"unsupported key: {key!r} (expected e.g. 'D minor')")
    return pitch_class, quality


def root_note(key: str, octave: int) -> int:
    """MIDI note of the key tonic at ``octave`` (C4 = 60 convention)."""
    pitch_class, _ = parse_key(key)
    return 12 * (octave + 1) + pitch_class
