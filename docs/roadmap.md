<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Roadmap

Setloom tracks progress as a series of shipped specs and working harness behaviors. Progress is not measured by calendar time or traditional human production timelines.

## Spec 0: Operating Rules

Define the project boundary.

Acceptance:

- English-only docs and harness prompts.
- Open-source-first tooling posture.
- AGPL-3.0-only core license.
- Human listening gate required for final approval.
- No proprietary samples or unclear model assets in the repo.

## Spec 1: Reference Survey

Build a bounded deep survey from tracks and DJ sets.

Acceptance:

- Reference corpus for starting anchors.
- Notes on BPM, groove, bass behavior, melody density, breakdown length, transition behavior, and set energy.
- A style grammar draft that agents can use.

## Spec 2: Style Grammar

Convert references into measurable constraints.

Acceptance:

- Style vector schema.
- Track section defaults.
- Groove and bass rules.
- Review vocabulary for "too busy", "too flat", "too EDM", "too static", and "not club-functional".
- First executable style pack under `style-packs/melodic-progressive-techno/style.yml`.

## Spec 3: Track Spec Schema

Define the file format for generated tracks.

Acceptance:

- YAML or JSON schema for title, BPM, key, energy, duration, sections, palette, style vector, and render targets.
- Example track spec.
- Example listening notes.
- Validation command planned or implemented.

## Spec 4: MIDI Candidate Generator

Generate editable musical candidates.

Acceptance:

- MIDI generation for drums, bass, chords, arp, lead motif, and fills.
- Multiple variants per request.
- Deterministic seeds for reproducibility.
- No final approval without listening notes.

## Spec 5: Render Engine

Render stems from specs and MIDI.

Acceptance:

- Open-source synthesis path.
- Stem export for kick, bass, drums, chords, pads, lead, and FX.
- Demo mix export.
- Render metadata.

## Spec 6: Review Gate

Separate automated checks from human taste decisions.

Acceptance:

- Technical checks: clipping, duration, section length, BPM, key center, stem presence.
- Musical checks: groove density, low-end risk, melodic density, transition readiness.
- Human listening notes format.
- Candidate decision states: keep, revise, reject.

## Spec 7: Set Compiler

Sequence tracks into a DJ set plan.

Acceptance:

- BPM, key, energy, mood, and transition compatibility scoring.
- Intro/outro mixability notes.
- Set arc plan.
- Human approval for final ordering.

## Spec 8: Style Pack Expansion

Support more club lanes through new style grammars.

Acceptance:

- First style pack: melodic/progressive techno.
- Future packs: house, tech house, afro house, indie dance, and related lanes.
- Style packs must use constraints and review gates, not artist cloning.
