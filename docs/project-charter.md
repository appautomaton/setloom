<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Project Charter

## Thesis

Setloom is an open-source, keyboard-first tool and agentic harness for generating, tuning, mixing, and sequencing club tracks and DJ sets.

The project lives under the AppAutomaton organization as `appautomaton/setloom` and should be presented as `Setloom by AppAutomaton`.

The project exists for creators who have rhythm, taste, and dancefloor intuition, but do not want the first step of music creation to be mastering a complex DAW interface.

## Audience

Setloom is for:

- Rave and club music listeners who can judge groove, energy, and emotional flow.
- Technically curious creators who prefer specs, prompts, and command-line workflows.
- Independent musicians and developers who want editable MIDI, stems, and set plans.
- People who want agentic creation without giving up human listening judgment.

Setloom is not primarily for:

- Professional mix engineers.
- Traditional DAW power users who already prefer manual plugin and routing workflows.
- Users looking for one-click finished music with no review loop.

## Starting Lane

The first working lane is melodic/progressive techno.

That lane is currently in reset/rebuild mode. The old fixed reference-anchor
list is not active guidance, because a named-artist list too easily becomes a
template. Future references should enter the project as timestamped listening
studies in `local/corpus/`, tied to stem/layer evidence and abstract musical
moves.

References are evidence and vocabulary sources. They are not instructions to
imitate, clone, or convert one artist's habits into genre law.

## Design Principles

- Keyboard-first, not DAW-first.
- Open-source first, no proprietary core dependencies.
- Agentic, but not autopilot-only.
- File-based and reproducible where possible.
- Human listening is required for approval.
- Low-end control is protected by technical checks, not left to opaque audio generation.
- Style is expressed through track-specific specs, listening vocabulary, and evidence-backed diagnostics, not universal musical gates or vague taste words.

## V1 Target

V1 should produce:

```text
Editable MIDI
Rendered stems
Demo mixes
Listening notes
Track review reports
Set sequencing plans
```

V1 does not need to produce commercial-ready masters.
