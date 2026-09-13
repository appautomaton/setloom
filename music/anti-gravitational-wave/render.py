# SPDX-License-Identifier: AGPL-3.0-only
"""Render the editable production MIDI to a candidate or scratch WAV."""

import argparse
import copy
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import mido
import numpy as np
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfilt

import baseline_synth as synth
import piano_synth
import electric_piano
from mix_processing import prepare_mix
from midi_import import import_midi
from setloom.audio import integrated_lufs, write_audio, write_master

HERE = Path(__file__).resolve().parent
REPO = next(p for p in HERE.parents if (p / "pyproject.toml").exists())


def project_midi(full, work):
    names = [tr.name for tr in full.tracks]
    assert len(names) == len(set(names)) == 17

    def save(filename, tracks):
        out = mido.MidiFile(type=1, ticks_per_beat=full.ticks_per_beat)
        out.tracks = tracks
        out.save(work / filename)
        return work / filename

    tracks = {tr.name: tr for tr in full.tracks}
    conductor = full.tracks[0]
    excluded = {
        "piano",
        "piano_B_lower",
        "piano_B_upper",
        "intro_source_spine",
        "intro_source_short_high",
        "electric_piano",
    }
    original = save("synth.mid", [tr for tr in full.tracks if tr.name not in excluded])
    a = save("piano-A.mid", [conductor, tracks["piano"]])
    b_tracks = [conductor]
    for name, translated in [("piano_B_lower", "pulse_lower"), ("piano_B_upper", "pulse_upper")]:
        track = mido.MidiTrack(e.copy() for e in tracks[name])
        track.name = translated
        b_tracks.append(track)
    return original, a, save("piano-B.mid", b_tracks)


def hits(track, ppq):
    tick = 0
    result = []
    for e in track:
        tick += e.time
        if e.type == "note_on" and e.velocity:
            result.append((mido.tick2second(tick, ppq, 400000), e.velocity))
    return result


