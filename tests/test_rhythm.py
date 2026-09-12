# SPDX-License-Identifier: AGPL-3.0-only

import json

import numpy as np
import pytest
import soundfile as sf

from setloom.cli import main
from setloom.rhythm import FrequencyBand, analyze_rhythm, grid_positions

BAND = (FrequencyBand("test", 250, 1800),)


def test_grid_preserves_absolute_phase_and_offgrid_peaks(tmp_path):
    sr = 8000
    time = np.arange(sr) / sr
    audio = np.zeros(sr)
    # One attack deliberately falls between grid positions.
    attacks = [0.234, 0.334, 0.481]
    for when in attacks:
        local = time - when
        audio += np.where(local >= 0, np.exp(-np.maximum(local, 0) / 0.008), 0) * (
            0.2 * np.sin(2 * np.pi * 700 * time)
        )
    path = tmp_path / "offgrid.wav"
    sf.write(path, audio, sr, subtype="FLOAT")
    report = analyze_rhythm(path, start=0.15, end=0.8, bpm=150,
                            grid_origin=0.234, bands=BAND)
    data = report["bands"][0]
    peaks = np.array([p["peak_seconds"] for p in data["landmarks"]])
    for when in attacks:
        assert np.min(abs(peaks - when)) < 0.012
    grid = data["grid_measurements"]
    assert grid[0]["grid_seconds"] == pytest.approx(0.234)
    assert grid[0]["grid_index"] == 0
    assert any(abs(p - 0.481) < 0.012 for p in peaks)
    assert all(abs(g["grid_seconds"] - 0.481) > 0.04 for g in grid)
    assert report["grid"]["provenance"].startswith("caller-supplied")


def test_rms_calibration_and_antiphase_stereo_do_not_cancel(tmp_path):
    sr = 8000
    tone = 0.1 * np.sin(2 * np.pi * 700 * np.arange(sr) / sr)
    paths = [tmp_path / "mono.wav", tmp_path / "antiphase.wav"]
    sf.write(paths[0], tone, sr, subtype="FLOAT")
    sf.write(paths[1], np.column_stack([tone, -tone]), sr, subtype="FLOAT")
    results = [analyze_rhythm(p, start=0.5, end=0.8, bands=BAND) for p in paths]
    levels = [r["bands"][0]["rms_dbfs"] for r in results]
    assert levels[0] == pytest.approx(-23.0103, abs=0.08)
    assert levels[1] == pytest.approx(levels[0], abs=1e-9)
    assert all(r["grid"] is None for r in results)


def test_complete_window_measurements_distinguish_short_attack_from_long_tail(tmp_path):
    sr = 8000
    time = np.arange(sr) / sr
    audio = np.zeros(sr)
    for onset, decay in ((0.2, 0.01), (0.6, 0.1)):
        local = time - onset
        audio += np.where(local >= 0, np.exp(-np.maximum(local, 0) / decay), 0) * (
            0.2 * np.sin(2 * np.pi * 700 * time)
        )
    path = tmp_path / "tails.wav"
    sf.write(path, audio, sr, subtype="FLOAT")
    report = analyze_rhythm(path, bpm=150, grid_origin=0.2, bands=BAND)
    events = report["bands"][0]["grid_measurements"]
    short = min(events, key=lambda e: abs(e["grid_seconds"] - 0.2))
    long = min(events, key=lambda e: abs(e["grid_seconds"] - 0.6))
    assert short["attack_vs_pre_db"] > 40
    assert long["tail_vs_attack_db"] > short["tail_vs_attack_db"] + 15


def test_silence_and_edge_windows_have_no_fabricated_peak_or_nan(tmp_path):
    path = tmp_path / "silence.wav"
    sf.write(path, np.zeros((800, 2)), 8000)
    report = analyze_rhythm(path, bpm=150, bands=BAND)
    data = report["bands"][0]
    assert not data["landmarks"]
    event = data["grid_measurements"][0]
    assert event["pre_rms_dbfs"] is None
    assert event["attack_vs_pre_db"] is None
    assert event["attack_rms_dbfs"] == -200
    assert event["local_peak_seconds"] is None
    tiny = analyze_rhythm(path, end=0.002, bpm=150, bands=BAND)
    assert tiny["bands"][0]["grid_measurements"][0]["attack_rms_dbfs"] is None
    json.dumps([report, tiny], allow_nan=False)


