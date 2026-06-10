# SPDX-License-Identifier: AGPL-3.0-only
"""Grid-locked groove and low-end enhancement for rendered candidates.

This is a deterministic repair pass for candidates whose original stems cannot
be remixed separately. It prints an aligned drum/low-end support stem, then
mixes that stem under the existing candidate with conservative master safety.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from setloom.schema import TrackSpec, load_spec
from setloom.stylepack import spec_duration_seconds

SAMPLE_RATE = 44_100


@dataclass(frozen=True)
class GrooveEvent:
    layer: str
    section: str
    bar: float
    beat: float
    gain: float
    pan: float = 0.0


def beat_seconds(spec: TrackSpec, beats: float) -> float:
    return beats * 60.0 / spec.bpm


def event_seconds(spec: TrackSpec, bar: float, beat: float = 0.0) -> float:
    return beat_seconds(spec, bar * 4 + beat)


def section_starts(spec: TrackSpec) -> dict[str, int]:
    starts: dict[str, int] = {}
    bar = 0
    for name, bars in spec.sections.items():
        starts[name.rstrip("0123456789_")] = bar
        bar += bars
    return starts


def section_lengths(spec: TrackSpec) -> dict[str, int]:
    return {name.rstrip("0123456789_"): bars for name, bars in spec.sections.items()}


def run(cmd: list[str]) -> None:
    import subprocess

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "command failed:\n"
            + " ".join(cmd)
            + "\nstdout:\n"
            + result.stdout[-2000:]
            + "\nstderr:\n"
            + result.stderr[-2000:]
        )


def add_event(
    events: list[GrooveEvent],
    starts: dict[str, int],
    section: str,
    rel_bar: float,
    beat: float,
    layer: str,
    gain: float,
    pan: float = 0.0,
) -> None:
    if section not in starts:
        return
    events.append(GrooveEvent(layer, section, starts[section] + rel_bar, beat, gain, pan))


def build_groove_plan(spec: TrackSpec) -> list[GrooveEvent]:
    starts = section_starts(spec)
    lengths = section_lengths(spec)
    events: list[GrooveEvent] = []

    for section, bars in lengths.items():
        if section in {"intro", "outro"}:
            intensity = 0.45
        elif section == "groove_a":
            intensity = 0.75
        elif section == "break":
            intensity = 0.28
        elif section == "drop":
            intensity = 0.92
        elif section == "peak":
            intensity = 1.00
        else:
            intensity = 0.60

        for rel_bar in range(bars):
            phrase = rel_bar % 8
            dense = section in {"drop", "peak"}
            if section != "break":
                for beat in (0.0, 1.0, 2.0, 3.0):
                    add_event(events, starts, section, rel_bar, beat, "kick_shadow", 0.25 * intensity)

            if section in {"groove_a", "drop", "peak"}:
                for beat in (0.5, 1.5, 2.5, 3.5):
                    add_event(events, starts, section, rel_bar, beat, "sub_pulse", 0.34 * intensity)
                for beat in (0.5, 1.5, 2.5, 3.5):
                    add_event(events, starts, section, rel_bar, beat, "open_hat", 0.23 * intensity, 0.05)
                for beat in (0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75):
                    pan = -0.08 if int(beat * 4) % 2 == 0 else 0.08
                    add_event(events, starts, section, rel_bar, beat, "closed_hat", 0.12 * intensity, pan)
                for beat in (0.375, 1.375, 2.375, 3.375):
                    add_event(events, starts, section, rel_bar, beat, "shaker", 0.11 * intensity, -0.12)
                for beat in (0.875, 1.875, 2.875, 3.875):
                    add_event(events, starts, section, rel_bar, beat, "shaker", 0.095 * intensity, 0.12)
                if dense and phrase in {4, 5, 6, 7}:
                    for beat in (0.0, 2.0):
                        add_event(events, starts, section, rel_bar, beat, "ride_lift", 0.10 * intensity, 0.08)
                if phrase in {3, 7}:
                    add_event(events, starts, section, rel_bar, 3.5, "fill_tick", 0.14 * intensity, -0.05)
                    add_event(events, starts, section, rel_bar, 3.75, "fill_tick", 0.12 * intensity, 0.05)
                if section in {"drop", "peak"} and phrase in {1, 5}:
                    add_event(events, starts, section, rel_bar, 1.0, "clap_ghost", 0.10 * intensity, -0.04)
                    add_event(events, starts, section, rel_bar, 3.0, "clap_ghost", 0.12 * intensity, 0.04)

    return sorted(events, key=lambda event: (event.bar, event.beat, event.layer))


def envelope(length: int, attack: int, decay: int) -> list[float]:
    values: list[float] = []
    for i in range(length):
        if i < attack:
            amp = i / max(1, attack)
        else:
            amp = max(0.0, 1.0 - (i - attack) / max(1, decay))
        values.append(amp)
    return values


def render_hit(layer: str, gain: float, pan: float, length: int, phase_seed: float) -> tuple[list[float], list[float]]:
    out: list[float] = []
    env_fast = envelope(length, max(1, int(0.002 * SAMPLE_RATE)), max(1, length - int(0.002 * SAMPLE_RATE)))
    for i, env in enumerate(env_fast):
        t = i / SAMPLE_RATE
        if layer == "kick_shadow":
            tone = math.sin(2 * math.pi * (54 + 38 * math.exp(-t * 36)) * t)
            click = math.sin(2 * math.pi * 2100 * t) * math.exp(-t * 95)
            sample = (tone * math.exp(-t * 18) * 0.95 + click * 0.12) * env
        elif layer == "sub_pulse":
            sample = math.sin(2 * math.pi * 55 * t) * math.exp(-t * 8.5) * env
        elif layer == "open_hat":
            noise = math.sin(2 * math.pi * (6120 + phase_seed * 120) * t)
            noise += math.sin(2 * math.pi * 8210 * t) * 0.45
            sample = noise * math.exp(-t * 18) * env
        elif layer == "closed_hat":
            noise = math.sin(2 * math.pi * 7420 * t) + math.sin(2 * math.pi * 10110 * t) * 0.50
            sample = noise * math.exp(-t * 42) * env
        elif layer == "shaker":
            noise = math.sin(2 * math.pi * (9400 + phase_seed * 300) * t)
            noise += math.sin(2 * math.pi * 11800 * t) * 0.42
            sample = noise * math.exp(-t * 30) * env
        elif layer == "ride_lift":
            sample = (
                math.sin(2 * math.pi * 5400 * t)
                + math.sin(2 * math.pi * 6900 * t) * 0.50
                + math.sin(2 * math.pi * 9100 * t) * 0.25
            ) * math.exp(-t * 9) * env
        elif layer == "clap_ghost":
            noise = math.sin(2 * math.pi * 1450 * t) + math.sin(2 * math.pi * 2300 * t) * 0.45
            sample = noise * math.exp(-t * 25) * env
        else:
            sample = (math.sin(2 * math.pi * 1800 * t) + math.sin(2 * math.pi * 4100 * t) * 0.35) * math.exp(-t * 45) * env
        out.append(sample * gain)
    left_gain = 1.0 - max(0.0, pan)
    right_gain = 1.0 + min(0.0, pan)
    return [x * left_gain for x in out], [x * right_gain for x in out]


def layer_duration(layer: str) -> float:
    return {
        "kick_shadow": 0.18,
        "sub_pulse": 0.24,
        "open_hat": 0.18,
        "closed_hat": 0.075,
        "shaker": 0.10,
        "ride_lift": 0.38,
        "clap_ghost": 0.11,
        "fill_tick": 0.085,
    }[layer]


def write_wav24(path: Path, left: array, right: array, peak_target: float = 0.70) -> None:
    peak = max(max((abs(x) for x in left), default=0.0), max((abs(x) for x in right), default=0.0), 1e-9)
    gain = min(1.0, peak_target / peak)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(3)
        wav.setframerate(SAMPLE_RATE)
        chunk = bytearray()
        for left_sample, right_sample in zip(left, right):
            for sample in (left_sample * gain, right_sample * gain):
                value = int(max(-1.0, min(1.0, sample)) * 8_388_607)
                if value < 0:
                    value += 1 << 24
                chunk.extend((value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF))
            if len(chunk) >= 262_144:
                wav.writeframesraw(bytes(chunk))
                chunk.clear()
        if chunk:
            wav.writeframesraw(bytes(chunk))


def render_groove_stem(spec: TrackSpec, out_dir: Path) -> dict[str, int]:
    events = build_groove_plan(spec)
    length = int((spec_duration_seconds(spec) + 4.0) * SAMPLE_RATE)
    left = array("f", [0.0]) * length
    right = array("f", [0.0]) * length
    counts: dict[str, int] = {}

    for index, event in enumerate(events):
        counts[event.layer] = counts.get(event.layer, 0) + 1
        start = int(event_seconds(spec, event.bar, event.beat) * SAMPLE_RATE)
        hit_length = int(layer_duration(event.layer) * SAMPLE_RATE)
        hit_left, hit_right = render_hit(event.layer, event.gain, event.pan, hit_length, index * 0.137)
        for i, (l_sample, r_sample) in enumerate(zip(hit_left, hit_right)):
            idx = start + i
            if 0 <= idx < length:
                left[idx] += l_sample
                right[idx] += r_sample

    raw = out_dir / ".raw-stem-groove-drums.wav"
    write_wav24(raw, left, right, 0.70)
    dst = out_dir / "stem-groove-drums.wav"
    run(
        [
            "sox",
            str(raw),
            str(dst),
            "highpass",
            "32",
            "lowpass",
            "12500",
            "gain",
            "-n",
            "-11.0",
        ]
    )
    raw.unlink(missing_ok=True)
    return counts


def mix_boost(source_dir: Path, out_dir: Path, spec: TrackSpec) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for source in source_dir.iterdir():
        if source.is_file() and source.name != "vibe_mix.wav":
            shutil.copy2(source, out_dir / source.name)
    counts = render_groove_stem(spec, out_dir)
    premaster = out_dir / ".premaster-grooveboost.wav"
    run(
        [
            "sox",
            "-m",
            "-v",
            "0.78",
            str(source_dir / "vibe_mix.wav"),
            "-v",
            "0.36",
            str(out_dir / "stem-groove-drums.wav"),
            str(premaster),
            "gain",
            "-n",
            "-8",
        ]
    )
    run(
        [
            "sox",
            str(premaster),
            str(out_dir / "vibe_mix.wav"),
            "highpass",
            "28",
            "compand",
            "0.004,0.100",
            "6:-70,-70,-36,-31,-24,-20,-18,-15,-12,-10,-8,-7,-4,-3",
            "0",
            "-90",
            "0.02",
            "gain",
            "5",
            "compand",
            "0.001,0.012",
            "-5,-5,-2,-2,0,-1.2",
            "0",
            "-90",
            "0.001",
            "gain",
            "-n",
            "-1.8",
        ]
    )
    premaster.unlink(missing_ok=True)
    report = {
        "design_target": "melodic-techno grid-locked multi-layer drum and low-end support",
        "alignment": "all hits are derived from bpm/bar/beat positions and rendered to exact sample indexes",
        "counts": counts,
        "mix_rule": "existing full mix tucked down; groove drum support added underneath with safety limiting",
        "stems": {
            "groove_drums": "stem-groove-drums.wav",
            "mix": "vibe_mix.wav",
        },
    }
    (out_dir / "groove-boost-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )


def check_tools() -> None:
    missing = [tool for tool in ("sox",) if shutil.which(tool) is None]
    if missing:
        raise SystemExit("missing required existing tool(s): " + ", ".join(missing))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add grid-locked groove layers to a candidate")
    parser.add_argument("spec")
    parser.add_argument("source_variant")
    parser.add_argument("out_variant")
    args = parser.parse_args(argv)

    check_tools()
    mix_boost(Path(args.source_variant), Path(args.out_variant), load_spec(args.spec))
    print(Path(args.out_variant) / "vibe_mix.wav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
