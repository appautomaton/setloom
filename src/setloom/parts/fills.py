# SPDX-License-Identifier: AGPL-3.0-only
"""Fills: a snare/tom run on the last beat of every 16th bar (channel 9)."""

import random

from setloom.midi import DRUM_CHANNEL, SIXTEENTH_TICKS, NoteEvent, beat_to_tick
from setloom.schema import TrackSpec

SNARE = 38
TOM_LOW = 45
TOM_HIGH = 47

FILL_INTERVAL_BARS = 16

# Four 16th-note runs; the seeded pick varies which run lands each phrase.
RUNS = (
    (SNARE, SNARE, TOM_HIGH, TOM_LOW),
    (SNARE, TOM_HIGH, SNARE, TOM_LOW),
    (SNARE, SNARE, SNARE, TOM_HIGH),
    (TOM_HIGH, TOM_HIGH, TOM_LOW, SNARE),
)


class FillsGenerator:
    name = "fills"

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]:
        total_bars = sum(spec.sections.values())
        events: list[NoteEvent] = []
        for bar in range(FILL_INTERVAL_BARS - 1, total_bars, FILL_INTERVAL_BARS):
            run = rng.choice(RUNS)
            for step, note in enumerate(run):
                tick = beat_to_tick(bar, 3) + step * SIXTEENTH_TICKS
                velocity = 80 + 8 * step  # rising into the next phrase
                events.append(NoteEvent(DRUM_CHANNEL, note, velocity, tick, SIXTEENTH_TICKS))
        return events
