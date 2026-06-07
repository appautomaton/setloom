# SPDX-License-Identifier: AGPL-3.0-only
"""MIDI core: PPQ-480 tick math, bar-grid helpers, and a format-1 part writer.

All Setloom MIDI is 4/4 at a constant tempo taken from the track spec.
Generators produce ``NoteEvent`` lists in absolute ticks; the writer turns
them into a standalone single-track format-1 file per part whose
end_of_track lands at exactly the arrangement's total tick length.
"""

from pathlib import Path
from typing import NamedTuple

import mido

from setloom.schema import TrackSpec

PPQ = 480
BEATS_PER_BAR = 4
TICKS_PER_BAR = PPQ * BEATS_PER_BAR
SIXTEENTH_TICKS = PPQ // 4  # 120
EIGHTH_TICKS = PPQ // 2  # 240

DRUM_CHANNEL = 9


class NoteEvent(NamedTuple):
    """One note in absolute ticks; onsets sit on the 16th grid."""

    channel: int
    note: int
    velocity: int
    start_tick: int
    duration_ticks: int


def section_layout(spec: TrackSpec) -> dict[str, tuple[int, int]]:
    """Map each section name to its ``(start_bar, bars)``, in spec order."""
    layout: dict[str, tuple[int, int]] = {}
    start = 0
    for name, bars in spec.sections.items():
        layout[name] = (start, bars)
        start += bars
    return layout


def bar_to_tick(bar: int) -> int:
    """Absolute tick of the first beat of ``bar`` (0-based)."""
    return bar * TICKS_PER_BAR


def beat_to_tick(bar: int, beat: int) -> int:
    """Absolute tick of ``beat`` (0-3) within ``bar`` (0-based)."""
    return bar * TICKS_PER_BAR + beat * PPQ


def total_ticks(spec: TrackSpec) -> int:
    """Tick length of the full arrangement: sum(sections) bars of 4/4."""
    return sum(spec.sections.values()) * TICKS_PER_BAR


def write_part_midi(path: str | Path, spec: TrackSpec, events: list[NoteEvent]) -> None:
    """Write ``events`` as a standalone format-1 .mid at the spec's tempo.

    The single track carries set_tempo at tick 0, note_on/note_off pairs in
    delta time (note_off sorts before note_on at equal ticks), and an
    end_of_track at exactly ``total_ticks(spec)``.
    """
    end_tick = total_ticks(spec)
    for event in events:
        if event.start_tick < 0 or event.start_tick + event.duration_ticks > end_tick:
            raise ValueError(f"note event outside track bounds [0, {end_tick}]: {event}")

    timed: list[tuple[int, int, int, int, mido.Message]] = []
    for event in events:
        on = mido.Message(
            "note_on",
            channel=event.channel,
            note=event.note,
            velocity=event.velocity,
            time=0,
        )
        off = mido.Message(
            "note_off", channel=event.channel, note=event.note, velocity=0, time=0
        )
        timed.append((event.start_tick, 1, event.channel, event.note, on))
        timed.append((event.start_tick + event.duration_ticks, 0, event.channel, event.note, off))
    timed.sort(key=lambda item: item[:4])

    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(spec.bpm), time=0))
    cursor = 0
    for tick, _, _, _, message in timed:
        message.time = tick - cursor
        cursor = tick
        track.append(message)
    track.append(mido.MetaMessage("end_of_track", time=end_tick - cursor))

    midi_file = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    midi_file.tracks.append(track)
    midi_file.save(str(path))
