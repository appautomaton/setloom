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
from typing import TYPE_CHECKING

from setloom.parts.base import groove_vocabulary
from setloom.schema import TrackSpec

if TYPE_CHECKING:
    from setloom.stylepack import StylePack

KICK = 36
CLOSED_HAT = 42
OPEN_HAT = 46  # offbeat sizzle in drop/peak (style.yml groove.percussion.offbeat_open_hat)
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


def _track_drums_plan(spec: TrackSpec):
    groove = getattr(spec, "groove", None)
    if groove is None or groove.drums is None:
        return None
    return groove.drums


def _custom_perc_patterns(spec: TrackSpec):
    plan = _track_drums_plan(spec)
    if plan is None or not plan.percussion_patterns:
        return None
    return tuple(
        tuple(tuple(int(step) for step in bar) for bar in pattern)
        for pattern in plan.percussion_patterns
        if pattern
    )


class DrumsGenerator:
    name = "drums"

    def generate(
        self, spec: TrackSpec, rng: random.Random, pack: "StylePack | None" = None
    ) -> list[NoteEvent]:
        vocab = groove_vocabulary(pack) or {}
        plan = _track_drums_plan(spec)
        phrase_bars = (plan.phrase_bars if plan and plan.phrase_bars else None) or vocab.get(
            "phrase_bars", 8
        )
        perc_patterns = _custom_perc_patterns(spec) or PERC_PATTERNS
        drums_vocab = vocab.get("drums", {})
        phrase_end_vocab = drums_vocab.get("phrase_end", {})
        hat_breath = bool(phrase_end_vocab.get("groove_hat_breath"))
        bed_accents = phrase_end_vocab.get("bed_accent_steps") or ()
        break_kick_fractions = drums_vocab.get("break_accent_kicks") or ()

        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            kick = not section.startswith("break")
            hats = section.startswith(("groove", "drop", "peak"))
            hat_bed = section.startswith(("drop", "peak"))
            # Corpus signature: lone accent kicks inside the breakdown. Bar
            # positions derive from section length — no rng draws added, so
            # draw counts stay structural.
            accent_kick_bars = (
                {min(bars - 1, int(bars * f)) for f in break_kick_fractions}
                if section.startswith("break") and bars >= 6
                else set()
            )
            # Exactly one rng draw per section keeps draw counts structural.
            pattern = rng.choice(perc_patterns)
            for bar_in_section in range(bars):
                bar = start_bar + bar_in_section
                phrase_end = bar_in_section % phrase_bars == phrase_bars - 1
                if bar_in_section in accent_kick_bars:
                    events.append(
                        NoteEvent(DRUM_CHANNEL, KICK, 104, beat_to_tick(bar, 0), SIXTEENTH_TICKS)
                    )
                for beat in range(4):
                    tick = beat_to_tick(bar, beat)
                    if kick:
                        events.append(NoteEvent(DRUM_CHANNEL, KICK, 112, tick, SIXTEENTH_TICKS))
                    if hats and not hat_bed:
                        if hat_breath and phrase_end and beat == 3:
                            # phrase turn: the last offbeat hat rests, an open
                            # hat marks the corner instead
                            events.append(
                                NoteEvent(
                                    DRUM_CHANNEL,
                                    OPEN_HAT,
                                    64,
                                    tick + EIGHTH_TICKS,
                                    EIGHTH_TICKS,
                                )
                            )
                            continue
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
                    for beat in range(4):  # offbeat open hat: the lane's signature sizzle
                        tick = beat_to_tick(bar, beat) + EIGHTH_TICKS
                        events.append(NoteEvent(DRUM_CHANNEL, OPEN_HAT, 58, tick, EIGHTH_TICKS))
                    if phrase_end:
                        for step, velocity in bed_accents:
                            tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
                            events.append(
                                NoteEvent(
                                    DRUM_CHANNEL, CLOSED_HAT, velocity, tick, SIXTEENTH_TICKS
                                )
                            )
                for step in pattern[bar_in_section % len(pattern)]:
                    if step % 4 == 0:
                        continue
                    tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
                    events.append(
                        NoteEvent(DRUM_CHANNEL, PERC, PERC_VELOCITY, tick, SIXTEENTH_TICKS)
                    )
        return events
