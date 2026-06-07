# SPDX-License-Identifier: AGPL-3.0-only
"""Drums: four-on-floor kick, offbeat hats, sparse seeded percussion (channel 9).

The kick plays on every beat of every section that is not a break, so the
intro and outro keep mixable edges. Hats mark the offbeat 8ths in the
energetic sections. Percussion is sparse, seeded, and never lands on a beat
tick, so it can never collide with a kick onset.
"""

import random

from setloom.midi import (
    DRUM_CHANNEL,
    EIGHTH_TICKS,
    PPQ,
    SIXTEENTH_TICKS,
    STEPS_PER_BAR,
    NoteEvent,
    bar_to_tick,
    beat_to_tick,
    section_layout,
)
from setloom.schema import TrackSpec

KICK = 36
CLOSED_HAT = 42
PERC = 39

PERC_PROBABILITY = 0.05


class DrumsGenerator:
    name = "drums"

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]:
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            kick = not section.startswith("break")
            hats = section.startswith(("groove", "drop", "peak"))
            for bar in range(start_bar, start_bar + bars):
                for beat in range(4):
                    tick = beat_to_tick(bar, beat)
                    if kick:
                        events.append(NoteEvent(DRUM_CHANNEL, KICK, 112, tick, SIXTEENTH_TICKS))
                    if hats:
                        events.append(
                            NoteEvent(
                                DRUM_CHANNEL, CLOSED_HAT, 72, tick + EIGHTH_TICKS, SIXTEENTH_TICKS
                            )
                        )
                for step in range(STEPS_PER_BAR):
                    tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
                    if tick % PPQ == 0:
                        continue  # never on kick beats
                    if rng.random() < PERC_PROBABILITY:
                        events.append(NoteEvent(DRUM_CHANNEL, PERC, 56, tick, SIXTEENTH_TICKS))
        return events
