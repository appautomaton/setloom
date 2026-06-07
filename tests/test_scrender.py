# SPDX-License-Identifier: AGPL-3.0-only
"""Spec 5 vibe-slice tests: score export units always; NRT integration when sclang exists."""

from pathlib import Path

import pytest

from setloom.midi import NoteEvent
from setloom.schema import load_spec
from setloom.scrender import (
    build_scd,
    export_score,
    export_score_json,
    find_sclang,
    render_part_stem,
    ticks_to_seconds,
    vibe_events,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
T02 = REPO_ROOT / "examples" / "tracks" / "T02" / "spec.yml"


def test_ticks_to_seconds_at_124() -> None:
    assert ticks_to_seconds(480, 124.0) == pytest.approx(60 / 124)
    assert ticks_to_seconds(128 * 4 * 480, 124.0) == pytest.approx(247.742, abs=0.01)


def test_export_score_rows_and_determinism() -> None:
    events = [
        NoteEvent(1, 38, 96, 480, 210),
        NoteEvent(1, 38, 96, 0, 210),
    ]
    rows = export_score(events, 124.0)
    assert rows[0]["start"] == 0.0 and rows[1]["note"] == 38
    assert rows[1]["start"] == pytest.approx(60 / 124, abs=1e-6)
    assert rows[0]["amp"] == pytest.approx(96 / 127, abs=1e-4)
    assert export_score_json(events, 124.0) == export_score_json(list(events), 124.0)


def test_vibe_events_kick_only_and_deterministic() -> None:
    spec = load_spec(T02)
    events = vibe_events(spec, spec.seed, 1)
    assert set(events) == {"kick", "bass", "pad"}
    assert all(e.note == 36 for e in events["kick"]) and events["kick"]
    assert events == vibe_events(spec, spec.seed, 1)


def test_build_scd_contains_patch_and_score() -> None:
    spec = load_spec(T02)
    events = vibe_events(spec, spec.seed, 1)
    scd = build_scd("bass", export_score(events["bass"], spec.bpm), spec.bpm, 247.7, "/tmp/x.wav")
    assert "vibe_bass" in scd and "recordNRT" in scd and "patches.scd" in scd
    assert scd == build_scd(
        "bass", export_score(events["bass"], spec.bpm), spec.bpm, 247.7, "/tmp/x.wav"
    )


@pytest.mark.skipif(find_sclang() is None, reason="SuperCollider not installed")
def test_nrt_renders_kick_stem(tmp_path: Path) -> None:
    spec = load_spec(T02)
    events = vibe_events(spec, spec.seed, 1)
    out = tmp_path / "stem-kick.wav"
    # Render only the first two bars of kick events to keep the test fast.
    short = [e for e in events["kick"] if e.start_tick < 2 * 4 * 480]
    render_part_stem("kick", short, spec, out, find_sclang(), tmp_path)
    assert out.exists() and out.stat().st_size > 44100  # > ~0.5s of 16-bit stereo
