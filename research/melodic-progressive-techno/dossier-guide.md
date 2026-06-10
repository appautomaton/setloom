<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Dossier Guide: Reading `setloom anatomize` Output

One dossier pair per track under `anatomy/_dossiers/` (local-only): `<track>.quick.yml` (full mix), `<track>.stems.yml` (per stem), plus `<track>.bass.mid` (bass transcription, never committed) and a corpus-wide `corpus-summary.yml`.

## `<track>.quick.yml` — full-mix pass

| Field | Musical meaning |
| --- | --- |
| `bpm_estimate`, `first_beat_s` | The beat grid every other metric is quantized to. `tempo_suspect: true` means folding could not place the raw estimate in 100–160 and the grid was (or must be) re-anchored from the drum stem. |
| `key_estimate`, `key_confidence` | Krumhansl chroma match. Confidence is a correlation, not a probability; relative-major/minor confusion is the known failure — trust the bass stem's tonic over this. |
| `integrated_lufs` | Master loudness. Corpus center is -8.45 (see `anatomy-findings.md`). |
| `sections[]` | Novelty-detected boundaries snapped to 4-bar multiples, labeled by band energy (`intro/groove/break/peak/outro`). Heuristic — the stem-level kick map is the ground truth for breaks. |
| `energy_curve_16bar[]` | Low/mid/high RMS per 16 bars, each band normalized to its own per-track max (0–1). Compare shapes, not absolute values, across tracks. |

## `<track>.stems.yml` — per-stem pass

| Field | Musical meaning |
| --- | --- |
| `drums.kick_gap_bars` | Bar spans with fewer than 2 detected kick onsets — where the floor drops out. The longest span is the main breakdown. Single-bar dropouts are ignored. |
| `drums.kick_per_bar_mode` | 4 = four-on-the-floor confirmed. |
| `drums.high_perc_onsets_per_bar_groove` | Hat/percussion event density (>5 kHz onsets) in kick-present bars; the "too busy / drum monotony" axis. |
| `bass.tonic_candidate`, `pitch_class_share` | Where the bass actually sits; the most reliable tonic signal in the dossier. |
| `bass.step_occupancy` | Fraction of 16th steps voiced. ≥0.85 = rolling pulse; ≤0.5 = sparse/sustained bass. |
| `bass.note_len_16ths_median`, `share_one_step_notes` | 2.0 median = 8th-note pulse; high one-step share = 16th-note movement. |
| `other.chords_per_2bars`, `harmonic_changes_per_16bars` | Harmony skeleton from the chords/lead/pad stem. Major/minor flips on the same root are usually template flicker; read change *rate*, not exact labels. ≈2/16 bars = static-pedal mode, ≈4–5 = slow-progression mode. |
| `vocals.active_share`, `active_bar_ranges` | How much, and exactly where, vocal material sits. Short 2–3-bar islands = landmark fragments; large share = vocal collaboration. |

## Confidence limits

- Bass transcription uses pyin with a 0.4 voiced-fraction threshold per 16th; heavily effected or sub-only passages read as unvoiced (occupancy underestimates). The MIDI range top can include bleed — distrust notes above ~MIDI 60.
- Kick detection is presence-based (≥2 low-band onsets/bar); soft or heavily sidechained kicks can read as absent. A kick-timing-tightness metric was tried and dropped: low-band onset times are too contaminated to measure groove feel.
- Everything here is the technical half of review. None of it overrides the human listening gate.
