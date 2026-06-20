# SPDX-License-Identifier: AGPL-3.0-only
"""Track spec loader tests for scaffold and legacy track source."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from setloom.schema import load_spec

T01 = Path(__file__).resolve().parent / "fixtures" / "spec-t01.yml"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_t01_loads() -> None:
    spec = load_spec(T01)
    assert spec.id == "T01"
    assert spec.bpm == 124
    assert sum(spec.sections.values()) == spec.duration_bars


@pytest.mark.parametrize(
    ("fixture", "field"),
    [
        ("broken-missing-bpm.yml", "bpm"),
        ("broken-wrong-type.yml", "bpm"),
        ("broken-sections-mismatch.yml", "duration_bars"),
    ],
)
def test_broken_fixture_fails_naming_field(fixture: str, field: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        load_spec(FIXTURES / fixture)
    assert field in str(excinfo.value)


# --- Duration profiles: T02 streaming edit (change 2026-06-07-duration-profiles) ---

T02 = Path(__file__).resolve().parent / "fixtures" / "spec-t02.yml"


def test_t02_loads_streaming_profile() -> None:
    spec = load_spec(T02)
    assert spec.duration_profile == "streaming_edit"
    assert sum(spec.sections.values()) == spec.duration_bars == 128


def test_default_profile_is_club_extended() -> None:
    assert load_spec(T01).duration_profile == "club_extended"
