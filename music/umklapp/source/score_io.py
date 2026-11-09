# SPDX-License-Identifier: AGPL-3.0-only
"""Track-owned MIDI and automation serialization for Umklapp."""

import json

import mido
import numpy as np

BPM = 134
BEAT = 60 / BPM
PPQ = 960

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def curve(knots, bars):
    """Cosine segments prevent an automation corner from becoming an audio edge."""
    x, y = np.array(knots).T
    indices = np.clip(np.searchsorted(x, bars, side="right") - 1, 0, len(x) - 2)
    phase = np.clip((bars - x[indices]) / (x[indices + 1] - x[indices]), 0, 1)
    return (y[indices] + (y[indices + 1] - y[indices]) * (0.5 - 0.5 * np.cos(np.pi * phase))).astype("float32")


def write_midi(score, destination, selected=None):
    midi = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    conductor = mido.MidiTrack()
    midi.tracks.append(conductor)
    conductor.append(mido.MetaMessage("track_name", name="Umklapp", time=0))
    conductor.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(BPM), time=0))
    conductor.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    last = 0
    for section in score["sections"]:
        tick = section["start_bar"] * 4 * PPQ
        conductor.append(mido.MetaMessage("marker", text=section["name"], time=tick - last))
        last = tick
    finish = round(score["duration_seconds"] / BEAT * PPQ)
    conductor.append(mido.MetaMessage("end_of_track", time=finish - last))
    for part in score["parts"]:
        if selected and part["id"] != selected:
            continue
        track = mido.MidiTrack()
        midi.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=part["id"], time=0))
        events = []
        for index, note in enumerate(part["notes"]):
            a = round(note["start_beat"] * PPQ)
            b = max(a + 1, round((note["start_beat"] + note["duration_beats"]) * PPQ))
            events.extend([
                (a, 2 * index + 1, mido.MetaMessage("text", text=note["id"], time=0)),
                (a, 2 * index + 2, mido.Message("note_on", channel=part["channel"], note=note["pitch"], velocity=note["velocity"], time=0)),
                (b, 0, mido.Message("note_off", channel=part["channel"], note=note["pitch"], velocity=0, time=0)),
            ])
        cursor = 0
        for tick, _, message in sorted(events, key=lambda item: item[:2]):
            message.time = tick - cursor
            track.append(message)
            cursor = tick
        track.append(mido.MetaMessage("end_of_track", time=max(0, finish - cursor)))
    midi.save(destination)

