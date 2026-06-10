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

    def test_merge_rows_updates_in_place_and_appends(self):
        existing = [{"track": "a", "bpm": 120.0}, {"track": "b", "bpm": 121.0}]
        new = [{"track": "c", "bpm": 124.0}, {"track": "b", "bpm": 123.0}]
        merged = co.merge_rows(existing, new)
        assert [r["track"] for r in merged] == ["a", "b", "c"]  # subset never shrinks
        assert merged[1]["bpm"] == 123.0  # updated in place
        assert merged[0]["bpm"] == 120.0  # untouched row survives

    def test_merge_rows_identity_on_full_rerun(self):
        rows = [{"track": "a", "bpm": 120.0}, {"track": "b", "bpm": 121.0}]
        assert co.merge_rows(rows, [dict(r) for r in rows]) == rows
        assert co.merge_rows([], rows) == rows


class TestCli:
    def test_anatomize_registered(self):
        from setloom.cli import build_parser

        args = build_parser().parse_args(["anatomize", "somewhere", "--no-separate"])
        assert args.no_separate is True
        assert args.out == "anatomy/_dossiers"
        assert args.stems_dir == "anatomy/_stems"
        assert callable(args.func)


def _synthesize_stems(stem_dir, sr=22050, bpm=120.0, n_bars=8):
    """Hermetic 8-bar A-minor techno skeleton: no models, no real audio."""
    import soundfile as sf

    bar_dur = 4.0 * 60.0 / bpm
    total = int(n_bars * bar_dur * sr)
    t = np.arange(total) / sr

    drums = np.zeros(total)
    burst = np.sin(2 * np.pi * 60.0 * np.arange(int(0.08 * sr)) / sr)
    burst *= np.exp(-np.linspace(0, 6, len(burst)))
    for beat in range(n_bars * 4):
        start = int(beat * (bar_dur / 4) * sr)
        drums[start : start + len(burst)] += 0.9 * burst[: total - start]
    rng = np.random.default_rng(11)
    click = rng.standard_normal(int(0.02 * sr)) * 0.3
    for beat in range(n_bars * 4):
        start = int((beat + 0.5) * (bar_dur / 4) * sr)
        if start + len(click) < total:
            drums[start : start + len(click)] += click

    bass = 0.4 * np.sin(2 * np.pi * 110.0 * t)  # A2 pedal
    other = 0.2 * (
        np.sin(2 * np.pi * 220.0 * t)
        + np.sin(2 * np.pi * 261.63 * t)
        + np.sin(2 * np.pi * 329.63 * t)
    )  # A minor triad
    vocals = np.zeros(total)

    stem_dir.mkdir(parents=True, exist_ok=True)
    for name, y in [("drums", drums), ("bass", bass), ("other", other), ("vocals", vocals)]:
        sf.write(stem_dir / f"{name}.wav", y, sr)
    return drums + bass + other


class TestPipelineIntegration:
    def test_stem_pass_on_synthetic_stems(self, tmp_path):
        from setloom.anatomy import pipeline as pl

        stem_dir = tmp_path / "stems" / "synthetic"
        _synthesize_stems(stem_dir, sr=pl.SR)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        grid = pl.Grid(bpm=120.0, t0=0.0, n_bars=8)

        dossier = pl.stem_pass("synthetic", stem_dir, grid, out_dir)
        assert dossier["drums"]["kick_bars_present"] == 8
        assert dossier["drums"]["kick_gap_bars"] == []
        assert dossier["bass"]["tonic_candidate"] == "A"
        assert dossier["bass"]["step_occupancy"] > 0.8
        chords = [c for c in dossier["other"]["chords_per_2bars"] if c]
        assert chords and max(set(chords), key=chords.count) == "Am"
        assert dossier["vocals"]["active_bar_ranges"] == []
        assert (out_dir / "synthetic.bass.mid").is_file()

    def test_fullmix_pass_on_synthetic_mix(self, tmp_path):
        import soundfile as sf

        from setloom.anatomy import pipeline as pl

        mix = _synthesize_stems(tmp_path / "stems", sr=pl.SR)
        wav = tmp_path / "synthetic.wav"
        sf.write(wav, mix, pl.SR)

        dossier = pl.fullmix_pass(wav)
        assert 100.0 <= dossier["bpm_estimate"] <= 160.0
        assert dossier["bars_estimated"] >= 6
        assert dossier["sections"]
        assert isinstance(dossier["integrated_lufs"], float)
        assert dossier["key_estimate"].endswith("minor")


