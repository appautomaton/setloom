# SPDX-License-Identifier: AGPL-3.0-only
"""Technical scorer: an anatomy dossier measured against current pack targets.

Scores are diagnostics, never taste verdicts. During a pack rebuild, missing
targets are acceptable and reported as missing instead of forcing stale musical
rules back into the system. Each metric carries the provenance of its target
(``corpus`` / ``evidence`` / ``assumption``) for older packs and test fixtures.

Inputs come from the current cached quick dossier; targets come from
:func:`setloom.stylepack.load_style_pack`. Target numbers are never duplicated
here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from setloom.anatomy import corpus as co
from setloom.stylepack import StylePack

LISTENING_GATE_LINE = (
    "scores are the technical half of review; musical judgment stays with the listening gate"
)

# Coarse conversion for the vocal_presence taste knob (0-10) into a maximum
# expected vocal active share. A judgment call, labeled assumption-grade:
# knob 1 -> share <= 0.15, matching the corpus "near-absent" mode (0.01-0.14).
VOCAL_KNOB_BASE = 0.05
VOCAL_KNOB_STEP = 0.10


@dataclass(frozen=True)
class MetricScore:
    metric: str
    source_field: str
    target: object
    measured: object
    status: str  # "in" | "out" | "missing"
    distance: float | None  # signed: <0 below target, >0 above; 0.0 in range; None if n/a
    provenance: str  # corpus | evidence | assumption


@dataclass(frozen=True)
class ScoreReport:
    track: str
    pack_id: str
    metrics: list[MetricScore]

    @property
    def counts(self) -> dict[str, int]:
        out = {"in": 0, "out": 0, "missing": 0}
        for m in self.metrics:
            out[m.status] += 1
        return out


def _target(pack: StylePack, path: tuple[str, ...]):
    node = pack.raw
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _range_score(measured, target) -> tuple[str, float | None]:
    lo, hi = float(target[0]), float(target[1])
    value = float(measured)
    if value < lo:
        return "out", round(value - lo, 4)
    if value > hi:
        return "out", round(value - hi, 4)
    return "in", 0.0


# metric -> (source field shown in reports, target path in style.yml, kind, provenance)
# kinds: "range" = [lo, hi] window; "mode" = string match.
METRICS: tuple[tuple[str, str, tuple[str, ...], str, str], ...] = (
    ("bpm", "row.bpm", ("generation_defaults", "bpm_range"), "range", "corpus"),
    ("lufs", "row.lufs", ("generation_defaults", "loudness_target_lufs"), "range", "corpus"),
    (
        "bass_occupancy",
        "row.bass_occupancy",
        ("groove", "bass_step_occupancy_target"),
        "range",
        "corpus",
    ),
    (
        "main_break_start_frac",
        "row.main_break_start_frac",
        ("arrangement_tension", "main_break_start_fraction"),
        "range",
        "corpus",
    ),
    (
        "duration_minutes",
        "row.duration_s / 60",
        ("generation_defaults", "club_edit_duration_minutes"),
        "range",
        "evidence",
    ),
    ("key_mode", "quick.key_estimate", ("generation_defaults", "key_mode_bias"), "mode", "evidence"),
    (
        "vocal_share",
        "row.vocal_share",
        ("style_vector_defaults", "vocal_presence"),
        "vocal_knob",
        "assumption",
    ),
)


def _measure(metric: str, row: dict, quick: dict):
    if metric == "duration_minutes":
        dur = row.get("duration_s")
        return None if dur is None else round(dur / 60.0, 2)
    if metric == "key_mode":
        key = quick.get("key_estimate")
        return key.split()[-1] if isinstance(key, str) and " " in key else None
    return row.get(metric)


def score_row(row: dict, quick: dict, pack: StylePack) -> ScoreReport:
    """Score one track row (plus its quick dossier) against a style pack."""
    metrics: list[MetricScore] = []
    for name, source, path, kind, provenance in METRICS:
        target = _target(pack, path)
        measured = _measure(name, row, quick)
        if target is None and measured is None:
            continue
        if kind == "vocal_knob" and target is not None:
            target = [0.0, round(min(1.0, VOCAL_KNOB_BASE + VOCAL_KNOB_STEP * float(target)), 2)]
            kind = "range"
        if target is None or measured is None:
            status, distance = "missing", None
        elif kind == "mode":
            status = "in" if measured == target else "out"
            distance = None
        else:
            status, distance = _range_score(measured, target)
        metrics.append(MetricScore(name, source, target, measured, status, distance, provenance))
    return ScoreReport(track=row["track"], pack_id=pack.id, metrics=metrics)


def report_to_dict(report: ScoreReport) -> dict:
    return {
        "track": report.track,
        "pack": report.pack_id,
        "metrics": [
            {
                "metric": m.metric,
                "measured": m.measured,
                "target": m.target,
                "status": m.status,
                "distance": m.distance,
                "provenance": m.provenance,
                "source": m.source_field,
            }
            for m in report.metrics
        ],
        "counts": report.counts,
        "note": LISTENING_GATE_LINE,
    }


def report_lines(report: ScoreReport) -> list[str]:
    """Compact human-readable report for the CLI."""
    lines = [f"{report.track} — {report.pack_id}"]
    for m in report.metrics:
        flag = {"in": "in ", "out": "OUT", "missing": "?? "}[m.status]
        dist = f" {m.distance:+g}" if m.status == "out" and m.distance is not None else ""
        lines.append(
            f"  {m.metric:<22} {m.measured!s:>8}  {flag} {m.target!s:<16}{dist}  ({m.provenance})"
        )
    c = report.counts
    lines.append(f"  in {c['in']} / out {c['out']} / missing {c['missing']}")
    lines.append(f"  {LISTENING_GATE_LINE}")
    return lines


def load_row(track: str, out_dir: Path) -> tuple[dict, dict] | None:
    """Build (row, quick) from the cached quick dossier."""
    quick_path = out_dir / f"{track}.quick.yml"
    if not quick_path.is_file():
        return None
    quick = yaml.safe_load(quick_path.read_text(encoding="utf-8"))
    return co.quick_row(track, quick), quick


def score_track(
    audio: Path,
    pack: StylePack,
    out_dir: Path = Path("local/corpus/dossiers"),
) -> tuple[ScoreReport, Path]:
    """Score one audio file from an existing cached quick dossier."""
    from setloom.anatomy import analysis as an

    track = an.nfc(audio.stem)
    loaded = load_row(track, out_dir)
    if loaded is None:
        raise RuntimeError(f"no cached quick dossier for {audio}")
    row, quick = loaded
    report = score_row(row, quick, pack)
    score_path = out_dir / f"{track}.score.yml"
    text = yaml.safe_dump(report_to_dict(report), sort_keys=False, width=100, allow_unicode=True)
    if not (score_path.is_file() and score_path.read_text(encoding="utf-8") == text):
        score_path.write_text(text, encoding="utf-8")
    return report, score_path
