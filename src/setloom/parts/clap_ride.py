# SPDX-License-Identifier: AGPL-3.0-only
"""Shadow backbeat and peak ride (channel 9).

Cross-model mix-architecture review (2026-06-07) + listening take-7 verdict:
a bright clap on every 2 and 4 reads tech-house/EDM, not this lane. The
backbeat is now a SHADOW — a dark rim accent on beats 2 and 4 of every
4th bar, peak sections only, mixed far below the kick. The ride keeps its
peak-only 8ths as restrained shimmer. Zero rng draws: fixed pattern.
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
from typing import TYPE_CHECKING

from setloom.schema import TrackSpec

if TYPE_CHECKING:
    from setloom.stylepack import StylePack

CLAP = 39  # rendered by vibe_clap as a dark rim/clap shadow
RIDE = 51

CLAP_VELOCITY = 64  # shadow, not statement
RIDE_ONBEAT_VELOCITY = 56
RIDE_OFFBEAT_VELOCITY = 68  # offbeat 8th carries the accent

CLAP_BEATS = (1, 3)  # 0-based: beats 2 and 4
CLAP_EVERY_BARS = 4  # phrase accent, not an every-bar backbeat


class ClapRideGenerator:
    name = "clap_ride"

    def generate(
        self, spec: TrackSpec, rng: random.Random, pack: "StylePack | None" = None
    ) -> list[NoteEvent]:
        # rng intentionally unused: deterministic constant pattern, zero draws.
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith("peak"):
                continue
            for bar_in_section in range(bars):
                bar = start_bar + bar_in_section
                if bar_in_section % CLAP_EVERY_BARS == 0:
                    for beat in CLAP_BEATS:
                        tick = beat_to_tick(bar, beat)
                        events.append(
                            NoteEvent(DRUM_CHANNEL, CLAP, CLAP_VELOCITY, tick, SIXTEENTH_TICKS)
                        )
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
