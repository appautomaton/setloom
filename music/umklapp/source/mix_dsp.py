# SPDX-License-Identifier: AGPL-3.0-only
"""Track-owned, bounded engineering of Umklapp's existing voices and returns."""
import numpy as np
from pedalboard import HighShelfFilter, PeakFilter
from scipy import signal


def filtered(audio, rate, low, high=None):
    cutoffs = [low, high] if high else low
    sos = signal.butter(2, cutoffs, fs=rate, btype="bandpass" if high else "highpass", output="sos")
    return signal.sosfilt(sos, audio, axis=0).astype("float32")


def macro(knots, bars):
    x, y = np.asarray(knots, dtype=float).T
    index = np.clip(np.searchsorted(x, bars, side="right") - 1, 0, len(x) - 2)
    phase = np.clip((bars - x[index]) / (x[index + 1] - x[index]), 0, 1)
    return (y[index] + (y[index + 1] - y[index]) * (.5 - .5*np.cos(np.pi*phase))).astype("float32")


def upper_width(audio, rate, scale, transition_hz):
    """Expand existing upper side energy; the center signal is unchanged."""
    mid = audio.mean(axis=1)
    side = (audio[:, 0] - audio[:, 1]) * .5
    side += filtered(side, rate, transition_hz) * (np.asarray(scale) - 1)
    return np.column_stack((mid + side, mid - side)).astype("float32")


def polish_return(audio, dry, settings, rate, timeline, audit=None):
    if not settings:
        return audio
    wet = audio - dry
    bars = timeline / (240 / 134)
    gain = macro(settings["gain_bar_keyframes"], bars)
    width = macro(settings["width_bar_keyframes"], bars)
    wet = upper_width(wet, rate, width, settings["side_transition_hz"])
    wet *= gain[:, None]
    if "dry_gain_db_bar_keyframes" not in settings:
        return (dry + wet).astype("float32")
    dry_db = macro(settings["dry_gain_db_bar_keyframes"], bars)
    wet_db = macro(settings["return_gain_db_bar_keyframes"], bars)
    foreground = dry * (10**(dry_db / 20))[:, None]
    returned = wet * (10**(wet_db / 20))[:, None]
    if audit is not None:
        def energy_db(value):
            return float(10*np.log10(max(float(np.mean(value*value)), 1e-14)))
        stages = []
        for label, first, last in [
            ("suspension-opening",96,104), ("suspension-exit",104,112),
            ("return-opening",112,120), ("return-development",120,128),
            ("metal-opening",160,164), ("metal-body",164,172),
            ("metal-handover",172,176), ("signal-return",176,184)
        ]:
            left = int(np.searchsorted(bars, first))
            right = int(np.searchsorted(bars, last))
            if right <= left:
                continue
            old_dry, new_dry = energy_db(dry[left:right]), energy_db(foreground[left:right])
            old_wet, new_wet = energy_db(wet[left:right]), energy_db(returned[left:right])
            stages.append(dict(block=label, bars=[first,last],
                               dry_change_db=new_dry-old_dry, return_change_db=new_wet-old_wet,
                               before_dry_to_return_db=old_dry-old_wet,
                               after_dry_to_return_db=new_dry-new_wet))
        audit["foreground_refinement"] = dict(
            dry_gain_range_db=[float(dry_db.min()),float(dry_db.max())],
            return_gain_range_db=[float(wet_db.min()),float(wet_db.max())],
            stages=stages,
            measurement_surface="Rendered source and returns after inherited space processing, before unchanged voice EQ, ducking, fader and mastering.")
    return (foreground + returned).astype("float32")


def upper_guard(audio, settings, rate):
    """Gently ride a noise band with linked gain and explicit attack/release.

    This is conventional band dynamics, not a spectral-dynamics emulation. The
    full voice outside the treated band continues at its existing level.
    """
    band = filtered(audio, rate, *settings["band_hz"])
    hop = max(1, round(rate / settings["control_rate_hz"]))
    count = int(np.ceil(len(band) / hop))
    energy = np.mean(np.pad(band, ((0, count*hop-len(band)), (0, 0))).reshape(count, hop, 2)**2, axis=(1, 2))
    level = 10*np.log10(np.maximum(energy, 1e-14))
    desired = np.minimum(np.maximum(level-settings["threshold_dbfs"], 0)*(1-1/settings["ratio"]), settings["maximum_cut_db"])
    control_rate = rate / hop
    attack = np.exp(-1 / (control_rate*settings["attack_ms"] / 1000))
    release = np.exp(-1 / (control_rate*settings["release_ms"] / 1000))
    reduction = np.empty(count, dtype="float32")
    state = 0.0
    for index, target in enumerate(desired):
        coefficient = attack if target > state else release
        state = coefficient*state + (1-coefficient)*target
        reduction[index] = state
    samples = np.arange(len(audio))
    applied = np.interp(samples, np.arange(count)*hop + .5*hop, reduction).astype("float32")
    result = audio + band*(10**(-applied[:, None]/20)-1)
    report = dict(band_hz=settings["band_hz"], threshold_dbfs=settings["threshold_dbfs"], maximum_reduction_db=float(reduction.max()),
                  active_percent=float(np.mean(reduction>.1)*100), mean_reduction_when_active_db=float(reduction[reduction>.1].mean()) if np.any(reduction>.1) else 0)
    return result.astype("float32"), report


def polish_voice(audio, settings, rate, kick_activity):
    report = {}
    for band in settings.get("eq", []):
        cls = PeakFilter if band["type"] == "peak" else HighShelfFilter
        processor = cls(cutoff_frequency_hz=band["frequency_hz"], gain_db=band["gain_db"], q=band["q"])
        audio = processor(audio.T, rate).T.astype("float32")
    if settings.get("low_pocket"):
        pocket = settings["low_pocket"]
        band = filtered(audio, rate, *pocket["band_hz"])
        reduction = pocket["maximum_cut_db"]*kick_activity
        audio += band*(10**(-reduction[:, None]/20)-1)
        report["low_pocket"] = dict(band_hz=pocket["band_hz"], maximum_reduction_db=float(reduction.max()))
    if settings.get("upper_guard"):
        audio, report["upper_guard"] = upper_guard(audio, settings["upper_guard"], rate)
    if settings.get("upper_side_scale"):
        audio = upper_width(audio, rate, settings["upper_side_scale"], settings["side_transition_hz"])
    assert np.isfinite(audio).all()
    return audio.astype("float32"), report
