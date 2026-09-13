"""Explicit JSON score to MIDI conversion; the renderer does not call this file."""

import json
from pathlib import Path
import mido

HERE = Path(__file__).resolve().parent
PPQ = 960


def main():
    score = json.loads((HERE / "performance.json").read_text())
    tempo = mido.bpm2tempo(score["bpm"])

    def tick(seconds):
        return round(mido.second2tick(seconds, PPQ, tempo))

    midi = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    conductor = mido.MidiTrack()
    midi.tracks.append(conductor)
    conductor.extend(
        [
            mido.MetaMessage("track_name", name=score["title"].replace("—", "-")),
            mido.MetaMessage("set_tempo", tempo=tempo),
            mido.MetaMessage("time_signature", numerator=4, denominator=4),
            mido.MetaMessage("end_of_track", time=tick(score["duration_seconds"])),
        ]
    )
    for part in score["tracks"]:
        track = mido.MidiTrack()
        midi.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=part["name"]))
        channel = part["channel"]
        if channel != 9:
            program = {
                "sub": 38,
                "pulse": 39,
                "formant": 38,
                "arp": 81,
                "downshift": 103,
                "riser": 96,
                "piano": 0,
                "stab": 90,
                "prism": 81,
                "chimes": 9,
            }[part["instrument"]]
            track.append(mido.Message("program_change", channel=channel, program=program))
        bend_range = part.get("bend_range_semitones", 2)
        if "pitch_bends" in part:
            for control, value in [
                (101, 0),
                (100, 0),
                (6, bend_range),
                (38, 0),
                (101, 127),
                (100, 127),
            ]:
                track.append(
                    mido.Message("control_change", channel=channel, control=control, value=value)
                )
        events = []
        for n in part["notes"]:
            if n["end"] <= n["start"]:
                raise ValueError(n)
            events.extend(
                [
                    (
                        tick(n["start"]),
                        2,
                        mido.Message(
                            "note_on", channel=channel, note=n["pitch"], velocity=n["velocity"]
                        ),
                    ),
                    (
                        tick(n["end"]),
                        0,
                        mido.Message("note_off", channel=channel, note=n["pitch"], velocity=0),
                    ),
                ]
            )
        for c in part["controllers"]:
            events.append(
                (
                    tick(c["time"]),
                    1,
                    mido.Message(
                        "control_change", channel=channel, control=c["control"], value=c["value"]
                    ),
                )
            )
        for b in part.get("pitch_bends", []):
            value = round(8192 * b["semitones"] / bend_range)
            events.append(
                (
                    tick(b["time"]),
                    1,
                    mido.Message("pitchwheel", channel=channel, pitch=max(-8192, min(8191, value))),
                )
            )
        previous = 0
        for time, _, message in sorted(events, key=lambda e: (e[0], e[1])):
            track.append(message.copy(time=time - previous))
            previous = time
        track.append(
            mido.MetaMessage(
                "end_of_track", time=max(0, tick(score["duration_seconds"]) - previous)
            )
        )
    midi.save(HERE / "performance.mid")
    individual = HERE / "midi"
    individual.mkdir(exist_ok=True)
    for track in midi.tracks[1:]:
        isolated = mido.MidiFile(type=1, ticks_per_beat=PPQ)
        isolated.tracks = [conductor, track]
        isolated.save(individual / f"{track.name}.mid")
    arrangement = {
        k: score[k] for k in ["title", "duration_seconds", "source_recording", "audio_tracks"]
    }
    arrangement["parts"] = [
        {k: p[k] for k in ["name", "instrument", "channel"]} for p in score["tracks"]
    ]
    for key in ["solo_track"]:
        if key in score:
            arrangement[key] = score[key]
    (HERE / "arrangement.json").write_text(json.dumps(arrangement, indent=2) + "\n")
    print(f"Wrote {len(midi.tracks)} MIDI tracks.")


if __name__ == "__main__":
    main()
