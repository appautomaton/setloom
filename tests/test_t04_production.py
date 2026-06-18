# SPDX-License-Identifier: AGPL-3.0-only
"""T04 production-manifest guardrails."""

from importlib import util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSEMBLE = REPO_ROOT / "music/tracks/T04/assemble.py"


@pytest.fixture(scope="module")
def t04_assemble():
    spec = util.spec_from_file_location("t04_assemble", ASSEMBLE)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def production(t04_assemble):
    return t04_assemble.load_production()


def test_t04_production_has_complete_section_progression(production):
    assert production["total_bars"] == 124
    sections = production["sections"]
    assert [section["name"] for section in sections] == [
        "intro",
        "groove_a",
        "break_1",
        "drop_1",
        "groove_b",
        "break_2",
        "peak",
        "outro",
    ]
    assert sections[0]["start_bar"] == 0
    assert sections[-1]["end_bar"] == production["total_bars"]
    assert sections[-1]["name"] == "outro"
    assert sections[-1]["end_bar"] - sections[-1]["start_bar"] == 4


def test_t04_production_rejects_t02_and_lead_bus(t04_assemble, production):
    dumped = t04_assemble.yaml.safe_dump(production)
    assert "T02" not in dumped
    assert all(
        not lane["stem"].startswith("lead")
        for lane in production["automation"]["lanes"].values()
    )


def test_t04_production_demotes_rejected_arp_and_lifts_bass(production):
    lanes = production["automation"]["lanes"]
    assert "arp" not in lanes
    assert "arp" not in production["automation"].get("duck_lanes", [])
    assert lanes["bass"]["gain"] >= 0.55
    assert lanes["bass"]["section_db"]["drop_1"] > 0
    assert lanes["chords"]["section_db"]["break_2"] > -6.0


def test_t04_production_supports_vocal_with_pads_not_leads(production):
    lanes = production["automation"]["lanes"]
    assert lanes["pad"]["section_db"]["break_2"] > -3.0
    assert lanes["pad"]["section_width"]["break_2"] >= 1.6
    main_break_pads = [
        pad for pad in production["genai_pads"]
        if pad["start_bar"] <= 72 and pad["end_bar"] >= 88
    ]
    assert main_break_pads
    assert main_break_pads[0]["gain"] >= 0.5
    assert main_break_pads[0]["highpass_hz"] >= 200
    assert all(pad["asset"] == "t04-pad-break" for pad in production["genai_pads"])
    assert all(not lane["stem"].startswith("lead") for lane in lanes.values())
    fullverse = next(
        placement for placement in production["voice"]["placements"]
        if placement["piece"] == "fullverse"
    )
    assert -3.5 <= fullverse["duck_db"] <= -2.5


def test_t04_phrase_moves_orchestrate_only_support_lanes(production):
    moves = production["automation"]["phrase_moves"]
    lanes = {move["lane"] for move in moves}
    assert "voice" not in lanes
    assert "lead" not in lanes
    assert {"perc", "chords", "pad", "fx", "genai_pad"} <= lanes

    drop_moves = [
        move for move in moves
        if 32.03 <= float(move["start_bar"]) and float(move["end_bar"]) <= 72.17
    ]
    peak_gap_moves = [
        move for move in moves
        if (
            89.06 <= float(move["start_bar"]) and float(move["end_bar"]) <= 95.42
        ) or (
            103.61 <= float(move["start_bar"]) and float(move["end_bar"]) <= 111.42
        )
    ]
    assert len(drop_moves) >= 12
    assert len(peak_gap_moves) >= 8

    protected = [
        (27.17, 32.03),
        (72.17, 89.06),
        (95.42, 103.61),
        (111.42, 119.61),
    ]
    for move in moves:
        start = float(move["start_bar"])
        end = float(move["end_bar"])
        assert all(end <= lo or start >= hi for lo, hi in protected), move


def test_t04_production_keeps_locked_voice_and_gate_clips(production):
    assert production["sources"]["voice"].endswith(
        "latin-vocal-clean-take6-tailfix-breathfix.wav"
    )
    repair = production["voice"]["source_repair"]
    assert repair["original"].endswith("latin-vocal-clean-take6-tailfix.wav")
    assert repair["derivative"] == production["sources"]["voice"]
    assert repair["method"] == "near-remove"
    assert repair["breath_windows_s"] == [
        {"start": 11.007, "end": 11.650, "maps_to": "fullverse preview 7.80-8.33s plus tail"},
        {"start": 18.747, "end": 19.500, "maps_to": "fullverse preview 15.54-16.10s plus tail"},
    ]
    assert {placement["piece"] for placement in production["voice"]["placements"]} == {
        "tease",
        "fullverse",
        "hook1",
        "hook2",
    }
    assert len(production["auditions"]) >= 3


def test_t04_assemble_runtime_output_root_override(t04_assemble, production, tmp_path):
    scratch = tmp_path / "scratch-render"
    variant = tmp_path / "variant-01"
    runtime = t04_assemble.with_runtime_overrides(
        production,
        output_root=scratch,
        variant_dir=variant,
    )
    assert runtime["sources"]["variant_dir"] == str(variant)
    assert runtime["render"]["mix_dir"] == str(scratch / "mix")
    assert runtime["render"]["audition_dir"] == str(scratch / "auditions")
    assert runtime["render"]["pieces_dir"] == str(scratch / "voice-pieces")
    assert t04_assemble.pieces_dir(runtime) == scratch / "voice-pieces"
