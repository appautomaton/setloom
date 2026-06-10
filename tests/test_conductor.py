# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path

from setloom.conductor import build_conductor
from setloom.schema import load_spec

REPO_ROOT = Path(__file__).resolve().parents[1]
T02 = REPO_ROOT / "examples" / "tracks" / "T02" / "spec.yml"


def test_conductor_exposes_shared_phrase_and_harmony_clock() -> None:
    spec = load_spec(T02)
    conductor = build_conductor(spec)

    assert len(conductor.progression) == 4
    assert len(set(conductor.progression)) >= 3
    assert conductor.harmonic_events

    point = conductor.phrase_point(16)
    assert point.section == "break_1"
    assert point.section_kind == "break"
    assert point.is_8bar_boundary
    assert point.is_16bar_boundary
    assert point.chord == conductor.chord_at_bar(16)


def test_conductor_energy_tracks_section_function() -> None:
    spec = load_spec(T02)
    conductor = build_conductor(spec)

    intro = conductor.energy_at_bar(0)
    drop = conductor.energy_at_bar(32)
    peak = conductor.energy_at_bar(72)

    assert intro < drop < peak
    assert conductor.foreground_owner("break") == "lead"
    assert conductor.foreground_owner("drop") == "groove"
