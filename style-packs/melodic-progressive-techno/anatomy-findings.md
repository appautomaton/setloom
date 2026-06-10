<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Anatomy Findings: 8-Track Local Reference Corpus

Measured 2026-06-10 with `setloom anatomize` (demucs `htdemucs` stems; librosa beat/chroma/pyin; pyloudnorm). Corpus: seven 8Kays tracks (including collaborations and one remix) plus one Miss Monique track, supplied locally and never committed. Aggregates live in `corpus-summary.yml` next to the change artifacts (`.agent/work/2026-06-10-anatomy-pipeline-corpus-grammar/`); per-track dossiers are local-only under `anatomy/_dossiers/`. Read metrics via `dossier-guide.md`.

## The Five Rules

1. **One tempo.** All 8 tracks measure 123.0 BPM. The lane is effectively single-valued; `style.yml` narrows `bpm_range` to [122, 124] on this basis.
2. **Rolling pedal bass.** Bass occupies 0.75–0.93 of the 16th grid (mean 0.87), median note length 2 sixteenths in 7/8 tracks; tonic pitch-class share 0.47–0.92. The bass is a rolling 8th-pulse pedal with neighbor motion, not a progression instrument.
3. **Main break lands just before the midpoint.** The principal kick-absent span starts at 0.42–0.48 of track length in 7/8 tracks (mean 0.43; the outlier is a short edit at 0.30). Break length varies widely: 8–43 bars.
4. **Two harmonic modes.** Static one-chord hypnosis (2 tracks, ≈2 chord changes per 16 bars, mostly artifact noise) versus slow progressions (6 tracks, ≈4–5 changes per 16 bars ≈ one chord per 4 bars). Harmonic stasis is a lane, not the law.
5. **Loudness centers at -8.45 LUFS.** Masters span -9.34 to -7.61 integrated. The render target recenters to (-9.0, -8.0).

Secondary observations: kick coverage 0.65–0.92 of bars (four-on-the-floor, mode 4 kicks/bar, everywhere); vocals are bimodal — 0.01–0.14 active share as 2–3-bar landmark fragments in instrumentals versus 0.34–0.54 in true vocal collaborations; one signature gesture: isolated accent kicks inside the breakdown (Magma bars 43 and 46).

## Per-Track Measurements

| Track | BPM | LUFS | Bars | Tonic (share) | Bass occ. | Kick cov. | Break at | Break bars |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8Kays — Magma | 123 | -8.61 | 113 | A# (0.72) | 0.93 | 0.81 | 0.30 | 9 |
| 8Kays, Delhia De France — Human Nature | 123 | -7.61 | 142 | F# (0.68) | 0.88 | 0.74 | 0.45 | 11 |
| 8Kays, OBSESH — TTXTC | 123 | -7.66 | 106 | D (0.67) | 0.75 | 0.79 | 0.46 | 9 |
| 8Kays — Basic | 123 | -8.03 | 127 | D# (0.47) | 0.85 | 0.65 | 0.42 | 43 |
| Falling Down (w/ Juan Hansen, Colyn) | 123 | -8.85 | 185 | D (0.85) | 0.84 | 0.88 | 0.43 | 15 |
| Matemática (w/ Glowal, Abrão) | 123 | -9.34 | 193 | D# (0.71) | 0.92 | 0.92 | 0.45 | 8 |
| Woo York — Samum (8Kays Remix) | 123 | -8.87 | 198 | D (0.92) | 0.92 | 0.84 | 0.42 | 20 |
| Miss Monique — Charybdis | 123 | -8.64 | 202 | G (0.92) | 0.89 | 0.83 | 0.48 | 24 |

## Caveats

- **n=8, 8Kays-centric.** Numbers are revisable as the corpus grows; treat ranges as the current lane, not the genre.
- **Basic is unverified by ears.** Its 0.47 tonic share, 43-bar "break", and 0.65 kick coverage suggest either an unusual arrangement or soft kicks under the detector threshold. Route to the listening worksheet.
- **Harmonic-change counts are comparative, not absolute.** Major/minor triad templates flicker when the third is buried; trust mode separation (static vs moving), not exact counts.
- **Section labels and energy curves are heuristics** pending ears; the kick map from drum stems is the ground truth for break boundaries.
- These are skeleton measurements. The engineering fingerprint (spectral motion, stereo width, space design) and lead-layer phrasing are deferred to future anatomize slices and are where per-artist signature beyond arrangement lives.