def test_closeup_reads_bounded_context_and_keeps_file_time_grid(tmp_path, monkeypatch):
    sr = 8000
    path = tmp_path / "long.wav"
    time = np.arange(sr * 3) / sr
    sf.write(path, 0.1 * np.sin(2 * np.pi * 700 * time), sr, subtype="FLOAT")
    original = sf.read
    reads = []

    def read(path, **kwargs):
        reads.append((kwargs["start"], kwargs["stop"]))
        return original(path, **kwargs)

    monkeypatch.setattr(sf, "read", read)
    close = analyze_rhythm(path, start=1.001, end=1.1, bands=BAND)
    assert len(reads) == 1
    lo, hi = reads[0]
    assert 0 < lo < round(1.001 * sr) < round(1.1 * sr) < hi < 2 * sr
    assert hi - lo < sr // 2
    source = close["source"]
    assert source["analysis_frames"] == [8008, 8800]
    assert source["read_frames"] == [lo, hi]
    assert len(source["decoded_read_sha256"]) == 64
    full = analyze_rhythm(path, bands=BAND)
    close_env = close["bands"][0]["envelope"]
    full_env = full["bands"][0]["envelope"]
    times = np.array(full_env["seconds"])
    mask = (times >= close_env["seconds"][0]) & (times <= close_env["seconds"][-1])
    np.testing.assert_allclose(np.array(full_env["rms_dbfs"])[mask],
                               close_env["rms_dbfs"], atol=1e-6)


@pytest.mark.parametrize("options", [
    {"bands": (FrequencyBand("bad", 800, 4000),)},
    {"envelope_ms": 0}, {"bpm": float("nan")}, {"start": -1},
    {"subdivisions": 0}, {"end": 0.00001},
])
def test_invalid_options_fail_before_pcm_read(tmp_path, monkeypatch, options):
    path = tmp_path / "valid.wav"
    sf.write(path, np.zeros(8000), 8000)

    def unexpected(*args, **kwargs):
        pytest.fail("invalid analysis should not read PCM")

    monkeypatch.setattr(sf, "read", unexpected)
    with pytest.raises(ValueError):
        analyze_rhythm(path, **options)


def test_grid_crop_keeps_global_indices_and_negative_origin():
    indices, times = grid_positions(1.03, 1.4, 150, origin=-0.066, subdivisions=4)
    np.testing.assert_array_equal(indices, [11, 12, 13, 14])
    np.testing.assert_allclose(times, [1.034, 1.134, 1.234, 1.334])


@pytest.mark.parametrize("layout", ["overlay", "stack"])
def test_cli_rhythm_writes_labelled_comparison_and_finite_json(tmp_path, layout):
    path = tmp_path / "reference.wav"
    sf.write(path, np.zeros((2400, 2)), 8000)
    out = tmp_path / "plots" / "rhythm.png"
    report_path = tmp_path / "reports" / "evidence.json"
    assert main([
        "inspect", str(path), "--compare", str(path), "--view", "rhythm",
        "--compare-label-a", "Original", "--compare-label-b", "Rebuilt",
        "--compare-layout", layout, "--band", "mid:250:1800", "--bpm", "150",
        "--grid-origin", "0.034", "--grid", "subdivisions",
        "--out", str(out), "--report", str(report_path),
    ]) == 0
    report = json.loads(report_path.read_text())
    assert [s["label"] for s in report["sources"]] == [
        "Original: reference.wav", "Rebuilt: reference.wav",
    ]
    assert report["sources"][0]["evidence"]["grid"]["origin_seconds"] == 0.034
    assert out.stat().st_size > 0
