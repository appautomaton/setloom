# SPDX-License-Identifier: AGPL-3.0-only
"""FX: chromatic riser into each drop/peak entry, impact on its downbeat (channel 6).

For every drop_* and peak section entry, a 16th-note chromatic run climbs
from the root at octave 4 across the four bars before the entry bar, with
velocity ramping from ~40 to ~110; the entry downbeat then lands a low root
impact. Nothing plays anywhere else — fx exist only to mark these arrivals
(T01 palette: "noise risers, impacts"; a MIDI approximation until
render-domain sound design). One rng draw per run picks the rise rate: one
semitone every 2 or every 4 steps.
"""

import random

from setloom.midi import (
    SIXTEENTH_TICKS,
    STEPS_PER_BAR,
    TICKS_PER_BAR,
    NoteEvent,
    bar_to_tick,
    section_layout,
)
from setloom.parts.base import root_note
from typing import TYPE_CHECKING

from setloom.schema import TrackSpec

if TYPE_CHECKING:
    from setloom.stylepack import StylePack

FX_CHANNEL = 6

RISER_BARS = 4
RISER_OCTAVE = 4
RISER_VELOCITY_LO = 40
RISER_VELOCITY_HI = 110
STEPS_PER_SEMITONE_OPTIONS = (2, 4)  # contour speed: semitone every 2 or 4 steps

IMPACT_OCTAVE = 1
IMPACT_VELOCITY = 120


class FxGenerator:
    name = "fx"

    def generate(
        self, spec: TrackSpec, rng: random.Random, pack: "StylePack | None" = None
    ) -> list[NoteEvent]:
        riser_root = root_note(spec.key, RISER_OCTAVE)
        impact_note = root_note(spec.key, IMPACT_OCTAVE)
        # Exactly one rng draw per run keeps draw counts structural.
        steps_per_semitone = rng.choice(STEPS_PER_SEMITONE_OPTIONS)
        run_steps = RISER_BARS * STEPS_PER_BAR
        events: list[NoteEvent] = []
        for section, (start_bar, _) in section_layout(spec).items():
            if not section.startswith(("drop", "peak")):
                continue
            if start_bar >= RISER_BARS:  # guard: a full riser must fit before the entry
                run_start = bar_to_tick(start_bar - RISER_BARS)
                for step in range(run_steps):
                    note = riser_root + step // steps_per_semitone
                    velocity = (
                        RISER_VELOCITY_LO
                        + (RISER_VELOCITY_HI - RISER_VELOCITY_LO) * step // (run_steps - 1)
                    )
                    tick = run_start + step * SIXTEENTH_TICKS
                    events.append(NoteEvent(FX_CHANNEL, note, velocity, tick, SIXTEENTH_TICKS))
            events.append(
                NoteEvent(
                    FX_CHANNEL,
                    impact_note,
                    IMPACT_VELOCITY,
                    bar_to_tick(start_bar),
                    TICKS_PER_BAR // 2,
                )
            )
        return events
