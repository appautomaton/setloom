---
name: setloom-reference-reconstruction
description: Recover a reference recording as editable musical parts and a new performance. Use for missing content, pitch or rhythm mismatches with the reference, or preserving a recovered gesture on another instrument.
---

<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Setloom Reference Reconstruction

Recover a supported, editable interpretation of the recording within the brief;
this does not establish the producer's original MIDI or session. Use
[Workflow](../../../docs/workflow.md) for working stages and scoped listening feedback.

## Musical decisions

- Identify the audible gesture and what the brief asks to preserve or change.
  Distinguish pitch spans, fresh attacks, retriggers, modulation and effects.
- Treat separated stems as overlapping evidence. Their labels do not determine
  the instrument assignments. Distinguish inferred parts and authored additions.
- Check meaningful content omitted by the performance and support for inferred
  events. A completed transcription pass or review of implemented parts alone
  cannot establish coverage.
- Compare complete phrases and relevant repeats. When a feature remains wrong,
  reconsider its musical explanation before adding models or thresholds.
- For an instrument change, decide how melody, pulse and expression survive on
  the target. Rendered phrasing matters beyond event preservation.

## Relevant detail

- [Sound, gesture and control](../setloom-expressive-arrangement/references/expressive-controls.md):
  translate timbre and motion into an independently playable instrument.
- [Expressive arrangement](../setloom-expressive-arrangement/SKILL.md): when the
  brief calls for new composition or arrangement from the recovered material.
- [Evidence and provenance](../../../docs/reconstruction.md): ambiguous parts,
  residual sounds, timing interpretation and grounded comparisons.
- [Instrument reinterpretation](../../../docs/reconstruction.md#instrument-reinterpretation):
  articulation, controllers and the boundary between a swap and new writing.
- [Tooling](../../../docs/tooling.md): runtimes, analysis units and commands.

Keep notes, controls, patches and supporting decisions editable in per-track
source. Deliver audio for the user to judge; retain the identity and verdict of
the reviewed artifact. Technical checks verify the implementation, not taste.
