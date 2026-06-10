<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Dossier Guide: Reading `setloom anatomize` Output

One dossier pair per track under `local/corpus/dossiers/` (local-only): `<track>.quick.yml` (full mix), `<track>.stems.yml` (per stem), plus `<track>.bass.mid` (bass transcription, never committed) and a corpus-wide `corpus-summary.yml`. With `--layers`, each track also gets `<track>.layers.yml` and per-layer MIDI (see the layer-lens section below).

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
| `partition_residual_db` | Sanity check that the 4 demucs stems sum back to the source — the property that makes every share above meaningful. Corpus baseline −30 dB and lower; above −20 dB the run is flagged `partition:suspect` and the dossier's energy numbers should not be trusted. |

## `<track>.layers.yml` — 53-stem layer lens (opt-in: `anatomize --layers`)

Extracted by the MVSep Mega BS-RoFormer checkpoint into named layers, cached under `local/corpus/stems53/<track>/`. Two contracts to keep straight:

- **Layers are overlapping extractions, not a partition.** The same content can appear in several layers (the synth layer carries the bassline too). Energy-accounting metrics stay on the demucs stems above; layer metrics describe each layer in isolation.
- **Weights caveat:** the upstream checkpoint's license is unstated. The weights live in the gitignored model store at `models/roformer/`, are used for local analysis only, and are never committed or redistributed.

| Field | Musical meaning |
| --- | --- |
| `kept_layers[]` | Layers above the −40 dBFS keep threshold. The per-track `manifest.yml` in the stems cache lists *all 53* with RMS/activity, so dropped layers are auditable, never silently lost. |
| `melodic.<layer>.*` | Same note-stats schema as `bass.*`, computed per layer (synth is high-passed at 120 Hz first — it duplicates the bassline). `tonic_candidate` agreement with `bass.tonic_candidate` is a good sanity signal. |
| `<track>.<layer>.mid` | Transcription per melodic layer. **Monophonic dominant line only** (torchfcpe): chords and overlapping voices collapse to the loudest line. Read riffs and contours, not full voicings. |

## `<track>.score.yml` — grammar score (`setloom score <audio>`)

Measures a track's dossier against the style-pack targets in `style.yml` and reports per-metric distance. Works on any anatomized audio — corpus reference or generated candidate (candidates never enter `corpus-summary.yml`). A score is the technical half of review only; it never overrides the listening gate, and the report says so on its last line.

| Field | Meaning |
| --- | --- |
| `metrics[].status` | `in` / `out` of the target window, or `missing` (no measured value or no target in the pack — never a crash). |
| `metrics[].distance` | Signed: negative below the window, positive above, `0.0` inside. How far, not how bad. |
| `metrics[].provenance` | Trust grade of the *target*: `corpus` (measured from reference audio) > `evidence` (corroborated survey/metadata) > `assumption` (taste knob or model knowledge, pending listening). Distance from an assumption is not distance from the grammar. |
| `metrics[].source` | Which dossier field produced the measured value — every mapping is auditable. |

Calibration note (2026-06-10, 8-track corpus): bpm 8/8 in, bass occupancy 8/8, break window 7/8 (Magma 0.30 is the known outlier), lufs outs match the measured master spread, vocal outs are exactly the featured-collab tracks. `duration_minutes` reads low on most corpus files — they are short edits, while the evidence-backed window describes extended club mixes; that disagreement is real and stays visible.

## Confidence limits

- Bass transcription uses pyin with a 0.4 voiced-fraction threshold per 16th; heavily effected or sub-only passages read as unvoiced (occupancy underestimates). The MIDI range top can include bleed — distrust notes above ~MIDI 60.
- Kick detection is presence-based (≥2 low-band onsets/bar); soft or heavily sidechained kicks can read as absent. A kick-timing-tightness metric was tried and dropped: low-band onset times are too contaminated to measure groove feel.
- Everything here is the technical half of review. None of it overrides the human listening gate.
