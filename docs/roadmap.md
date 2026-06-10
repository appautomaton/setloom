<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Roadmap

Setloom tracks progress as a series of shipped specs and working harness behaviors. Progress is not measured by calendar time or traditional human production timelines.

## Spec 0: Operating Rules

Define the project boundary.

Status: shipped — `AGENTS.md`, `docs/licensing.md`, `CONTRIBUTING.md` (DCO).

Acceptance:

- English-only docs and harness prompts.
- Open-source-first tooling posture.
- AGPL-3.0-only core license.
- Human listening gate required for final approval.
- No proprietary samples or unclear model assets in the repo.

## Spec 1: Reference Survey

Build a bounded deep survey from tracks and DJ sets.

Status: shipped — corpus and findings under `research/melodic-progressive-techno/`.

Acceptance:

- Reference corpus for starting anchors.
- Notes on BPM, groove, bass behavior, melody density, breakdown length, transition behavior, and set energy.
- A style grammar draft that agents can use.

## Spec 2: Style Grammar

Convert references into measurable constraints.

Status: shipped — `style-packs/melodic-progressive-techno/style.yml` with corpus-annotated targets; `research/melodic-progressive-techno/taste-lexicon.md`.

Acceptance:

- Style vector schema.
- Track section defaults.
- Groove and bass rules.
- Review vocabulary for "too busy", "too flat", "too EDM", "too static", and "not club-functional".
- First executable style pack under `style-packs/melodic-progressive-techno/style.yml`.

## Spec 3: Track Spec Schema

Define the file format for generated tracks.

Status: shipped — `setloom validate`, `src/setloom/schema.py`, `examples/tracks/`.

Acceptance:

- YAML or JSON schema for title, BPM, key, energy, duration, sections, palette, style vector, and render targets.
- Example track spec.
- Example listening notes.
- Validation command (`setloom validate`).

## Spec 4: MIDI Candidate Generator

Generate editable musical candidates.

Status: shipped — `setloom generate` (deterministic seeds, multiple variants), `src/setloom/parts/`, `src/setloom/conductor.py`.

Acceptance:

- MIDI generation for drums, bass, chords, arp, lead motif, and fills.
- Multiple variants per request.
- Deterministic seeds for reproducibility.
- No final approval without listening notes.

## Spec 5: Render Engine

Render stems from specs and MIDI.

Status: shipped — `src/setloom/scrender.py` and `render/patches.scd` (SuperCollider path).

Acceptance:

- Open-source synthesis path.
- Stem export for kick, bass, drums, chords, pads, lead, and FX.
- Demo mix export.
- Render metadata.

## Spec 6: Review Gate

Separate automated checks from human taste decisions.

Status: shipped — technical half is `setloom anatomize` and `setloom score` (`src/setloom/anatomy/`); the human half stays listening notes with keep/revise/reject.

Acceptance:

- Technical checks: clipping, duration, section length, BPM, key center, stem presence.
- Musical checks: groove density, low-end risk, melodic density, transition readiness.
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

## Spec 8: Style Pack Expansion

Support more club lanes through new style grammars.

Status: in progress — first pack shipped; expansion lanes not started.

Acceptance:

- First style pack: melodic/progressive techno.
- Future packs: house, tech house, afro house, indie dance, and related lanes.
- Style packs must use constraints and review gates, not artist cloning.

## Spec 9: GenAI Candidate Lane

Generate full-audio candidates from local models, graded by the same instruments as the corpus.

Status: shipped — `scripts/generate_candidate.py` (ACE-Step 1.5 songwriter pillar), `scripts/magenta_smoke.py` (Magenta RT 2 sound-design/jam pillar), the `models/` store, and corpus-exempt routing into `anatomy/_candidates/`; recipes in `research/melodic-progressive-techno/generation-recipes.md`.

Acceptance:

- One repo-local environment; models join via dependency groups, never per-model virtualenvs.
- Candidates land in `anatomy/_candidates/` and never enter the corpus summary.
- The same anatomize/score instruments grade reference tracks and candidates alike.
- GenAI covers melody, motif, atmosphere, and texture lanes; groove and low-end safety stay rule-based.
- Every candidate routes to the human listening gate; scores are technical distance only.
