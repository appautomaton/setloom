<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Roadmap

Setloom tracks progress as a series of shipped specs and working harness behaviors. Progress is not measured by calendar time or traditional human production timelines.

## Spec 0: Operating Rules

Define the project boundary.

Status: shipped — `AGENTS.md`, `docs/licensing.md`, `CONTRIBUTING.md` (DCO).

Acceptance:

- English-only docs, specs, and public copy.
- Open-source-first tooling posture.
- AGPL-3.0-only core license.
- Human listening gate required for final approval.
- No proprietary samples or unclear model assets in the repo.

## Spec 1: Reference Survey

Build timestamped studies from tracks and DJ sets.

Status: superseded — the first corpus and findings were cleared from the active
pack on 2026-06-15 because they over-promoted stale and restrictive evidence.

Acceptance:

- Reference studies selected case by case for a clear musical question.
- Timestamped listening notes tied to stem/layer evidence.
- Abstract musical moves that do not copy named artists.

## Spec 2: Style Pack Contract

Convert evidence into vocabulary, diagnostics, and track-specific hypotheses.

Status: reset — `music/packs/melodic-progressive-techno/style.yml` now keeps
only lane routing and technical-hygiene scaffolding while the real music
evidence is rebuilt.

Acceptance:

- Clear separation between technical hygiene and musical taste.
- No pack-level BPM, groove, bass, or kick defaults as creative authority.
- Review vocabulary for listening notes, not score targets.
- Executable style pack remains loadable under `music/packs/melodic-progressive-techno/style.yml`.

## Spec 3: Track Spec Schema

Define the file format for generated tracks.

Status: shipped — `setloom validate`, `src/setloom/schema.py`, `tracks/`.

Acceptance:

- YAML or JSON schema for title, BPM, key, energy, duration, sections, palette, style vector, and render targets.
- Example track spec.
- Example listening notes.
- Validation command (`setloom validate`).

## Spec 4: Candidate Production

Generate editable musical candidates.

Status: shipped — per-track code under `music/tracks/TNN/` composes candidates
using `setloom.midi`, `setloom.conductor`, external MIDI, and genai. The
deterministic generator (`setloom generate`) was retired: inventing notes from
built-in patterns made the harness an opinion owner.

Acceptance:

- Per-track code produces editable MIDI for each part.
- Deterministic seeds for reproducibility where code uses RNG.
- No final approval without listening notes.

## Spec 5: Render

Render stems from MIDI and per-track synthesis.

Status: shipped — per-track code renders stems using `setloom.audio` DSP-hygiene
primitives (loudness, mono-safety, filters, envelopes). The SuperCollider
render monolith (`scrender.py`, `patches.scd`) was retired: it baked in a fixed
lead/mix/master architecture and preset timbres.

Acceptance:

- Per-track code renders reproducible stems and a demo mix.
- DSP hygiene (clip prevention, loudness target, mono-safety) via `setloom.audio`.
- Render metadata alongside output.

## Spec 6: Review Gate

Separate automated checks from human taste decisions.

Status: shipped — the technical-hygiene gate runs in `setloom validate`; diagnostic tools are `setloom anatomize` and `setloom score` (`src/setloom/anatomy/`); musical review stays listening notes with keep/revise/reject.

Acceptance:

- Technical diagnostics: clipping, duration, section length, detected tempo, detected key center, stem presence.
- Musical review prompts: groove density, low-end feel, melodic density, transition readiness.
- Human listening notes format.
- Candidate decision states: keep, revise, reject.

## Spec 7: Set Compiler

Sequence tracks into a DJ set plan.

Status: not started.

Acceptance:

- BPM, key, energy, mood, and transition compatibility scoring.
- Intro/outro mixability notes.
- Set arc plan.
- Human approval for final ordering.

## Spec 8: Lane Pack Expansion

Support more club lanes through lane-specific packs.

Status: in progress — first pack shipped; expansion lanes not started.

Acceptance:

- First lane pack: melodic/progressive techno.
- Future packs: house, tech house, afro house, indie dance, and related lanes.
- Packs must separate technical gates from musical vocabulary and must not clone artists.

## Spec 9: GenAI Candidate Lane

Generate local candidates from explicit track theses, then route them through
technical diagnostics and the human listening gate.

Status: partially reset — runtime/model-store plumbing remains useful; old
pack-prompt recipes are deprecated as musical guidance.

Acceptance:

- One repo-local environment; models join via dependency groups, never per-model virtualenvs.
- Candidates land in `local/candidates/genai/` and never enter the corpus summary.
- The same anatomize/score instruments can diagnose reference tracks and candidates.
- Musical ideas, including groove and bass identity, belong to the track thesis and listening gate; deterministic code is an execution surface, not a taste owner.
- Every candidate routes to the human listening gate; scores are technical distance only.
