# SPDX-License-Identifier: AGPL-3.0-only
"""Fills: transition-aware variants in the final bar of each section (channel 9).

One seeded variant per section transition (every section except the last):
a rising snare roll, a sparse hat roll, a restrained low impact, or silence.
No timer-based fills; per style.yml rejection rule `unphrased-fills`, fills
exist only to mark section transitions.
"""

import random

from setloom.midi import (
    DRUM_CHANNEL,
    EIGHTH_TICKS,
    SIXTEENTH_TICKS,
    NoteEvent,
    bar_to_tick,
    beat_to_tick,
    section_layout,
)
from setloom.schema import TrackSpec

SNARE = 38
CLOSED_HAT = 42
TOM_LOW = 45


def _snare_roll(final_bar: int) -> list[NoteEvent]:
    """16th-note snare roll over the last two beats, velocity rising."""
    base = beat_to_tick(final_bar, 2)
    return [
        NoteEvent(DRUM_CHANNEL, SNARE, 72 + 5 * i, base + i * SIXTEENTH_TICKS, SIXTEENTH_TICKS)
        for i in range(8)
    ]


def _hat_roll(final_bar: int) -> list[NoteEvent]:
    """Sparse 8th-note hat roll across the final bar, lifting gently."""
    base = bar_to_tick(final_bar)
    return [
        NoteEvent(DRUM_CHANNEL, CLOSED_HAT, 58 + 4 * i, base + i * EIGHTH_TICKS, SIXTEENTH_TICKS)
        for i in range(8)
    ]


def _impact(final_bar: int) -> list[NoteEvent]:
    """Single restrained low impact on the final beat before the transition."""
    return [NoteEvent(DRUM_CHANNEL, TOM_LOW, 92, beat_to_tick(final_bar, 3), EIGHTH_TICKS)]


def _dropout(final_bar: int) -> list[NoteEvent]:
    """Silence: the transition is marked by the absence of a fill."""
    return []


# Seeded per-transition pick; all variants live inside the section's final bar.
VARIANTS = (_snare_roll, _hat_roll, _impact, _dropout)


class FillsGenerator:
    name = "fills"

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]:
        layout = list(section_layout(spec).items())
        events: list[NoteEvent] = []
        # Exactly one rng draw per transition keeps draw counts structural.
        for _, (start_bar, bars) in layout[:-1]:
            variant = rng.choice(VARIANTS)
            events.extend(variant(start_bar + bars - 1))
        return events
