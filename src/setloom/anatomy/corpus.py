# SPDX-License-Identifier: AGPL-3.0-only
"""Corpus aggregation over current anatomy dossiers. Pure dict/array math."""

from __future__ import annotations

import numpy as np


def quick_row(track: str, quick: dict) -> dict:
    """Aggregate only current full-mix evidence.

    Quick dossiers are navigation-grade technical caches. They intentionally do
    not infer groove, bass, vocal, or break metrics.
    """
    return {
        "track": track,
        "artist": quick["artist_dir"],
        "bpm": quick["bpm_estimate"],
        "lufs": quick["integrated_lufs"],
        "bars": quick["bars_estimated"],
        "duration_s": quick["duration_s"],
    }


def merge_rows(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge freshly analyzed rows into an existing summary's rows.

    Rows are keyed by ``track``: existing rows update in place (file order
    preserved), unseen tracks append in run order. Subset runs therefore
    never shrink the corpus aggregate (the old behavior was last-run-wins).
    """
    fresh = {r["track"]: r for r in new}
    merged = [fresh.pop(r["track"], r) for r in existing]
    merged.extend(r for r in new if r["track"] in fresh)
    return merged


def _col(rows: list[dict], key: str) -> list[float]:
    return [r[key] for r in rows if isinstance(r.get(key), (int, float))]


def _mean(values: list[float], ndigits: int = 2) -> float | None:
    return round(float(np.mean(values)), ndigits) if values else None


def _range(values: list[float]) -> list[float] | None:
    return [min(values), max(values)] if values else None


def corpus_stats(rows: list[dict]) -> dict:
    bpm_values = sorted({r["bpm"] for r in rows if isinstance(r.get("bpm"), (int, float))})
    lufs = _col(rows, "lufs")
    duration_s = _col(rows, "duration_s")
    bars = _col(rows, "bars")
    return {
        "tracks": len(rows),
        "bpm_values": bpm_values,
        "lufs_mean": _mean(lufs),
        "lufs_range": _range(lufs),
        "duration_s_range": _range(duration_s),
        "bars_range": _range(bars),
    }
