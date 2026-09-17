---
name: setloom-reference-reconstruction
description: Reconstruct a recording as editable notes, expressive controls and a new performance. Use for missing voices or mismatched pitch, rhythm, articulation or timbral motion, including instrument reinterpretation.
---

<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Setloom Reference Reconstruction

Recover a supported musical interpretation within the brief. The original MIDI,
preset and session architecture remain unknown unless supplied.

The primary agent performs the reconstruction directly. Do not delegate source
comparison, note/voice inference, articulation or timbral interpretation, or
fidelity review to subagents. Inspect the underlying passages and plots; another
agent's summary is not sufficient evidence.

- Account for the whole commissioned form; concentrate close inspection on
  distinct phrases, ambiguous layers and transitions. Check meaningful changes
  in repeats before reusing a recovered pattern.
- Open and examine relevant time- and frequency-domain plots, comparing the
  original and rebuilt passages. Model candidates and reports do not replace this
  work; let the musical question determine its depth.
- Distinguish independent voices, instrument layers, modulation and effect returns
  from their behavior. Separated estimates can overlap or omit content.
- Preserve articulation and timbral motion that carry identity, including bass
  and percussion. Notes, controls and the instrument must realize the gesture.
- Check what the original contains that the performance still fails to explain.
  Correct demonstrated mismatches and retain uncertainty where evidence is
  inconclusive. Detector thresholds and note counts do not establish fidelity.

Read only the detail needed:

- [Evidence and provenance](../../../docs/reconstruction.md#representation-and-provenance):
  voice grouping, competing explanations and source support.
- [First audition](../../../docs/reconstruction.md#first-audition):
  when a baseline is useful for listening feedback.
- [Instrument reinterpretation](../../../docs/reconstruction.md#instrument-reinterpretation):
  preserve a gesture on a different instrument.
- [Sound, gesture and control](../setloom-expressive-arrangement/references/expressive-controls.md):
  perform recovered tone, movement and space.
- [Expressive arrangement](../setloom-expressive-arrangement/SKILL.md):
  when the brief includes new composition.
- [Tooling](../../../docs/tooling.md): analysis units, runtimes and decoder limits.

Keep musical decisions, editable performance and current listening state with
the track; use [Workflow](../../../docs/workflow.md) for retention or promotion.
