# SPDX-License-Identifier: AGPL-3.0-only
"""Pad: sustained harmonic bed in breaks, drops, and peak (channel 5).

The default pad keeps the legacy tonic power stack for compatibility. Tracks
can opt into a conductor-driven bed when the tonic stack is too generic.
"""

import random
from typing import TYPE_CHECKING

from setloom.conductor import build_conductor
from setloom.midi import TICKS_PER_BAR, NoteEvent, bar_to_tick, section_layout
from setloom.parts.base import parse_key

from setloom.schema import TrackSpec

if TYPE_CHECKING:
    from setloom.stylepack import StylePack

PAD_CHANNEL = 5
PAD_OCTAVE = 3  # root below the chords part's octave 4

# Tonic stack offsets in semitones: root, fifth, ninth — deliberately no
# third (see module docstring: quality-neutral against any progression).
STACK_OFFSETS = (0, 7, 14)

PAD_VELOCITY = 50  # soft bed
PEAK_VELOCITY = 58  # slightly louder under the peak

NOTE_BARS_OPTIONS = (2, 4)


class PadGenerator:
    name = "pad"

    def generate(
        self, spec: TrackSpec, rng: random.Random, pack: "StylePack | None" = None
    ) -> list[NoteEvent]:
        plan = spec.groove.pad if spec.groove else None
        if plan and plan.mode == "conductor_bed":
            return self._generate_conductor_bed(spec, plan.note_bars)

        pitch_class, _ = parse_key(spec.key)
        octave = plan.octave if plan else PAD_OCTAVE
        base = 12 * (octave + 1) + pitch_class
        # Exactly one rng draw per run keeps draw counts structural.
        note_bars = plan.note_bars if plan and plan.note_bars else rng.choice(NOTE_BARS_OPTIONS)
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith(("break", "drop", "peak")):
                continue
            velocity = (
                (plan.peak_velocity if plan else PEAK_VELOCITY)
                if section.startswith("peak")
                else (plan.velocity if plan else PAD_VELOCITY)
            )
            for bar_in_section in range(0, bars, note_bars):
                # Clamp the last note so it never overflows the section.
                span_bars = min(note_bars, bars - bar_in_section)
                tick = bar_to_tick(start_bar + bar_in_section)
                duration = span_bars * TICKS_PER_BAR
                for offset in STACK_OFFSETS:
                    events.append(NoteEvent(PAD_CHANNEL, base + offset, velocity, tick, duration))
        return events

    def _generate_conductor_bed(
        self,
        spec: TrackSpec,
        planned_note_bars: int | None,
    ) -> list[NoteEvent]:
        conductor = build_conductor(spec)
        plan = spec.groove.pad if spec.groove else None
        octave = plan.octave if plan else PAD_OCTAVE
        note_bars = planned_note_bars or 4
        base = 12 * (octave + 1) + conductor.pitch_class
        events: list[NoteEvent] = []
        windows = [
            (section, start_bar, start_bar + bars)
            for section, (start_bar, bars) in section_layout(spec).items()
            if section.startswith(("break", "drop", "peak"))
        ]
        for harmonic in conductor.harmonic_events:
            for section, lo, hi in windows:
                start = max(harmonic.start_bar, lo)
                end = min(harmonic.start_bar + harmonic.bars, hi)
                if end <= start:
                    continue
                velocity = (
                    (plan.peak_velocity if plan else PEAK_VELOCITY)
                    if section.startswith("peak")
                    else (plan.velocity if plan else PAD_VELOCITY)
                )
                for bar in range(start, end, note_bars):
                    span = min(note_bars, end - bar)
                    tick = bar_to_tick(bar)
                    duration = span * TICKS_PER_BAR
                    for tone in conductor.chord_tones(harmonic):
                        events.append(NoteEvent(PAD_CHANNEL, base + tone, velocity, tick, duration))
        return events
