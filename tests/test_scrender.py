# SPDX-License-Identifier: AGPL-3.0-only
"""Spec 5 vibe-slice tests: score export units always; NRT integration when sclang exists."""

import json
from pathlib import Path

import pytest

from setloom.midi import PPQ, NoteEvent
from setloom.schema import load_spec
from setloom.scrender import (
    LEAD_ATMOSPHERES,
    LEAD_EFFECTS,
    LEAD_EXPRESSION_KEYS,
    LEAD_FAMILY_STEMS,
    LEAD_LAYERS,
    LOUDNESS_TARGET_LUFS,
    MASTER_CHAIN,
    MIX_GAINS,
    PATCHES,
    PEAK_TARGET_DBFS,
    build_scd,
    export_score,
    export_score_json,
    find_sclang,
    lead_bus_report,
    lead_atmos_score,
    lead_coherence_report,
    lead_effect_score,
    lead_family_score_groups,
    lead_layer_score,
    lead_layer_score_json,
    loudness_proof_command,
    peak_proof_command,
    render_part_stem,
    score_for_part,
    section_windows,
    ticks_to_seconds,
    vibe_events,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
T02 = Path(__file__).resolve().parent / "fixtures" / "spec-t02.yml"


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
    assert 'oscFilePath: "/tmp/x.wav.osc"' in scd
    assert 'File.delete("/tmp/x.wav.osc")' in scd
    assert scd == build_scd(
        "bass", export_score(events["bass"], spec.bpm), spec.bpm, 247.7, "/tmp/x.wav"
    )


def test_lead_layers_define_required_roles() -> None:
    layers = {layer.name: layer for layer in LEAD_LAYERS}
    assert set(layers) == {"lead_body", "lead_edge", "lead_air", "lead_shadow"}
    for layer in layers.values():
        assert layer.synth.startswith("vibe_lead_")
        assert layer.family in LEAD_FAMILY_STEMS
        assert layer.role and layer.spectral_range and layer.phase_rule
        assert layer.arrangement_role and layer.rationale
    assert {layer.family for layer in layers.values()} == {"main", "atmos"}


def test_lead_effects_define_required_roles() -> None:
    effects = {effect.name: effect for effect in LEAD_EFFECTS}
    assert set(effects) == {"lead_fx_tease", "lead_fx_throw", "lead_fx_whoop"}
    for effect in effects.values():
        assert effect.synth.startswith("vibe_lead_fx_")
        assert effect.family == "fx"
        assert effect.role and effect.spectral_range and effect.phase_rule
        assert effect.arrangement_role and effect.rationale


def test_lead_atmospheres_define_required_roles() -> None:
    atmospheres = {atmosphere.name: atmosphere for atmosphere in LEAD_ATMOSPHERES}
    assert set(atmospheres) == {"lead_atmos_bloom", "lead_atmos_pulse"}
    for atmosphere in atmospheres.values():
        assert atmosphere.synth.startswith("vibe_lead_atmos_")
        assert atmosphere.family == "atmos"
        assert atmosphere.role and atmosphere.spectral_range and atmosphere.phase_rule
        assert atmosphere.arrangement_role and atmosphere.rationale


def test_lead_layer_synthdefs_document_modern_roles() -> None:
    text = PATCHES.read_text(encoding="utf-8")
    for layer in LEAD_LAYERS:
        assert f"SynthDef(\\{layer.synth}" in text
    for effect in LEAD_EFFECTS:
        assert f"SynthDef(\\{effect.synth}" in text
    for atmosphere in LEAD_ATMOSPHERES:
        assert f"SynthDef(\\{atmosphere.synth}" in text
    for phrase in (
        "Lead-family bus",
        "dark rave function, not MIDI-note patches",
        "Anti-EDM safeguards",
        "no static single saw/pulse disco lead",
        "no bright",
        "no dry MIDI-note playback",
        "no equal-status octave/unison doubling",
        "Spectral allocation",
        "atmosphere-family",
        "row-level cutoff",
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
    assert {"main", "atmos"} <= {row["family"] for row in rows}
    assert all(key in rows[0] for key in LEAD_EXPRESSION_KEYS)
    break_body = [row["amp"] for row in rows if row["layer"] == "lead_body" and row["section"] == "break"]
    peak_body = [row["amp"] for row in rows if row["layer"] == "lead_body" and row["section"] == "peak"]
    assert max(break_body) > max(peak_body)
    assert any(row["note"] < 72 for row in rows if row["layer"] == "lead_shadow")
    assert len({row["cutoff"] for row in rows if row["layer"] == "lead_body"}) > 2
    assert len({row["motion"] for row in rows if row["section"] == "peak"}) > 2
    assert lead_layer_score_json(lead, spec) == lead_layer_score_json(list(reversed(lead)), spec)


def test_t02_entry_profile_and_effect_source_arrive_early() -> None:
    spec = load_spec(T02)
    assert sum(spec.sections.values()) == 128
    assert spec.sections["intro"] == 8
    assert spec.sections["groove_a"] == 8

    effects = lead_effect_score(spec)
    assert effects
    assert min(row["start"] for row in effects) <= 15.5
    assert any(row["start"] < 69.68 for row in effects)
    assert {row["source"] for row in effects} == {"effect"}
    assert {row["family"] for row in effects} == {"fx"}
    by_section = {}
    for row in effects:
        by_section.setdefault(row["section"], set()).add(row["effect"])
    assert by_section["break"] != by_section["drop"]
    assert by_section["drop"] != by_section["peak"]


def test_lead_atmosphere_source_supports_family_motion() -> None:
    spec = load_spec(T02)
    atmos = lead_atmos_score(spec)
    assert atmos
    assert {row["source"] for row in atmos} == {"atmos"}
    assert {row["family"] for row in atmos} == {"atmos"}
    assert {row["atmos"] for row in atmos} == {"lead_atmos_bloom", "lead_atmos_pulse"}
    assert min(row["start"] for row in atmos) < 16.0
    assert {"intro", "groove_a", "break", "drop", "peak"} <= {row["section"] for row in atmos}
    assert len({row["motion"] for row in atmos}) > 3


def test_lead_bus_score_covers_section_roles() -> None:
    spec = load_spec(T02)
    starts = {kind: start for start, _end, kind in section_windows(spec)}

    def section_burst(kind: str) -> list[NoteEvent]:
        return [NoteEvent(1, 72, 100, starts[kind] + PPQ + i * 120, PPQ) for i in range(6)]

    events = (
        section_burst("intro")
        + section_burst("break")
        + section_burst("drop")
        + section_burst("peak")
        + section_burst("outro")
    )
    rows = score_for_part("lead", events, spec)
    groups = lead_family_score_groups(rows)
    assert set(groups) == {"main", "fx", "atmos"}
    assert all(groups[family] for family in groups)
    by_section = {}
    melodic_rows = [row for row in rows if row["source"] == "melodic"]
    for row in melodic_rows:
        by_section.setdefault(row["section"], set()).add(row["layer"])
    assert "intro" not in by_section  # intro identity now comes from effect source
    assert "outro" not in by_section
    assert by_section["break"] == {"lead_body", "lead_edge", "lead_air", "lead_shadow"}
    assert by_section["drop"] == {"lead_body", "lead_edge"}
    assert by_section["peak"] == {"lead_body", "lead_edge", "lead_air", "lead_shadow"}

    effect_rows = [row for row in rows if row["source"] == "effect"]
    assert min(row["start"] for row in effect_rows) <= 15.5
    assert {"intro", "groove_a", "break", "drop", "peak"} <= {
        row["section"] for row in effect_rows
    }
    atmos_rows = [row for row in rows if row["source"] == "atmos"]
    assert atmos_rows
    assert min(row["start"] for row in atmos_rows) < min(row["start"] for row in melodic_rows)
    assert {"main", "fx", "atmos"} == {row["family"] for row in rows}
    assert len({row["accent"] for row in rows}) > 4


def test_build_scd_uses_layered_lead_score_and_report() -> None:
    spec = load_spec(T02)
    starts = {kind: start for start, _end, kind in section_windows(spec)}
    lead = [
        NoteEvent(1, 72, 100, starts["break"] + PPQ, PPQ),
        NoteEvent(1, 72, 100, starts["drop"] + PPQ, PPQ),
        NoteEvent(1, 72, 100, starts["peak"] + PPQ, PPQ),
    ]
    score = score_for_part("lead", lead, spec)
    scd = build_scd("lead", score, spec.bpm, 247.7, "/tmp/lead.wav")
    for layer in LEAD_LAYERS:
        assert f"'{layer.synth}'" in scd
    for effect in LEAD_EFFECTS:
        assert f"'{effect.synth}'" in scd
    for atmosphere in LEAD_ATMOSPHERES:
        assert f"'{atmosphere.synth}'" in scd
    assert "'cutoff', n[5]" in scd
    assert "'drive', n[6]" in scd
    assert "'accent', n[11]" in scd
    assert "'vibe_lead'" not in scd
    assert scd == build_scd("lead", list(score), spec.bpm, 247.7, "/tmp/lead.wav")

    report = lead_bus_report(score)
    assert {layer["name"] for layer in report["layers"]} == {
        "lead_body",
        "lead_edge",
        "lead_air",
        "lead_shadow",
    }
    assert {"break", "drop", "peak"} <= set(report["sections"])
    assert report["sources"]["counts"]["melodic"] > 0
    assert report["sources"]["counts"]["effect"] > 0
    assert report["sources"]["counts"]["atmos"] > 0
    assert report["sources"]["first_event_seconds"]["effect"] <= 15.5
    assert set(report["families"]["counts"]) == {"main", "fx", "atmos"}
    assert all(report["families"]["counts"][family] > 0 for family in LEAD_FAMILY_STEMS)
    assert set(report["families"]["stems"]) == {"main", "fx", "atmos"}
    assert report["expression"]["cutoff"]["distinct"] > 4
    assert report["expression"]["motion"]["distinct"] > 4
    assert {effect["name"] for effect in report["effects"]} == {
        "lead_fx_tease",
        "lead_fx_throw",
        "lead_fx_whoop",
    }
    assert {atmosphere["name"] for atmosphere in report["atmospheres"]} == {
        "lead_atmos_bloom",
        "lead_atmos_pulse",
    }
    assert set(report["coherence"]) == {"pad", "arp", "chords", "perc"}


def test_lead_coherence_report_names_neighboring_parts() -> None:
    report = lead_coherence_report()
    assert set(report) == {"pad", "arp", "chords", "perc"}
    for rules in report.values():
        assert set(rules) == {"shares", "avoids", "rule"}
        assert all(rules.values())


def test_master_loudness_contract_is_inspectable() -> None:
    assert LOUDNESS_TARGET_LUFS == (-9.0, -8.0)
    assert PEAK_TARGET_DBFS == -1.0
    assert MASTER_CHAIN.count("gain") >= 2
    makeup_gain = float(MASTER_CHAIN[MASTER_CHAIN.index("gain") + 1])
    assert makeup_gain >= 13.0
    assert MIX_GAINS["lead"] == pytest.approx(0.40)

    wav = Path("/tmp/candidate.wav")
    assert loudness_proof_command(wav) == [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        "/tmp/candidate.wav",
        "-filter_complex",
        "ebur128",
        "-f",
        "null",
        "-",
    ]
    assert peak_proof_command(wav) == ["sox", "/tmp/candidate.wav", "-n", "stat"]


@pytest.mark.skipif(find_sclang() is None, reason="SuperCollider not installed")
def test_nrt_renders_kick_stem(tmp_path: Path) -> None:
    spec = load_spec(T02)
    events = vibe_events(spec, spec.seed, 1)
    out = tmp_path / "stem-kick.wav"
    # Render only the first two bars of kick events to keep the test fast.
    short = [e for e in events["kick"] if e.start_tick < 2 * 4 * 480]
    render_part_stem("kick", short, spec, out, find_sclang(), tmp_path)
    assert out.exists() and out.stat().st_size > 44100  # > ~0.5s of 16-bit stereo


@pytest.mark.skipif(find_sclang() is None, reason="SuperCollider not installed")
def test_nrt_renders_short_lead_bus_stem(tmp_path: Path) -> None:
    spec = load_spec(T02)
    starts = {kind: start for start, _end, kind in section_windows(spec)}
    out = tmp_path / "stem-lead.wav"
    events = [NoteEvent(1, 72, 100, starts["break"] + PPQ, PPQ)]
    render_part_stem("lead", events, spec, out, find_sclang(), tmp_path)
    report = json.loads((tmp_path / "lead-bus-report.json").read_text(encoding="utf-8"))
    assert out.exists() and out.stat().st_size > 44100
    for stem in LEAD_FAMILY_STEMS.values():
        assert (tmp_path / stem).exists()
        assert (tmp_path / stem).stat().st_size > 44100
    assert {layer["name"] for layer in report["layers"]} == {
        "lead_body",
        "lead_edge",
        "lead_air",
        "lead_shadow",
    }
    assert report["sections"]["break"] >= 4
    assert report["sources"]["counts"]["melodic"] == 4
    assert report["sources"]["counts"]["effect"] > 0
