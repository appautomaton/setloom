# SPDX-License-Identifier: AGPL-3.0-only
"""Unit tests for the pure anatomy analysis and corpus aggregation math."""

import numpy as np

from setloom.anatomy import analysis as an
from setloom.anatomy import corpus as co


class TestTempo:
    def test_fold_octave_up(self):
        assert an.fold_tempo(61.5) == 123.0

    def test_fold_octave_down(self):
        assert an.fold_tempo(246.0) == 123.0

    def test_in_band_unchanged(self):
        assert an.fold_tempo(123.0) == 123.0

    def test_metrical_level_error_is_suspect(self):
        # The Matemática case: 80.7 is a 3:2 metrical error for a true 123;
        # octave folding cannot rescue it, so it must read as suspect and
        # trigger the drum-stem re-anchor in the pipeline.
        assert an.tempo_suspect(80.7) is True

    def test_club_tempo_not_suspect(self):
        assert an.tempo_suspect(123.0) is False


class TestKey:
    def test_minor_profile_recovered(self):
        chroma = np.roll(an.KRUMHANSL_MINOR, 9)  # root on A
        key, conf = an.estimate_key(chroma)
        assert key == "A minor"
        assert conf > 0.99

    def test_major_profile_recovered(self):
        chroma = np.roll(an.KRUMHANSL_MAJOR, 7)  # root on G
        key, _ = an.estimate_key(chroma)
        assert key == "G major"


class TestBandEnergy:
    def test_band_attribution_per_bar(self):
        freqs = np.array([50.0, 1000.0, 8000.0])
        frame_times = np.array([0.5, 1.5, 2.5, 3.5])
        grid = np.array([0.0, 2.0, 4.0])  # two 2-second bars
        power = np.zeros((3, 4))
        power[0, :2] = 4.0  # low energy in bar 1 only
        power[1, 2:] = 4.0  # mid energy in bar 2 only
        bands = an.band_energy_per_bar(power, freqs, frame_times, grid)
        assert bands["low"][0] > 0.99 and bands["low"][1] < 0.01
        assert bands["mid"][1] > 0.99 and bands["mid"][0] < 0.01


class TestSections:
    def test_boundary_detected_at_change(self):
        feats = np.zeros((64, 2))
        feats[:32] = [1.0, 0.0]
        feats[32:] = [0.0, 1.0]
        assert an.section_boundaries(feats) == [32]

    def test_feature_matrix_shape(self):
        frame_times = np.linspace(0, 8, 80)
        grid = np.array([0.0, 2.0, 4.0, 6.0, 8.0])
        chroma = np.random.default_rng(7).random((12, 80))
        mfcc = np.random.default_rng(8).random((12, 80))
        feats = an.bar_feature_matrix(chroma, mfcc, frame_times, grid)
        assert feats.shape == (4, 24)

    def test_labels(self):
        assert an.label_section(0.9, 0.5, 0.2, 0, 5) == "intro"
        assert an.label_section(0.9, 0.5, 0.2, 4, 5) == "outro"
        assert an.label_section(0.04, 0.3, 0.1, 2, 5) == "break"
        assert an.label_section(0.80, 0.70, 0.4, 2, 5) == "peak"
        assert an.label_section(0.74, 0.53, 0.3, 2, 5) == "groove"


class TestKickMap:
    def test_events_per_bar_counts(self):
        bar_dur = 2.0
        times = [0.1, 0.6, 1.1, 1.6, 4.2, 4.7]  # 4 kicks bar 1, 2 kicks bar 3
        counts = an.events_per_bar(np.array(times), t0=0.0, bar_dur=bar_dur, n_bars=3)
        assert list(counts) == [4, 0, 2]

    def test_magma_shaped_gaps(self):
        present = np.ones(113, dtype=bool)
        for a, b in [(34, 42), (44, 45), (47, 53), (94, 95)]:
            present[a - 1 : b] = False
        present[59] = False  # single-bar dropout must be ignored
        assert an.presence_gaps(present) == [(34, 42), (44, 45), (47, 53), (94, 95)]

    def test_trailing_gap(self):
        present = np.array([True, True, False, False])
        assert an.presence_gaps(present) == [(3, 4)]


