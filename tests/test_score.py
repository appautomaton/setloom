# SPDX-License-Identifier: AGPL-3.0-only
"""Hermetic tests for the grammar scorer (change: generation-scoring-loop).

Synthetic rows and a synthetic pack only — no audio, no models, no repo
style.yml dependence.
"""

import subprocess
import sys

import yaml

from setloom.anatomy import score as sc
from setloom.stylepack import StylePack

RAW = {
    "id": "test-pack",
    "style_vector_defaults": {"vocal_presence": 1},
    "generation_defaults": {
        "bpm_range": [122, 124],
        "loudness_target_lufs": [-9.0, -8.0],
        "key_mode_bias": "minor",
        "club_edit_duration_minutes": [5.5, 8.5],
    },
    "groove": {"bass_step_occupancy_target": [0.75, 0.93]},
    "arrangement_tension": {"main_break_start_fraction": [0.42, 0.48]},
}
PACK = StylePack(
    id="test-pack",
    generation_defaults=RAW["generation_defaults"],
    rejection_rules=[],
    raw=RAW,
)
QUICK = {"key_estimate": "A# minor"}


def _row(**over):
    row = {
        "track": "t",
        "bpm": 123.0,
        "lufs": -8.5,
        "duration_s": 396.0,  # 6.6 min
        "bass_occupancy": 0.9,
        "main_break_start_frac": 0.45,
        "vocal_share": 0.1,
    }
    row.update(over)
    return row


def _by_metric(report):
    return {m.metric: m for m in report.metrics}


class TestScoreRow:
    def test_all_in_range(self):
        report = sc.score_row(_row(), QUICK, PACK)
        assert report.counts == {"in": 7, "out": 0, "missing": 0}
        assert all(m.distance in (0.0, None) for m in report.metrics)

    def test_out_of_range_signed_distance(self):
        report = sc.score_row(
            _row(bpm=120.0, lufs=-7.5, main_break_start_frac=0.3), QUICK, PACK
        )
        m = _by_metric(report)
        assert (m["bpm"].status, m["bpm"].distance) == ("out", -2.0)  # below lo
        assert (m["lufs"].status, m["lufs"].distance) == ("out", 0.5)  # above hi
        assert (m["main_break_start_frac"].status, m["main_break_start_frac"].distance) == (
            "out",
            -0.12,
        )

    def test_missing_measured_and_missing_target(self):
        report = sc.score_row(_row(main_break_start_frac=None), QUICK, PACK)
        assert _by_metric(report)["main_break_start_frac"].status == "missing"

        bare = StylePack(id="bare", generation_defaults={}, rejection_rules=[], raw={})
        report = sc.score_row(_row(), QUICK, bare)
        assert report.counts == {"in": 0, "out": 0, "missing": 7}  # never crashes

    def test_provenance_labels(self):
        provenance = {m.metric: m.provenance for m in sc.score_row(_row(), QUICK, PACK).metrics}
        assert provenance["bpm"] == "corpus"
        assert provenance["main_break_start_frac"] == "corpus"
        assert provenance["duration_minutes"] == "evidence"
        assert provenance["key_mode"] == "evidence"
        assert provenance["vocal_share"] == "assumption"

    def test_vocal_knob_converts_to_share_band(self):
        m = _by_metric(sc.score_row(_row(vocal_share=0.2), QUICK, PACK))["vocal_share"]
        assert m.target == [0.0, 0.15]  # knob 1 -> understated band
        assert (m.status, m.distance) == ("out", 0.05)

    def test_key_mode_match(self):
        m = _by_metric(sc.score_row(_row(), {"key_estimate": "A# major"}, PACK))["key_mode"]
        assert (m.status, m.measured, m.distance) == ("out", "major", None)

    def test_report_lines_end_with_listening_gate(self):
        lines = sc.report_lines(sc.score_row(_row(), QUICK, PACK))
        assert lines[-1].strip() == sc.LISTENING_GATE_LINE


def _cached_dossiers(tmp_path, track="t"):
    out_dir = tmp_path / "dossiers"
    out_dir.mkdir()
    quick = {
        "artist_dir": "art",
        "bpm_estimate": 123.0,
        "integrated_lufs": -8.5,
        "duration_s": 396.0,
        "key_estimate": "A# minor",
    }
    stems = {
        "track": track,
        "bars": 100,
        "drums": {"kick_gap_bars": ["44-52"], "kick_bars_present": 90},
        "bass": {
            "tonic_candidate": "A#",
            "pitch_class_share": {"A#": 0.7},
            "step_occupancy": 0.9,
            "note_len_16ths_median": 2.0,
        },
        "other": {"harmonic_changes_per_16bars": 2.0},
        "vocals": {"active_share": 0.1},
    }
    (out_dir / f"{track}.quick.yml").write_text(yaml.safe_dump(quick), encoding="utf-8")
    (out_dir / f"{track}.stems.yml").write_text(yaml.safe_dump(stems), encoding="utf-8")
    return out_dir


class TestScoreTrack:
    def test_writes_score_yaml_and_is_byte_stable(self, tmp_path):
        out_dir = _cached_dossiers(tmp_path)
        audio = tmp_path / "t.mp3"
        audio.touch()

        report, score_path = sc.score_track(audio, PACK, out_dir=out_dir)
        assert score_path.is_file()
        first = score_path.read_text(encoding="utf-8")
        data = yaml.safe_load(first)
        assert data["track"] == "t"
        assert data["counts"] == report.counts
        assert data["note"] == sc.LISTENING_GATE_LINE

        report2, _ = sc.score_track(audio, PACK, out_dir=out_dir)
        assert score_path.read_text(encoding="utf-8") == first
        assert report2.counts == report.counts
        # scored tracks never enter the corpus aggregate
        assert not (out_dir / "corpus-summary.yml").exists()


def test_score_import_is_torch_free():
    code = "import sys, setloom.anatomy.score; assert 'torch' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)
