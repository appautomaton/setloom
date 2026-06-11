# SPDX-License-Identifier: AGPL-3.0-only
"""Pad: sustained tonic-pedal harmonic bed in breaks, drops, and peak (channel 5).

The pad holds a root + fifth + ninth stack on the key tonic — the
"no_third_power_stack" color from style.yml harmony_and_melody.chord_colors.
Omitting the third keeps the stack quality-neutral, so the bed can never
clash with whatever diatonic progression the chords part drew for the same
run. One note length (2 or 4 bars) is drawn per run; velocity stays soft and
lifts slightly at peak. This is the harmonic floor the first listening notes
said the peak lacked.
"""

import random

from setloom.midi import TICKS_PER_BAR, NoteEvent, bar_to_tick, section_layout
from setloom.parts.base import parse_key
from typing import TYPE_CHECKING

from setloom.schema import TrackSpec

if TYPE_CHECKING:
    from setloom.stylepack import StylePack

PAD_CHANNEL = 5
PAD_OCTAVE = 3  # root below the chords part's octave 4

# Tonic stack offsets in semitones: root, fifth, ninth — deliberately no
# third (see module docstring: quality-neutral against any progression).
STACK_OFFSETS = (0, 7, 14)

PAD_VELOCITY = 50  # soft bed
PEAK_VELOCITY = 58  # slightly louder under the peak

NOTE_BARS_OPTIONS = (2, 4)


class PadGenerator:
    name = "pad"

    def generate(
        self, spec: TrackSpec, rng: random.Random, pack: "StylePack | None" = None
    ) -> list[NoteEvent]:
        pitch_class, _ = parse_key(spec.key)
        base = 12 * (PAD_OCTAVE + 1) + pitch_class
        # Exactly one rng draw per run keeps draw counts structural.
        note_bars = rng.choice(NOTE_BARS_OPTIONS)
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith(("break", "drop", "peak")):
                continue
            velocity = PEAK_VELOCITY if section.startswith("peak") else PAD_VELOCITY
            for bar_in_section in range(0, bars, note_bars):
                # Clamp the last note so it never overflows the section.
                span_bars = min(note_bars, bars - bar_in_section)
                tick = bar_to_tick(start_bar + bar_in_section)
                duration = span_bars * TICKS_PER_BAR
                for offset in STACK_OFFSETS:
                    events.append(NoteEvent(PAD_CHANNEL, base + offset, velocity, tick, duration))
        return events
