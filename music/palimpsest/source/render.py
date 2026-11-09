# SPDX-License-Identifier: AGPL-3.0-only
"""Perform Palimpsest's current composition. Musical decisions live in its score and patches."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import mido
import numpy as np
from scipy import signal

from setloom.audio import integrated_lufs, write_audio
from instruments import add_gesture, add_wrapped, bass_space, held_voice, grain, ground, kick, pulse, room
from instruments import percussion, inner, veil, harmony_clearance

ROOT = Path(__file__).resolve().parents[1]
# Generated audio and reports stay outside the tracked production.
OUT = ROOT.parents[1] / "tmp/palimpsest"


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def movement(points: list, beats):
    values = np.asarray(points, dtype=np.float64)
    return np.interp(beats, values[:, 0], values[:, 1])


def level_at(score: dict, voice: str, beat):
    return movement(score["levels"][voice], np.asarray(beat)/4)


def compile_events(score: dict) -> list[dict]:
    """Compose entrances, tied common tones, withdrawals and returns from the form."""
    total = score["bars"]*score["beats_per_bar"]
    events = [dict(voice="bass", beat=0, note=score["bass"]["note"],
                   velocity=score["bass"]["velocity"], gate_beats=total)]
    # Tonal context remains continuous; the harmonic instrument plays selected phrases.
    for entrance, release in score["harmony_windows_bars"]:
        active = {}
        for region in score["harmonic_regions"]:
            start_bar = max(entrance,region["start_bar"])
            end_bar = min(release,region["start_bar"]+region["bars"])
            if start_bar>=end_bar:continue
            start, length = start_bar*4,(end_bar-start_bar)*4
            continuing = {}
            for note, velocity in score["harmony_palette"][region["voicing"]]["notes"]:
                prior = active.get(note)
                if prior and prior["velocity"] == velocity and prior["beat"]+prior["gate_beats"] == start:
                    prior["gate_beats"] += length
                    event = prior
                else:
                    event = dict(voice="bed",beat=start,note=note,velocity=velocity,gate_beats=length)
                    events.append(event)
                continuing[note] = event
            active = continuing
    for bar in range(score["bars"]):
        phrase = next(item for item in score["phrases"]
                      if item["start_bar"] <= bar < item["start_bar"]+item["bars"])
        sequence = phrase["pulse_sequence"]
        cell = score["pulse_cells"][sequence[(bar-phrase["start_bar"]) % len(sequence)]]
        for placement, note, velocity, gate in cell:
            beat = bar*4+placement
            if level_at(score,"pulse",beat) <= 1e-8:continue
            events.append(dict(voice="pulse",beat=beat,note=note,velocity=velocity,gate_beats=gate,
                               colour=float(movement(score["colour_points"],beat/4))))
        for placement, velocity, gate in score["air"]["pattern"]:
            beat = bar*4+placement
            if level_at(score,"air",beat) <= 1e-8:continue
            events.append(dict(voice="air",beat=beat,note=score["air"]["note"],
                               velocity=velocity,gate_beats=gate))
        for region in score["kick_regions"]:
            if not region["start_bar"] <= bar < region["end_bar"]:continue
            for placement in region["placements"]:
                position = bar*4+placement
                if any(a <= position < b for a,b in score["kick_silences_beats"]):continue
                strength = score["kick_accents"][placement]*region["strength"]
                events.append(dict(voice="kick",beat=position,note=36,strength=strength,
                                   velocity=round(105*strength),gate_beats=.125))
    for voice in ("percussion","inner"):
        spec = score[voice]
        cycle_beats = spec["cycle_bars"]*4
        for base in range(0,total,cycle_beats):
            for index, row in enumerate(spec["pattern"]):
                beat = base+row[0]
                if not any(start*4<=beat<stop*4 for start,stop in spec["windows_bars"]):continue
                if level_at(score,voice,beat)<=1e-8:continue
                if voice == "percussion":
                    _, velocity, pan, articulation = row
                    events.append(dict(voice=voice,beat=beat,note=spec["note"],velocity=velocity,
                                       gate_beats=spec["gate_beats"],pan=pan,articulation=articulation))
                else:
                    if 72*4<=beat<88*4 and index % spec["break_every_events"]:continue
                    _, degree, velocity, pan, gate = row
                    region = next(r for r in score["harmonic_regions"]
                                  if r["start_bar"]*4<=beat<(r["start_bar"]+r["bars"])*4)
                    note = spec["pitch_palettes"][region["voicing"]][degree]
                    events.append(dict(voice=voice,beat=beat,note=note,velocity=velocity,gate_beats=gate,
                                       pan=pan,colour=float(movement(score["colour_points"],beat/4))))
    events.extend(dict(voice="veil",beat=e["beat"],note=e["note"]+score["veil"]["transpose_semitones"],
                       velocity=round(e["velocity"]*score["veil"]["velocity_scale"]),gate_beats=e["gate_beats"])
                  for e in list(events) if e["voice"]=="bed")
    return sorted(events, key=lambda event: (event["beat"], event["voice"]))


def midi_velocity(event: dict, score: dict) -> int:
    # The air's brief strokes carry expression in velocity; no drum-channel CC can touch kick.
    value = event["velocity"]
    if event["voice"] in ("air","percussion"):
        value *= level_at(score, event["voice"], event["beat"])
    return max(1, min(127, round(value)))


def write_midi(score: dict, events: list[dict], relative: str) -> None:
    ppq = 480
    end = score["bars"]*4*ppq
    file = mido.MidiFile(type=1, ticks_per_beat=ppq)
    clock = mido.MidiTrack([
        mido.MetaMessage("track_name", name=f'{score["title"]} · {score["edition"]}'),
        mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(score["bpm"])),
        mido.MetaMessage("time_signature", numerator=4, denominator=4),
        mido.MetaMessage("key_signature", key=score["tonality"]["midi_key"]),
    ])
    cursor = 0
    for phrase in score["phrases"]:
        tick = phrase["start_bar"]*4*ppq
        clock.append(mido.MetaMessage("marker", text=phrase["label"], time=tick-cursor))
        cursor = tick
    clock.append(mido.MetaMessage("end_of_track", time=end-cursor))
    file.tracks.append(clock)
    for voice, channel in (("kick",9),("bass",0),("bed",1),("pulse",2),("air",9),
                           ("percussion",9),("inner",3),("veil",4)):
        track = mido.MidiTrack([mido.MetaMessage("track_name", name=voice.title())])
        timed = []
        for event in (item for item in events if item["voice"] == voice):
            start = round(event["beat"]*ppq)
            stop = min(end, start+round(event["gate_beats"]*ppq))
            timed.append((start, 2, mido.Message("note_on", channel=channel, note=event["note"],
                          velocity=midi_velocity(event, score))))
            timed.append((stop, 1, mido.Message("note_off", channel=channel, note=event["note"], velocity=0)))
        if voice in ("bass","bed","pulse","inner","veil"):
            for beat in np.arange(0, score["bars"]*4+.125, .25):
                value = max(0, min(127, round(float(level_at(score, voice, beat))*127)))
                timed.append((round(beat*ppq), 0, mido.Message("control_change", channel=channel,
                              control=11, value=value)))
        if voice in ("pulse","inner","bed"):
            for beat in np.arange(0, score["bars"]*4+.125, .25):
                points = score["harmony_colour_points"] if voice == "bed" else score["colour_points"]
                value = max(0, min(127, round(float(movement(points, beat/4))*127)))
                timed.append((round(beat*ppq), 0, mido.Message("control_change", channel=channel,
                              control=74, value=value)))
        cursor = 0
        for tick, _, message in sorted(timed, key=lambda value: (value[0], value[1])):
            message.time = tick-cursor
            track.append(message)
            cursor = tick
        track.append(mido.MetaMessage("end_of_track", time=end-cursor))
        file.tracks.append(track)
    path = ROOT/relative
    path.parent.mkdir(parents=True, exist_ok=True)
    file.save(path)


def main() -> None:
    score = json.loads((ROOT/"source/score.json").read_text())
    patches = json.loads((ROOT/"source/patches.json").read_text())
    if score["beats_per_bar"] != 4:
        raise ValueError("This composition uses 4/4")
    cursor = 0
    for phrase in score["phrases"]:
        if phrase["start_bar"] != cursor: raise ValueError("Phrases must be contiguous")
        cursor += phrase["bars"]
    if cursor != score["bars"]: raise ValueError("Phrases must cover the sketch")
    cursor = 0
    for region in score["harmonic_regions"]:
        if region["start_bar"] != cursor:raise ValueError("Harmonic regions must be contiguous")
        cursor += region["bars"]
    if cursor != score["bars"]:raise ValueError("Harmony must cover the song")
    previous_end = 0
    for start,stop in score["harmony_windows_bars"]:
        if not previous_end<=start<stop<=score["bars"]:
            raise ValueError("Harmonic phrases must be ordered and non-overlapping")
        previous_end = stop
    for name, points in {**score["levels"],**score["pulse_space_sends"]}.items():
        if any(a[0]>=b[0] for a,b in zip(points,points[1:])):
            raise ValueError("Control positions must increase: "+name)
    rate, beat_s = score["sample_rate"], 60/score["bpm"]
    beats = score["bars"]*4
    frames = round(beats*beat_s*rate)
    duration = frames/rate
    t = np.arange(frames)/rate
    events = compile_events(score)
    midi = "palimpsest.mid"
    write_midi(score, events, midi)
    save(OUT/"render/performance.json", {"events": events, "tonality": score["tonality"]})
    controls = {name: movement(points, t/beat_s/4).astype(np.float32)
                for name, points in score["levels"].items()}
    parts = {
        "bass": ground(score["bass"]["note"], patches["bass"], t)
                * (score["bass"]["velocity"]/127),
        **{voice:np.zeros((frames,2),dtype=np.float32)
           for voice in ("bed","pulse","air","percussion","inner","veil")},
    }
    parts["bass"] *= bass_space(t, beat_s, patches["bass"],
                                 [e["beat"] for e in events if e["voice"]=="kick"])[:,None]
    rng = np.random.default_rng(score["seed"]+101)
    percussion_rng = np.random.default_rng(score["seed"]+301)
    veil_rng = np.random.default_rng(score["seed"]+302)
    for event in events:
        if event["voice"] == "pulse":
            add_gesture(parts["pulse"], pulse(event, patches["pulse"], rate, beat_s),
                        round(event["beat"]*beat_s*rate))
        elif event["voice"] == "bed":
            add_gesture(parts["bed"], held_voice(event, patches["bed"], rate, beat_s, score["harmony_colour_points"]),
                        round(event["beat"]*beat_s*rate))
        elif event["voice"] == "air":
            gesture = grain(event, patches["air"], rate, rng)*float(level_at(score,"air",event["beat"]))
            add_gesture(parts["air"], gesture, round(event["beat"]*beat_s*rate))
        elif event["voice"] == "percussion":
            gesture = percussion(event,patches["percussion"],rate,percussion_rng)
            gesture *= float(level_at(score,"percussion",event["beat"]))
            add_gesture(parts["percussion"],gesture,round(event["beat"]*beat_s*rate))
        elif event["voice"] == "inner":
            add_gesture(parts["inner"],inner(event,patches["inner"],rate,beat_s),
                        round(event["beat"]*beat_s*rate))
        elif event["voice"] == "veil":
            add_gesture(parts["veil"],veil(event,patches["veil"],rate,beat_s,veil_rng),
                        round(event["beat"]*beat_s*rate))
    for name in ("bass","bed","pulse","inner","veil"):
        parts[name] *= controls[name][:, None]
    # Brief foreground clearance preserves the harmonic instrument's sustained body.
    clearance = np.zeros(frames,dtype=np.float32)
    for event in (e for e in events if e["voice"]=="pulse"):
        start = round(event["beat"]*beat_s*rate)
        contour = harmony_clearance(event,patches["pulse"],rate)
        contour *= float(level_at(score,"pulse",event["beat"]))
        stop = min(frames,start+len(contour))
        clearance[start:stop] = np.maximum(clearance[start:stop],contour[:stop-start])
    parts["bed"] *= (1-clearance)[:,None]
    pulse_sends = {name:movement(points,t/beat_s/4).astype(np.float32)
                   for name,points in score["pulse_space_sends"].items()}
    short_send = (parts["pulse"]*pulse_sends["short"][:,None]+parts["bed"]*patches["space"]["bed_send"]
                  +parts["inner"]*patches["space"]["inner_send"]
                  +parts["percussion"]*patches["space"]["percussion_send"]) * controls["space"][:,None]
    long_send = (parts["pulse"]*pulse_sends["long"][:,None]+parts["bed"]*patches["space_long"]["bed_send"]
                 +parts["inner"]*patches["space_long"]["inner_send"]
                 +parts["veil"]*patches["space_long"]["veil_send"]) * controls["space_long"][:,None]
    parts["space"] = room(short_send,
                          patches["space"], rate, np.random.default_rng(score["seed"]+202))
    parts["space"] += room(long_send,patches["space_long"],rate,np.random.default_rng(score["seed"]+203))
    # Sends shape new energy entering the room; existing tails remain free to decay.
    ending = round(patches["space_ending_fade_s"]*rate)
    parts["space"][-ending:] *= (.5+.5*np.cos(np.linspace(0,np.pi,ending)))[:,None]
    # One stated tonal-group trim preserves the foreground/backdrop relationship.
    for name in ("bed", "pulse", "space"):
        parts[name] *= patches["synth_group_gain"]
    parts["space"] *= patches["space_return_gain"]
    synth = parts["bed"]+parts["pulse"]+parts["inner"]+parts["veil"]+parts["space"]
    views = {**parts, "synth": synth}
    for index, patch in enumerate(patches["kicks"]):
        print("Rendering", patch["label"], "foundation", flush=True)
        loop = np.zeros((frames, 2), dtype=np.float32)
        gesture = kick(patch, rate, np.random.default_rng(score["seed"]+index))
        baseline = np.zeros((patch["baseline_frames"], 2), dtype=np.float32)
        for beat in range(64):
            add_wrapped(baseline, gesture*score["kick_accents"][beat%4], round(beat*beat_s*rate))
        baseline *= patch["calibration_gain"]
        if hashlib.sha256(baseline.tobytes()).hexdigest() != patch["baseline_pcm_sha256"]:
            raise ValueError("The reviewed kick changed: "+patch["id"])
        for event in (item for item in events if item["voice"] == "kick"):
            add_gesture(loop, gesture*event["strength"], round(event["beat"]*beat_s*rate))
        loop *= patch["calibration_gain"]
        views["kick-"+patch["id"]] = loop
        views["foundation-"+patch["id"]] = loop+parts["bass"]
        views["mix-"+patch["id"]] = loop+parts["bass"]+synth+parts["air"]+parts["percussion"]
    gain = patches["master_gain"]
    metadata = {}
    audio_root = OUT/"audio"/score["revision"]
    audio_root.mkdir(parents=True, exist_ok=True)
    for name, raw in views.items():
        print("Exporting", name, flush=True)
        audio = (raw*gain).astype(np.float32)
        true_peak = float(np.max(np.abs(signal.resample_poly(audio, 4, 1, axis=0))))
        if true_peak > 10**(patches["true_peak_ceiling_db"]/20):
            raise ValueError("Revise the musical balance for headroom: "+name)
        wav = OUT/"render"/f"{name}.wav"
        write_audio(wav, audio, sample_rate=rate, subtype="FLOAT")
        encoded = audio_root/f"{name}.m4a"
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-threads", "1",
                        "-i", str(wav), "-c:a", "aac", "-b:a", "256k", str(encoded)], check=True)
        activity = [round(float(np.sqrt(np.mean(block**2))), 6) for block in np.array_split(audio, 352)]
        metadata[name] = dict(path=f'audio/{score["revision"]}/{name}.m4a',
                             wav=f"render/{name}.wav", activity=activity,
                             peak_dbfs=20*math.log10(float(np.max(np.abs(audio)))),
                             true_peak_dbtp=20*math.log10(true_peak),
                             lufs=integrated_lufs(audio, sample_rate=rate))
    save(OUT/"render/manifest.json", dict(
        title=score["title"], revision=score["revision"], edition=score["edition"], tonality=score["tonality"],
        bpm=score["bpm"], bars=score["bars"], frames=frames, sample_rate=rate, duration_s=duration,
        common_gain=gain, midi=midi, kicks=patches["kicks"], phrases=score["phrases"],
        comparison_history=score["comparison_history"],
        views=metadata,
        harmonic_regions=score["harmonic_regions"], harmony_palette=score["harmony_palette"],
        harmony_windows_bars=score["harmony_windows_bars"],
        audio_origin="Fresh oscillators, seeded grain and generated diffuse impulse responses. No recorded audio input.",
        musical_model="The established G-centred gesture alternates foreground ownership with played harmonic scenes and genuine harmonic rests; their upper field and spatial releases follow the same form.",
    ))
    print(f"Ready: {duration:.3f} seconds · {len(views)} views", flush=True)


if __name__ == "__main__":
    main()
