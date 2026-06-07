# SPDX-License-Identifier: AGPL-3.0-only
"""SuperCollider NRT rendering for the vibe parts (Spec 5 vertical slice).

Renders kick (from drums), bass, and pad through the designed patches in
``render/patches.scd`` via headless ``sclang`` non-realtime synthesis, then
mixes them with FluidSynth GM stems of the remaining parts into
``vibe_mix.wav``. Deterministic end to end: patches use no random UGens and
NRT scores are derived from the same seeded events as ``setloom generate``.

Usage: ``uv run python -m setloom.scrender <spec.yml> <variant-dir> [--seed S] [--variant N]``
"""

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from setloom.midi import PPQ, NoteEvent, total_ticks
from setloom.parts import ALL_PARTS, part_rng
from setloom.parts.base import SCALES, parse_key
from setloom.schema import TrackSpec, load_spec

SC_APP_SCLANG = "/Applications/SuperCollider.app/Contents/MacOS/sclang"
PATCHES = Path(__file__).resolve().parents[2] / "render" / "patches.scd"

KICK_NOTE = 36

# Which generated parts feed which patch; kick events are the drum part's
# kick notes only. Tranche 3: GM is fully retired — percussion renders
# through the designed kit as one "perc" stem.
VIBE_PARTS = ("kick", "bass", "pad", "chords", "arp", "lead", "fx", "perc")

# Generated parts whose events merge into the perc stem (drums minus kick).
PERC_SOURCE_PARTS = ("drums", "fills", "shaker", "clap_ride")

# GM percussion note -> designed kit synth.
PERC_SYNTH_FOR_NOTE = {
    42: "vibe_hat",
    46: "vibe_openhat",
    39: "vibe_clap",
    51: "vibe_ride",
    70: "vibe_shaker",
    38: "vibe_clap",  # fill snare renders as the dark clap family
    45: "vibe_tom",
    47: "vibe_tom",
}

# Per-synth amp scaling inside the perc stem — the spectral/gain hierarchy
# from the cross-model mix-architecture review (2026-06-07): top loops are
# felt more than heard (-18 to -22 dB vs kick), ride is peak shimmer (-22),
# the clap shadow stays far back (-18 or lower).
PERC_ROLE_SCALE = {
    "vibe_hat": 0.22,
    "vibe_openhat": 0.25,
    "vibe_shaker": 0.16,
    "vibe_ride": 0.12,
    "vibe_clap": 0.18,
    "vibe_tom": 0.50,
}

# Mix gains: kick = 0 dB reference; values are the review's dB targets as
# linear gains (10 ** (dB/20)). Near-equal faders were the collage tell.
MIX_GAINS = {
    "kick": 1.00,   #  0 dB reference
    "bass": 0.71,   # -3 dB
    "pad": 0.35,    # -9 dB (break bed)
    "chords": 0.32,  # -10 dB
    "arp": 0.20,    # -14 dB
    "lead": 0.40,   # -8 dB foreground
    "fx": 0.25,     # riser ramps live inside the patch
    "perc": 1.00,   # roles pre-scaled per synth above
}

LOUDNESS_TARGET_LUFS = (-8.0, -7.0)
PEAK_TARGET_DBFS = -1.0
LEAD_EXPRESSION_KEYS = ("cutoff", "drive", "tone", "motion", "width", "space", "accent")
LEAD_EXPRESSION_DEFAULTS = {
    "cutoff": 2600.0,
    "drive": 1.5,
    "tone": 0.5,
    "motion": 0.4,
    "width": 0.25,
    "space": 0.3,
    "accent": 1.0,
}
LEAD_FAMILY_STEMS = {
    "main": "stem-lead-main.wav",
    "fx": "stem-lead-fx.wav",
    "atmos": "stem-lead-atmos.wav",
}
LEAD_FAMILY_MIX_GAINS = {
    "main": 1.00,
    "fx": 0.90,
    "atmos": 0.85,
}
MASTER_CHAIN = (
    "highpass", "28",
    "compand", "0.003,0.090",
    "6:-70,-70,-36,-30,-24,-20,-18,-15,-12,-10,-8,-7,-4,-3", "0", "-90", "0.02",
    # Club/mastered candidate pass: raise into a fast safety limiter so loudness
    # comes from whole-mix density and controlled saturation, not a lead fader bump.
    "gain", "13",
    "compand", "0.001,0.010", "-5,-5,-2,-2,0,-1.4", "0", "-90", "0.001",
    "gain", "-n", str(PEAK_TARGET_DBFS),
)

SYNTH_FOR_PART = {
    "kick": "vibe_kick",
    "bass": "vibe_bass",
    "pad": "vibe_pad",
    "chords": "vibe_chords",
    "arp": "vibe_arp",
    "lead": "vibe_lead_body",
    "fx": "vibe_fx",
}


