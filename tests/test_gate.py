# SPDX-License-Identifier: AGPL-3.0-only
"""Hygiene-gate tests."""

from pathlib import Path

import pytest
import yaml

from setloom.schema import TrackSpec, load_spec
from setloom.hygiene import evaluate_hygiene_gate

T01 = Path(__file__).resolve().parent / "fixtures" / "spec-t01.yml"


def _spec_with(**overrides) -> TrackSpec:
    raw = yaml.safe_load(T01.read_text(encoding="utf-8"))
    raw.update(overrides)
    return TrackSpec.model_validate(raw)


def test_t01_passes_gate() -> None:
    result = evaluate_hygiene_gate(load_spec(T01))
    assert result.passed
    assert result.blocking == []


def test_bpm_138_is_not_blocked() -> None:
    result = evaluate_hygiene_gate(_spec_with(bpm=138))
    assert result.passed


def test_long_duration_is_not_blocked() -> None:
    sections = {"intro": 32, "groove_a": 64, "drop_1": 96, "peak": 96, "outro": 32}
    result = evaluate_hygiene_gate(_spec_with(bpm=122, duration_bars=320, sections=sections))
    assert result.passed


def test_missing_outro_fails_unmixable_edges() -> None:
    sections = {"intro": 32, "groove_a": 96, "drop_1": 64, "peak": 64}
    result = evaluate_hygiene_gate(_spec_with(duration_bars=256, sections=sections))
    assert "unmixable-edges" in [v.rule_id for v in result.blocking]


# --- Duration profiles ---

STREAMING_SECTIONS = {
    "intro": 16, "groove_a": 16, "break_1": 16, "drop_1": 32, "peak": 32, "outro": 16,
}


def test_streaming_edit_passes_gate() -> None:
    spec = _spec_with(
        duration_profile="streaming_edit", duration_bars=128, sections=STREAMING_SECTIONS
    )
    result = evaluate_hygiene_gate(spec)
    assert result.passed, result.blocking


def test_streaming_edit_without_break_passes() -> None:
    sections = {"intro": 16, "groove_a": 32, "drop_1": 32, "peak": 32, "outro": 16}
    spec = _spec_with(duration_profile="streaming_edit", duration_bars=128, sections=sections)
    result = evaluate_hygiene_gate(spec)
    assert result.passed


def test_club_profile_128_bars_passes() -> None:
    spec = _spec_with(duration_bars=128, sections=STREAMING_SECTIONS)
    result = evaluate_hygiene_gate(spec)
    assert result.passed


def test_streaming_edit_skips_mixable_edges() -> None:
    sections = {"groove_a": 32, "break_1": 16, "drop_1": 32, "peak": 48}  # no intro/outro
    spec = _spec_with(duration_profile="streaming_edit", duration_bars=128, sections=sections)
    result = evaluate_hygiene_gate(spec)
    assert "unmixable-edges" not in [v.rule_id for v in result.blocking]


def test_unknown_duration_profile_raises() -> None:
    spec = _spec_with(duration_profile="vinyl_edit")
    with pytest.raises(ValueError, match="unknown duration_profile"):
        evaluate_hygiene_gate(spec)
