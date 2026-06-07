# SPDX-License-Identifier: AGPL-3.0-only
"""Arp: 16th-note ascending chord-tone arpeggio in drops and peak (channel 3)."""

import random

from setloom.midi import SIXTEENTH_TICKS, NoteEvent, bar_to_tick, section_layout
from setloom.parts.base import TRIADS, parse_key
from setloom.schema import TrackSpec

ARP_OCTAVE = 5
STEPS_PER_BAR = 16
OCTAVE_JUMP_PROBABILITY = 0.08


class ArpGenerator:
    name = "arp"

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]:
        pitch_class, quality = parse_key(spec.key)
        root = 12 * (ARP_OCTAVE + 1) + pitch_class
        tones = TRIADS[quality] + (12,)  # root, third, fifth, octave, ascending
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith(("drop", "peak")):
                continue
            for bar in range(start_bar, start_bar + bars):
                for step in range(STEPS_PER_BAR):
                    note = root + tones[step % len(tones)]
                    if rng.random() < OCTAVE_JUMP_PROBABILITY:
                        note += 12  # seeded octave-jump sparkle
                    tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
                    events.append(NoteEvent(3, note, 78, tick, SIXTEENTH_TICKS))
        return events
