# SPDX-License-Identifier: AGPL-3.0-only
"""Clap and ride: backbeat claps in drops and peak, ride 8ths at peak (channel 9).

Claps (GM 39) mark beats 2 and 4 wherever the floor is open (drop_* and
peak); the ride (GM 51) joins on 8ths in peak only, offbeat-accented, as the
top-end lift that separates the peak from the drops. The pattern is a fixed
constant, so this generator consumes zero rng draws — adding or reordering
it can never shift another part's seeded stream.
"""

import random

from setloom.midi import (
    DRUM_CHANNEL,
    EIGHTH_TICKS,
    SIXTEENTH_TICKS,
    NoteEvent,
    beat_to_tick,
    section_layout,
)
from setloom.schema import TrackSpec

CLAP = 39  # GM hand clap
RIDE = 51  # GM ride cymbal 1

CLAP_VELOCITY = 92
RIDE_ONBEAT_VELOCITY = 56
RIDE_OFFBEAT_VELOCITY = 68  # offbeat 8th carries the accent

CLAP_BEATS = (1, 3)  # 0-based: beats 2 and 4 of the bar


class ClapRideGenerator:
    name = "clap_ride"

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]:
        # rng intentionally unused: deterministic constant pattern, zero draws.
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith(("drop", "peak")):
                continue
            ride = section.startswith("peak")
            for bar in range(start_bar, start_bar + bars):
                for beat in CLAP_BEATS:
                    tick = beat_to_tick(bar, beat)
                    events.append(
                        NoteEvent(DRUM_CHANNEL, CLAP, CLAP_VELOCITY, tick, SIXTEENTH_TICKS)
                    )
                if not ride:
                    continue
                for beat in range(4):
                    tick = beat_to_tick(bar, beat)
                    events.append(
                        NoteEvent(DRUM_CHANNEL, RIDE, RIDE_ONBEAT_VELOCITY, tick, SIXTEENTH_TICKS)
                    )
                    events.append(
                        NoteEvent(
                            DRUM_CHANNEL,
                            RIDE,
                            RIDE_OFFBEAT_VELOCITY,
                            tick + EIGHTH_TICKS,
                            SIXTEENTH_TICKS,
                        )
                    )
        return events
