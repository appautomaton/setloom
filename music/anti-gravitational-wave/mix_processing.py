# SPDX-License-Identifier: AGPL-3.0-only
"""Retained stereo-bass preparation and musical edge fades."""

import numpy as np
from scipy.signal import butter, sosfiltfilt


def prepare_mix(audio, sample_rate, fade_ms, mono_below=None):
    if mono_below is not None:
        side = (audio[:, 0] - audio[:, 1]) * 0.5
        low = sosfiltfilt(butter(4, mono_below, fs=sample_rate, output="sos"), side)
        audio[:, 0] -= low
        audio[:, 1] += low
    n = round(fade_ms * sample_rate / 1000)
    if n:
        fade = np.sin(np.linspace(0, np.pi / 2, n)) ** 2
        audio[:n] *= fade[:, None]
        audio[-n:] *= fade[::-1, None]
    return audio
