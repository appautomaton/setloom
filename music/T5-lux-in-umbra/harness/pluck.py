# SPDX-License-Identifier: AGPL-3.0-only
"""SuperCollider pluck lane rendering."""

from __future__ import annotations

import asyncio
import math

import numpy as np
import soundfile as sf
from supriya import Envelope, Score, SynthDef, SynthDefBuilder, scsynth, ugens

from .context import BAR_S, BEAT_S, NOTE, OUT, PLUCK_PATCH, SCSYNTH, SR, TOTAL_BARS
from .dsp import fit, midi_to_hz, normalize
from .events import pluck_events


def build_pluck_synthdef() -> SynthDef:
    voice = PLUCK_PATCH["voice"]
    envelopes = PLUCK_PATCH["envelopes"]
    effects = PLUCK_PATCH["effects"]
    defaults = dict(PLUCK_PATCH["defaults"])
    defaults.update(
        {
            "fold_drive": voice["fold_drive"],
            "comb_gain": effects["comb_gain"],
            "comb_decay_time": effects["comb_decay_time"],
            "freeverb_mix": effects["freeverb_mix"],
            "freeverb_room_size": effects["freeverb_room_size"],
            "freeverb_damping": effects["freeverb_damping"],
            "output_hpf": voice["output_hpf_hz"],
        }
    )
    with SynthDefBuilder(**defaults) as builder:
        freq = builder["freq"]
        amp = builder["amp"]
        release = builder["release"]
        cutoff = builder["cutoff"]
        bright = builder["bright"]
        sweep = builder["sweep"]
        pan = builder["pan"]
        mode = builder["mode"]
        fold_drive = builder["fold_drive"]
        comb_gain = builder["comb_gain"]
        comb_decay_time = builder["comb_decay_time"]
        freeverb_mix = builder["freeverb_mix"]
        freeverb_room_size = builder["freeverb_room_size"]
        freeverb_damping = builder["freeverb_damping"]
        output_hpf = builder["output_hpf"]
        amp_env = ugens.EnvGen.ar(envelope=Envelope.percussive(envelopes["amp_attack"], release, curve=envelopes["amp_curve"]), done_action=2)
        filt_env = ugens.EnvGen.ar(
            envelope=Envelope.percussive(envelopes["filter_attack"], envelopes["filter_decay"], curve=envelopes["filter_curve"]),
            level_scale=1.0,
        )
        bend = ugens.XLine.ar(start=freq * envelopes["bend_start_ratio"], stop=freq, duration=envelopes["bend_duration"])
        warm = (
            ugens.Saw.ar(frequency=freq * 0.997)
            + ugens.Saw.ar(frequency=freq)
            + ugens.Saw.ar(frequency=freq * 1.003)
            + (ugens.Pulse.ar(frequency=freq * 0.5, width=0.42) * 0.12)
        ) * voice["warm_gain"]
        clean = (
            ugens.VarSaw.ar(frequency=freq * 0.995, width=0.38)
            + ugens.VarSaw.ar(frequency=freq * 1.006, width=0.62)
            + (ugens.Pulse.ar(frequency=freq * 2.0, width=0.24) * 0.18)
            + (ugens.WhiteNoise.ar() * 0.018)
        ) * voice["clean_gain"]
        singing = (
            ugens.Saw.ar(frequency=bend * 0.995)
            + ugens.Saw.ar(frequency=bend * 1.005)
            + (ugens.VarSaw.ar(frequency=bend * 2.0, width=0.47) * 0.16)
        ) * voice["singing_gain"]
        source = ugens.Select.ar(selector=mode, sources=[warm, clean, singing])
        source = ugens.HPF.ar(source=ugens.LeakDC.ar(source=source), frequency=voice["input_hpf_hz"])
        filter_freq = ugens.Clip.ar(
            source=cutoff * bright * sweep + (filt_env * cutoff * voice["filter_env_scale"]),
            minimum=voice["filter_min_hz"],
            maximum=voice["filter_max_hz"],
        )
        filtered = ugens.MoogFF.ar(source=source, frequency=filter_freq * voice["moog_frequency_scale"], gain=voice["moog_gain"])
        driven = ugens.Fold.ar(source=filtered * fold_drive, minimum=voice["fold_min"], maximum=voice["fold_max"]) * voice["fold_output_gain"]
        dry = driven * amp_env * amp
        delay = (
            ugens.CombC.ar(
                source=dry,
                maximum_delay_time=effects["comb_max_delay"],
                delay_time=effects["comb_delay_beats"] * BEAT_S,
                decay_time=comb_decay_time,
            )
            * comb_gain
        )
        wet = ugens.FreeVerb.ar(source=dry + delay, mix=freeverb_mix, room_size=freeverb_room_size, damping=freeverb_damping)
        out = ugens.HPF.ar(source=dry + delay + wet, frequency=output_hpf)
        out = ugens.Limiter.ar(source=out, level=voice["limiter_level"], duration=voice["limiter_duration"])
        ugens.Out.ar(bus=0, source=ugens.Pan2.ar(source=out, position=pan))
    return builder.build(PLUCK_PATCH["synthdef_name"])


