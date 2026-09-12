<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Reference reconstruction

Recover editable musical information and perform it within the user's brief.
Use [Workflow](workflow.md) for audition stages and listening verdicts; keep the
musical interpretation and current evidence in the track's source.

## Representation and provenance

Represent notes, timing, articulation, dynamics, and controls needed for the
audible gesture. A drum strike, a same-pitch retrigger, and modulation inside a
sustained note require different explanations.

Distinguish separated estimates, inferred parts, re-performed instruments, and
authored additions in source and review labels. An extra render layer is not an
extra separator stem or proof of an independent original instrument. Measurements
of the full mix describe combined activity until a narrower interpretation is
supported. Several estimates may share a voice; avoid sounding duplicates.

A separated synth estimate can contain several pitched voices, articulations
and effect returns. Choose their grouping from how they behave across the
phrase; one estimate does not require one instrument or one MIDI track.

Check coverage from the recording toward the performance, including meaningful
content the current implementation does not explain. Shared evidence warrants
reconciliation, not automatic exclusion. Uncertain pitch or voice assignment
remains a hypothesis until local evidence supports it; interpolation alone does
not resolve that uncertainty.

Original PCM supplies reference evidence and labelled comparisons. Independent
instrument samples may perform recovered notes; replaying the original recording
does not constitute a new performance.

## Choose evidence for the question

| Question | Useful evidence | Interpretation limit |
| --- | --- | --- |
| Did pitch move or another voice enter? | Spectrogram and raw pitch/onset activations. | A ridge may be a harmonic, modulation product, or effect. |
| Is this a fresh strike or a continuing pulse? | Short-window rhythm and onset evidence. | Energy peaks and grid points do not prove retriggers. |
| Did a source part disappear? | Original mix and relevant separated estimates. | A separator may lose content or share it across outputs. |
| Why does an unwanted sound remain? | Current rendered passage, contributing tracks, effects, and routing. | Muting one layer does not remove every source of a similar sound. |
| Why does a new instrument feel different? | Notes, controllers, envelope behavior, and a complete rendered phrase. | Equal note counts or controller values do not preserve expression. |

Use enough phrase context to compare explanations, including repeated motifs and
their development. If a feature stays wrong, reconsider the musical explanation
before adding another model or tuning more thresholds. Inspect the actual visual
evidence when it can resolve the question; generating a plot or reading summary
statistics does not perform that inspection. Correct demonstrated mismatches
before an audition. Competing explanations call for further source comparison
and internal trials, not routine confirmation from the human. Use auditory perception
when available; plots and playback for the user do not mean the agent heard it.

[Tooling](tooling.md) defines analysis units and runtimes. Keep file seconds,
excerpt offsets, frame times, and MIDI ticks distinct. A small spectrogram hop
does not undo long-window smearing, and separately normalized excerpts can hide
the relative levels that matter in the mix.

Basic Pitch exposes raw activations through Python. Its generic 127.7 ms minimum
note duration exceeds a 100 ms sixteenth at 150 BPM; inspect raw evidence when
decoded MIDI appears incomplete and choose settings for the actual material.

## Instrument reinterpretation

Identify what carries the melody, pulse, and expression in the source, and decide
how the target instrument will carry those roles. A held synth note may contain
amplitude pulses that need separate piano strikes. Other gestures need sustained
tone, overlap, pedal, or dynamic shaping. Preserve recurring phrase identity when
it matters to the brief; keep additional composition distinguishable from a swap.

Choose touch, note length, density, and timing to realize the intended gesture.
Inspect the rendered phrase against that intent, including its interaction with
the accompaniment. Fixed event counts, constant density, and random timing offsets
do not establish musicality. An otherwise supported score needs re-transcription
when evidence exposes a specific gap, not whenever its new performance fails.

Check the target instrument's actual response to velocity, expression, pitch
bends, pedal, and release. Keep musical preferences scoped to the current brief;
a request for fast piano in one track is not a rule for every performance.

For reconstructing tone and modulation on either the original instrument type or
a new one, read [Gesture and control](../.agents/skills/setloom-expressive-arrangement/references/expressive-controls.md).
