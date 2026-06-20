# SPDX-License-Identifier: AGPL-3.0-only
"""Production source paths, source loading, and shared timing constants."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SOURCE = HERE / "source"
OUT = HERE / "render"


def load_source_json(name: str) -> dict:
    return json.loads((SOURCE / name).read_text(encoding="utf-8"))


SCORE = load_source_json("score.json")
PLUCK_PATCH = load_source_json("pluck-synth.json")
MIX_PLAN = load_source_json("mix-plan.json")
KICK_SYNTH = load_source_json("kick-synth.json")

SCSYNTH = PLUCK_PATCH["scsynth_executable"]
STEINWAY = Path(MIX_PLAN["external_runtime_assets"]["steinway_sample_dir"])

SR = 44_100
BPM = 123.0
PPQ = 480
BEAT_S = 60.0 / BPM
BAR_S = 4.0 * BEAT_S
TOTAL_BARS = 120
TOTAL_N = int(round(TOTAL_BARS * BAR_S * SR))

NOTE = {
    "D3": 50,
    "E3": 52,
    "F#3": 54,
    "G3": 55,
    "A3": 57,
    "B3": 59,
    "C4": 60,
    "D4": 62,
    "E4": 64,
    "F#4": 66,
    "G4": 67,
    "A4": 69,
    "B4": 71,
    "C5": 72,
    "D5": 74,
    "E5": 76,
    "F#5": 78,
    "G5": 79,
    "A5": 81,
    "B5": 83,
    "C6": 84,
    "D6": 86,
    "E6": 88,
    "F#6": 90,
    "G6": 91,
    "A6": 93,
    "B6": 95,
}