class TestBassNotes:
    def test_segmentation(self):
        steps = np.array([-1, 45, 45, 45, -1, -1, 47, 47])
        assert an.segment_notes(steps) == [(1, 3, 45), (6, 2, 47)]

    def test_stats(self):
        notes = [(1, 3, 45), (6, 2, 47)]
        stats = an.note_stats(notes, n_steps=8)
        assert stats["tonic_candidate"] == "A"
        assert stats["step_occupancy"] == 0.62
        assert stats["midi_range"] == [45, 47]
        assert stats["note_count"] == 2
        assert stats["share_one_step_notes"] == 0.0

    def test_empty(self):
        stats = an.note_stats([], n_steps=16)
        assert stats["tonic_candidate"] == "?"
        assert stats["midi_range"] is None


class TestTriads:
    def test_major(self):
        vec = np.zeros(12)
        vec[[0, 4, 7]] = 1.0
        assert an.match_triad(vec)[0] == "C"

    def test_minor(self):
        vec = np.zeros(12)
        vec[[9, 0, 4]] = 1.0
        assert an.match_triad(vec)[0] == "Am"


class TestActiveRanges:
    def test_threshold_and_min_len(self):
        per_bar = np.array([0.0, 0.0, 5.0, 5.0, 5.0, 0.0, 5.0, 0.0])
        assert an.active_ranges(per_bar) == [(3, 5)]


class TestUnicode:
    def test_nfd_equals_nfc_after_normalization(self):
        nfd = "Matématica"
        nfc = "Matématica"
        assert an.nfc(nfd) == an.nfc(nfc)


def _stem_fixture(track, n_bars, gaps, occupancy, tonic_share):
    return {
        "track": track,
        "bars": n_bars,
        "drums": {"kick_gap_bars": gaps, "kick_bars_present": n_bars - 20},
        "bass": {
            "tonic_candidate": "A#",
            "pitch_class_share": {"A#": tonic_share},
            "step_occupancy": occupancy,
            "note_len_16ths_median": 2.0,
        },
        "other": {"harmonic_changes_per_16bars": 2.0},
        "vocals": {"active_share": 0.1},
    }


def _quick_fixture():
    return {
        "artist_dir": "8kays",
        "bpm_estimate": 123.0,
        "integrated_lufs": -8.5,
        "duration_s": 220.0,
    }


class TestCorpus:
    def test_parse_span(self):
        assert co.parse_span("34-53") == (34, 53)

    def test_main_break_picks_longest(self):
        assert co.main_break([(34, 42), (47, 60), (94, 95)]) == (47, 60)
        assert co.main_break([]) is None

    def test_track_row(self):
        row = co.track_row(
            _quick_fixture(), _stem_fixture("t1", 100, ["34-42", "44-45"], 0.9, 0.72)
        )
        assert row["main_break_start_frac"] == 0.34
        assert row["main_break_len_bars"] == 9
        assert row["kick_coverage"] == 0.8
        assert row["tonic_share"] == 0.72

    def test_corpus_stats(self):
        rows = [
            co.track_row(_quick_fixture(), _stem_fixture("t1", 100, ["40-49"], 0.9, 0.7)),
            co.track_row(_quick_fixture(), _stem_fixture("t2", 200, ["80-99"], 0.8, 0.9)),
        ]
        stats = co.corpus_stats(rows)
        assert stats["tracks"] == 2
        assert stats["bpm_values"] == [123.0]
        assert stats["bass_occupancy_mean"] == 0.85
        assert stats["main_break_len_bars_values"] == [10, 20]
