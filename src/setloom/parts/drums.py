# SPDX-License-Identifier: AGPL-3.0-only
"""Drums: four-on-floor kick, contoured hats, phrase-patterned percussion (channel 9).

The kick plays on every beat of every section that is not a break, so the
intro and outro keep mixable edges. Hats mark the offbeat 8ths in groove
sections and thicken to an accented 16th bed in drops and peak (style.yml
groove.percussion.closed_hat_16th_bed: section_dependent). Percussion picks
one seeded 2/4/8-bar pattern per section and repeats it (style.yml
groove.percussion.random_percussion: phrase_patterned_only); pattern steps
never land on a beat tick, so they can never collide with a kick onset.
"""

import random

from setloom.midi import (
    DRUM_CHANNEL,
    EIGHTH_TICKS,
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

# Hat velocity contours: index is step-within-beat for the 16th bed (offbeat
# 8th accented), beat-within-bar for the offbeat-8th-only groove hats.
HAT_BED_VELOCITIES = (46, 52, 78, 56)
HAT_OFFBEAT_VELOCITIES = (76, 72, 78, 72)

PERC_VELOCITY = 56

# Percussion pattern bank: per-bar 16th steps inside a 2/4/8-bar phrase.
# Steps avoid multiples of 4 (beat ticks) by construction; every length
# divides 8, so bar N and bar N+8 of a section always share a pattern bar.
PERC_PATTERNS = (
    ((7,), (7, 14)),
    ((3, 11), (3, 11, 14)),
    ((7,), (7,), (7, 10), (7, 14)),
    ((), (7,), (), (7, 14), (), (7,), (3,), (7, 14)),
)


class DrumsGenerator:
    name = "drums"

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]:
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            kick = not section.startswith("break")
            hats = section.startswith(("groove", "drop", "peak"))
            hat_bed = section.startswith(("drop", "peak"))
            # Exactly one rng draw per section keeps draw counts structural.
            pattern = rng.choice(PERC_PATTERNS)
            for bar_in_section in range(bars):
                bar = start_bar + bar_in_section
                for beat in range(4):
                    tick = beat_to_tick(bar, beat)
                    if kick:
                        events.append(NoteEvent(DRUM_CHANNEL, KICK, 112, tick, SIXTEENTH_TICKS))
                    if hats and not hat_bed:
                        velocity = HAT_OFFBEAT_VELOCITIES[beat]
                        events.append(
                            NoteEvent(
                                DRUM_CHANNEL,
                                CLOSED_HAT,
                                velocity,
                                tick + EIGHTH_TICKS,
                                SIXTEENTH_TICKS,
                            )
                        )
                if hats and hat_bed:
                    for step in range(STEPS_PER_BAR):
                        tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
                        velocity = HAT_BED_VELOCITIES[step % 4]
                        events.append(
                            NoteEvent(DRUM_CHANNEL, CLOSED_HAT, velocity, tick, SIXTEENTH_TICKS)
                        )
                for step in pattern[bar_in_section % len(pattern)]:
                    tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
                    events.append(
                        NoteEvent(DRUM_CHANNEL, PERC, PERC_VELOCITY, tick, SIXTEENTH_TICKS)
                    )
        return events
