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

SYNTH_FOR_PART = {
    "kick": "vibe_kick",
    "bass": "vibe_bass",
    "pad": "vibe_pad",
    "chords": "vibe_chords",
    "arp": "vibe_arp",
    "lead": "vibe_lead",
    "fx": "vibe_fx",
}


@dataclass(frozen=True)
class LeadLayer:
    """One role inside the lead bus: musical intent plus deterministic render rules."""

    name: str
    synth: str
    role: str
    spectral_range: str
    phase_rule: str
    arrangement_role: str
    rationale: str
    section_amp: dict[str, float]
    transpose: int = 0
    note_stride: int = 1


LEAD_LAYERS = (
    LeadLayer(
        name="lead_body",
        synth="vibe_lead_body",
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
    for start, end, kind in windows:
        if start <= tick < end:
            return kind
    return "unknown"


def lead_layer_score(events: list[NoteEvent], spec: TrackSpec) -> list[dict]:
    """Fan logical lead notes into role-specific lead-bus score rows."""
    windows = section_windows(spec)
    rows: list[dict] = []
    for index, row in enumerate(export_score(events, spec.bpm)):
        tick = round(row["start"] * spec.bpm * PPQ / 60)
        section = section_kind_at_tick(tick, windows)
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
            layered["section"] = section
            rows.append(layered)
    return sorted(rows, key=lambda r: (r["start"], r["layer"], r["note"]))


def lead_layer_score_json(events: list[NoteEvent], spec: TrackSpec) -> str:
    """Stable JSON representation for tests and report plumbing."""
    return json.dumps(lead_layer_score(events, spec), sort_keys=True)


def lead_coherence_report() -> dict[str, dict[str, str]]:
    """Neighboring-part rules that prevent patch-over-patch accumulation."""
    return {part: dict(rules) for part, rules in LEAD_COHERENCE.items()}


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


def build_scd(part: str, score: list[dict], bpm: float, total_seconds: float, out_wav: str) -> str:
    """One self-contained sclang NRT script for a part stem (deterministic text).

    Score rows may carry a per-row ``synth`` (the perc stem routes notes to
    kit synths); single-synth parts fall back to ``SYNTH_FOR_PART``.
    24-bit stems leave gain-staging headroom for the master bus.
    """
    default_synth = SYNTH_FOR_PART.get(part, "vibe_hat")
    pump_rate = round(bpm / 60.0, 6)
    note_rows = ",\n".join(
        f"    [{row['start']}, {row['note']}, {row['amp']}, {row['dur']}, "
        f"'{row.get('synth', default_synth)}']"
        for row in score
    )
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
         'freq', n[1].midicps, 'amp', n[2], 'sustain', n[3], 'pumpRate', {pump_rate}]
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


def render_part_stem(
    part: str,
    events: list[NoteEvent],
    spec: TrackSpec,
    out_wav: Path,
    sclang: str,
    workdir: Path,
) -> None:
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
    seconds = ticks_to_seconds(total_ticks(spec), spec.bpm)
    scd = build_scd(part, score, spec.bpm, seconds, str(out_wav))
    scd_path = workdir / f"render-{part}.scd"
    scd_path.write_text(scd, encoding="utf-8")
    result = subprocess.run(
        [sclang, str(scd_path)], capture_output=True, text=True, timeout=600
    )
    if f"RENDER-DONE {part}" not in result.stdout or not out_wav.exists():
        raise RuntimeError(f"sclang render failed for {part}:\n{result.stdout[-2000:]}")


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
        ["sox", str(premaster), str(out_wav),
         "highpass", "28",
         "compand", "0.003,0.120",
         "6:-70,-70,-36,-30,-24,-20,-18,-15,-12,-10,-8,-7,-4,-3", "0", "-90", "0.02",
         # Genre-default loudness (taste-owner decision 2026-06-07): techno/tech
         # house masters run ~-8..-6 LUFS, well above vocal-music norms. Push
         # makeup harder and limit tighter; aim drop RMS ~ -9 dBFS.
         "gain", "9",
         "compand", "0.001,0.012", "-4,-4,0,-2", "0", "-90", "0.001",  # brickwall-ish limiter
         "gain", "-n", "-1"],
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
