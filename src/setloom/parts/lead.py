# SPDX-License-Identifier: AGPL-3.0-only
"""Lead: no-vocal melodic-techno period writing on the shared Conductor.

The lead is now a phrase-level vocal substitute, not a two-bar cell loop.
Each full statement is a 16-bar period: A, A-prime, B, A-double-prime.
The Conductor supplies harmonic roots and phrase clock; the seeded draw only
selects a contour variant and small repeat variation rules.
"""

import random
from dataclasses import dataclass

from setloom.conductor import Conductor, build_conductor
from setloom.midi import SIXTEENTH_TICKS, NoteEvent, bar_to_tick, section_layout
from typing import TYPE_CHECKING

from setloom.schema import TrackSpec

if TYPE_CHECKING:
    from setloom.stylepack import StylePack

LEAD_CHANNEL = 4
LEAD_OCTAVE = 5
LEAD_VELOCITY = 84
PHRASE_BARS = 4
PERIOD_BARS = 16


@dataclass(frozen=True)
class Gesture:
    """One melodic gesture in 16th steps from the start of a 4-bar phrase."""

    degree_offset: int
    start_16th: int
    duration_16ths: int
    velocity_delta: int = 0


# Question phrase: climbs to an unresolved chord tone and leaves air at the end.
QUESTION = (
    Gesture(0, 2, 3, -6),
    Gesture(2, 6, 3, -2),
    Gesture(3, 10, 4, 1),
    Gesture(4, 18, 6, 5),
    Gesture(2, 30, 4, -2),
    Gesture(1, 38, 3, -4),
    Gesture(2, 43, 3, 0),
    Gesture(4, 48, 8, 6),
)

# Answer phrase: keeps the rhythm identity but resolves the tail.
ANSWER = (
    Gesture(0, 2, 3, -5),
    Gesture(2, 6, 3, 0),
    Gesture(3, 11, 3, 2),
    Gesture(4, 18, 5, 4),
    Gesture(5, 28, 4, 2),
    Gesture(4, 36, 3, -1),
    Gesture(2, 42, 3, -2),
    Gesture(0, 48, 10, 7),
)

# Contrast phrase: higher register sequence-like movement for the B phrase.
CONTRAST = (
    Gesture(4, 0, 4, 2),
    Gesture(5, 6, 3, 4),
    Gesture(7, 10, 5, 7),
    Gesture(5, 20, 4, 1),
    Gesture(4, 28, 3, -2),
    Gesture(2, 34, 4, -1),
    Gesture(3, 42, 3, 3),
    Gesture(5, 48, 8, 5),
)

PERIOD_PLAN = ("A", "A_PRIME", "B", "A_DOUBLE_PRIME")


def _phrase_template(kind: str) -> tuple[Gesture, ...]:
    if kind == "B":
        return CONTRAST
    if kind == "A_DOUBLE_PRIME":
        return ANSWER
    return QUESTION


def _transform_gesture(gesture: Gesture, phrase_kind: str, statement_index: int) -> Gesture:
    """Keep identity stable while varying exactly one or two dimensions."""
    degree = gesture.degree_offset
    start = gesture.start_16th
    duration = gesture.duration_16ths
    velocity = gesture.velocity_delta
    if phrase_kind == "A_PRIME":
        if start >= 28:
            degree += 1  # tail lift only; keeps the question identity audible
        if start in (38, 43):
            start += 1
    elif phrase_kind == "A_DOUBLE_PRIME":
        if start >= 42:
            degree = max(0, degree - 2)  # resolve the final answer
        if start == 48:
            duration += 2
            velocity += 2
    elif phrase_kind == "B":
        if statement_index % 2 == 1 and start >= 28:
            degree += 1
    return Gesture(degree, start, duration, velocity)


def _note_for_gesture(
    conductor: Conductor,
    phrase_bar: int,
    gesture: Gesture,
    *,
    octave_lift: int,
) -> int:
    chord = conductor.chord_at_bar(phrase_bar)
    degree = chord.degree + gesture.degree_offset
    return conductor.degree_note(degree, LEAD_OCTAVE) + octave_lift


