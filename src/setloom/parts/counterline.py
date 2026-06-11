# SPDX-License-Identifier: AGPL-3.0-only
"""Counterline: sparse answer gestures in lead rests (channel 6)."""

import random

from setloom.conductor import build_conductor
from setloom.midi import SIXTEENTH_TICKS, NoteEvent, bar_to_tick, section_layout
from typing import TYPE_CHECKING

from setloom.schema import TrackSpec

if TYPE_CHECKING:
    from setloom.stylepack import StylePack

COUNTER_CHANNEL = 6
COUNTER_OCTAVE = 5
COUNTER_VELOCITY = 68

# Four-bar phrase rest-window answers: start steps avoid the lead's dense heads
# and favor phrase tails, so the counterline reads as response, not another lead.
ANSWER_WINDOWS = (
    (3, 2, 13, 2),  # bar offset, scale-degree offset, start 16th in bar, dur
)
PEAK_WINDOWS = (
    (3, 5, 12, 2),
    (3, 2, 14, 2),
)


class CounterlineGenerator:
    name = "counterline"

    def generate(
        self, spec: TrackSpec, rng: random.Random, pack: "StylePack | None" = None
    ) -> list[NoteEvent]:
        conductor = build_conductor(spec)
        # One draw controls whether the answer leans lower or higher this run.
        register_shift = rng.choice((-12, 0))
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith(("break", "peak")):
                continue
            windows = PEAK_WINDOWS if section.startswith("peak") else ANSWER_WINDOWS
            for period_start in range(0, bars, 16):
                if period_start + 16 > bars:
                    continue
                for phrase_start in (period_start, period_start + 4, period_start + 8, period_start + 12):
                    for bar_offset, degree_offset, step, dur in windows:
                        bar = start_bar + phrase_start + bar_offset
                        chord = conductor.chord_at_bar(bar)
                        note = (
                            conductor.degree_note(chord.degree + degree_offset, COUNTER_OCTAVE)
                            + register_shift
                        )
                        tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
                        energy = conductor.energy_at_bar(bar)
                        velocity = min(92, int(COUNTER_VELOCITY + energy * 12))
                        events.append(NoteEvent(COUNTER_CHANNEL, note, velocity, tick, dur * SIXTEENTH_TICKS))
        return events
