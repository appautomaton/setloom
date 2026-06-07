# SPDX-License-Identifier: AGPL-3.0-only
"""Spec 5 vibe-slice tests: score export units always; NRT integration when sclang exists."""

from pathlib import Path

import pytest

from setloom.midi import NoteEvent
from setloom.schema import load_spec
from setloom.scrender import (
    LEAD_LAYERS,
    PATCHES,
    build_scd,
    export_score,
    export_score_json,
    find_sclang,
    lead_coherence_report,
    lead_layer_score,
    lead_layer_score_json,
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
    assert set(events) == {"kick", "bass", "pad", "chords", "arp", "lead", "fx", "perc"}
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


def test_lead_layers_define_required_roles() -> None:
    layers = {layer.name: layer for layer in LEAD_LAYERS}
    assert set(layers) == {"lead_body", "lead_edge", "lead_air", "lead_shadow"}
    for layer in layers.values():
        assert layer.synth.startswith("vibe_lead_")
        assert layer.role and layer.spectral_range and layer.phase_rule
        assert layer.arrangement_role and layer.rationale


def test_lead_layer_synthdefs_document_modern_roles() -> None:
    text = PATCHES.read_text(encoding="utf-8")
    for layer in LEAD_LAYERS:
        assert f"SynthDef(\\{layer.synth}" in text
    for phrase in (
        "role-separated layers",
        "no static single saw/pulse disco lead",
        "no bright",
        "no equal-status octave/unison doubling",
        "Spectral allocation",
        "Stereo/phase",
        "Psychoacoustic role",
        "Temporal rule",
    ):
        assert phrase in text


def test_lead_layer_score_is_section_aware_and_deterministic() -> None:
    spec = load_spec(T02)
    lead = vibe_events(spec, spec.seed, 1)["lead"]
    rows = lead_layer_score(lead, spec)
    assert {row["layer"] for row in rows} == {
        "lead_body",
        "lead_edge",
        "lead_air",
        "lead_shadow",
    }
    assert {"break", "peak"} <= {row["section"] for row in rows}
    break_body = [row["amp"] for row in rows if row["layer"] == "lead_body" and row["section"] == "break"]
    peak_body = [row["amp"] for row in rows if row["layer"] == "lead_body" and row["section"] == "peak"]
    assert max(break_body) > max(peak_body)
    assert any(row["note"] < 72 for row in rows if row["layer"] == "lead_shadow")
    assert lead_layer_score_json(lead, spec) == lead_layer_score_json(list(reversed(lead)), spec)


def test_lead_coherence_report_names_neighboring_parts() -> None:
    report = lead_coherence_report()
    assert set(report) == {"pad", "arp", "chords", "perc"}
    for rules in report.values():
        assert set(rules) == {"shares", "avoids", "rule"}
        assert all(rules.values())


@pytest.mark.skipif(find_sclang() is None, reason="SuperCollider not installed")
def test_nrt_renders_kick_stem(tmp_path: Path) -> None:
    spec = load_spec(T02)
    events = vibe_events(spec, spec.seed, 1)
    out = tmp_path / "stem-kick.wav"
    # Render only the first two bars of kick events to keep the test fast.
    short = [e for e in events["kick"] if e.start_tick < 2 * 4 * 480]
    render_part_stem("kick", short, spec, out, find_sclang(), tmp_path)
    assert out.exists() and out.stat().st_size > 44100  # > ~0.5s of 16-bit stereo