def _emit_phrase(
    conductor: Conductor,
    start_bar: int,
    phrase_kind: str,
    statement_index: int,
    *,
    octave_lift: int = 0,
    velocity_lift: int = 0,
) -> list[NoteEvent]:
    events: list[NoteEvent] = []
    for gesture in _phrase_template(phrase_kind):
        shaped = _transform_gesture(gesture, phrase_kind, statement_index)
        phrase_bar_offset = min(PHRASE_BARS - 1, shaped.start_16th // 16)
        bar = start_bar + phrase_bar_offset
        note = _note_for_gesture(conductor, bar, shaped, octave_lift=octave_lift)
        tick = bar_to_tick(start_bar) + shaped.start_16th * SIXTEENTH_TICKS
        duration = shaped.duration_16ths * SIXTEENTH_TICKS
        velocity = max(1, min(127, LEAD_VELOCITY + shaped.velocity_delta + velocity_lift))
        events.append(NoteEvent(LEAD_CHANNEL, note, velocity, tick, duration))
    return events


def _emit_period(
    conductor: Conductor,
    start_bar: int,
    *,
    statement_index: int,
    octave_lift: int = 0,
    velocity_lift: int = 0,
) -> list[NoteEvent]:
    events: list[NoteEvent] = []
    for phrase_index, phrase_kind in enumerate(PERIOD_PLAN):
        events.extend(
            _emit_phrase(
                conductor,
                start_bar + phrase_index * PHRASE_BARS,
                phrase_kind,
                statement_index,
                octave_lift=octave_lift,
                velocity_lift=velocity_lift,
            )
        )
    return events


def _emit_drop_fragments(conductor: Conductor, start_bar: int, bars: int) -> list[NoteEvent]:
    """Sparse call-response fragments for drive sections; the groove stays foreground."""
    events: list[NoteEvent] = []
    for phrase_start in range(0, bars, 8):
        if phrase_start + 4 > bars:
            continue
        bar = start_bar + phrase_start
        for gesture in (Gesture(0, 6, 3, -10), Gesture(2, 14, 4, -6), Gesture(4, 40, 6, -3)):
            note = _note_for_gesture(conductor, bar, gesture, octave_lift=0)
            tick = bar_to_tick(bar) + gesture.start_16th * SIXTEENTH_TICKS
            events.append(
                NoteEvent(
                    LEAD_CHANNEL,
                    note,
                    max(1, LEAD_VELOCITY + gesture.velocity_delta),
                    tick,
                    gesture.duration_16ths * SIXTEENTH_TICKS,
                )
            )
    return events


class LeadGenerator:
    name = "lead"

    def generate(
        self, spec: TrackSpec, rng: random.Random, pack: "StylePack | None" = None
    ) -> list[NoteEvent]:
        conductor = build_conductor(spec)
        # One seeded structural choice: peak statements may be normal or octave-lift first.
        peak_lift_first = rng.choice((False, True))
        events: list[NoteEvent] = []
        statement_index = 0
        for section, (start_bar, bars) in section_layout(spec).items():
            if section.startswith("drop"):
                events.extend(_emit_drop_fragments(conductor, start_bar, bars))
                continue
            if not section.startswith(("break", "peak")):
                continue
            for period_start in range(0, bars, PERIOD_BARS):
                if period_start + PERIOD_BARS > bars:
                    continue
                peak = section.startswith("peak")
                lift = 12 if peak and (peak_lift_first or statement_index % 2 == 1) else 0
                velocity_lift = 8 if peak else 0
                events.extend(
                    _emit_period(
                        conductor,
                        start_bar + period_start,
                        statement_index=statement_index,
                        octave_lift=lift,
                        velocity_lift=velocity_lift,
                    )
                )
                statement_index += 1
        return events
