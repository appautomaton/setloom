# SPDX-License-Identifier: AGPL-3.0-only
"""Style-pack loading and the generation-time rejection gate.

The gate evaluates the spec-evaluable rejection rules from a style pack's
``rejection_rules`` block. Rules that are properties of produced MIDI
(``low-end-conflict``) are enforced by construction in the part generators
and their invariant tests; ``no-listening-no-approval`` belongs to the
approval flow, not generation. Both are intentionally not evaluated here.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from setloom.schema import TrackSpec

SPEC_EVALUABLE_RULES = (
    "bpm-out-of-lane",
    "club-length",
    "unmixable-edges",
    "short-edit-identity",
)

# Fallback window when a pack predates duration_profiles.
CLUB_LENGTH_MIN_SECONDS = 5 * 60
CLUB_LENGTH_MAX_SECONDS = 9 * 60


@dataclass(frozen=True)
class GateViolation:
    rule_id: str
    message: str


@dataclass(frozen=True)
class GateResult:
    blocking: list[GateViolation] = field(default_factory=list)
    overridden: list[GateViolation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.blocking


@dataclass(frozen=True)
class StylePack:
    id: str
    generation_defaults: dict
    rejection_rules: list[dict]
    raw: dict

    @property
    def rule_ids(self) -> list[str]:
        return [rule["id"] for rule in self.rejection_rules]


def load_style_pack(pack_id: str, root: str | Path = ".") -> StylePack:
    """Load ``style-packs/<pack_id>/style.yml`` under ``root``."""
    path = Path(root) / "style-packs" / pack_id / "style.yml"
    if not path.is_file():
        raise FileNotFoundError(f"style pack '{pack_id}' not found at {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return StylePack(
        id=raw.get("id", pack_id),
        generation_defaults=raw.get("generation_defaults") or {},
        rejection_rules=raw.get("rejection_rules") or [],
        raw=raw,
    )


def spec_duration_seconds(spec: TrackSpec) -> float:
    """Duration of a 4/4 spec in seconds (bars x beats / bpm)."""
    return spec.duration_bars * 4 * 60 / spec.bpm


def _check_bpm_out_of_lane(spec: TrackSpec, pack: StylePack) -> GateViolation | None:
    bpm_range = pack.generation_defaults.get("bpm_range")
    if bpm_range and not (bpm_range[0] <= spec.bpm <= bpm_range[1]):
        return GateViolation(
            "bpm-out-of-lane",
            f"bpm {spec.bpm:g} outside {pack.id} bpm_range [{bpm_range[0]}, {bpm_range[1]}]",
        )
    return None


def duration_profile(spec: TrackSpec, pack: StylePack) -> dict:
    """The spec's duration profile from the pack; ValueError on unknown ids."""
    profiles = pack.generation_defaults.get("duration_profiles") or {}
    if not profiles:
        # Pack predates duration_profiles: behave like the original club gate.
        return {
            "duration_minutes": [CLUB_LENGTH_MIN_SECONDS / 60, CLUB_LENGTH_MAX_SECONDS / 60],
            "mixable_edges": "required",
        }
    profile = profiles.get(spec.duration_profile)
    if profile is None:
        raise ValueError(
            f"unknown duration_profile {spec.duration_profile!r} "
            f"(known: {sorted(profiles)})"
        )
    return profile


def _check_club_length(spec: TrackSpec, pack: StylePack) -> GateViolation | None:
    window = duration_profile(spec, pack)["duration_minutes"]
    minutes = spec_duration_seconds(spec) / 60
    if minutes < window[0] or minutes > window[1]:
        return GateViolation(
            "club-length",
            f"duration {minutes:.2f} min outside {spec.duration_profile} window "
            f"[{window[0]:g}, {window[1]:g}] min",
        )
    return None


def _check_unmixable_edges(spec: TrackSpec, pack: StylePack) -> GateViolation | None:
    if duration_profile(spec, pack).get("mixable_edges") != "required":
        return None  # profile-scoped: streaming edits run reduced edges
    names = list(spec.sections)
    has_intro = bool(names) and names[0].startswith("intro")
    has_outro = bool(names) and names[-1].startswith("outro")
    if not (has_intro and has_outro):
        return GateViolation(
            "unmixable-edges",
            "arrangement must start with an intro section and end with an outro section",
        )
    return None


def _check_short_edit_identity(spec: TrackSpec, pack: StylePack) -> GateViolation | None:
    if spec.duration_profile != "streaming_edit":
        return None
    has_break = any(name.startswith("break") for name in spec.sections)
    has_peak = any(name.startswith("peak") for name in spec.sections)
    if not (has_break and has_peak):
        return GateViolation(
            "short-edit-identity",
            "a streaming edit must keep at least one break and one peak section",
        )
    return None


_CHECKS = {
    "bpm-out-of-lane": _check_bpm_out_of_lane,
    "club-length": _check_club_length,
    "unmixable-edges": _check_unmixable_edges,
    "short-edit-identity": _check_short_edit_identity,
}


def evaluate_gate(
    spec: TrackSpec,
    pack: StylePack,
    allow_overrides: set[str] | None = None,
) -> GateResult:
    """Evaluate spec-evaluable rejection rules; partition by override allow-list."""
    overrides = allow_overrides or set()
    unknown = overrides - set(pack.rule_ids)
    if unknown:
        raise ValueError(f"unknown override rule ids: {sorted(unknown)}")

    blocking: list[GateViolation] = []
    overridden: list[GateViolation] = []
    for rule in pack.rejection_rules:
        check = _CHECKS.get(rule["id"])
        if check is None:
            continue  # not spec-evaluable (see module docstring)
        violation = check(spec, pack)
        if violation is None:
            continue
        if violation.rule_id in overrides:
            overridden.append(violation)
        else:
            blocking.append(violation)
    return GateResult(blocking=blocking, overridden=overridden)