def short_voice(events, settings, time, sr):
    """Supported intro reconstruction noise/metal voice, with MIDI dynamics."""
    output = np.zeros((len(time), 2))
    for onset, velocity in events:
        start = np.searchsorted(time, onset)
        end = min(len(time), np.searchsorted(time, onset + 0.16))
        local = time[start:end] - onset
        rng = np.random.default_rng(settings["short_seed"] + round(onset * 1000))
        common = rng.normal(size=len(local))
        noise = np.column_stack(
            [0.9 * common + 0.3 * rng.normal(size=len(local)) for _ in range(2)]
        )
        noise = sosfilt(
            butter(2, [6500, 14000], btype="bandpass", fs=sr, output="sos"), noise, axis=0
        )
        metal = sum(np.sin(2 * np.pi * f * local) for f in [7400, 9880, 12520]) / 3
        envelope = (
            np.minimum(local / 0.0015, 1)
            * np.exp(-local / 0.020)
            * np.clip((0.16 - local) / 0.008, 0, 1)
        )
        output[start:end] += (
            (0.88 * noise + 0.12 * metal[:, None]) * envelope[:, None] * (velocity / 100) ** 2
        )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=REPO / "tmp/anti-gravitational-wave")
    parser.add_argument(
        "--keep-premaster",
        action="store_true",
        help="Retain the mix before mastering for level revisions.",
    )
    args = parser.parse_args()
    out = args.out_dir.resolve()
    roots = [REPO / "tmp", Path(tempfile.gettempdir()), Path("/tmp")]
    if (
        not any(out.is_relative_to(p.resolve()) for p in roots)
        or out == HERE
        or HERE in out.parents
    ):
        raise ValueError("Choose a scratch output directory outside production source.")
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError("Choose an empty output directory.")
    destination = out / "Anti Gravitational Wave.wav"
    recipe = json.loads((HERE / "recipe.json").read_text())
    controls = json.loads((HERE / "controls.json").read_text())
    patch = json.loads((HERE / "patch.json").read_text())
    piano_patch = json.loads((HERE / "piano-patch.json").read_text())
    ep_patch = json.loads((HERE / "electric-piano-patch.json").read_text())
    full = mido.MidiFile(HERE / "performance.mid")
    assert {e.tempo for tr in full.tracks for e in tr if e.type == "set_tempo"} == {400000}
    sr = recipe["sample_rate"]
    executable = shutil.which("fluidsynth") or piano_patch["fluidsynth"]
    assert Path(executable).is_file()
    piano_patch["fluidsynth"] = executable
    soundfont = REPO / recipe["instrument"]["soundfont"]
    with tempfile.TemporaryDirectory(
        prefix="anti-gravitational-wave-render-", dir=destination.parent
    ) as directory:
        work = Path(directory)
        original, a_midi, b_midi = project_midi(full, work)
        score = import_midi(original, controls)
        frames = round(score["duration_seconds"] * sr)
        print(
            "Rendering both editable piano performances with the existing sampled grand...",
            flush=True,
        )
        a, instrument = piano_synth.synthesize(a_midi, piano_patch, REPO, work, frames, sr)
        a = a.astype(np.float32).astype(np.float64)
        a *= 10 ** (recipe["gain_db"]["A_from_existing_bus"] / 20)
        raw = work / "piano-B-dry.wav"
        subprocess.run(
            [
                executable,
                "-ni",
                "-r",
                "48000",
                "-g",
                str(recipe["B_engine_gain"]),
                "-R",
                "0",
                "-C",
                "0",
                "-o",
                "synth.polyphony=256",
                "-T",
                "wav",
                "-O",
                "float",
                "-F",
                str(raw),
                str(soundfont),
                str(b_midi),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        b, source_sr = sf.read(raw, dtype="float32", always_2d=True)
        assert source_sr == 48000
        b = resample_poly(b, 147, 160, axis=0).astype(np.float32)
        assert len(b) >= frames
        b = b[:frames].astype(np.float64)
        b *= 10 ** (recipe["gain_db"]["B_from_dry_engine"] / 20)
        a += b
        del b
        n = round(0.005 * sr)
        fade = np.sin(np.linspace(0, np.pi / 2, n)) ** 2
        a[:n] *= fade[:, None]
        a[-n:] *= fade[::-1, None]
        a *= 10 ** (recipe["gain_db"]["common_pair"] / 20)
        pair_path = work / "piano-pair.wav"
        sf.write(pair_path, a, sr, subtype="PCM_24")
        del a
        intro = controls["intro"]
        for e in score["hats"]:
            if e["source_seconds"] < intro["end_seconds"]:
                e["gain_db"] += intro["existing_long_percussion_bus_gain_db"]
        for e in score["bright_percussion"]:
            if e[0] < intro["end_seconds"]:
                e[1] += intro["existing_long_percussion_bus_gain_db"]
        print("Rendering synth, bass, percussion and MIDI-triggered FX...", flush=True)
        audio = synth.synthesize(score, patch)
        pair, _ = sf.read(pair_path, always_2d=True)
        audio += pair * 10 ** (recipe["gain_db"]["piano_mix_bus"] / 20)
        del pair
        tracks = {tr.name: tr for tr in full.tracks}
        spine_events = hits(tracks["intro_source_spine"], full.ticks_per_beat)
        short_events = hits(tracks["intro_source_short_high"], full.ticks_per_beat)
        last = max(t for t, v in spine_events + short_events) + 0.4
        intro_frames = min(frames, round(last * sr))
        time = np.arange(intro_frames) / sr
        spine_score = copy.deepcopy(score)
        spine_score["snares"] = [[t, "hit", 40 * np.log10(v / 100)] for t, v in spine_events]
        for name, value in [
            ("snare_gain_db", 0),
            ("snare_lowpass_hz", intro["spine_lowpass_hz"]),
            ("snare_tail_mix", intro["spine_tail_mix"]),
        ]:
            spine_score["section_controls"][name] = [[0, value], [last, value]]
        spine_patch = copy.deepcopy(patch)
        spine_patch["snare"].update(
            decay_ms=intro["spine_decay_ms"], tail_ms=intro["spine_tail_ms"]
        )
        audio[:intro_frames] += synth.snare_voice(spine_score, spine_patch, time) * 10 ** (
            intro["spine_bus_gain_db"] / 20
        )
        audio[:intro_frames] += short_voice(short_events, intro, time, sr) * 10 ** (
            intro["short_bus_gain_db"] / 20
        )
        print("Rendering the new editable electric-piano counterpart...", flush=True)
        ep = electric_piano.synthesize(full, ep_patch, frames, sr)
        ep_levels = []
        for start, end in [
            (29.034, 30.034),
            (30.034, 32.234),
            (32.234, 38.634),
            (38.634, 45.434),
            (45.434, 49.834),
            (49.834, 51.434),
            (51.434, 52.034),
            (211.434, 217.834),
            (217.834, 221.034),
            (221.034, 223.634),
            (223.634, 225.034),
        ]:
            lo, hi = round(start * sr), round(end * sr)
            power = float(np.mean(ep[lo:hi] ** 2))
            backing = float(np.mean(audio[lo:hi] ** 2))
            ep_levels.append(
                {
                    "seconds": [start, end],
                    "ep_rms_dbfs": float(10 * np.log10(max(power, 1e-20))),
                    "ep_relative_to_existing_mix_db": float(
                        10 * np.log10(max(power, 1e-20) / max(backing, 1e-20))
                    ),
                }
            )
        audio += ep
        del ep
        assert audio.shape == (frames, 2) and np.isfinite(audio).all()
        print("Mastering the full local arrangement and checking levels...", flush=True)
        audio = prepare_mix(
            audio, sr, patch["audition"]["edge_fade_ms"], patch["audition"]["mono_below_hz"]
        )
        print("Premaster LUFS:", integrated_lufs(audio, sample_rate=sr), flush=True)
        if args.keep_premaster:
            write_audio(out / "premaster.wav", audio, sample_rate=sr, subtype="FLOAT")
        levels = write_master(destination, audio, sample_rate=sr, **recipe["mastering"])
        report = {
            "status": "Render completed",
            "file": destination.name,
            "duration_seconds": frames / sr,
            "frames": frames,
            "sample_rate": sr,
            "subtype": "PCM_24",
            "mastering": levels,
            "finite_audio": bool(np.isfinite(audio).all()),
            "render_input": "performance.mid plus local JSON settings; no score regeneration",
            "synthesis_audio_input": str(soundfont.relative_to(REPO)),
            "original_or_separated_recording_used_in_render": False,
            "instrument_credit": recipe["instrument"]["credit"],
            "instrument_license": recipe["instrument"]["license"],
            "piano_A_dry_clipped_samples": instrument["dry_clipped_samples"],
            "electric_piano": {
                "track": "electric_piano",
                "midi_channel_zero_based": 12,
                "patch": "electric-piano-patch.json",
                "synthesis": "Locally authored FM/additive tine instrument",
                "isolated_levels": ep_levels,
            },
            "outro": controls["outro"],
        }
        (out / "render.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(levels, indent=2), flush=True)


if __name__ == "__main__":
    main()
