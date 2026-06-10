<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Findings: Melodic/Progressive Techno Reference Survey

Synthesis of the corpus under `corpus/` (12 anchors, 34 track entries — **33 unique records**, since "Home" appears under both `marino-canal.yml` and `adriatique.yml` and is marked `duplicate_of`; 13 sets; surveyed 2026-06-07).
Constraint-like statements only; every claim cites corpus files. Values the metadata cannot settle are routed to `listening-worksheet.md`.

## Method and Confidence

- Evidence is public metadata (Beatport, SongBPM, Tunebat, 1001tracklists, Discogs, Bandcamp, press). No audio was analyzed; all `structure_notes` are unknown pending listening.
- `corroborated` means two or more independent sources agree; `single-source` values are usable but flagged. Key conflicts carry `key_confidence: conflicting`.

## Style Dimensions

### BPM

- Starting-anchor tracks span **120–125 BPM** in the corroborated subset (7 tracks: `innellea.yml` Loss Of Hope 123, Angel 1 122; `colyn.yml` Resolve 123, Amor 124; `marino-canal.yml` Home 120; `jono-stephenson.yml` I Can't Save You 125; `miss-monique.yml` Concorde 124).
- Including single-source values, starting anchors span 120–128; the only value above 125 is Innellea "Euphoria" at 128 (single-source). Expansion anchors reach down to 118 (`whomadewho.yml`).
- Median across all 34 tracks ≈ 123. The draft `bpm_range [122,126]` was too high at the floor and unsupported at 126: four sourced tracks sit at 120–121, none at 126–127.
- **Constraint:** generate inside **120–125 BPM**, default center 123.

### Key practice

- Mode is **minor-leaning, roughly 2:1** (about 19 minor vs 11 major sourced keys, 3 conflicted). F minor and G minor are the most recurrent minor centers.
- Major keys are not anomalies: Miss Monique's lane runs G major (`miss-monique.yml` Concorde, Look At You), and Colyn ("Oxygen Levels Low" G major), Marino Canal ("Windspeak" E major) chart major-key club tracks.
- **Constraint:** default to minor keys; major keys allowed, weighted ~1 in 3.

### Duration

- Sixteen sourced durations run **5:37–8:35**, median ≈ 6:38; the one shorter value (4:28, `whomadewho.yml` "Silence & Secrets") is a vocal-act single edit, not a club extended mix.
- **Constraint:** club edits target **5:30–8:30**, default ~6:30.

### Label ecosystem (context, not constraint)

- Afterlife Records dominates starting-anchor catalogs (6 of 7 starting anchors have Afterlife releases); the wider ecosystem is Siamese, Cercle, Diynamic, Siona, ZAMNA, Interstellar (Insomniac), Radikon, Distorted Youth/[PIAS].

## Set Construction (what metadata shows)

- 13 sets documented; **all BPM/key movement and transition data is unknown** — web tracklists record IDs and lengths, not mixing behavior. Audit Q2 (energy flow, transition length, useful repetition) cannot be answered without listening; see worksheet.
- Documented set lengths run ~58 min (podcast) to 2h02m (`colyn.yml` Brussels stream); festival tracklists log 8–28 IDs.
- Own-material-heavy set construction is evidenced for Innellea (both sets ≥7/10 own productions, `innellea.yml`).
- Range registers exist: Colyn's 2020 stream is tagged deep house (slower lane), Miss Monique's Ibiza residency spans melodic/afro/indie tags vs her festival tags (`colyn.yml`, `miss-monique.yml`).
- Three corpus sets are radio/studio/podcast mixes, qualified in their `event` strings (`8kays.yml`, `marino-canal.yml`, `enai.yml`) — do not weight them as club-set evidence.

## Rejection Rules (rationale)

Encoded machine-readable in `music/packs/melodic-progressive-techno/style.yml` `rejection_rules`:

1. **bpm-out-of-lane** (evidence): outside 120–125 without explicit spec override — corpus span above.
2. **club-length** (evidence): final club edits under 5:00 or over 9:00 — duration span above.
3. **no-listening-no-approval** (policy): `docs/workflow.md` listening gate.
4. **low-end-conflict** (assumption): kick/bass register-and-timing overlap; thresholds need listening-derived data.
5. **unmixable-edges** (assumption): no mixable intro/outro; anchor intro/outro lengths unmeasured pending listening.

## Cross-Model Knowledge Layer (added 2026-06-07)

A Codex (GPT-5.5) domain review (`reviews/codex-cross-model-review-2026-06-07.md`) contributed
a `model-knowledge` evidence tier — between bare assumption and corpus evidence — now folded
into `style.yml`: section_model_presets (replacing the 288-bar draft that violated the pack's
own club-length rule), bass articulation weights, sidechain-as-rhythm, percussion character,
harmony/motif policy, tension devices, five lane-specific review-vocabulary terms, and three
rejection rules. All carry `model-knowledge` tags and route to the listening worksheet for
final confirmation. Two of its corpus flags were web-verified same day (Arodes Beyond
corroboration stands; Euphoria = 2024-11-01, [PIAS] Électronique).

## Audit Question Status

| Question | Status |
|---|---|
| Q1 defaults accurate? | BPM: corrected to 120–125. Section model & style vector: **no metadata evidence** — annotated as assumptions in style.yml. |
| Q2 set dynamics | Existence/length/track-count documented; movement data needs ears → worksheet. |
| Q3 supported constraints | BPM range, duration window, key-mode bias, three evidence/policy rejection rules. |
| Q4 needs ears | All structure bars, all set movement, 3 key conflicts, 17 single-source BPMs, Miss Monique "Look At You" value-conflation check. |
