# SPDX-License-Identifier: AGPL-3.0-only
"""Lead: seeded motif from a pattern bank, placed sparsely (channel 4).

One motif statement opens each 8-bar block of break and peak sections.
Motifs are (scale_degree, start_16th, duration_16ths) tuples spanning one
bar; degrees walk the natural minor or major scale at octave 5.
"""

import random

from setloom.midi import SIXTEENTH_TICKS, NoteEvent, bar_to_tick, section_layout
from setloom.parts.base import SCALES, parse_key
from setloom.schema import TrackSpec

LEAD_OCTAVE = 5
MOTIF_SPACING_BARS = 8

# Pattern bank: each motif is one bar of (scale_degree, start_16th, dur_16ths).
MOTIFS = (
    ((0, 0, 3), (3, 4, 3), (2, 8, 3), (0, 12, 4)),
    ((4, 0, 2), (2, 4, 2), (0, 6, 4), (1, 12, 4)),
    ((0, 0, 2), (2, 2, 2), (4, 4, 4), (7, 8, 6)),
    ((7, 0, 3), (5, 4, 3), (4, 8, 2), (2, 10, 2), (0, 12, 4)),
)


class LeadGenerator:
    name = "lead"

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]:
        pitch_class, quality = parse_key(spec.key)
        scale = SCALES[quality]
        base = 12 * (LEAD_OCTAVE + 1) + pitch_class
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith(("break", "peak")):
                continue
            for block in range(bars // MOTIF_SPACING_BARS):
                motif = rng.choice(MOTIFS)
                bar = start_bar + block * MOTIF_SPACING_BARS
                for degree, start_16th, dur_16ths in motif:
                    note = base + 12 * (degree // len(scale)) + scale[degree % len(scale)]
                    tick = bar_to_tick(bar) + start_16th * SIXTEENTH_TICKS
                    events.append(NoteEvent(4, note, 84, tick, dur_16ths * SIXTEENTH_TICKS))
        return events
