# SPDX-License-Identifier: AGPL-3.0-only
"""Rejection-gate tests (SPEC AC6 logic)."""

from pathlib import Path

import pytest
import yaml

from setloom.schema import TrackSpec, load_spec
from setloom.stylepack import evaluate_gate, load_style_pack

REPO_ROOT = Path(__file__).resolve().parents[1]
T01 = REPO_ROOT / "tracks" / "T01" / "spec.yml"


@pytest.fixture(scope="module")
def pack():
    return load_style_pack("melodic-progressive-techno", root=REPO_ROOT)


def _spec_with(**overrides) -> TrackSpec:
    raw = yaml.safe_load(T01.read_text(encoding="utf-8"))
    raw.update(overrides)
    return TrackSpec.model_validate(raw)


def test_t01_passes_gate(pack) -> None:
    result = evaluate_gate(load_spec(T01), pack)
    assert result.passed
    assert result.blocking == [] and result.overridden == []


def test_bpm_138_fails_naming_rule(pack) -> None:
    result = evaluate_gate(_spec_with(bpm=138), pack)
    assert not result.passed
    assert [v.rule_id for v in result.blocking] == ["bpm-out-of-lane"]


def test_bpm_138_override_passes_and_records(pack) -> None:
    result = evaluate_gate(_spec_with(bpm=138), pack, allow_overrides={"bpm-out-of-lane"})
    assert result.passed
    assert [v.rule_id for v in result.overridden] == ["bpm-out-of-lane"]


def test_club_length_too_long_fails(pack) -> None:
    # 320 bars at 122 BPM = 10:29 — over the 9:00 ceiling. 122 stays inside the
    # corpus-narrowed bpm_range so only club-length is exercised here.
    sections = {"intro": 32, "groove_a": 64, "drop_1": 96, "peak": 96, "outro": 32}
    result = evaluate_gate(
        _spec_with(bpm=122, duration_bars=320, sections=sections), pack
    )
    assert "club-length" in [v.rule_id for v in result.blocking]


def test_missing_outro_fails_unmixable_edges(pack) -> None:
    sections = {"intro": 32, "groove_a": 96, "drop_1": 64, "peak": 64}
    result = evaluate_gate(_spec_with(duration_bars=256, sections=sections), pack)
    assert "unmixable-edges" in [v.rule_id for v in result.blocking]


def test_unknown_override_rejected(pack) -> None:
    with pytest.raises(ValueError, match="unknown override"):
        evaluate_gate(load_spec(T01), pack, allow_overrides={"not-a-rule"})


# --- Duration profiles (change 2026-06-07-duration-profiles) ---

STREAMING_SECTIONS = {
    "intro": 16, "groove_a": 16, "break_1": 16, "drop_1": 32, "peak": 32, "outro": 16,
}


def test_streaming_edit_passes_gate(pack) -> None:
    spec = _spec_with(
        duration_profile="streaming_edit", duration_bars=128, sections=STREAMING_SECTIONS
    )
    result = evaluate_gate(spec, pack)
    assert result.passed, result.blocking


def test_streaming_edit_without_break_fails_identity(pack) -> None:
    sections = {"intro": 16, "groove_a": 32, "drop_1": 32, "peak": 32, "outro": 16}
    spec = _spec_with(duration_profile="streaming_edit", duration_bars=128, sections=sections)
    result = evaluate_gate(spec, pack)
    assert [v.rule_id for v in result.blocking] == ["short-edit-identity"]


def test_128_bars_under_club_profile_fails_length(pack) -> None:
    spec = _spec_with(duration_bars=128, sections=STREAMING_SECTIONS)  # default club profile
    result = evaluate_gate(spec, pack)
    assert "club-length" in [v.rule_id for v in result.blocking]


def test_streaming_edit_skips_mixable_edges(pack) -> None:
    sections = {"groove_a": 32, "break_1": 16, "drop_1": 32, "peak": 48}  # no intro/outro
    spec = _spec_with(duration_profile="streaming_edit", duration_bars=128, sections=sections)
    result = evaluate_gate(spec, pack)
    assert "unmixable-edges" not in [v.rule_id for v in result.blocking]


def test_unknown_duration_profile_raises(pack) -> None:
    spec = _spec_with(duration_profile="vinyl_edit")
    with pytest.raises(ValueError, match="unknown duration_profile"):
        evaluate_gate(spec, pack)
