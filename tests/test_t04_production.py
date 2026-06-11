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


def test_t04_production_rejects_t02_and_lead_bus(t04_assemble, production):
    dumped = t04_assemble.yaml.safe_dump(production)
    assert "T02" not in dumped
    assert all(
        not lane["stem"].startswith("lead")
        for lane in production["automation"]["lanes"].values()
    )


def test_t04_production_keeps_locked_voice_and_gate_clips(production):
    assert production["sources"]["voice"].endswith("latin-vocal-clean-take6-tailfix.wav")
    assert {placement["piece"] for placement in production["voice"]["placements"]} == {
        "tease",
        "chop",
        "fullverse",
        "hook1",
        "hook2",
    }
    assert len(production["auditions"]) >= 3
