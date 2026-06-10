# SPDX-License-Identifier: AGPL-3.0-only
"""Shared composition conductor for phrase, harmony, energy, and space plans."""

from __future__ import annotations

import random
from dataclasses import dataclass

from setloom.midi import TICKS_PER_BAR, section_layout
from setloom.schema import TrackSpec

PITCH_CLASSES = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}

SCALES = {
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "major": (0, 2, 4, 5, 7, 9, 11),
}


def parse_key(key: str) -> tuple[int, str]:
    tonic, _, quality = key.strip().partition(" ")
    quality = quality.strip().lower()
    pitch_class = PITCH_CLASSES.get(tonic)
    if pitch_class is None or quality not in SCALES:
        raise ValueError(f"unsupported key: {key!r} (expected e.g. 'D minor')")
    return pitch_class, quality


@dataclass(frozen=True)
class HarmonicEvent:
    """One chord span in bars, expressed as a diatonic scale degree."""

    start_bar: int
    bars: int
    degree: int
    color: str


@dataclass(frozen=True)
class PhrasePoint:
    """Position of one bar inside the shared arrangement clock."""

    bar: int
    section: str
    section_kind: str
    bar_in_section: int
    phrase_bar: int
    is_8bar_boundary: bool
    is_16bar_boundary: bool
    is_32bar_boundary: bool
    energy: float
    chord: HarmonicEvent


@dataclass(frozen=True)
class Conductor:
    """The single composition-level source of truth for part generators."""

    spec: TrackSpec
    scale: tuple[int, ...]
    pitch_class: int
    quality: str
    progression: tuple[int, int, int, int]
    chord_color: str
    harmonic_events: tuple[HarmonicEvent, ...]

    def phrase_point(self, bar: int) -> PhrasePoint:
        section = "unknown"
        section_kind = "unknown"
        bar_in_section = bar
        for name, (start_bar, bars) in section_layout(self.spec).items():
            if start_bar <= bar < start_bar + bars:
                section = name
                section_kind = name.rstrip("0123456789_")
                bar_in_section = bar - start_bar
                break
        return PhrasePoint(
            bar=bar,
            section=section,
            section_kind=section_kind,
            bar_in_section=bar_in_section,
            phrase_bar=bar % 16,
            is_8bar_boundary=bar % 8 == 0,
            is_16bar_boundary=bar % 16 == 0,
            is_32bar_boundary=bar % 32 == 0,
            energy=self.energy_at_bar(bar),
            chord=self.chord_at_bar(bar),
        )

    def chord_at_bar(self, bar: int) -> HarmonicEvent:
        for event in self.harmonic_events:
            if event.start_bar <= bar < event.start_bar + event.bars:
                return event
        return self.harmonic_events[-1]

    def energy_at_bar(self, bar: int) -> float:
        point = _section_point(self.spec, bar)
        if point is None:
            return 0.0
        section, bar_in_section, bars = point
        kind = section.rstrip("0123456789_")
        phrase_lift = 0.06 if bar % 8 in (6, 7) else 0.0
        if kind == "intro":
            return min(0.34, 0.16 + 0.14 * bar_in_section / max(1, bars - 1))
        if kind == "groove_a":
            return 0.46 + phrase_lift
        if kind == "break":
            return 0.36 + 0.28 * bar_in_section / max(1, bars - 1)
        if kind == "drop":
            return 0.78 + phrase_lift
        if kind == "peak":
            return 0.92 + phrase_lift
        if kind == "outro":
            return max(0.20, 0.52 - 0.28 * bar_in_section / max(1, bars - 1))
        return 0.55

    def scale_offset(self, degree: int) -> int:
        return self.scale[degree % len(self.scale)] + 12 * (degree // len(self.scale))

    def degree_note(self, degree: int, octave: int) -> int:
        return 12 * (octave + 1) + self.pitch_class + self.scale_offset(degree)

    def chord_root_note(self, bar: int, octave: int) -> int:
        return self.degree_note(self.chord_at_bar(bar).degree, octave)

    def chord_tones(self, event: HarmonicEvent | None = None) -> tuple[int, ...]:
        chord = event or self.harmonic_events[0]
        degree = chord.degree
        root = self.scale_offset(degree)
        fifth = self.scale_offset(degree + 4)
        if chord.color == "sus2":
            return (root, self.scale_offset(degree + 1), fifth)
        if chord.color == "sus4":
            return (root, self.scale_offset(degree + 3), fifth)
        third = self.scale_offset(degree + 2)
        if chord.color == "add9":
            return (root, third, fifth, self.scale_offset(degree + 8))
        return (root, third, fifth)

    def foreground_owner(self, section_kind: str) -> str:
        if section_kind == "intro":
            return "atmos"
        if section_kind == "groove_a":
            return "arp"
        if section_kind == "break":
            return "lead"
        if section_kind == "drop":
            return "groove"
        if section_kind == "peak":
            return "lead"
        return "atmos"


MINOR_PROGRESSIONS = (
    (0, 5, 2, 6),  # i-VI-III-VII
    (0, 6, 5, 6),  # i-VII-VI-VII
    (0, 5, 6, 4),  # i-VI-VII-v
    (0, 2, 6, 5),  # i-III-VII-VI
)

MAJOR_PROGRESSIONS = (
    (0, 5, 3, 4),  # I-vi-IV-V
    (0, 4, 5, 3),  # I-V-vi-IV
)

CHORD_COLORS = ("triad", "sus2", "sus4", "add9")
SECTION_HARMONIC_RHYTHM = {
    "intro": 8,
    "groove_a": 4,
    "break": 4,
    "drop": 4,
    "peak": 2,
    "outro": 8,
}


def build_conductor(spec: TrackSpec) -> Conductor:
    """Build a deterministic conductor shared by all musical parts."""
    pitch_class, quality = parse_key(spec.key)
    rng = random.Random(f"{spec.seed}:{spec.key}:{spec.duration_bars}:conductor")
    progressions = MINOR_PROGRESSIONS if quality == "minor" else MAJOR_PROGRESSIONS
    progression = rng.choice(progressions)
    color = rng.choice(CHORD_COLORS)
    scale = SCALES[quality]
    events: list[HarmonicEvent] = []
    for section, (start_bar, bars) in section_layout(spec).items():
        kind = section.rstrip("0123456789_")
        harmonic_bars = SECTION_HARMONIC_RHYTHM.get(kind, 4)
        for offset in range(0, bars, harmonic_bars):
            span = min(harmonic_bars, bars - offset)
            step = (offset // harmonic_bars) % len(progression)
            events.append(
                HarmonicEvent(
                    start_bar=start_bar + offset,
                    bars=span,
                    degree=progression[step],
                    color=color,
                )
            )
    return Conductor(
        spec=spec,
        scale=scale,
        pitch_class=pitch_class,
        quality=quality,
        progression=progression,
        chord_color=color,
        harmonic_events=tuple(events),
    )


def _section_point(spec: TrackSpec, bar: int) -> tuple[str, int, int] | None:
    for name, (start_bar, bars) in section_layout(spec).items():
        if start_bar <= bar < start_bar + bars:
            return name, bar - start_bar, bars
    return None


def melodic_span_bars(events) -> int:
    """Rounded bar span covered by a set of events; used by report gates."""
    if not events:
        return 0
    lo = min(event.start_tick for event in events)
    hi = max(event.start_tick + event.duration_ticks for event in events)
    return max(1, (hi - lo + TICKS_PER_BAR - 1) // TICKS_PER_BAR)
