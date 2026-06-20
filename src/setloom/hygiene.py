# SPDX-License-Identifier: AGPL-3.0-only
"""Spec-evaluable technical hygiene checks.

This module intentionally carries only checks the harness can evaluate from a
track spec. Musical taste, groove, timbre, and arrangement choices stay in the
track's own source files and listening notes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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


DURATION_PROFILES = {
    "club_extended": {"mixable_edges": "required"},
    "streaming_edit": {"mixable_edges": "reduced"},
}


def spec_duration_seconds(spec: TrackSpec) -> float:
    """Duration of a 4/4 spec in seconds (bars x beats / bpm)."""
    return spec.duration_bars * 4 * 60 / spec.bpm


def duration_profile(spec: TrackSpec) -> dict[str, str]:
    """Return the spec's product-form profile; ValueError on unknown ids."""
    profile = DURATION_PROFILES.get(spec.duration_profile)
    if profile is None:
        raise ValueError(
            f"unknown duration_profile {spec.duration_profile!r} "
            f"(known: {sorted(DURATION_PROFILES)})"
        )
    return profile


def _check_unmixable_edges(spec: TrackSpec) -> GateViolation | None:
    if duration_profile(spec).get("mixable_edges") != "required":
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


def evaluate_hygiene_gate(spec: TrackSpec) -> GateResult:
    """Run the built-in spec-level hygiene gate."""
    blocking = []
    violation = _check_unmixable_edges(spec)
    if violation is not None:
        blocking.append(violation)
    return GateResult(blocking=blocking)