@dataclass(frozen=True)
class LeadLayer:
    """One role inside the lead bus: musical intent plus deterministic render rules."""

    name: str
    synth: str
    family: str
    role: str
    spectral_range: str
    phase_rule: str
    arrangement_role: str
    rationale: str
    section_amp: dict[str, float]
    transpose: int = 0
    note_stride: int = 1


@dataclass(frozen=True)
class LeadEffect:
    """One phrase-aware rave/effect source row family inside the lead bus."""

    name: str
    synth: str
    family: str
    role: str
    spectral_range: str
    phase_rule: str
    arrangement_role: str
    rationale: str
    degree: int
    transpose: int = 0


@dataclass(frozen=True)
class LeadAtmosphere:
    """One long-form atmosphere or motion source inside the lead family."""

    name: str
    synth: str
    family: str
    role: str
    spectral_range: str
    phase_rule: str
    arrangement_role: str
    rationale: str
    degree: int
    transpose: int = 0


LEAD_LAYERS = (
    LeadLayer(
        name="lead_body",
        synth="vibe_lead_body",
        family="main",
        role="center identity/body",
        spectral_range="400 Hz-3.5 kHz",
        phase_rule="mostly center; width only above 350 Hz",
        arrangement_role="foreground in break/peak, reduced in drop",
        rationale="The ear needs one stable mid-band identity before edge or air can read.",
        section_amp={"break": 0.95, "drop": 0.45, "peak": 0.85, "default": 0.0},
    ),
    LeadLayer(
        name="lead_edge",
        synth="vibe_lead_edge",
        family="main",
        role="transient/attack bite",
        spectral_range="1.2-4.8 kHz",
        phase_rule="narrow transient; no sustained wide brass",
        arrangement_role="short attack layer, stronger in peak than drop",
        rationale="Attack defines presence without making the whole lead bright or retro.",
        section_amp={"break": 0.24, "drop": 0.12, "peak": 0.32, "default": 0.0},
    ),
    LeadLayer(
        name="lead_air",
        synth="vibe_lead_air",
        family="atmos",
        role="filtered air/grain space",
        spectral_range="3-5.5 kHz, low-passed below hat band",
        phase_rule="wide only after high-pass; never owns >6 kHz brightness",
        arrangement_role="sparse motion around emotional sections",
        rationale="Air creates contemporary texture while leaving hats/shakers as the top band.",
        section_amp={"break": 0.10, "peak": 0.18, "default": 0.0},
        note_stride=3,
    ),
    LeadLayer(
        name="lead_shadow",
        synth="vibe_lead_shadow",
        family="main",
        role="quiet octave/response support",
        spectral_range="160-900 Hz, high-passed chest support",
        phase_rule="mono/narrow; no phase damage in body range",
        arrangement_role="response/support only, never every note at equal status",
        rationale="A shadow layer gives weight without turning into a second foreground lead.",
        section_amp={"break": 0.12, "peak": 0.18, "default": 0.0},
        transpose=-12,
        note_stride=2,
    ),
)

LEAD_EFFECTS = (
    LeadEffect(
        name="lead_fx_tease",
        synth="vibe_lead_fx_tease",
        family="fx",
        role="early filtered identity cue",
        spectral_range="3-5.5 kHz filtered air/resonance",
        phase_rule="wide only after high-pass; no low-mid smear",
        arrangement_role="intro/groove cue before the main motif arrives",
        rationale="The listener needs a signature before the break; a tease avoids full-hook overload.",
        degree=0,
    ),
    LeadEffect(
        name="lead_fx_throw",
        synth="vibe_lead_fx_throw",
        family="fx",
        role="dark resonant throw",
        spectral_range="1.2-4.8 kHz short-tonal motion",
        phase_rule="narrow transient with filtered tail",
        arrangement_role="break/drop/peak phrase marker and response",
        rationale="Throws create rave-functional identity without turning the lead into a plain note line.",
        degree=4,
    ),
    LeadEffect(
        name="lead_fx_whoop",
        synth="vibe_lead_fx_whoop",
        family="fx",
        role="semi-pitched whoop response",
        spectral_range="500 Hz-3.5 kHz swept body",
        phase_rule="mostly center with only high-passed width",
        arrangement_role="drop/peak call-response, never continuous foreground",
        rationale="A response gesture supplies stage/rave character while leaving motif space intact.",
        degree=7,
        transpose=12,
    ),
)

