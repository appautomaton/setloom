# SPDX-License-Identifier: AGPL-3.0-only
"""Spec 3 schema tests: T01 validates; broken fixtures fail naming the field."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from setloom import cli
from setloom.schema import TrackSpec, load_spec

REPO_ROOT = Path(__file__).resolve().parents[1]
T01 = Path(__file__).resolve().parent / "fixtures" / "spec-t01.yml"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_t01_validates() -> None:
    spec = load_spec(T01)
    assert spec.id == "T01"
    assert spec.bpm == 124
    assert sum(spec.sections.values()) == spec.duration_bars


def test_t01_cli_exit_zero(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    assert cli.main(["validate", str(T01)]) == 0
    assert "OK: T01" in capsys.readouterr().out


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


@pytest.mark.parametrize(
    ("fixture", "field"),
    [
        ("broken-missing-bpm.yml", "bpm"),
        ("broken-wrong-type.yml", "bpm"),
        ("broken-sections-mismatch.yml", "duration_bars"),
    ],
)
def test_broken_fixture_cli_exit_nonzero(
    fixture: str, field: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["validate", str(FIXTURES / fixture)]) == 1
    assert field in capsys.readouterr().err


# --- Duration profiles: T02 streaming edit (change 2026-06-07-duration-profiles) ---

T02 = Path(__file__).resolve().parent / "fixtures" / "spec-t02.yml"
T04 = REPO_ROOT / "music/tracks/T04/spec.yml"


def test_t02_validates_streaming_profile() -> None:
    spec = load_spec(T02)
    assert spec.duration_profile == "streaming_edit"
    assert sum(spec.sections.values()) == spec.duration_bars == 128


def test_default_profile_is_club_extended() -> None:
    assert load_spec(T01).duration_profile == "club_extended"


def test_t04_validates_with_track_groove_plan() -> None:
    spec = load_spec(T04)
    assert spec.groove is not None
    assert spec.groove.bass is not None
    assert spec.groove.bass.label == "t04-vocal-answer-roller"
    assert spec.groove.drums is not None
    assert spec.groove.drums.phrase_bars == 16


def test_track_bass_groove_rejects_beat_tick() -> None:
    raw = load_spec(T04).model_dump(mode="python")
    raw["groove"]["bass"]["bars"][0][0] = (4, 96, 1)
    with pytest.raises(ValidationError) as excinfo:
        TrackSpec.model_validate(raw)
    assert "beat tick reserved for kick space" in str(excinfo.value)


def test_track_percussion_groove_rejects_beat_tick() -> None:
    raw = load_spec(T04).model_dump(mode="python")
    raw["groove"]["drums"]["percussion_patterns"][0][0] = [3, 8]
    with pytest.raises(ValidationError) as excinfo:
        TrackSpec.model_validate(raw)
    assert "beat tick reserved for kick space" in str(excinfo.value)
