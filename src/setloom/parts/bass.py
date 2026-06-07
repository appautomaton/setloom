# SPDX-License-Identifier: AGPL-3.0-only
"""Bass: root-note offbeat 8ths in the energetic sections (channel 1).

Every onset sits on the "and" of a beat, so by construction bass never
shares a tick with kick onsets, which sit on the beats themselves.
"""

import random

from setloom.midi import EIGHTH_TICKS, NoteEvent, beat_to_tick, section_layout
from setloom.parts.base import root_note
from setloom.schema import TrackSpec

BASS_OCTAVE = 2  # D minor -> D2 = 38


class BassGenerator:
    name = "bass"

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]:
        root = root_note(spec.key, BASS_OCTAVE)
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith(("groove", "drop", "peak")):
                continue
            for bar in range(start_bar, start_bar + bars):
                for beat in range(4):
                    tick = beat_to_tick(bar, beat) + EIGHTH_TICKS
                    events.append(NoteEvent(1, root, 96, tick, EIGHTH_TICKS))
        return events
