# SPDX-License-Identifier: AGPL-3.0-only

import numpy as np
from scipy.signal import resample_poly

from setloom.audio import (
    beat_pump_envelope,
    integrated_lufs,
    limit_peak,
    master,
    mono_below,
    ms_width,
    normalize_peak,
    peak_dbfs,
)


def test_ms_width_preserves_shape_and_mono_mid() -> None:
    audio = np.column_stack([np.linspace(-0.5, 0.5, 128), np.linspace(-0.5, 0.5, 128)]).astype(
        np.float32
    )

    widened = ms_width(audio, 1.8)

    assert widened.shape == audio.shape
    np.testing.assert_allclose(widened, audio, atol=1e-6)


def test_pump_envelope_starts_below_unity() -> None:
    envelope = beat_pump_envelope(44_100, bpm=120, depth_db=6, release_ms=250)

    assert envelope.shape == (44_100,)
    assert envelope[0] < 1.0
    assert envelope.max() <= 1.0
    assert envelope.min() > 0.0


def test_normalize_peak_hits_target() -> None:
    audio = np.array([[0.25, -0.5], [0.125, 0.1]], dtype=np.float32)

    normalized = normalize_peak(audio, target_dbfs=-6.0)

    assert normalized.shape == audio.shape
    assert np.max(np.abs(normalized)) == np.float32(10 ** (-6.0 / 20.0))


def test_mono_below_preserves_stereo_shape() -> None:
    left = np.sin(np.linspace(0, 1, 2048, dtype=np.float32) * 30)
    right = -left
    audio = np.column_stack([left, right]).astype(np.float32)

    processed = mono_below(audio, 120)

    assert processed.shape == audio.shape


def test_integrated_lufs_returns_finite_value() -> None:
    tone = np.sin(np.linspace(0, np.pi * 64, 44_100, dtype=np.float32)) * 0.1
    audio = np.column_stack([tone, tone]).astype(np.float32)

    assert np.isfinite(integrated_lufs(audio))


def test_master_hits_target_lufs_with_stereo_meter() -> None:
    # A quiet 1 kHz sine needs only gain (no limiting), so it lands exactly on target.
    sr = 44_100
    tone = np.sin(np.linspace(0, 2 * np.pi * 1000 * 2.0, sr * 2, dtype=np.float32)) * 0.2
    audio = np.column_stack([tone, tone]).astype(np.float32)

    out = master(audio, sample_rate=sr, target_lufs=-16.0, ceiling_dbtp=-1.0)

    assert abs(integrated_lufs(out, sample_rate=sr) - (-16.0)) < 0.5
    assert peak_dbfs(out) <= -1.0 + 0.1


def test_limit_peak_holds_true_peak_ceiling() -> None:
    # Broadband transients expose inter-sample overshoot after gain modulation.
    sr = 44_100
    audio = np.random.default_rng(0).uniform(-2.0, 2.0, (sr, 2)).astype(np.float32)

    limited = limit_peak(audio, sample_rate=sr, ceiling_dbfs=-1.0)

    reconstructed_peak = np.max(np.abs(resample_poly(limited, 4, 1, axis=0)))
    assert 20 * np.log10(reconstructed_peak) <= -1.0 + 1e-5


def test_master_preserves_silence_without_nan() -> None:
    audio = np.zeros((44_100, 2), dtype=np.float32)

    out = master(audio, target_lufs=-16.0)

    assert np.isfinite(out).all()
    np.testing.assert_array_equal(out, audio)
