# SPDX-License-Identifier: AGPL-3.0-only
"""Typed note events decoded from source/score.json."""

from __future__ import annotations

from dataclasses import dataclass

from .context import BAR_S, BEAT_S, SCORE


@dataclass(frozen=True)
class PluckNote:
    bar: int
    beat: float
    pitch: str
    duration: float
    velocity: int

    @property
    def start_s(self) -> float:
        return (self.bar * 4.0 + self.beat) * BEAT_S

    @property
    def duration_s(self) -> float:
        return self.duration * BEAT_S


@dataclass(frozen=True)
class PianoNote:
    bar: int
    beat: float
    pitch: str
    duration: float
    velocity: float
    pan: float = 0.5

    @property
    def start_s(self) -> float:
        return self.bar * BAR_S + self.beat * BEAT_S

    @property
    def duration_s(self) -> float:
        return self.duration * BEAT_S


def piano_events() -> list[PianoNote]:
    return [
        PianoNote(
            bar=int(event["bar"]),
            beat=float(event["beat"]),
            pitch=str(event["pitch"]),
            duration=float(event["duration_beats"]),
            velocity=float(event["velocity"]),
            pan=float(event["pan"]),
        )
        for event in SCORE["piano_events"]
    ]


def pluck_events() -> list[PluckNote]:
    return [
        PluckNote(
            bar=int(event["bar"]),
            beat=float(event["beat"]),
            pitch=str(event["pitch"]),
            duration=float(event["duration_beats"]),
            velocity=int(event["velocity"]),
        )
        for event in SCORE["pluck_events"]
    ]
