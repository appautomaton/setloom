# SPDX-License-Identifier: AGPL-3.0-only
"""Corpus aggregation over per-track anatomy dossiers. Pure dict/array math."""

from __future__ import annotations

import numpy as np


def parse_span(span: str) -> tuple[int, int]:
    a, b = span.split("-")
    return int(a), int(b)


def main_break(spans: list[tuple[int, int]]) -> tuple[int, int] | None:
    """Longest kick-absent span; the track's principal breakdown."""
    return max(spans, key=lambda ab: ab[1] - ab[0]) if spans else None


def track_row(quick: dict, stem: dict) -> dict:
    spans = [parse_span(g) if isinstance(g, str) else tuple(g) for g in stem["drums"]["kick_gap_bars"]]
    n_bars = stem["bars"]
    brk = main_break(spans)
    share = stem["bass"]["pitch_class_share"]
    return {
        "track": stem["track"],
        "artist": quick["artist_dir"],
        "bpm": quick["bpm_estimate"],
        "lufs": quick["integrated_lufs"],
        "bars": n_bars,
        "duration_s": quick["duration_s"],
        "tonic": stem["bass"]["tonic_candidate"],
        "tonic_share": next(iter(share.values())) if share else None,
        "bass_occupancy": stem["bass"]["step_occupancy"],
        "bass_note_len_median_16ths": stem["bass"]["note_len_16ths_median"],
        "kick_coverage": round(stem["drums"]["kick_bars_present"] / n_bars, 2),
        "kick_gaps": len(spans),
        "main_break_start_frac": round(brk[0] / n_bars, 2) if brk else None,
        "main_break_len_bars": (brk[1] - brk[0] + 1) if brk else 0,
        "harmonic_changes_per_16bars": stem["other"]["harmonic_changes_per_16bars"],
        "vocal_share": stem["vocals"]["active_share"],
    }


def corpus_stats(rows: list[dict]) -> dict:
    def col(key: str) -> list[float]:
        return [r[key] for r in rows if isinstance(r.get(key), (int, float))]

    return {
        "tracks": len(rows),
        "bpm_values": sorted({r["bpm"] for r in rows}),
        "lufs_mean": round(float(np.mean(col("lufs"))), 2),
        "lufs_range": [min(col("lufs")), max(col("lufs"))],
        "bass_occupancy_mean": round(float(np.mean(col("bass_occupancy"))), 2),
        "bass_occupancy_range": [min(col("bass_occupancy")), max(col("bass_occupancy"))],
        "kick_coverage_mean": round(float(np.mean(col("kick_coverage"))), 2),
        "main_break_start_frac_mean": round(float(np.mean(col("main_break_start_frac"))), 2),
        "main_break_len_bars_values": sorted(r["main_break_len_bars"] for r in rows),
        "harmonic_changes_per_16bars_mean": round(
            float(np.mean(col("harmonic_changes_per_16bars"))), 1
        ),
        "vocal_share_mean": round(float(np.mean(col("vocal_share"))), 2),
    }
