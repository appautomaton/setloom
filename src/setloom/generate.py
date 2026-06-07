# SPDX-License-Identifier: AGPL-3.0-only
"""Candidate generation orchestrator (Spec 4).

Turns a validated track spec into N MIDI candidate variants plus one
compact review report per run. Output layout:

    <out>/<spec.id>/seed-<seed>/variant-NN/{part}.mid
    <out>/<spec.id>/seed-<seed>/report.md

Determinism: each part's RNG derives from (seed, variant_index, part_name),
so the same spec + seed always produce byte-identical MIDI.
"""

from dataclasses import dataclass
from pathlib import Path

from setloom.midi import TICKS_PER_BAR, NoteEvent, section_layout, write_part_midi
from setloom.parts import ALL_PARTS, part_rng
from setloom.parts.bass import select_articulation_profile
from setloom.schema import TrackSpec
from setloom.stylepack import GateResult, StylePack, evaluate_gate, spec_duration_seconds

# Foreground melodic streams only — pad is deliberately excluded: it is a
# harmonic BED, and the melodic-layer-overload review rule counts foreground
# layers (see style.yml; ears datapoint 2026-06-07).
MELODIC_PARTS = ("chords", "arp", "lead")

HUMAN_GATE_NOTICE = (
    "These candidates are NOT final. Per the Setloom workflow, no candidate "
    "may be approved without human listening notes (decision states: keep / "
    "revise / reject)."
)


class GateError(Exception):
    """Raised when the rejection gate blocks generation."""

    def __init__(self, result: GateResult):
        self.result = result
        rules = ", ".join(v.rule_id for v in result.blocking)
        super().__init__(f"rejection gate blocked generation: {rules}")


@dataclass(frozen=True)
class VariantResult:
    index: int
    directory: Path
    note_counts: dict[str, int]
    bass_profile: str
    melodic_layers: dict[str, int]  # section type -> active melodic layer count
    fill_bars: list[int]


@dataclass(frozen=True)
class RunResult:
    run_dir: Path
    report_path: Path
    gate: GateResult
    variants: list[VariantResult]


def _unknown_parts(spec: TrackSpec) -> list[str]:
    return [part for part in spec.render_targets.midi if part not in ALL_PARTS]


def _section_type(name: str) -> str:
    """Collapse section names to their type: drop_1 -> drop."""
    return name.rstrip("0123456789_")


def _melodic_layers(spec: TrackSpec, events: dict[str, list[NoteEvent]]) -> dict[str, int]:
    """Count active melodic layers (chords/arp/lead) per section type."""
    layers: dict[str, int] = {}
    for section, (start_bar, bars) in section_layout(spec).items():
        start, end = start_bar * TICKS_PER_BAR, (start_bar + bars) * TICKS_PER_BAR
        active = sum(
            1
            for part in MELODIC_PARTS
            if any(start <= e.start_tick < end for e in events.get(part, []))
        )
        kind = _section_type(section)
        layers[kind] = max(layers.get(kind, 0), active)
    return layers


def _fill_bars(events: list[NoteEvent]) -> list[int]:
    return sorted({e.start_tick // TICKS_PER_BAR for e in events})


def generate_candidates(
    spec: TrackSpec,
    pack: StylePack,
    out_dir: str | Path,
    variants: int,
    seed: int | None = None,
    allow_overrides: set[str] | None = None,
) -> RunResult:
    """Generate ``variants`` candidate sets for ``spec`` under ``out_dir``."""
    if variants < 1:
        raise ValueError("variants must be >= 1")
    unknown = _unknown_parts(spec)
    if unknown:
        raise ValueError(f"unknown midi render targets: {unknown} (available: {sorted(ALL_PARTS)})")

    gate = evaluate_gate(spec, pack, allow_overrides)
    if not gate.passed:
        raise GateError(gate)

    effective_seed = spec.seed if seed is None else seed
    run_dir = Path(out_dir) / spec.id / f"seed-{effective_seed}"
    results: list[VariantResult] = []
    for index in range(1, variants + 1):
        variant_dir = run_dir / f"variant-{index:02d}"
        variant_dir.mkdir(parents=True, exist_ok=True)
        counts: dict[str, int] = {}
        part_events: dict[str, list[NoteEvent]] = {}
        for part_name in spec.render_targets.midi:
            generator = ALL_PARTS[part_name]
            events: list[NoteEvent] = generator.generate(
                spec, part_rng(effective_seed, index, part_name)
            )
            write_part_midi(variant_dir / f"{part_name}.mid", spec, events)
            counts[part_name] = len(events)
            part_events[part_name] = events
        # Same rng derivation as BassGenerator's first (only) profile draw,
        # so the reported profile matches the rendered bass exactly.
        bass_profile = select_articulation_profile(spec, part_rng(effective_seed, index, "bass"))
        results.append(
            VariantResult(
                index=index,
                directory=variant_dir,
                note_counts=counts,
                bass_profile=bass_profile,
                melodic_layers=_melodic_layers(spec, part_events),
                fill_bars=_fill_bars(part_events.get("fills", [])),
            )
        )

    report_path = run_dir / "report.md"
    report_path.write_text(
        _render_report(spec, pack, effective_seed, gate, results), encoding="utf-8"
    )
    return RunResult(run_dir=run_dir, report_path=report_path, gate=gate, variants=results)


def _render_report(
    spec: TrackSpec,
    pack: StylePack,
    seed: int,
    gate: GateResult,
    variants: list[VariantResult],
) -> str:
    bars = spec.duration_bars
    minutes = spec_duration_seconds(spec) / 60
    lines = [
        f"# Candidate Report: {spec.id} '{spec.title}'",
        "",
        f"- style pack: {pack.id}",
        f"- bpm {spec.bpm:g} | key {spec.key} | {bars} bars (~{minutes:.1f} min) | seed {seed}",
        f"- variants: {len(variants)}",
        "",
        "## Rejection Gate",
        "",
    ]
    if gate.overridden:
        for violation in gate.overridden:
            lines.append(f"- OVERRIDDEN {violation.rule_id}: {violation.message}")
    else:
        lines.append("- all spec-evaluable rules passed")
    lines += ["", "## Variants", ""]
    for variant in variants:
        density = {
            part: f"{count / bars:.1f}/bar" for part, count in variant.note_counts.items()
        }
        counts = ", ".join(f"{part} {count} ({density[part]})" for part, count in variant.note_counts.items())
        layers = ", ".join(f"{kind} {n}" for kind, n in variant.melodic_layers.items())
        fills = ", ".join(str(bar) for bar in variant.fill_bars) or "none"
        lines.append(f"- variant-{variant.index:02d} [rng (seed={seed}, variant={variant.index})]: {counts}")
        lines.append(f"  - bass articulation: {variant.bass_profile}")
        lines.append(f"  - melodic layers by section: {layers}")
        lines.append(f"  - fill bars: {fills}")
    lines += ["", "## Listening Gate", "", HUMAN_GATE_NOTICE, ""]
    return "\n".join(lines)
