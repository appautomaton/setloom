# SPDX-License-Identifier: AGPL-3.0-only
"""Shaker: 16th-note texture bed in grooves, drops, and peak (channel 9).

GM maracas (70) play every 16th step with a per-beat velocity contour, so
the bed breathes instead of flat-lining. One contour is drawn per run.
Shaker onsets may land on beat ticks: this is texture riding the groove,
not a voice competing with the kick — the bass/perc avoid-kick invariants
are about foreground onsets and stay untouched.
"""

import random

from setloom.midi import (
    DRUM_CHANNEL,
    SIXTEENTH_TICKS,
    STEPS_PER_BAR,
    NoteEvent,
    bar_to_tick,
    section_layout,
)
from typing import TYPE_CHECKING

from setloom.schema import TrackSpec

if TYPE_CHECKING:
    from setloom.stylepack import StylePack

MARACAS = 70  # GM percussion

# Velocity contours indexed by step-within-beat: downbeat push, soft inner
# 16ths, a lift on the offbeat 8th. All contours are deliberately nonflat.
CONTOURS = (
    (72, 48, 58, 48),
    (70, 44, 62, 50),
    (66, 52, 74, 52),
)


class ShakerGenerator:
    name = "shaker"

    def generate(
        self, spec: TrackSpec, rng: random.Random, pack: "StylePack | None" = None
    ) -> list[NoteEvent]:
        # Exactly one rng draw per run keeps draw counts structural.
        contour = rng.choice(CONTOURS)
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith(("groove", "drop", "peak")):
                continue
            for bar in range(start_bar, start_bar + bars):
                for step in range(STEPS_PER_BAR):
                    tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
                    events.append(
                        NoteEvent(DRUM_CHANNEL, MARACAS, contour[step % 4], tick, SIXTEENTH_TICKS)
                    )
        return events