LEAD_ATMOSPHERES = (
    LeadAtmosphere(
        name="lead_atmos_bloom",
        synth="vibe_lead_atmos_bloom",
        family="atmos",
        role="wide filtered lead atmosphere",
        spectral_range="650 Hz-4.8 kHz dark breath and harmonic motion",
        phase_rule="wide after high-pass; no low-mid phase smear",
        arrangement_role="prepares break and peak without becoming the hook",
        rationale="A professional lead often has a support atmosphere that makes the main line feel staged.",
        degree=2,
    ),
    LeadAtmosphere(
        name="lead_atmos_pulse",
        synth="vibe_lead_atmos_pulse",
        family="atmos",
        role="rhythmic shimmer/tension support",
        spectral_range="1.1-5 kHz filtered rhythmic grain",
        phase_rule="stereo texture only above the body band",
        arrangement_role="adds phrase motion around drop and peak responses",
        rationale="Subtle pulsed texture prevents the stem from reading as dry note playback.",
        degree=5,
        transpose=12,
    ),
)

LEAD_COHERENCE = {
    "pad": {
        "shares": "dark saturation family and slow filter motion",
        "avoids": "420 Hz body collision and full-bright pad under foreground lead",
        "rule": "pad stays warm/wide; lead body owns focused identity when foreground",
    },
    "arp": {
        "shares": "filtered pluck language and delay grid",
        "avoids": "equal foreground 1-5 kHz motion",
        "rule": "arp is texture/support when lead body is foreground",
    },
    "chords": {
        "shares": "minor/suspended harmonic color and dark room",
        "avoids": "break-body wash competing with pad plus lead",
        "rule": "break chords step back when pad/lead carry body",
    },
    "perc": {
        "shares": "dark spectral ceiling and phrase-aware restraint",
        "avoids": "lead air stealing the open >6 kHz hat/shaker band",
        "rule": "lead air is filtered below the percussion brightness zone",
    },
}

# Section-aware level scaling (cross-model lead consult, 2026-06-07): a fixed
# lead fader is too blunt for this lane. Factors multiply the note amp relative
# to the part's base mix gain (lead base = -8 dB vs kick at peak foreground).
SECTION_AMP_SCALE = {
    "lead": {"break": 1.26, "drop": 0.84},  # break -6 dB hook; drop ~-9.5 support
    "chords": {"break": 0.63},  # the ecstasy pad supplies the break wash; chords step back
}


def find_sclang() -> str | None:
    return shutil.which("sclang") or (SC_APP_SCLANG if Path(SC_APP_SCLANG).exists() else None)


def ticks_to_seconds(ticks: int, bpm: float) -> float:
    return ticks * 60.0 / (bpm * PPQ)


def export_score(events: list[NoteEvent], bpm: float) -> list[dict]:
    """NoteEvents -> JSON-able score rows (deterministic, sorted)."""
    rows = [
        {
            "note": e.note,
            "amp": round(e.velocity / 127, 4),
            "start": round(ticks_to_seconds(e.start_tick, bpm), 6),
            "dur": round(ticks_to_seconds(e.duration_ticks, bpm), 6),
        }
        for e in events
    ]
    return sorted(rows, key=lambda r: (r["start"], r["note"]))


def section_windows(spec: TrackSpec) -> list[tuple[int, int, str]]:
    """Absolute tick windows with collapsed section type names."""
    windows: list[tuple[int, int, str]] = []
    cursor = 0
    for name, bars in spec.sections.items():
        end = cursor + bars * 4 * PPQ
        windows.append((cursor, end, name.rstrip("0123456789_")))
        cursor = end
    return windows


def section_kind_at_tick(tick: int, windows: list[tuple[int, int, str]]) -> str:
    """Return the collapsed section type containing ``tick``."""
    kind, _start, _end = section_info_at_tick(tick, windows)
    return kind


def section_info_at_tick(tick: int, windows: list[tuple[int, int, str]]) -> tuple[str, int, int]:
    """Return the collapsed section type and absolute tick window for ``tick``."""
    for start, end, kind in windows:
        if start <= tick < end:
            return kind, start, end
    return "unknown", 0, 0


