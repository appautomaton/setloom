# SPDX-License-Identifier: AGPL-3.0-only
"""Bass: one seeded articulation profile per run, pedal-safe and sidechain-aware.

Three profiles cover the lane's articulation range: ``rolling_16th_sub``
(16th root pulses that skip every beat tick), ``offbeat_eighth_pulse``
(root notes on the "and" of each beat), and ``syncopated_pedal`` (a sparse
two-bar syncopation). Profile weights derive deterministically from the
spec's style vector; the final pick is one seeded draw.

Hard invariant for all profiles: bass onsets never land on a beat tick, so
they can never share a tick with kick onsets, and every note ends strictly
before the next beat tick to leave sidechain-shaped space for the kick.
This lane is the sub/low-end anchor. It deliberately stays on the tonic
pedal root; harmonic movement belongs in mid-bass, chords, arp, or lead lanes.
Moving the sub directly through the chord progression makes the low end
unstable and can read as a puffy transient effect after master processing.
"""

import random

from setloom.midi import (
    EIGHTH_TICKS,
    PPQ,
    SIXTEENTH_TICKS,
    STEPS_PER_BAR,
    NoteEvent,
    bar_to_tick,
    beat_to_tick,
    section_layout,
)
from setloom.schema import StyleVector, TrackSpec
from setloom.parts.base import root_note

BASS_OCTAVE = 2  # D minor -> D2 = 38

# Sidechain-shaped gap before the next onset/beat, in ticks (a 64th at PPQ 480).
SIDECHAIN_GAP_TICKS = 30

# Base weights mirror style.yml groove.bass_articulation_weights (assumption:
# model-knowledge, cross-model review 2026-06-07). Hardcoded so the spec stays
# the single runtime input; style.yml drives the gate and defaults only.
BASE_WEIGHTS = {
    "rolling_16th_sub": 0.45,
    "offbeat_eighth_pulse": 0.35,
    "syncopated_pedal": 0.20,
}
HIGH_PRESSURE_WEIGHTS = {
    "rolling_16th_sub": 0.70,
    "offbeat_eighth_pulse": 0.20,
    "syncopated_pedal": 0.10,
}
LOW_PRESSURE_WEIGHTS = {
    "rolling_16th_sub": 0.10,
    "offbeat_eighth_pulse": 0.50,
    "syncopated_pedal": 0.40,
}

# Rolling 16th velocity contour, indexed by step-within-beat (1-3); the
# offbeat 8th carries the accent so kick and bass breathe as one groove.
ROLLING_VELOCITIES = {1: 84, 2: 100, 3: 88}

# Two-bar syncopated pedal cell: (bar offset, 16th step, velocity); steps
# avoid multiples of 4 (beat ticks) by construction.
PEDAL_CELL = (
    (0, 2, 98),
    (0, 7, 88),
    (0, 10, 88),
    (1, 2, 98),
    (1, 7, 88),
    (1, 14, 90),
)


def articulation_weights(vector: StyleVector) -> dict[str, float]:
    """Deterministic profile weights from the spec's style vector."""
    if vector.bass_aggression >= 7 or vector.peak_time_pressure >= 7:
        return HIGH_PRESSURE_WEIGHTS
    if vector.bass_aggression <= 3 and vector.peak_time_pressure <= 3:
        return LOW_PRESSURE_WEIGHTS
    return BASE_WEIGHTS


def select_articulation_profile(spec: TrackSpec, rng: random.Random) -> str:
    """Pick the run's articulation profile: one seeded draw over the weights."""
    weights = articulation_weights(spec.style_vector)
    names = list(weights)
    return rng.choices(names, weights=[weights[n] for n in names], k=1)[0]


def _gapped_duration(onset_tick: int) -> int:
    """Longest duration (capped at an 8th) ending a sidechain gap before the next beat."""
    to_next_beat = PPQ - onset_tick % PPQ
    return min(EIGHTH_TICKS, to_next_beat) - SIDECHAIN_GAP_TICKS


def _rolling_bar(root: int, bar: int) -> list[NoteEvent]:
    events = []
    for step in range(STEPS_PER_BAR):
        if step % 4 == 0:
            continue  # kick-duck gap: never on a beat tick
        tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
        velocity = ROLLING_VELOCITIES[step % 4]
        events.append(NoteEvent(1, root, velocity, tick, SIXTEENTH_TICKS - SIDECHAIN_GAP_TICKS))
    return events


def _offbeat_bar(root: int, bar: int) -> list[NoteEvent]:
    events = []
    for beat in range(4):
        tick = beat_to_tick(bar, beat) + EIGHTH_TICKS
        events.append(NoteEvent(1, root, 96, tick, EIGHTH_TICKS - SIDECHAIN_GAP_TICKS))
    return events


def _pedal_bar(root: int, bar: int, bar_in_section: int) -> list[NoteEvent]:
    events = []
    for bar_offset, step, velocity in PEDAL_CELL:
        if bar_offset != bar_in_section % 2:
            continue
        tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
        events.append(NoteEvent(1, root, velocity, tick, _gapped_duration(tick)))
    return events


class BassGenerator:
    name = "bass"

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]:
        # Exactly one rng draw per run keeps draw counts structural.
        profile = select_articulation_profile(spec, rng)
        root = root_note(spec.key, BASS_OCTAVE)
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith(("groove", "drop", "peak")):
                continue
            for bar_in_section in range(bars):
                bar = start_bar + bar_in_section
                if profile == "rolling_16th_sub":
                    events.extend(_rolling_bar(root, bar))
                elif profile == "offbeat_eighth_pulse":
                    events.extend(_offbeat_bar(root, bar))
                else:
                    events.extend(_pedal_bar(root, bar, bar_in_section))
        return events