def timbre_scene_for_bar(bar: int) -> dict:
    scene: dict = {}
    for candidate in PLUCK_PATCH.get("timbre_scenes", []):
        if int(candidate["start_bar"]) <= bar < int(candidate["end_bar"]):
            scene = candidate
    return scene


def render_pluck() -> np.ndarray:
    output_path = OUT / "stem-pluck.wav"
    synthdef = build_pluck_synthdef()
    option_cfg = PLUCK_PATCH["options"]
    options = scsynth.Options(
        executable=SCSYNTH,
        input_bus_channel_count=option_cfg["input_bus_channel_count"],
        output_bus_channel_count=option_cfg["output_bus_channel_count"],
        sample_rate=SR,
        verbosity=option_cfg["verbosity"],
    )
    score = Score(options=options)
    sat = score.at
    sadd_synthdefs = score.add_synthdefs
    sadd_synth = score.add_synth
    srender = score.render
    with sat(0.0):
        sadd_synthdefs(synthdef)
    event_cfg = PLUCK_PATCH["event_mapping"]
    voice = PLUCK_PATCH["voice"]
    effects = PLUCK_PATCH["effects"]
    for i, event in enumerate(pluck_events()):
        phrase_pos = event.bar / TOTAL_BARS
        scene = timbre_scene_for_bar(event.bar)
        release = max(
            event_cfg["release_min"],
            min(event_cfg["release_max"], event.duration_s * event_cfg["release_duration_scale"] + event_cfg["release_extra_seconds"]),
        )
        release *= float(scene.get("release_mult", 1.0))
        release = max(event_cfg["release_min"], min(event_cfg["release_max"] * 1.4, release))
        pan_depth = event_cfg["pan_depth"] * float(scene.get("pan_depth_mult", 1.0))
        pan = pan_depth * math.sin((i * event_cfg["pan_event_scale"]) + (NOTE[event.pitch] * event_cfg["pan_pitch_scale"]))
        pan = max(-0.95, min(0.95, pan))
        amp = event_cfg["amp_base"] * ((event.velocity / 100.0) ** event_cfg["amp_velocity_exponent"])
        amp *= float(scene.get("amp_mult", 1.0))
        cutoff = event_cfg["cutoff_base"] + (event.velocity - event_cfg["cutoff_velocity_center"]) * event_cfg["cutoff_velocity_slope"]
        cutoff += float(scene.get("cutoff_bias", 0.0))
        bright = event_cfg["bright_base"] + (event.velocity - event_cfg["bright_velocity_center"]) * event_cfg["bright_velocity_slope"]
        bright *= float(scene.get("bright_mult", 1.0))
        bright += float(scene.get("bright_bias", 0.0))
        bright = max(0.25, bright)
        sweep = event_cfg["sweep_base"] + event_cfg["sweep_phrase_scale"] * phrase_pos
        sweep *= float(scene.get("sweep_mult", 1.0))
        sweep += float(scene.get("sweep_bias", 0.0))
        sweep = max(0.25, sweep)
        with sat(event.start_s):
            sadd_synth(
                synthdef,
                freq=midi_to_hz(NOTE[event.pitch]),
                amp=amp,
                release=release,
                cutoff=cutoff,
                bright=bright,
                sweep=sweep,
                pan=pan,
                mode=float(scene.get("mode", event_cfg["mode"])),
                fold_drive=voice["fold_drive"] * float(scene.get("fold_drive_mult", 1.0)),
                comb_gain=effects["comb_gain"] * float(scene.get("comb_gain_mult", 1.0)),
                comb_decay_time=effects["comb_decay_time"] * float(scene.get("comb_decay_mult", 1.0)),
                freeverb_mix=float(scene.get("freeverb_mix", effects["freeverb_mix"] * float(scene.get("freeverb_mix_mult", 1.0)))),
                freeverb_room_size=float(scene.get("freeverb_room_size", effects["freeverb_room_size"])),
                freeverb_damping=float(scene.get("freeverb_damping", effects["freeverb_damping"])),
                output_hpf=float(scene.get("output_hpf_hz", voice["output_hpf_hz"])),
            )
    path, exit_code = asyncio.run(
        srender(
            output_file_path=output_path,
            duration=(TOTAL_BARS * BAR_S) + 3.0,
            header_format="WAV",
            sample_format="FLOAT",
            sample_rate=SR,
            options=options,
        )
    )
    if exit_code != 0 or path is None:
        raise RuntimeError(f"scsynth render failed: exit={exit_code}, path={path}")
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    if sr != SR:
        raise ValueError(f"pluck stem sr={sr}, expected {SR}")
    return fit(normalize(audio[:, :2], peak=event_cfg["output_peak"]))
