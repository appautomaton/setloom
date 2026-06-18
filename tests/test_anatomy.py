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
        # octave folding cannot rescue it, so it must read as suspect.
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


def _quick_fixture():
    return {
        "artist_dir": "8kays",
        "bpm_estimate": 123.0,
        "integrated_lufs": -8.5,
        "duration_s": 220.0,
        "bars_estimated": 112,
    }


class TestCorpus:
    def test_quick_row_uses_current_fullmix_fields_only(self):
        row = co.quick_row("t1", _quick_fixture())
        assert row == {
            "track": "t1",
            "artist": "8kays",
            "bpm": 123.0,
            "lufs": -8.5,
            "bars": 112,
            "duration_s": 220.0,
        }
        assert "bass_occupancy" not in row
        assert "main_break_start_frac" not in row

    def test_corpus_stats(self):
        rows = [
            co.quick_row("t1", _quick_fixture()),
            co.quick_row(
                "t2",
                {
                    **_quick_fixture(),
                    "bpm_estimate": 124.0,
                    "integrated_lufs": -9.5,
                    "duration_s": 300.0,
                    "bars_estimated": 150,
                },
            ),
        ]
        stats = co.corpus_stats(rows)
        assert stats["tracks"] == 2
        assert stats["bpm_values"] == [123.0, 124.0]
        assert stats["lufs_mean"] == -9.0
        assert stats["lufs_range"] == [-9.5, -8.5]
        assert stats["duration_s_range"] == [220.0, 300.0]
        assert stats["bars_range"] == [112, 150]

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

        args = build_parser().parse_args(["anatomize", "somewhere"])
        assert args.out == "local/corpus/dossiers"
        assert args.layer_stems_dir == "local/corpus/stems53"
        assert args.models_dir == "models/roformer"
        assert callable(args.func)

    def test_anatomize_accepts_layer_scratch_dirs(self):
        from setloom.cli import build_parser

        args = build_parser().parse_args(
            [
                "anatomize",
                "somewhere",
                "--layers",
                "--out",
                "/tmp/dossiers",
                "--layer-stems-dir",
                "/tmp/stems53",
                "--models-dir",
                "/tmp/models",
            ]
        )
        assert args.layers is True
        assert args.out == "/tmp/dossiers"
        assert args.layer_stems_dir == "/tmp/stems53"
        assert args.models_dir == "/tmp/models"

def _synthesize_mix(sr=22050, bpm=120.0, n_bars=8):
    """Hermetic 8-bar A-minor techno skeleton: no models, no real audio."""
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
    return drums + bass + other


class TestPipelineIntegration:
    def test_fullmix_pass_on_synthetic_mix(self, tmp_path):
        import soundfile as sf

        from setloom.anatomy import pipeline as pl

        mix = _synthesize_mix(sr=pl.SR)
        wav = tmp_path / "synthetic.wav"
        sf.write(wav, mix, pl.SR)

        dossier = pl.fullmix_pass(wav)
        assert 100.0 <= dossier["bpm_estimate"] <= 160.0
        assert dossier["bars_estimated"] >= 6
        assert dossier["sections"]
        assert isinstance(dossier["integrated_lufs"], float)
        assert dossier["key_estimate"].endswith("minor")


class TestPipelineRun:
    def test_layers_run_reports_quick_and_layers_only(self, monkeypatch, tmp_path):
        from setloom.anatomy import pipeline as pl

        audio = tmp_path / "Radiance.mp3"
        audio.touch()
        out_dir = tmp_path / "dossiers"
        layer_stems_dir = tmp_path / "stems53"

        monkeypatch.setattr(
            pl,
            "fullmix_pass",
            lambda path: {
                **_quick_fixture(),
                "file": path.name,
                "first_beat_s": 0.0,
                "bars_estimated": 16,
                "tempo_suspect": False,
                "sections": [],
                "energy_curve_16bar": [],
            },
        )

        class FakeLayerLens:
            @staticmethod
            def layer_pass(audio_path, track, grid, out_dir, layer_stems_dir, models_dir):
                return ["layers:analyzed"]

        original_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "setloom.anatomy" and fromlist and "layers" in fromlist:
                return type("FakeAnatomy", (), {"layers": FakeLayerLens})()
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr("builtins.__import__", fake_import)

        statuses = pl.run(
            audio,
            out_dir=out_dir,
            layers=True,
            layer_stems_dir=layer_stems_dir,
        )

        assert statuses["Radiance"] == ["quick:analyzed", "layers:analyzed"]
        summary = out_dir / "corpus-summary.yml"
        assert summary.exists()

    def test_collect_audio_skips_candidates_but_takes_file_target(self, tmp_path):
        from setloom.anatomy import pipeline as pl

        (tmp_path / "art").mkdir()
        (tmp_path / "art" / "a.mp3").touch()
        cand = tmp_path / "_candidates" / "c.wav"
        cand.parent.mkdir()
        cand.touch()
        assert [p.name for p in pl.collect_audio(tmp_path)] == ["a.mp3"]
        assert pl.collect_audio(cand) == [cand]
