# SPDX-License-Identifier: AGPL-3.0-only
"""Chords: conductor-driven diatonic progression with color voicings (channel 2).

The Conductor owns progression, chord color, and harmonic rhythm so chords,
bass, lead, and counterline hear the same harmonic timeline. Breaks sustain
each conductor chord as a pad across its span; drops and peak reduce density
to one short offbeat stab per bar so the bass and arp keep the foreground.
"""

import random

from setloom.conductor import HarmonicEvent, build_conductor
from setloom.midi import (
    EIGHTH_TICKS,
    PPQ,
    SIXTEENTH_TICKS,
    TICKS_PER_BAR,
    NoteEvent,
    bar_to_tick,
    section_layout,
)
from typing import TYPE_CHECKING

from setloom.schema import TrackSpec

if TYPE_CHECKING:
    from setloom.stylepack import StylePack

CHORD_OCTAVE = 4  # mid register
PAD_VELOCITY = 64  # modest pad level in breaks
STAB_VELOCITY = 70  # short offbeat stabs in drops/peak
PEAK_BED_VELOCITY = 46  # soft sustained bed an octave up, under the peak stabs


def chord_tones(scale: tuple[int, ...], degree: int, color: str) -> tuple[int, ...]:
    """Semitone offsets from the key tonic for a colored diatonic chord."""
    root = scale[degree % 7] + 12 * (degree // 7)
    fifth = scale[(degree + 4) % 7] + 12 * ((degree + 4) // 7)
    if color == "sus2":
        return (root, scale[(degree + 1) % 7] + 12 * ((degree + 1) // 7), fifth)
    if color == "sus4":
        return (root, scale[(degree + 3) % 7] + 12 * ((degree + 3) // 7), fifth)
    third = scale[(degree + 2) % 7] + 12 * ((degree + 2) // 7)
    if color == "add9":
        return (root, third, fifth, scale[(degree + 8) % 7] + 12 * ((degree + 8) // 7))
    return (root, third, fifth)


def _events_for_chord(
    event: HarmonicEvent,
    base: int,
    tones: tuple[int, ...],
    *,
    sustained: bool,
    stabs: bool,
    bed_lift: int,
    section_start_bar: int,
    section_bars: int,
) -> list[NoteEvent]:
    events: list[NoteEvent] = []
    span_bars = min(event.bars, section_start_bar + section_bars - event.start_bar)
    if sustained and span_bars > 0:
        velocity = PEAK_BED_VELOCITY if bed_lift else PAD_VELOCITY
        for tone in tones:
            events.append(
                NoteEvent(
                    2,
                    base + bed_lift + tone,
                    velocity,
                    bar_to_tick(event.start_bar),
                    span_bars * TICKS_PER_BAR,
                )
            )
    if stabs:
        for bar in range(event.start_bar, event.start_bar + span_bars):
            tick = bar_to_tick(bar) + 2 * PPQ + EIGHTH_TICKS  # the "and" of beat 3
            for tone in tones:
                events.append(NoteEvent(2, base + tone, STAB_VELOCITY, tick, EIGHTH_TICKS))
    return events


def _track_chords_plan(spec: TrackSpec):
    groove = getattr(spec, "groove", None)
    if groove is None or groove.chords is None:
        return None
    return groove.chords


def _section_plan(plan, section: str):
    kind = section.rstrip("0123456789_")
    return plan.sections.get(section) or plan.sections.get(kind)


def _planned_tones(conductor, harmonic: HarmonicEvent, color: str) -> tuple[int, ...]:
    if color == "conductor":
        return conductor.chord_tones(harmonic)
    return chord_tones(conductor.scale, harmonic.degree, color)


def _planned_chord_events(
    event: HarmonicEvent,
    base: int,
    tones: tuple[int, ...],
    plan,
    *,
    section_start_bar: int,
    section_bars: int,
) -> list[NoteEvent]:
    events: list[NoteEvent] = []
    if plan.mode == "silent":
        return events
    span_bars = min(event.bars, section_start_bar + section_bars - event.start_bar)
    if span_bars <= 0:
        return events

    if plan.mode in ("sustain", "bed_and_stabs"):
        for tone in tones:
            events.append(
                NoteEvent(
                    2,
                    base + plan.bed_lift + tone,
                    plan.bed_velocity,
                    bar_to_tick(event.start_bar),
                    span_bars * TICKS_PER_BAR,
                )
            )

    if plan.mode in ("stabs", "bed_and_stabs"):
        patterns = plan.stab_patterns or ([plan.stab_steps] if plan.stab_steps else [])
        if not patterns:
            return events
        duration = plan.duration_steps * SIXTEENTH_TICKS
        for bar in range(event.start_bar, event.start_bar + span_bars):
            bar_in_section = bar - section_start_bar
            for step in patterns[bar_in_section % len(patterns)]:
                tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
                clipped = min(duration, TICKS_PER_BAR - step * SIXTEENTH_TICKS)
                for tone in tones:
                    events.append(NoteEvent(2, base + tone, plan.stab_velocity, tick, clipped))
    return events


class ChordsGenerator:
    name = "chords"

    def generate(
        self, spec: TrackSpec, rng: random.Random, pack: "StylePack | None" = None
    ) -> list[NoteEvent]:
        _ = rng  # Chords follow the shared conductor; per-run variation lives there.
        conductor = build_conductor(spec)
        track_plan = _track_chords_plan(spec)
        base = 12 * (CHORD_OCTAVE + 1) + conductor.pitch_class
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            planned_section = _section_plan(track_plan, section) if track_plan else None
            if planned_section:
                section_base = 12 * (planned_section.octave + 1) + conductor.pitch_class
                for harmonic in conductor.harmonic_events:
                    if not start_bar <= harmonic.start_bar < start_bar + bars:
                        continue
                    events.extend(
                        _planned_chord_events(
                            harmonic,
                            section_base,
                            _planned_tones(conductor, harmonic, planned_section.color),
                            planned_section,
                            section_start_bar=start_bar,
                            section_bars=bars,
                        )
                    )
                continue
            if track_plan or not section.startswith(("break", "drop", "peak")):
                continue
            # Texture per section: breaks sustain, drops stab, peak does BOTH —
            # the climax keeps a harmonic bed under the stabs (listening note
            # 2026-06-07: peak "too simplistic"). The peak bed sits an octave
            # above the stabs so same-pitch note pairing never collides and the
            # low mids stay clear (review_vocabulary.overfilled_low_mids).
            sustained = section.startswith(("break", "peak"))
            stabs = section.startswith(("drop", "peak"))
            bed_lift = 12 if section.startswith("peak") else 0
            for harmonic in conductor.harmonic_events:
                if not start_bar <= harmonic.start_bar < start_bar + bars:
                    continue
                events.extend(
                    _events_for_chord(
                        harmonic,
                        base,
                        conductor.chord_tones(harmonic),
                        sustained=sustained,
                        stabs=stabs,
                        bed_lift=bed_lift,
                        section_start_bar=start_bar,
                        section_bars=bars,
                    )
                )
        return events
