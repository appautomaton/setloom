# SPDX-License-Identifier: AGPL-3.0-only
"""Style-pack loading and the technical-hygiene gate.

The gate evaluates spec-evaluable rejection rules listed in a style pack's
``rejection_rules`` block. Only ``unmixable-edges`` is implemented today: it
requires intro+outro sections for duration profiles that request mixable edges.
Rules that depend on produced MIDI or audio (low-end conflict, clipping,
mono-safety) are not spec-evaluable and belong to per-track code or future
audio checks, not here.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from setloom.schema import TrackSpec


@dataclass(frozen=True)
class GateViolation:
    rule_id: str
    message: str


@dataclass(frozen=True)
class GateResult:
    blocking: list[GateViolation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.blocking


@dataclass(frozen=True)
class StylePack:
    id: str
    raw: dict


def load_style_pack(pack_id: str, root: str | Path = ".") -> StylePack:
    """Load ``music/packs/<pack_id>/style.yml`` under ``root``."""
    path = Path(root) / "music/packs" / pack_id / "style.yml"
    if not path.is_file():
        raise FileNotFoundError(f"style pack '{pack_id}' not found at {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return StylePack(id=raw.get("id", pack_id), raw=raw)


def spec_duration_seconds(spec: TrackSpec) -> float:
    """Duration of a 4/4 spec in seconds (bars x beats / bpm)."""
    return spec.duration_bars * 4 * 60 / spec.bpm


def duration_profile(spec: TrackSpec, pack: StylePack) -> dict:
    """The spec's duration profile from the pack; ValueError on unknown ids."""
    profiles = (pack.raw.get("generation_defaults") or {}).get("duration_profiles") or {}
    if not profiles:
        return {"mixable_edges": "required"}
    profile = profiles.get(spec.duration_profile)
    if profile is None:
        raise ValueError(
            f"unknown duration_profile {spec.duration_profile!r} "
            f"(known: {sorted(profiles)})"
        )
    return profile


def _check_unmixable_edges(spec: TrackSpec, pack: StylePack) -> GateViolation | None:
    if duration_profile(spec, pack).get("mixable_edges") != "required":
        return None
    names = list(spec.sections)
    has_intro = bool(names) and names[0].startswith("intro")
    has_outro = bool(names) and names[-1].startswith("outro")
    if not (has_intro and has_outro):
        return GateViolation(
            "unmixable-edges",
            "arrangement must start with an intro section and end with an outro section",
        )
    return None


_CHECKS = {
    "unmixable-edges": _check_unmixable_edges,
}


def evaluate_gate(spec: TrackSpec, pack: StylePack) -> GateResult:
    """Evaluate spec-evaluable rejection rules from the pack's rejection_rules."""
    blocking: list[GateViolation] = []
    for rule in pack.raw.get("rejection_rules") or []:
        check = _CHECKS.get(rule["id"])
        if check is None:
            continue
        violation = check(spec, pack)
        if violation is not None:
            blocking.append(violation)
    return GateResult(blocking=blocking)
