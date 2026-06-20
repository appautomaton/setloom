# SPDX-License-Identifier: AGPL-3.0-only
"""Export auditable MIDI from the JSON score source."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mido

from .context import NOTE, SOURCE

PPQ = 480
BEATS_PER_BAR = 4
TICKS_PER_BAR = PPQ * BEATS_PER_BAR
TOTAL_BARS = 120
TOTAL_TICKS = TOTAL_BARS * TICKS_PER_BAR
BPM = 123.0


@dataclass(frozen=True)
class MidiNote:
    channel: int
    note: int
    velocity: int
    start_tick: int
    duration_ticks: int


def beat_tick(bar: int, beat: float) -> int:
    return int(round((bar * BEATS_PER_BAR + beat) * PPQ))


def beat_duration_ticks(duration_beats: float) -> int:
    return max(1, int(round(duration_beats * PPQ)))


def seconds_duration_ticks(duration_seconds: float) -> int:
    return max(1, int(round(duration_seconds * (BPM / 60.0) * PPQ)))


def clamp_to_track(note: MidiNote) -> MidiNote | None:
    if note.start_tick >= TOTAL_TICKS:
        return None
    duration = min(note.duration_ticks, TOTAL_TICKS - note.start_tick)
    if duration <= 0:
        return None
    return MidiNote(note.channel, note.note, note.velocity, note.start_tick, duration)


def write_midi(path: Path, tracks: list[tuple[str, list[MidiNote]]]) -> None:
    midi = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    for name, notes in tracks:
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM), time=0))
        timed = []
        for note in notes:
            clipped = clamp_to_track(note)
            if clipped is None:
                continue
            on = mido.Message(
                "note_on",
                channel=clipped.channel,
                note=clipped.note,
                velocity=clipped.velocity,
                time=0,
            )
            off = mido.Message(
                "note_off",
                channel=clipped.channel,
                note=clipped.note,
                velocity=0,
                time=0,
            )
            timed.append((clipped.start_tick, 1, clipped.note, on))
            timed.append((clipped.start_tick + clipped.duration_ticks, 0, clipped.note, off))
        timed.sort(key=lambda item: item[:3])
        cursor = 0
        for tick, _, _, message in timed:
            message.time = tick - cursor
            cursor = tick
            track.append(message)
        track.append(mido.MetaMessage("end_of_track", time=TOTAL_TICKS - cursor))
        midi.tracks.append(track)
    path.parent.mkdir(parents=True, exist_ok=True)
    midi.save(path)


def score_payload() -> dict:
    import json

    return json.loads((SOURCE / "score.json").read_text(encoding="utf-8"))


def bass_payload() -> dict:
    import json

    return json.loads((SOURCE / "remapped-bass-events.json").read_text(encoding="utf-8"))


def piano_notes(score: dict) -> list[MidiNote]:
    out = []
    for event in score["piano_events"]:
        out.append(
            MidiNote(
                channel=0,
                note=NOTE[str(event["pitch"])],
                velocity=max(1, min(127, int(round(float(event["velocity"]) * 127)))),
                start_tick=beat_tick(int(event["bar"]), float(event["beat"])),
                duration_ticks=beat_duration_ticks(float(event["duration_beats"])),
            )
        )
    return out


def pluck_notes(score: dict) -> list[MidiNote]:
    out = []
    for event in score["pluck_events"]:
        out.append(
            MidiNote(
                channel=1,
                note=NOTE[str(event["pitch"])],
                velocity=int(event["velocity"]),
                start_tick=beat_tick(int(event["bar"]), float(event["beat"])),
                duration_ticks=beat_duration_ticks(float(event["duration_beats"])),
            )
        )
    return out


def support_notes(score: dict) -> list[MidiNote]:
    out = []
    for event in score["support_notes"]:
        out.append(
            MidiNote(
                channel=2,
                note=NOTE[str(event["pitch"])],
                velocity=max(1, min(127, int(round(float(event["gain"]) * 127 * 5.0)))),
                start_tick=beat_tick(int(event["bar"]), 0.0),
                duration_ticks=seconds_duration_ticks(float(event["duration_seconds"])),
            )
        )
    return out


def bass_notes(payload: dict) -> list[MidiNote]:
    return [
        MidiNote(
            channel=3,
            note=int(event["note"]),
            velocity=int(event["velocity"]),
            start_tick=int(event["start_tick"]),
            duration_ticks=int(event["duration_ticks"]),
        )
        for event in payload["events"]
    ]


def kick_notes() -> list[MidiNote]:
    return [
        MidiNote(
            channel=9,
            note=36,
            velocity=105,
            start_tick=beat_tick(bar, beat),
            duration_ticks=PPQ // 4,
        )
        for bar in range(TOTAL_BARS)
        for beat in range(BEATS_PER_BAR)
    ]


def main() -> int:
    score = score_payload()
    bass = bass_payload()
    lanes = {
        "piano": piano_notes(score),
        "pluck": pluck_notes(score),
        "support": support_notes(score),
        "bass": bass_notes(bass),
        "kick": kick_notes(),
    }
    out = SOURCE / "midi"
    write_midi(out / "full-arrangement.mid", [(name, notes) for name, notes in lanes.items()])
    for name, notes in lanes.items():
        write_midi(out / f"lane-{name}.mid", [(name, notes)])
    print(f"wrote {out}")
    return 0