def _fake_cached_track(tmp_path, track="fake"):
    """A fully cached track: run() touches no audio, only YAML and wav existence."""
    import yaml

    audio = tmp_path / "art" / f"{track}.mp3"
    audio.parent.mkdir()
    audio.touch()
    out_dir = tmp_path / "dossiers"
    out_dir.mkdir()
    quick = {
        **_quick_fixture(),
        "first_beat_s": 0.0,
        "bars_estimated": 100,
        "tempo_suspect": False,
        "stem_model": "htdemucs",
    }
    (out_dir / f"{track}.quick.yml").write_text(yaml.safe_dump(quick), encoding="utf-8")
    stems = _stem_fixture(track, 100, ["40-49"], 0.9, 0.7)
    (out_dir / f"{track}.stems.yml").write_text(yaml.safe_dump(stems), encoding="utf-8")
    stems_dir = tmp_path / "stems"
    (stems_dir / track).mkdir(parents=True)
    for name in ("drums", "bass", "other", "vocals"):
        (stems_dir / track / f"{name}.wav").touch()
    return audio, out_dir, stems_dir


class TestSummaryMerge:
    def test_subset_run_merges_into_existing_summary(self, tmp_path):
        import yaml

        from setloom.anatomy import pipeline as pl

        audio, out_dir, stems_dir = _fake_cached_track(tmp_path)
        other_row = {"track": "other-track", "bpm": 121.0, "main_break_len_bars": 8}
        (out_dir / "corpus-summary.yml").write_text(
            yaml.safe_dump({"tracks": [other_row], "corpus": {}}), encoding="utf-8"
        )

        statuses = pl.run(audio, out_dir=out_dir, stems_dir=stems_dir, separate=False)
        assert statuses["corpus-summary"] == ["written"]
        summary = yaml.safe_load((out_dir / "corpus-summary.yml").read_text(encoding="utf-8"))
        assert [r["track"] for r in summary["tracks"]] == ["other-track", "fake"]
        assert summary["tracks"][0] == other_row  # subset run no longer shrinks the aggregate

    def test_summary_false_skips_summary_write(self, tmp_path):
        from setloom.anatomy import pipeline as pl

        audio, out_dir, stems_dir = _fake_cached_track(tmp_path)
        statuses = pl.run(
            audio, out_dir=out_dir, stems_dir=stems_dir, separate=False, summary=False
        )
        assert "corpus-summary" not in statuses
        assert not (out_dir / "corpus-summary.yml").exists()

    def test_collect_audio_skips_candidates_but_takes_file_target(self, tmp_path):
        from setloom.anatomy import pipeline as pl

        (tmp_path / "art").mkdir()
        (tmp_path / "art" / "a.mp3").touch()
        cand = tmp_path / "_candidates" / "c.wav"
        cand.parent.mkdir()
        cand.touch()
        assert [p.name for p in pl.collect_audio(tmp_path)] == ["a.mp3"]
        assert pl.collect_audio(cand) == [cand]


class TestAnalyzeVocalsSilenceFloor:
    """Separation bleed on vocal-free mixes must not self-normalize to 'active'."""

    def test_bleed_floor_scores_zero(self):
        from setloom.anatomy import pipeline as pl

        grid = pl.Grid(bpm=123.0, t0=0.0, n_bars=16)
        n = int(grid.n_bars * grid.bar_dur * pl.SR)
        rng = np.random.default_rng(7)
        bleed = rng.normal(0.0, 1.58e-3, n).astype(np.float32)  # ~-56 dBFS RMS
        res = pl._analyze_vocals(bleed, grid)
        assert res["active_share"] == 0.0
        assert res["active_bar_ranges"] == []

    def test_real_singing_still_counts(self):
        from setloom.anatomy import pipeline as pl

        grid = pl.Grid(bpm=123.0, t0=0.0, n_bars=16)
        n = int(grid.n_bars * grid.bar_dur * pl.SR)
        rng = np.random.default_rng(7)
        y = rng.normal(0.0, 1.58e-3, n).astype(np.float32)
        half = n // 2
        t = np.arange(half) / pl.SR
        y[:half] += (0.05 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)  # ~-29 dBFS
        res = pl._analyze_vocals(y, grid)
        assert 0.3 <= res["active_share"] <= 0.7
        assert res["active_bar_ranges"] != []


class TestCandidateSummaryExemption:
    def test_explicit_candidate_target_gets_dossier_but_no_summary_row(self, tmp_path):
        from setloom.anatomy import pipeline as pl

        audio, out_dir, stems_dir = _fake_cached_track(tmp_path)
        cand = tmp_path / "_candidates" / audio.name
        cand.parent.mkdir()
        audio.rename(cand)

        statuses = pl.run(cand, out_dir=out_dir, stems_dir=stems_dir, separate=False)
        assert "fake" in statuses
        assert "corpus-summary" not in statuses
        assert not (out_dir / "corpus-summary.yml").exists()
