---
name: setloom-reference-reconstruction
description: Recover or revise reference audio as editable musical parts and a new performance. Use for reconstruction, missing layers, incorrect rhythm or pitch, and instrument reinterpretation in Setloom.
---

<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Setloom Reference Reconstruction

Ground the work in the current brief, recording, performance, and listening
feedback. Use [Workflow](../../../docs/workflow.md) for working stages and scoped
acceptance; a named audition can still be temporary.

## Musical decisions

- Identify the audible gesture and what the brief asks to preserve or change.
  Distinguish pitch spans, fresh attacks, retriggers, modulation, and effects.
- Treat separated stems as overlapping evidence. Label inferred parts and
  authored additions so they cannot be mistaken for raw separator outputs.
- Inspect meaningful source content the current performance does not explain;
  reviewing only the parts already implemented cannot establish coverage.
- Compare complete phrases and relevant repeats. When a feature remains wrong,
  reconsider its musical explanation before adding models or thresholds.
- For an instrument change, decide how melody, pulse, and expression survive
  on the target instrument. Rendered phrasing matters beyond event preservation.

## Relevant detail

- [Gesture and control](../setloom-expressive-arrangement/references/expressive-controls.md):
  reconstruct timbre and modulation without confusing measurements with synthesis parameters.
- [Expressive arrangement](../setloom-expressive-arrangement/SKILL.md): when the
  brief moves from recovery to developing a melody into layered electronic music.
- [Evidence and provenance](../../../docs/reconstruction.md): ambiguous parts,
  residual sounds, timing interpretation, and grounded comparisons.
- [Instrument reinterpretation](../../../docs/reconstruction.md#instrument-reinterpretation):
  articulation, controllers, and the boundary between a swap and new writing.
- [Tooling](../../../docs/tooling.md): runtimes, analysis units, and commands.

Keep notes, controls, patches, and supporting decisions editable in per-track
source. Deliver audio for the user to judge; retain the identity and verdict of
the reviewed artifact. Technical checks verify the implementation, not taste.
