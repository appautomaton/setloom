# SPDX-License-Identifier: AGPL-3.0-only
"""Chords: seeded diatonic progression with color voicings (channel 2).

One progression, one chord color, and one harmonic rhythm (4 or 8 bars) are
drawn per run (style.yml harmony_and_melody.harmonic_rhythm_bars and
chord_colors). Breaks sustain each chord as a whole pad across its span;
drops and peak reduce density to one short offbeat stab per bar so the bass
and arp keep the foreground.
"""

import random

from setloom.midi import (
    EIGHTH_TICKS,
    PPQ,
    TICKS_PER_BAR,
    NoteEvent,
    bar_to_tick,
    section_layout,
)
from setloom.parts.base import SCALES, parse_key
from setloom.schema import TrackSpec

CHORD_OCTAVE = 4  # mid register
PAD_VELOCITY = 64  # modest pad level in breaks
STAB_VELOCITY = 70  # short offbeat stabs in drops/peak
PEAK_BED_VELOCITY = 46  # soft sustained bed an octave up, under the peak stabs

# Diatonic progressions as 0-based scale degrees, e.g. minor i-VI-III-VII.
PROGRESSIONS = {
    "minor": (
        (0, 5, 2, 6),  # i-VI-III-VII
        (0, 6, 5, 6),  # i-VII-VI-VII
        (0, 5, 6, 4),  # i-VI-VII-v
        (0, 2, 6, 5),  # i-III-VII-VI
    ),
    "major": (
        (0, 5, 3, 4),  # I-vi-IV-V
        (0, 4, 5, 3),  # I-V-vi-IV
    ),
}

# Chord colors after style.yml harmony_and_melody.chord_colors (assumption:
# model-knowledge, cross-model review 2026-06-07). Deliberate divergences:
# "minor_triad" is generalized to "triad" (diatonic quality comes from the
# scale degree) and "no_third_power_stack" is deferred to a later pass.
COLORS = ("triad", "sus2", "sus4", "add9")

# Harmonic rhythm options in bars per full PROGRESSION cycle — note the unit:
# style.yml harmony_and_melody.harmonic_rhythm_bars [4, 8, 16] reads as
# bars-per-cycle here; 16 is dropped because a 16-bar cycle over 4 chords
# (4 bars per chord) exceeds the drop/peak density this v1 targets.
HARMONIC_RHYTHM_BARS = (4, 8)


def _scale_offset(scale: tuple[int, ...], degree: int) -> int:
    """Semitone offset of a (possibly octave-wrapped) scale degree."""
    return scale[degree % 7] + 12 * (degree // 7)


def chord_tones(scale: tuple[int, ...], degree: int, color: str) -> tuple[int, ...]:
    """Semitone offsets from the key tonic for a colored diatonic chord."""
    root = _scale_offset(scale, degree)
    fifth = _scale_offset(scale, degree + 4)
    if color == "sus2":
        return (root, _scale_offset(scale, degree + 1), fifth)
    if color == "sus4":
        return (root, _scale_offset(scale, degree + 3), fifth)
    third = _scale_offset(scale, degree + 2)
    if color == "add9":
        return (root, third, fifth, _scale_offset(scale, degree + 8))
    return (root, third, fifth)


class ChordsGenerator:
    name = "chords"

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]:
        pitch_class, quality = parse_key(spec.key)
        scale = SCALES[quality]
        base = 12 * (CHORD_OCTAVE + 1) + pitch_class
        # Exactly three rng draws per run keeps draw counts structural.
        progression = rng.choice(PROGRESSIONS[quality])
        if len(progression) != 4:  # HARMONIC_RHYTHM_BARS semantics assume 4-chord cycles
            raise ValueError(f"progressions must have 4 chords, got {len(progression)}")
        color = rng.choice(COLORS)
        bars_per_chord = rng.choice(HARMONIC_RHYTHM_BARS) // len(progression)
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith(("break", "drop", "peak")):
                continue
            # Texture per section: breaks sustain, drops stab, peak does BOTH —
            # the climax keeps a harmonic bed under the stabs (listening note
            # 2026-06-07: peak "too simplistic"). The peak bed sits an octave
            # above the stabs so same-pitch note pairing never collides and the
            # low mids stay clear (review_vocabulary.overfilled_low_mids).
            sustained = section.startswith(("break", "peak"))
            stabs = section.startswith(("drop", "peak"))
            bed_lift = 12 if section.startswith("peak") else 0
            for bar_in_section in range(bars):
                bar = start_bar + bar_in_section
                degree = progression[(bar_in_section // bars_per_chord) % len(progression)]
                tones = chord_tones(scale, degree, color)
                if sustained and bar_in_section % bars_per_chord == 0:
                    span_bars = min(bars_per_chord, bars - bar_in_section)
                    velocity = PEAK_BED_VELOCITY if bed_lift else PAD_VELOCITY
                    for tone in tones:
                        events.append(
                            NoteEvent(
                                2,
                                base + bed_lift + tone,
                                velocity,
                                bar_to_tick(bar),
                                span_bars * TICKS_PER_BAR,
                            )
                        )
                if stabs:
                    tick = bar_to_tick(bar) + 2 * PPQ + EIGHTH_TICKS  # the "and" of beat 3
                    for tone in tones:
                        events.append(NoteEvent(2, base + tone, STAB_VELOCITY, tick, EIGHTH_TICKS))
        return events