def _lead_expression(
    section: str,
    tick: int,
    section_start: int,
    family: str,
    role_name: str,
) -> dict[str, float]:
    """Deterministic row-level expression for lead-family sound design."""
    profiles = {
        "intro": (1850.0, 1.35, 0.30, 0.34, 0.30, 0.42, 0.90),
        "groove_a": (2100.0, 1.55, 0.38, 0.44, 0.30, 0.36, 0.95),
        "break": (2650.0, 1.85, 0.58, 0.54, 0.34, 0.50, 1.06),
        "drop": (2150.0, 2.00, 0.48, 0.66, 0.26, 0.32, 0.92),
        "peak": (3300.0, 2.25, 0.72, 0.86, 0.42, 0.58, 1.14),
        "outro": (1700.0, 1.30, 0.28, 0.28, 0.20, 0.30, 0.75),
    }
    cutoff, drive, tone, motion, width, space, accent = profiles.get(section, profiles["drop"])
    ticks_per_bar = 4 * PPQ
    bar_in_section = max(0.0, (tick - section_start) / ticks_per_bar) if section_start else 0.0
    slot = int(bar_in_section // 2) % 8
    phrase = int(bar_in_section // 16)
    slot_lift = (0.00, 0.05, 0.10, 0.03, 0.00, 0.08, 0.12, 0.06)[slot]
    phrase_lift = 0.04 if phrase % 2 else 0.0

    cutoff *= 1.0 + slot_lift + phrase_lift
    tone = min(0.95, tone + slot_lift * 0.55)
    motion = min(0.98, motion + slot_lift * 0.70 + phrase_lift)
    accent = min(1.35, accent + slot_lift * 0.45)

    if family == "fx":
        cutoff *= 1.12
        drive += 0.20
        tone = min(0.98, tone + 0.12)
        motion = min(0.98, motion + 0.14)
        space = min(0.95, space + 0.22)
        accent = min(1.35, accent + 0.05)
    elif family == "atmos":
        cutoff *= 1.18
        drive = max(1.25, drive - 0.20)
        tone = min(0.90, tone + 0.06)
        motion = min(0.98, motion + 0.18)
        width = min(0.95, width + 0.30)
        space = min(0.98, space + 0.30)
        accent = min(1.15, accent)

    if role_name == "lead_edge":
        cutoff = max(cutoff, 4300.0)
        drive += 0.35
        tone = min(1.0, tone + 0.16)
        width = min(width, 0.18)
        space *= 0.55
    elif role_name == "lead_air":
        cutoff = max(cutoff, 4800.0)
        drive = 1.20
        motion = min(1.0, motion + 0.18)
        width = min(1.0, width + 0.22)
        space = min(1.0, space + 0.24)
    elif role_name == "lead_shadow":
        cutoff = 880.0 + slot * 24
        drive = 1.60
        tone = 0.22
        motion = min(0.55, motion)
        width = 0.08
        space = 0.14
        accent *= 0.88

    return {
        "cutoff": round(cutoff, 3),
        "drive": round(drive, 3),
        "tone": round(tone, 3),
        "motion": round(motion, 3),
        "width": round(width, 3),
        "space": round(space, 3),
        "accent": round(accent, 3),
    }


def lead_layer_score(events: list[NoteEvent], spec: TrackSpec) -> list[dict]:
    """Fan logical lead notes into role-specific lead-bus score rows."""
    windows = section_windows(spec)
    rows: list[dict] = []
    for index, row in enumerate(export_score(events, spec.bpm)):
        tick = round(row["start"] * spec.bpm * PPQ / 60)
        section, section_start, _section_end = section_info_at_tick(tick, windows)
        for layer in LEAD_LAYERS:
            if index % layer.note_stride != 0:
                continue
            scale = layer.section_amp.get(section, layer.section_amp.get("default", 0.0))
            if scale <= 0:
                continue
            layered = dict(row)
            layered["note"] = row["note"] + layer.transpose
            layered["amp"] = round(row["amp"] * scale, 4)
            layered["synth"] = layer.synth
            layered["layer"] = layer.name
            layered["role"] = layer.role
            layered["source"] = "melodic"
            layered["family"] = layer.family
            layered["section"] = section
            layered.update(_lead_expression(section, tick, section_start, layer.family, layer.name))
            rows.append(layered)
    return sorted(rows, key=lambda r: (r["start"], r["layer"], r["note"]))


def _lead_degree_note(spec: TrackSpec, degree: int, transpose: int = 0) -> int:
    pitch_class, quality = parse_key(spec.key)
    scale = SCALES[quality]
    base = 12 * 6 + pitch_class
    return base + transpose + 12 * (degree // len(scale)) + scale[degree % len(scale)]


def _lead_effect_note(spec: TrackSpec, effect: LeadEffect) -> int:
    return _lead_degree_note(spec, effect.degree, effect.transpose)


def _lead_atmos_note(spec: TrackSpec, atmosphere: LeadAtmosphere) -> int:
    return _lead_degree_note(spec, atmosphere.degree, atmosphere.transpose)


def lead_effect_score(spec: TrackSpec) -> list[dict]:
    """Deterministic phrase-aware lead-effect source rows.

    These rows are source events, not another melodic note layer. They create
    early identity and break/drop/peak call-response before Slice 2 assigns
    dedicated effect SynthDefs.
    """
    by_kind = {kind: start for start, _end, kind in section_windows(spec)}
    score: list[dict] = []
    schedule = (
        ("intro", 4.0, "lead_fx_tease", 0.18, 1.0),
        ("intro", 7.0, "lead_fx_tease", 0.14, 0.75),
        ("groove_a", 0.0, "lead_fx_throw", 0.16, 0.50),
        ("groove_a", 4.0, "lead_fx_tease", 0.12, 0.75),
        ("break", 0.0, "lead_fx_throw", 0.22, 1.0),
        ("break", 8.0, "lead_fx_tease", 0.16, 1.25),
        ("drop", 0.0, "lead_fx_throw", 0.20, 0.45),
        ("drop", 8.0, "lead_fx_whoop", 0.17, 0.70),
        ("drop", 16.0, "lead_fx_throw", 0.18, 0.45),
        ("drop", 24.0, "lead_fx_whoop", 0.18, 0.70),
        ("peak", 0.0, "lead_fx_throw", 0.24, 0.55),
        ("peak", 8.0, "lead_fx_whoop", 0.22, 0.80),
        ("peak", 16.0, "lead_fx_tease", 0.18, 1.0),
        ("peak", 24.0, "lead_fx_whoop", 0.22, 0.80),
        ("peak", 32.0, "lead_fx_throw", 0.24, 0.55),
    )
    effects = {effect.name: effect for effect in LEAD_EFFECTS}
    for section, bar_offset, name, amp, dur_bars in schedule:
        if section not in by_kind:
            continue
        effect = effects[name]
        start_tick = by_kind[section] + round(bar_offset * 4 * PPQ)
        row = {
            "note": _lead_effect_note(spec, effect),
            "amp": amp,
            "start": round(ticks_to_seconds(start_tick, spec.bpm), 6),
            "dur": round(ticks_to_seconds(round(dur_bars * 4 * PPQ), spec.bpm), 6),
            "synth": effect.synth,
            "effect": effect.name,
            "role": effect.role,
            "source": "effect",
            "family": effect.family,
            "section": section,
        }
        row.update(_lead_expression(section, start_tick, by_kind[section], effect.family, effect.name))
        score.append(row)
    return sorted(score, key=lambda r: (r["start"], r["effect"], r["note"]))


def lead_atmos_score(spec: TrackSpec) -> list[dict]:
    """Longer lead-family atmosphere rows that support the main motif."""
    by_kind = {kind: start for start, _end, kind in section_windows(spec)}
    schedule = (
        ("intro", 6.0, "lead_atmos_bloom", 0.10, 2.0),
        ("groove_a", 4.0, "lead_atmos_pulse", 0.09, 1.5),
        ("break", 0.0, "lead_atmos_bloom", 0.16, 8.0),
        ("break", 8.0, "lead_atmos_bloom", 0.14, 8.0),
        ("drop", 8.0, "lead_atmos_pulse", 0.11, 2.0),
        ("drop", 24.0, "lead_atmos_pulse", 0.12, 2.0),
        ("peak", 0.0, "lead_atmos_bloom", 0.18, 8.0),
        ("peak", 8.0, "lead_atmos_pulse", 0.14, 2.0),
        ("peak", 16.0, "lead_atmos_bloom", 0.17, 8.0),
        ("peak", 24.0, "lead_atmos_pulse", 0.15, 2.0),
        ("peak", 32.0, "lead_atmos_bloom", 0.18, 8.0),
    )
    atmospheres = {atmosphere.name: atmosphere for atmosphere in LEAD_ATMOSPHERES}
    score: list[dict] = []
    for section, bar_offset, name, amp, dur_bars in schedule:
        if section not in by_kind:
            continue
        atmosphere = atmospheres[name]
        start_tick = by_kind[section] + round(bar_offset * 4 * PPQ)
        row = {
            "note": _lead_atmos_note(spec, atmosphere),
            "amp": amp,
            "start": round(ticks_to_seconds(start_tick, spec.bpm), 6),
            "dur": round(ticks_to_seconds(round(dur_bars * 4 * PPQ), spec.bpm), 6),
            "synth": atmosphere.synth,
            "atmos": atmosphere.name,
            "role": atmosphere.role,
            "source": "atmos",
            "family": atmosphere.family,
            "section": section,
        }
        row.update(_lead_expression(section, start_tick, by_kind[section], atmosphere.family, name))
        score.append(row)
    return sorted(score, key=lambda r: (r["start"], r["atmos"], r["note"]))


def lead_bus_score(events: list[NoteEvent], spec: TrackSpec) -> list[dict]:
    """Combined lead bus source score: melodic motif layers plus effect gestures."""
    rows = lead_layer_score(events, spec) + lead_effect_score(spec) + lead_atmos_score(spec)
    return sorted(
        rows,
        key=lambda r: (
            r["start"],
            r.get("family", ""),
            r.get("source", ""),
            r.get("layer", r.get("effect", r.get("atmos", ""))),
            r["note"],
        ),
    )


def lead_layer_score_json(events: list[NoteEvent], spec: TrackSpec) -> str:
    """Stable JSON representation for tests and report plumbing."""
    return json.dumps(lead_layer_score(events, spec), sort_keys=True)


def lead_coherence_report() -> dict[str, dict[str, str]]:
    """Neighboring-part rules that prevent patch-over-patch accumulation."""
    return {part: dict(rules) for part, rules in LEAD_COHERENCE.items()}


def lead_bus_report(score: list[dict]) -> dict:
    """Inspectable lead-bus report for render logs and listening handoff."""
    layer_counts = {layer.name: 0 for layer in LEAD_LAYERS}
    effect_counts = {effect.name: 0 for effect in LEAD_EFFECTS}
    atmos_counts = {atmosphere.name: 0 for atmosphere in LEAD_ATMOSPHERES}
    family_counts = {family: 0 for family in LEAD_FAMILY_STEMS}
    family_first_event_seconds: dict[str, float] = {}
    source_counts: dict[str, int] = {}
    source_first_event_seconds: dict[str, float] = {}
    section_counts: dict[str, int] = {}
    expression_values: dict[str, set[float]] = {key: set() for key in LEAD_EXPRESSION_KEYS}
    for row in score:
        layer = row.get("layer")
        effect = row.get("effect")
        atmos = row.get("atmos")
        family = row.get("family")
        source = row.get("source", "unknown")
        section = row.get("section")
        if layer in layer_counts:
            layer_counts[layer] += 1
        if effect in effect_counts:
            effect_counts[effect] += 1
        if atmos in atmos_counts:
            atmos_counts[atmos] += 1
        if isinstance(family, str):
            family_counts[family] = family_counts.get(family, 0) + 1
            start = float(row["start"])
            if family not in family_first_event_seconds or start < family_first_event_seconds[family]:
                family_first_event_seconds[family] = start
        if isinstance(source, str):
            source_counts[source] = source_counts.get(source, 0) + 1
            start = float(row["start"])
            if source not in source_first_event_seconds or start < source_first_event_seconds[source]:
                source_first_event_seconds[source] = start
        if isinstance(section, str):
            section_counts[section] = section_counts.get(section, 0) + 1
        for key in LEAD_EXPRESSION_KEYS:
            if key in row:
                expression_values[key].add(float(row[key]))
    return {
        "layers": [
            {
                "name": layer.name,
                "synth": layer.synth,
                "family": layer.family,
                "role": layer.role,
                "spectral_range": layer.spectral_range,
                "phase_rule": layer.phase_rule,
                "arrangement_role": layer.arrangement_role,
                "events": layer_counts[layer.name],
            }
            for layer in LEAD_LAYERS
        ],
        "effects": [
            {
                "name": effect.name,
                "synth": effect.synth,
                "family": effect.family,
                "role": effect.role,
                "spectral_range": effect.spectral_range,
                "phase_rule": effect.phase_rule,
                "arrangement_role": effect.arrangement_role,
                "events": effect_counts[effect.name],
            }
            for effect in LEAD_EFFECTS
        ],
        "atmospheres": [
            {
                "name": atmosphere.name,
                "synth": atmosphere.synth,
                "family": atmosphere.family,
                "role": atmosphere.role,
                "spectral_range": atmosphere.spectral_range,
                "phase_rule": atmosphere.phase_rule,
                "arrangement_role": atmosphere.arrangement_role,
                "events": atmos_counts[atmosphere.name],
            }
            for atmosphere in LEAD_ATMOSPHERES
        ],
        "families": {
            "counts": dict(sorted(family_counts.items())),
            "first_event_seconds": dict(sorted(family_first_event_seconds.items())),
            "stems": dict(sorted(LEAD_FAMILY_STEMS.items())),
        },
        "sources": {
            "counts": dict(sorted(source_counts.items())),
            "first_event_seconds": dict(sorted(source_first_event_seconds.items())),
        },
        "expression": {
            key: {
                "distinct": len(values),
                "min": min(values) if values else None,
                "max": max(values) if values else None,
            }
            for key, values in sorted(expression_values.items())
        },
        "sections": dict(sorted(section_counts.items())),
        "coherence": lead_coherence_report(),
    }


def write_lead_bus_report(score: list[dict], path: Path) -> None:
    """Write deterministic lead-bus metadata beside generated stems."""
    path.write_text(json.dumps(lead_bus_report(score), indent=2, sort_keys=True), encoding="utf-8")


def lead_family_score_groups(score: list[dict]) -> dict[str, list[dict]]:
    """Split a combined lead-bus score into renderable family groups."""
    return {
        family: [row for row in score if row.get("family") == family]
        for family in LEAD_FAMILY_STEMS
    }


def loudness_proof_command(wav: Path) -> list[str]:
    """Command used to verify integrated LUFS for rendered candidates."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(wav),
        "-filter_complex",
        "ebur128",
        "-f",
        "null",
        "-",
    ]


def peak_proof_command(wav: Path) -> list[str]:
    """Command used to verify peak safety for rendered candidates."""
    return ["sox", str(wav), "-n", "stat"]


def vibe_events(spec: TrackSpec, seed: int, variant: int) -> dict[str, list[NoteEvent]]:
    """The designed parts' events, derived exactly like ``setloom generate``."""
    drums = ALL_PARTS["drums"].generate(spec, part_rng(seed, variant, "drums"))
    events: dict[str, list[NoteEvent]] = {
        "kick": [e for e in drums if e.note == KICK_NOTE],
        "perc": [e for e in drums if e.note != KICK_NOTE],
    }
    for part in PERC_SOURCE_PARTS:
        if part == "drums":
            continue
        events["perc"] += ALL_PARTS[part].generate(spec, part_rng(seed, variant, part))
    for part in VIBE_PARTS:
        if part in ("kick", "perc"):
            continue
        events[part] = ALL_PARTS[part].generate(spec, part_rng(seed, variant, part))
    return events


def score_for_part(part: str, events: list[NoteEvent], spec: TrackSpec) -> list[dict]:
    """Part-specific NRT score rows, including routed buses."""
    if part == "lead":
        return lead_bus_score(events, spec)
    score = export_score(events, spec.bpm)
    if part == "perc":  # route each note to its kit synth, pre-scaled per role
        by_tick = {(e.start_tick, e.note): e for e in events}
        for row in score:
            event = by_tick[(round(row["start"] * spec.bpm * PPQ / 60), row["note"])]
            synth = PERC_SYNTH_FOR_NOTE.get(event.note, "vibe_hat")
            row["synth"] = synth
            row["amp"] = round(row["amp"] * PERC_ROLE_SCALE[synth], 4)
    if part in SECTION_AMP_SCALE:
        scales = SECTION_AMP_SCALE[part]
        windows = section_windows(spec)
        for row in score:
            tick = round(row["start"] * spec.bpm * PPQ / 60)
            for lo, hi, kind in windows:
                if lo <= tick < hi:
                    row["amp"] = round(row["amp"] * scales.get(kind, 1.0), 4)
                    break
    return score


def build_scd(part: str, score: list[dict], bpm: float, total_seconds: float, out_wav: str) -> str:
    """One self-contained sclang NRT script for a part stem (deterministic text).

    Score rows may carry a per-row ``synth`` (the perc stem routes notes to
    kit synths); single-synth parts fall back to ``SYNTH_FOR_PART``.
    24-bit stems leave gain-staging headroom for the master bus.
    """
    default_synth = SYNTH_FOR_PART.get(part, "vibe_hat")
    pump_rate = round(bpm / 60.0, 6)
    uses_expression = any(key in row for row in score for key in LEAD_EXPRESSION_KEYS)
    if uses_expression:
        note_rows = ",\n".join(
            f"    [{row['start']}, {row['note']}, {row['amp']}, {row['dur']}, "
            f"'{row.get('synth', default_synth)}', "
            + ", ".join(str(row.get(key, LEAD_EXPRESSION_DEFAULTS[key])) for key in LEAD_EXPRESSION_KEYS)
            + "]"
            for row in score
        )
        synth_args = f"""'freq', n[1].midicps, 'amp', n[2], 'sustain', n[3], 'pumpRate', {pump_rate},
         'cutoff', n[5], 'drive', n[6], 'tone', n[7], 'motion', n[8],
         'width', n[9], 'space', n[10], 'accent', n[11]"""
    else:
        note_rows = ",\n".join(
            f"    [{row['start']}, {row['note']}, {row['amp']}, {row['dur']}, "
            f"'{row.get('synth', default_synth)}']"
            for row in score
        )
        synth_args = f"'freq', n[1].midicps, 'amp', n[2], 'sustain', n[3], 'pumpRate', {pump_rate}"
    tail = 4.0 if part == "pad" else 1.0
    return f"""// generated by setloom.scrender — do not edit
(
var defs, score, bundles, notes;
defs = "{PATCHES}".load;
notes = [
{note_rows}
];
bundles = defs.collect {{ |d| [0.0, ['/d_recv', d.asBytes]] }};
notes.do {{ |n|
    bundles = bundles.add([
        n[0] + 0.05,
        ['/s_new', n[4], -1, 0, 0,
         {synth_args}]
    ]);
}};
bundles = bundles.add([{round(total_seconds, 3)} + 0.05 + {tail}, [0]]);
score = Score(bundles);
score.recordNRT(
    outputFilePath: "{out_wav}",
    sampleRate: 44100,
    headerFormat: "WAV",
    sampleFormat: "int24",
    options: ServerOptions.new.numOutputBusChannels_(2).memSize_(2 ** 18),
    action: {{ "RENDER-DONE {part}".postln; 0.exit }}
);
)
"""


def render_score_stem(
    part: str,
    score: list[dict],
    spec: TrackSpec,
    out_wav: Path,
    sclang: str,
    workdir: Path,
    script_stem: str | None = None,
) -> None:
    seconds = ticks_to_seconds(total_ticks(spec), spec.bpm)
    scd = build_scd(part, score, spec.bpm, seconds, str(out_wav))
    scd_path = workdir / f"render-{script_stem or part}.scd"
    scd_path.write_text(scd, encoding="utf-8")
    result = subprocess.run(
        [sclang, str(scd_path)], capture_output=True, text=True, timeout=600
    )
    if f"RENDER-DONE {part}" not in result.stdout or not out_wav.exists():
        raise RuntimeError(f"sclang render failed for {part}:\n{result.stdout[-2000:]}")


def render_part_stem(
    part: str,
    events: list[NoteEvent],
    spec: TrackSpec,
    out_wav: Path,
    sclang: str,
    workdir: Path,
) -> None:
    score = score_for_part(part, events, spec)
    if part == "lead":
        write_lead_bus_report(score, workdir / "lead-bus-report.json")
        family_scores = lead_family_score_groups(score)
        family_stems: dict[str, Path] = {}
        for family, rows in family_scores.items():
            if not rows:
                raise RuntimeError(f"lead family has no rows: {family}")
            family_stem = workdir / LEAD_FAMILY_STEMS[family]
            render_score_stem("lead", rows, spec, family_stem, sclang, workdir, f"lead-{family}")
            family_stems[family] = family_stem
        raw_bus = workdir / "stem-lead-bus-raw.wav"
        cmd = ["sox", "-m"]
        for family, stem in family_stems.items():
            cmd += ["-v", str(LEAD_FAMILY_MIX_GAINS[family]), str(stem)]
        cmd.append(str(raw_bus))
        subprocess.run(cmd, check=True, capture_output=True)
        subprocess.run(["sox", str(raw_bus), str(out_wav), "gain", "-n", "-4"], check=True, capture_output=True)
        raw_bus.unlink()
        return
    render_score_stem(part, score, spec, out_wav, sclang, workdir)


def mix(variant_dir: Path, sc_stems: dict[str, Path], spec: TrackSpec, out_wav: Path) -> None:
    """Gain-staged mix + deterministic master bus (cross-model recipe).

    Premaster: hierarchy gains, normalized to -6 dB headroom. Master:
    rumble HPF, soft-knee bus compression, peak-normalize to -1 dB.
    """
    premaster = variant_dir / "premaster.wav"
    cmd = ["sox", "-m"]
    for part, stem in sc_stems.items():
        cmd += ["-v", str(MIX_GAINS[part]), str(stem)]
    cmd += [str(premaster), "gain", "-n", "-6"]
    subprocess.run(cmd, check=True, capture_output=True)
    subprocess.run(
        ["sox", str(premaster), str(out_wav), *MASTER_CHAIN],
        check=True,
        capture_output=True,
    )
    premaster.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render vibe stems via SuperCollider NRT")
    parser.add_argument("spec")
    parser.add_argument("variant_dir")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--variant", type=int, default=1)
    args = parser.parse_args(argv)

    sclang = find_sclang()
    if sclang is None:
        print("sclang not found — install SuperCollider", file=sys.stderr)
        return 1
    spec = load_spec(args.spec)
    seed = spec.seed if args.seed is None else args.seed
    variant_dir = Path(args.variant_dir)
    variant_dir.mkdir(parents=True, exist_ok=True)

    events = vibe_events(spec, seed, args.variant)
    stems: dict[str, Path] = {}
    for part in VIBE_PARTS:
        stem = variant_dir / f"stem-{part}.wav"
        render_part_stem(part, events[part], spec, stem, sclang, variant_dir)
        stems[part] = stem
        print(f"rendered {stem.name}")
    out = variant_dir / "vibe_mix.wav"
    mix(variant_dir, stems, spec, out)
    print(f"mixed {out}")
    print("reminder: candidates require human listening notes before approval")
    return 0


def export_score_json(events: list[NoteEvent], bpm: float) -> str:
    """Stable JSON for tests/interop."""
    return json.dumps(export_score(events, bpm), sort_keys=True)


if __name__ == "__main__":
    raise SystemExit(main())
