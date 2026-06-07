# SPDX-License-Identifier: AGPL-3.0-only
"""Chords: whole-bar sustained triad pads in breaks, drops, and peak (channel 2)."""

import random

from setloom.midi import TICKS_PER_BAR, NoteEvent, bar_to_tick, section_layout
from setloom.parts.base import TRIADS, parse_key
from setloom.schema import TrackSpec

CHORD_OCTAVE = 4  # mid register
CHORD_VELOCITY = 64  # modest pad level


class ChordsGenerator:
    name = "chords"

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]:
        pitch_class, quality = parse_key(spec.key)
        root = 12 * (CHORD_OCTAVE + 1) + pitch_class
        triad = TRIADS[quality]
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith(("break", "drop", "peak")):
                continue
            for bar in range(start_bar, start_bar + bars):
                tick = bar_to_tick(bar)
                for interval in triad:
                    events.append(
                        NoteEvent(2, root + interval, CHORD_VELOCITY, tick, TICKS_PER_BAR)
                    )
        return events
