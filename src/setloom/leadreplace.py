# SPDX-License-Identifier: AGPL-3.0-only
"""Logic-library sample based lead replacement.

This repair renderer keeps the existing groove/mix context, replaces only the
rejected lead bus, and writes a new candidate variant.

It does not require opening Logic Pro. It uses installed Logic Library samples
as source material, then composes a deterministic piano-forward melodic-techno
lead family from the track spec.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from setloom.schema import TrackSpec, load_spec
from setloom.stylepack import spec_duration_seconds

SAMPLE_RATE = 44_100
BARS_PER_FULL_HOOK = 8
LOGIC_LIBRARY = Path(
    os.environ.get("SETLOOM_LOGIC_LIBRARY", "/Users/ac/Music/Logic Pro Library.bundle")
)

# Deliberately less aggressive than the rejected -5 LUFS pass. The goal is a
# loud candidate without crushed piano transients or audible limiter grit.
MASTER_CHAIN = (
    "highpass",
    "28",
    "compand",
    "0.004,0.120",
    "6:-70,-70,-36,-31,-24,-20,-18,-15,-12,-10,-8,-7,-4,-3",
    "0",
    "-90",
    "0.02",
    "gain",
    "9",
    "compand",
    "0.001,0.012",
    "-5,-5,-2,-2,0,-1.2",
    "0",
    "-90",
    "0.001",
    "gain",
    "-n",
    "-2.0",
)

NOTE_PC = {
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

NOTE_NAMES_SHARP = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


@dataclass(frozen=True)
class SampleSource:
    key: str
    path: Path
    root_midi: int
    role: str


@dataclass(frozen=True)
class LeadEvent:
    layer: str
    source: str
    section: str
    bar: float
    beat: float
    pitch: str
    beats: float
    gain: float
    pan: float = 0.0
    fade: float = 0.05
    reverse: bool = False


SOURCES = {
    "piano_c5": SampleSource(
        "piano_c5",
        LOGIC_LIBRARY / "Samples/Keyboard/Acoustic Piano/Other/I-95 Chronicle Piano_C5.aif",
        72,
        "Logic Sample: I-95 Chronicle Piano C5",
    ),
    "piano_c3": SampleSource(
        "piano_c3",
        LOGIC_LIBRARY / "Samples/Keyboard/Acoustic Piano/Other/I-95 Chronicle Piano_C3.aif",
        48,
        "Logic Sample: I-95 Chronicle Piano C3",
    ),
    "piano_airy": SampleSource(
        "piano_airy",
        LOGIC_LIBRARY / "Samples/Keyboard/Acoustic Piano/Other/Airy Piano.aif",
        72,
        "Logic Sample: Airy Piano",
    ),
    "granular": SampleSource(
        "granular",
        LOGIC_LIBRARY
        / "Samples/Alchemy Samples/Strings/Synth Strings/Granular Strings/Granular String C5.caf",
        72,
        "Logic Alchemy Sample: Granular String C5",
    ),
    "vibe": SampleSource(
        "vibe",
        LOGIC_LIBRARY / "Samples/Mallet/Vibraphone_consolidated.caf",
        60,
        "Logic Sample: Vibraphone",
    ),
}

FAMILY_STEMS = {
    "main": "stem-lead-main.wav",
    "fx": "stem-lead-fx.wav",
    "atmos": "stem-lead-atmos.wav",
    "mixfx": "stem-mix-fx.wav",
}

LAYER_FAMILY = {
    "piano_hook": "main",
    "piano_low": "main",
    "piano_color": "main",
    "piano_air": "main",
    "piano_octave": "main",
    "vibe_unison": "fx",
    "vibe_sparkle": "fx",
    "granular_air": "atmos",
    "pre_cue": "atmos",
    "reverse_swell": "mixfx",
    "granular_bloom": "mixfx",
    "vibe_chime": "mixfx",
    "phrase_throw": "mixfx",
}


def run(cmd: list[str]) -> None:
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


def midi(note_name: str) -> int:
    octave = int(note_name[-1])
    pitch = note_name[:-1]
    return 12 * (octave + 1) + NOTE_PC[pitch]


def note_name(value: int) -> str:
    octave = value // 12 - 1
    return f"{NOTE_NAMES_SHARP[value % 12]}{octave}"


def transpose_pitch(pitch: str, semitones: int) -> str:
    return note_name(midi(pitch) + semitones)


def shimmer_pitch(pitch: str) -> str:
    value = midi(pitch)
    return note_name(value + 12 if value <= 77 else value)


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


def build_hook(
    events: list[LeadEvent],
    starts: dict[str, int],
    section: str,
    rel_bar: float,
    *,
    intensity: float,
    lifted: bool = False,
    sparse: bool = False,
    final_turn: bool = False,
) -> None:
    """Eight-bar, two-beat-cell piano hook.

    The hook is intentionally assertive: it anchors on beat 1/3 of each bar,
    then answers inside the half-bar cell. Variations happen at phrase marks,
    not through hesitant pickup-note wandering.
    """

    def add(
        layer: str,
        source: str,
        bar: float,
        beat: float,
        pitch: str,
        beats: float,
        gain: float,
        pan: float = 0.0,
        fade: float = 0.05,
        reverse: bool = False,
    ) -> None:
        events.append(
            LeadEvent(
                layer,
                source,
                section,
                starts[section] + rel_bar + bar,
                beat,
                pitch,
                beats,
                gain * intensity,
                pan,
                fade,
                reverse,
            )
        )

    def add_piano_stack(bar: float, beat: float, pitch: str, beats: float, gain: float) -> None:
        is_anchor = beat in (0.0, 2.0)
        base_beats = min(beats, 0.40 if sparse else 0.52)
        pan_air = -0.07 if beat < 2.0 else 0.07
        add("piano_hook", "piano_c5", bar, beat, pitch, base_beats, gain, fade=0.030)
        if not sparse:
            add(
                "piano_air",
                "piano_airy",
                bar,
                beat + 0.015,
                pitch,
                min(base_beats + 0.10, 0.58),
                gain * 0.18,
                pan_air,
                0.050,
            )
        elif is_anchor:
            add(
                "piano_air",
                "piano_airy",
                bar,
                beat + 0.012,
                pitch,
                min(base_beats + 0.08, 0.46),
                gain * 0.12,
                pan_air,
                0.042,
            )
        if is_anchor:
            add(
                "piano_octave",
                "piano_c5",
                bar,
                beat + 0.006,
                shimmer_pitch(pitch),
                min(base_beats * 0.52, 0.24),
                gain * (0.12 if not sparse else 0.075),
                -pan_air,
                0.026,
            )
            if not sparse and bar in (0, 2, 4, 6):
                add(
                    "vibe_unison",
                    "vibe",
                    bar,
                    beat + 0.020,
                    shimmer_pitch(pitch),
                    0.16,
                    gain * 0.052,
                    pan_air,
                    0.022,
                )

    if not sparse:
        add("pre_cue", "granular", -0.55, 0.0, "D6", 2.20, 0.13, 0.16, 0.18, True)
        add("pre_cue", "granular", -0.25, 1.5, "A5", 1.20, 0.08, -0.14, 0.16, True)

    phrase = (
        # Call: root -> 9th -> minor third, short and confident.
        ((0.0, "D5", 0.36, 0.72), (1.50, "E5", 0.18, 0.38), (2.00, "F5", 0.32, 0.56)),
        # Response: fifth falls back, leaving space after the answer.
        ((0.0, "A5", 0.30, 0.62), (1.75, "G5", 0.16, 0.34), (2.00, "F5", 0.28, 0.48)),
        # Development: repeats the call but reaches higher, not longer.
        ((0.0, "D5", 0.32, 0.60), (1.00, "F5", 0.18, 0.34), (2.00, "A5", 0.30, 0.62)),
        # Tension: C/B color gives lift without a sad classical cadence.
        ((0.0, "C6", 0.26, 0.64), (1.50, "B5", 0.15, 0.34), (2.00, "A5", 0.30, 0.54), (3.50, "E6", 0.14, 0.32)),
        # Lifted call.
        ((0.0, "D6", 0.34, 0.72), (1.50, "C6", 0.16, 0.36), (2.00, "A5", 0.30, 0.56)),
        # Lifted response.
        ((0.0, "F6", 0.28, 0.58), (1.75, "E6", 0.14, 0.32), (2.00, "D6", 0.28, 0.50)),
        # Pre-turn.
        ((0.0, "C6", 0.26, 0.54), (1.50, "A5", 0.14, 0.30), (2.00, "B5", 0.26, 0.48)),
        # Turnaround: resolves to D but keeps an upward tail for phrase energy.
        ((0.0, "A5", 0.24, 0.48), (1.50, "C6", 0.14, 0.32), (2.00, "D6", 0.32, 0.64), (3.50, "E6", 0.14, 0.30)),
    )

    for bar, cell in enumerate(phrase):
        b = float(bar)
        if lifted and bar >= 4:
            cell = tuple(
                (beat, transpose_pitch(pitch, 0 if midi(pitch) >= midi("A5") else 12), beats, gain)
                for beat, pitch, beats, gain in cell
            )
        if final_turn and bar in (6, 7):
            cell = (
                ((0.0, "C6", 0.25, 0.54), (1.50, "A5", 0.14, 0.30), (2.00, "E6", 0.26, 0.52))
                if bar == 6
                else ((0.0, "A5", 0.22, 0.46), (1.50, "C6", 0.14, 0.32), (2.00, "D6", 0.34, 0.68), (3.50, "F6", 0.14, 0.34))
            )
        if sparse and bar not in (0, 2, 4, 6):
            continue
        for beat, pitch, beats, gain in cell:
            if sparse and beat not in (0.0, 1.50, 2.00):
                continue
            add_piano_stack(b, beat, pitch, beats, gain)
        if not sparse and bar in (0, 2, 4, 6):
            add("piano_low", "piano_c3", b, 0.0, "D3" if bar != 4 else "A3", 0.28, 0.14)
        if not sparse and bar in (1, 3, 5, 7):
            add("vibe_sparkle", "vibe", b, 3.45, "A5" if bar < 5 else "B5", 0.30, 0.12, 0.07)
        if not sparse and bar in (3, 7):
            add("granular_air", "granular", b, 3.20, "D6" if bar == 7 else "A5", 0.95, 0.075, 0.14)


def build_anchor_hook(
    events: list[LeadEvent],
    starts: dict[str, int],
    section: str,
    rel_bar: float,
    *,
    intensity: float,
    every_bar: bool,
    lifted: bool = False,
) -> None:
    """Busy-section piano: fewer, stronger half-bar anchors.

    When the drums get dense, the piano should not keep answering on every
    offbeat. It becomes a confident harmonic/rhythmic support hook: beat 1 and
    beat 3 anchors, low octave at phrase points, sparse sparkle only at turns.
    """

    def add(
        layer: str,
        source: str,
        bar: float,
        beat: float,
        pitch: str,
        beats: float,
        gain: float,
        pan: float = 0.0,
        fade: float = 0.05,
        reverse: bool = False,
    ) -> None:
        events.append(
            LeadEvent(
                layer,
                source,
                section,
                starts[section] + rel_bar + bar,
                beat,
                pitch,
                beats,
                gain * intensity,
                pan,
                fade,
                reverse,
            )
        )

    def add_anchor_stack(
        bar: float,
        beat: float,
        pitch: str,
        beats: float,
        gain: float,
        *,
        phrase_bar: int,
    ) -> None:
        pan_air = -0.06 if beat < 2.0 else 0.06
        base_beats = min(beats, 0.34 if not every_bar else 0.42)
        add("piano_hook", "piano_c5", bar, beat, pitch, base_beats, gain, fade=0.026)
        add(
            "piano_air",
            "piano_airy",
            bar,
            beat + 0.012,
            pitch,
            min(base_beats + 0.08, 0.48),
            gain * 0.14,
            pan_air,
            0.040,
        )
        add(
            "piano_octave",
            "piano_c5",
            bar,
            beat + 0.006,
            shimmer_pitch(pitch),
            min(base_beats * 0.50, 0.20),
            gain * 0.08,
            -pan_air,
            0.022,
        )
        if phrase_bar in (0, 4, 7) or lifted:
            add(
                "vibe_unison",
                "vibe",
                bar,
                beat + 0.020,
                shimmer_pitch(pitch),
                0.15,
                gain * 0.036,
                pan_air,
                0.020,
            )

    add("pre_cue", "granular", -0.35, 1.5, "D6", 1.25, 0.075, 0.14, 0.16, True)
    anchor_phrase = (
        ((0.0, "D5", 0.32, 0.68), (2.0, "F5", 0.28, 0.54)),
        ((0.0, "A5", 0.26, 0.58), (2.0, "F5", 0.24, 0.44)),
        ((0.0, "D5", 0.28, 0.54), (1.5, "E5", 0.14, 0.26), (2.0, "A5", 0.26, 0.58)),
        ((0.0, "C6", 0.24, 0.58), (2.0, "A5", 0.26, 0.50), (3.5, "E6", 0.12, 0.24)),
        ((0.0, "D6", 0.30, 0.68), (2.0, "A5", 0.26, 0.52)),
        ((0.0, "F6", 0.24, 0.52), (2.0, "D6", 0.24, 0.46)),
        ((0.0, "C6", 0.24, 0.48), (2.0, "B5", 0.24, 0.42)),
        ((0.0, "A5", 0.22, 0.42), (1.5, "C6", 0.12, 0.24), (2.0, "D6", 0.30, 0.62)),
    )

    for bar, cell in enumerate(anchor_phrase):
        if not every_bar and bar not in (0, 2, 4, 6):
            continue
        b = float(bar)
        if lifted and bar >= 4:
            cell = tuple(
                (beat, transpose_pitch(pitch, 0 if midi(pitch) >= midi("A5") else 12), beats, gain)
                for beat, pitch, beats, gain in cell
            )
        for beat, pitch, beats, gain in cell:
            add_anchor_stack(b, beat, pitch, beats, gain, phrase_bar=bar)
        if bar in (0, 4):
            add("piano_low", "piano_c3", b, 0.0, "D3" if bar == 0 else "A3", 0.30, 0.13, fade=0.025)
        if bar in (3, 7):
            add("vibe_sparkle", "vibe", b, 3.25, "A5" if bar == 3 else "B5", 0.30, 0.09, 0.07)
            add("granular_air", "granular", b, 3.0, "D6", 0.90, 0.055, 0.14)


def build_mix_fx_returns(events: list[LeadEvent], spec: TrackSpec, starts: dict[str, int]) -> None:
    """Phrase-aware printed FX return layer.

    This is the "ecstasy" support layer: reverse swells into phrase entries,
    granular blooms underneath hooks, and small vibraphone/chime answers that
    keep the earlier cue from feeling like a one-off accident.
    """

    lengths = section_lengths(spec)

    def add(
        layer: str,
        source: str,
        section: str,
        rel_bar: float,
        beat: float,
        pitch: str,
        beats: float,
        gain: float,
        pan: float = 0.0,
        fade: float = 0.10,
        reverse: bool = False,
    ) -> None:
        if section not in starts:
            return
        events.append(
            LeadEvent(
                layer,
                source,
                section,
                starts[section] + rel_bar,
                beat,
                pitch,
                beats,
                gain,
                pan,
                fade,
                reverse,
            )
        )

    def phrase_marks(section: str, step: int = 8) -> list[int]:
        bars = lengths.get(section, 0)
        return list(range(0, bars, step))

    # Intro/groove identity: a cue should keep breathing, not chime once and vanish.
    for rel in phrase_marks("intro", 4):
        if rel == 0:
            continue
        add("granular_bloom", "granular", "intro", rel - 0.45, 1.5, "A5", 2.40, 0.030, -0.16)
        add("vibe_chime", "vibe", "intro", rel + 1.75, 3.0, "A5", 0.28, 0.025, 0.10)

    for rel in phrase_marks("groove_a", 4):
        add("reverse_swell", "granular", "groove_a", rel - 0.42, 1.5, "D6", 1.85, 0.042, 0.15, 0.18, True)
        add("granular_bloom", "granular", "groove_a", rel + 0.25, 0.0, "A5", 2.75, 0.032, -0.12)
        if rel % 8 == 4:
            add("vibe_chime", "vibe", "groove_a", rel + 2.75, 2.5, "F5", 0.26, 0.024, -0.08)

    # Bigger sections: returns mark 8-bar phrases and answer the piano hook.
    for section, swell_gain, bloom_gain, chime_gain in (
        ("break", 0.060, 0.046, 0.036),
        ("drop", 0.050, 0.034, 0.026),
        ("peak", 0.074, 0.052, 0.040),
    ):
        for index, rel in enumerate(phrase_marks(section, 8)):
            pitch = "D6" if index % 2 == 0 else "A5"
            answer = "B5" if section == "peak" and index >= 2 else "A5"
            add("reverse_swell", "granular", section, rel - 0.55, 0.0, pitch, 2.35, swell_gain, 0.18, 0.20, True)
            add("granular_bloom", "granular", section, rel + 0.05, 0.0, pitch, 3.60, bloom_gain, -0.14, 0.22)
            add("phrase_throw", "granular", section, rel + 3.75, 2.0, answer, 1.25, bloom_gain * 0.84, 0.16, 0.16)
            add("vibe_chime", "vibe", section, rel + 7.25, 3.0, answer, 0.30, chime_gain, -0.10)


def build_lead_plan(spec: TrackSpec) -> list[LeadEvent]:
    starts = section_starts(spec)
    events: list[LeadEvent] = []

    def add(
        layer: str,
        source: str,
        section: str,
        rel_bar: float,
        beat: float,
        pitch: str,
        beats: float,
        gain: float,
        pan: float = 0.0,
        fade: float = 0.05,
        reverse: bool = False,
    ) -> None:
        events.append(
            LeadEvent(
                layer,
                source,
                section,
                starts[section] + rel_bar,
                beat,
                pitch,
                beats,
                gain,
                pan,
                fade,
                reverse,
            )
        )

    # Intro/groove: no early piano hook. The rejected pass felt hesitant because
    # piano appeared before the arrangement was ready to support it.
    add("pre_cue", "granular", "intro", 5.5, 0.0, "D6", 1.20, 0.050, 0.14, 0.16, True)
    add("vibe_sparkle", "vibe", "intro", 6.75, 1.5, "A5", 0.30, 0.055, 0.08)

    # Break is the first identity statement, but not the climax. Keep it sparse
    # and decisive so the groove remains the body-weight of the record.
    build_hook(events, starts, "break", 0.0, intensity=0.40, sparse=True)
    build_hook(events, starts, "break", 8.0, intensity=0.48, sparse=True, final_turn=True)

    # Drop: the groove owns the section; lead is a tucked phrase marker, not a
    # foreground piano solo.
    for rel in (0.0, 8.0, 16.0, 24.0, 32.0):
        build_anchor_hook(events, starts, "drop", rel, intensity=0.24, every_bar=False)

    # Peak: denser drums need fewer, bigger piano anchors instead of a busy
    # offbeat-answer hook fighting the groove.
    for phrase, rel in enumerate((0.0, 8.0, 16.0, 24.0, 32.0)):
        build_anchor_hook(
            events,
            starts,
            "peak",
            rel,
            intensity=0.88 if phrase < 2 else 0.98,
            every_bar=True,
            lifted=phrase in (2, 3),
        )

    add("piano_hook", "piano_c5", "outro", 0.0, 0.0, "D5", 0.72, 0.22)
    add("granular_air", "granular", "outro", 1.8, 0.0, "A5", 1.25, 0.045, -0.12)
    build_mix_fx_returns(events, spec, starts)
    return sorted(events, key=lambda e: (e.bar, e.beat, e.layer, e.pitch))


def ensure_sources(workdir: Path) -> dict[str, Path]:
    missing = [str(src.path) for src in SOURCES.values() if not src.path.is_file()]
    if missing:
        raise FileNotFoundError("missing Logic sample assets:\n" + "\n".join(missing))
    decoded: dict[str, Path] = {}
    for key, source in SOURCES.items():
        out = workdir / f".source-{key}.wav"
        run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source.path),
                "-ar",
                str(SAMPLE_RATE),
                "-ac",
                "2",
                "-sample_fmt",
                "s16",
                str(out),
            ]
        )
        decoded[key] = out
    return decoded


def render_event(source_wav: Path, source_root: int, event: LeadEvent, spec: TrackSpec, workdir: Path, index: int) -> Path:
    dur = beat_seconds(spec, event.beats)
    cents = (midi(event.pitch) - source_root) * 100
    out = workdir / f".event-{index:04d}-{event.layer}.wav"
    run(
        [
            "sox",
            str(source_wav),
            "-b",
            "16",
            str(out),
            "trim",
            "0",
            f"{dur + 0.32:.4f}",
            "pitch",
            str(cents),
            "fade",
            "t",
            "0.004",
            f"{dur + 0.32:.4f}",
            f"{event.fade:.4f}",
            "rate",
            str(SAMPLE_RATE),
        ]
    )
    if event.reverse:
        reverse = workdir / f".event-{index:04d}-{event.layer}-reverse.wav"
        run(
            [
                "sox",
                str(out),
                str(reverse),
                "reverse",
                "fade",
                "t",
                "0.03",
                f"{dur + 0.32:.4f}",
                "0.02",
            ]
        )
        out.unlink(missing_ok=True)
        return reverse
    return out


def read_wav16(path: Path) -> tuple[array, array]:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        if width != 2:
            raise ValueError(f"expected 16-bit WAV: {path}")
        raw = array("h")
        raw.frombytes(wav.readframes(wav.getnframes()))
    if channels == 1:
        left = array("f", (sample / 32768.0 for sample in raw))
        return left, array("f", left)
    left = array("f", (raw[i] / 32768.0 for i in range(0, len(raw), channels)))
    right = array("f", (raw[i + 1] / 32768.0 for i in range(0, len(raw), channels)))
    return left, right


def write_wav24(path: Path, left: array, right: array, peak_target: float = 0.72) -> None:
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


def add_noise_swell(buffer: tuple[array, array], spec: TrackSpec, start_bar: float, beats: float, gain: float) -> None:
    left, right = buffer
    rng = random.Random(1001)
    start = int(event_seconds(spec, start_bar) * SAMPLE_RATE)
    length = int(beat_seconds(spec, beats) * SAMPLE_RATE)
    previous = 0.0
    for i in range(length):
        idx = start + i
        if idx < 0 or idx >= len(left):
            continue
        pos = i / max(1, length - 1)
        previous = previous * 0.92 + (rng.random() * 2.0 - 1.0) * 0.08
        signal = previous * (pos**2.2) * math.sin(math.pi * pos) * gain
        left[idx] += signal * 0.70
        right[idx] += signal * 1.00


def render_raw_families(spec: TrackSpec, events: list[LeadEvent], out_dir: Path) -> dict[str, Path]:
    decoded = ensure_sources(out_dir)
    seconds = spec_duration_seconds(spec) + 4.0
    length = int(seconds * SAMPLE_RATE)
    buffers = {
        family: (array("f", [0.0]) * length, array("f", [0.0]) * length)
        for family in FAMILY_STEMS
    }

    # A very low non-tonal lift before the first full statements. It supports
    # entry drama, not melody; the pitched cue is still the reversed granular sample.
    starts = section_starts(spec)
    if "break" in starts:
        add_noise_swell(buffers["atmos"], spec, starts["break"] - 0.55, 2.4, 0.030)
    if "peak" in starts:
        add_noise_swell(buffers["atmos"], spec, starts["peak"] - 0.55, 2.4, 0.035)

    rendered_events: list[Path] = []
    for index, event in enumerate(events):
        source = SOURCES[event.source]
        rendered = render_event(decoded[event.source], source.root_midi, event, spec, out_dir, index)
        rendered_events.append(rendered)
        event_left, event_right = read_wav16(rendered)
        family = LAYER_FAMILY[event.layer]
        left, right = buffers[family]
        start = int(event_seconds(spec, event.bar, event.beat) * SAMPLE_RATE)
        for i, (left_sample, right_sample) in enumerate(zip(event_left, event_right)):
            idx = start + i
            if idx < 0 or idx >= length:
                continue
            t = idx / SAMPLE_RATE
            beat_pos = (t * spec.bpm / 60.0) % 1.0
            duck = 0.80 + 0.20 * min(1.0, beat_pos / 0.30)
            if event.reverse:
                pos = i / max(1, len(event_left) - 1)
                envelope = pos**1.8
            else:
                envelope = 1.0
            gain = event.gain * duck * envelope
            left[idx] += left_sample * gain * (1.0 - event.pan)
            right[idx] += right_sample * gain * (1.0 + event.pan)

    for path in rendered_events:
        path.unlink(missing_ok=True)
    for path in decoded.values():
        path.unlink(missing_ok=True)

    raw_paths: dict[str, Path] = {}
    for family, (left, right) in buffers.items():
        raw = out_dir / f".raw-{FAMILY_STEMS[family]}"
        if family == "main":
            peak_target = 0.68
        elif family == "mixfx":
            peak_target = 0.44
        else:
            peak_target = 0.52
        write_wav24(raw, left, right, peak_target)
        raw_paths[family] = raw
    return raw_paths


def process_family(raw: Path, dst: Path, family: str) -> None:
    if family == "main":
        effects = [
            "highpass",
            "82",
            "lowpass",
            "8800",
            "echo",
            "0.72",
            "0.38",
            "242",
            "0.10",
            "echo",
            "0.68",
            "0.30",
            "484",
            "0.08",
            "reverb",
            "16",
            "10",
            "66",
            "18",
            "0.8",
            "0",
            "gain",
            "-n",
            "-4.5",
        ]
    elif family == "fx":
        effects = [
            "highpass",
            "220",
            "lowpass",
            "8200",
            "tremolo",
            "4.133",
            "10",
            "reverb",
            "22",
            "14",
            "68",
            "24",
            "1.0",
            "0",
            "gain",
            "-n",
            "-10",
        ]
    elif family == "atmos":
        effects = [
            "highpass",
            "260",
            "lowpass",
            "7600",
            "tremolo",
            "2.067",
            "12",
            "echo",
            "0.70",
            "0.42",
            "484",
            "0.14",
            "reverb",
            "34",
            "22",
            "80",
            "54",
            "3",
            "0",
            "gain",
            "-n",
            "-12",
        ]
    elif family == "mixfx":
        effects = [
            "highpass",
            "320",
            "lowpass",
            "7900",
            "tremolo",
            "2.067",
            "16",
            "echo",
            "0.68",
            "0.36",
            "242",
            "0.12",
            "echo",
            "0.64",
            "0.34",
            "484",
            "0.10",
            "echo",
            "0.58",
            "0.22",
            "968",
            "0.07",
            "reverb",
            "46",
            "28",
            "82",
            "72",
            "5",
            "0",
            "gain",
            "-n",
            "-13.5",
        ]
    else:
        effects = ["gain", "-n", "-8"]
    run(["sox", str(raw), str(dst), *effects])


def render_lead_family(spec: TrackSpec, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    events = build_lead_plan(spec)
    raw_paths = render_raw_families(spec, events, out_dir)
    stems: dict[str, str] = {}
    for family, raw in raw_paths.items():
        dst = out_dir / FAMILY_STEMS[family]
        process_family(raw, dst, family)
        raw.unlink(missing_ok=True)
        stems[family] = dst.name

    run(
        [
            "sox",
            "-m",
            "-v",
            "0.82",
            str(out_dir / stems["main"]),
            "-v",
            "0.60",
            str(out_dir / stems["fx"]),
            "-v",
            "0.64",
            str(out_dir / stems["atmos"]),
            "-v",
            "0.50",
            str(out_dir / stems["mixfx"]),
            str(out_dir / "stem-lead.wav"),
            "gain",
            "-n",
            "-7.2",
        ]
    )

    counts: dict[str, int] = {}
    first_seconds: dict[str, float] = {}
    used_sources: dict[str, str] = {}
    for event in events:
        counts[event.layer] = counts.get(event.layer, 0) + 1
        first_seconds.setdefault(event.layer, round(event_seconds(spec, event.bar, event.beat), 3))
        used_sources[event.source] = str(SOURCES[event.source].path)
    report = {
        "design_target": {
            "lane": "piano-forward melodic/progressive techno lead family",
            "role": "decisive vocal-substitute hook without actual vocals",
            "rejected_sources": [
                "Shelburne Road Anthem Synth",
                "harp",
                "fat strings as lead",
            ],
        },
        "melody_formula": {
            "key": spec.key,
            "rhythm": "4/4 track feel with two-beat hook cells",
            "grammar": [
                "downbeat and half-bar anchors instead of hesitant pickups",
                "break and drop stay groove-first; lead is sparse before the peak",
                "piano main identity with low-octave support at phrase anchors",
                "same-note stacked voicing: center piano, airy double, octave shimmer, and restrained vibe unison",
                "Dorian/suspended color without heavy classical harmonic-minor cadence",
                "granular reverse cue and vibraphone sparkle only at phrase marks",
                "printed FX returns that recur on phrase marks instead of one-off chimes",
            ],
            "first_identity_seconds": round(min(event_seconds(spec, e.bar, e.beat) for e in events), 3),
        },
        "mix_fx_target": {
            "role": "phrase-aware atmosphere and ecstasy support",
            "sources": ["granular reverse swells", "granular blooms", "vibraphone chime answers"],
            "mix_rule": "high-passed, filtered, wide, and quieter than the piano identity",
        },
        "layers": {
            "counts": counts,
            "first_event_seconds": first_seconds,
            "families": stems,
        },
        "logic_sources": used_sources,
    }
    (out_dir / "lead-production-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


def replace_lead_in_mix(source_dir: Path, out_dir: Path) -> None:
    old_mix = source_dir / "vibe_mix.wav"
    old_lead = source_dir / "stem-lead.wav"
    new_lead = out_dir / "stem-lead.wav"
    if not old_mix.is_file() or not old_lead.is_file():
        raise FileNotFoundError("source variant must contain vibe_mix.wav and stem-lead.wav")
    base = out_dir / ".instrumental-minus-old-lead.wav"
    premaster = out_dir / ".premaster.wav"
    run(
        [
            "sox",
            "-m",
            "-v",
            "1.0",
            str(old_mix),
            "-v",
            "-0.95",
            str(old_lead),
            str(base),
            "gain",
            "-n",
            "-7",
        ]
    )
    run(
        [
            "sox",
            "-m",
            "-v",
            "1.0",
            str(base),
            "-v",
            "1.00",
            str(new_lead),
            str(premaster),
            "gain",
            "-n",
            "-7",
        ]
    )
    run(["sox", str(premaster), str(out_dir / "vibe_mix.wav"), *MASTER_CHAIN])
    base.unlink(missing_ok=True)
    premaster.unlink(missing_ok=True)
    for auxiliary in ("stem-groove-lowend.wav", "groove-lowend-report.json"):
        source = source_dir / auxiliary
        if source.is_file():
            shutil.copy2(source, out_dir / auxiliary)


def check_tools() -> None:
    missing = [tool for tool in ("ffmpeg", "sox") if shutil.which(tool) is None]
    if missing:
        raise SystemExit("missing required existing tool(s): " + ", ".join(missing))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a Logic-sample lead replacement")
    parser.add_argument("spec")
    parser.add_argument("source_variant")
    parser.add_argument("out_variant")
    args = parser.parse_args(argv)

    check_tools()
    spec = load_spec(args.spec)
    source_dir = Path(args.source_variant)
    out_dir = Path(args.out_variant)
    render_lead_family(spec, out_dir)
    replace_lead_in_mix(source_dir, out_dir)
    print(out_dir / "vibe_mix.wav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
