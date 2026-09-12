# SPDX-License-Identifier: AGPL-3.0-only
"""File-meter consistency and opt-in limiter timing, stereo and ceiling behavior."""

import shutil

import numpy as np
import pytest
import soundfile as sf
from scipy.signal import resample_poly

from setloom.audio import limit_peak_lookahead, measure_loudness

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is required")


def test_meter_reports_input_without_modifying_file(tmp_path):
    sr = 48000
    t = np.arange(sr * 2) / sr
    tone = 0.1 * np.sin(2 * np.pi * 1000 * t)
    path = tmp_path / "piano $literal name.wav"
    sf.write(path, np.column_stack((tone, tone)), sr, subtype="PCM_24")
    before = path.read_bytes()
    result = measure_loudness(path)
    assert result["integrated_lufs"] == pytest.approx(-20, abs=0.2)
    assert result["true_peak_dbtp"] == pytest.approx(-20, abs=0.1)
    assert result["loudness_range_lu"] == 0
    assert path.read_bytes() == before


def test_meter_handles_silence_as_missing_loudness_and_peak(tmp_path):
    path = tmp_path / "silence.wav"
    sf.write(path, np.zeros((48000, 2)), 48000)
    assert measure_loudness(path) == {
        "integrated_lufs": None,
        "true_peak_dbtp": None,
        "loudness_range_lu": 0,
    }


def test_meter_missing_input_is_clear(tmp_path):
    with pytest.raises(FileNotFoundError):
        measure_loudness(tmp_path / "missing.wav")


def test_lookahead_preserves_alignment_without_makeup_gain():
    sr = 44100
    y = np.zeros((sr, 2), np.float32)
    y[10000, :] = [0.1, -0.025]
    out = limit_peak_lookahead(y, ceiling_dbtp=-1)
    assert out.shape == y.shape
    assert abs(np.argmax(abs(out[:, 0])) - 10000) <= 1
    assert 0.07 < np.max(abs(out[:, 0])) <= 0.101
    np.testing.assert_allclose(out[:, 1], -0.25 * out[:, 0], atol=1e-7)


def test_lookahead_limits_transients_and_preserves_stereo_relation():
    sr = 44100
    t = np.arange(sr * 2) / sr
    mono = 0.12 * np.sin(2 * np.pi * 67 * t)
    mono[10000:10040] += 3
    mono[45000:45030] -= 3
    y = np.column_stack((mono, -0.4 * mono)).astype(np.float32)
    out = limit_peak_lookahead(y, ceiling_dbtp=-1)
    assert out.shape == y.shape
    assert np.isfinite(out).all()
    assert np.max(abs(resample_poly(out, 4, 1, axis=0))) <= 10 ** (-1 / 20) + 1e-6
    np.testing.assert_allclose(out[:, 1], -0.4 * out[:, 0], atol=1e-6)
    # The second half has no overload; it should retain the quiet bass body.
    np.testing.assert_allclose(out[70000:75000], y[70000:75000], atol=3e-4)


@pytest.mark.parametrize("frames", [0, 32, 4410])
def test_lookahead_short_and_empty_mono_inputs(frames):
    y = np.full((frames, 1), 0.01, np.float32)
    out = limit_peak_lookahead(y)
    assert out.shape == y.shape
    assert np.isfinite(out).all()
    if frames:
        assert np.max(abs(out)) > 0.005


@pytest.mark.parametrize("drive,target,expected", [(10, -10, True), (0, -10, False)])
def test_write_master_checks_the_actual_output_without_chasing_target(
    tmp_path, drive, target, expected
):
    from setloom.audio import write_master

    sr = 48000
    tone = 0.1 * np.sin(2 * np.pi * 1000 * np.arange(sr * 2) / sr)
    audio = np.column_stack((tone, tone)).astype(np.float32)
    before = audio.copy()
    path = tmp_path / "master.wav"
    report = write_master(
        path,
        audio,
        sample_rate=sr,
        target_lufs=target,
        input_gain_db=drive,
        ceiling_dbtp=-1,
        lookahead_ms=3,
        release_ms=60,
    )
    assert report["within_target_tolerance"] is expected
    assert report["within_peak_ceiling"]
    assert report["measured"]["integrated_lufs"] == pytest.approx(-20 + drive, abs=0.2)
    assert sf.info(path).subtype == "PCM_24"
    np.testing.assert_array_equal(audio, before)
