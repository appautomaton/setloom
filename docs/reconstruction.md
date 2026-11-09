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
authored additions in source and review labels. Separator labels and levels do
not establish independent players, prominence or original faders. Use estimates
to locate and attribute evidence; judge timbre, weight and space in the original
mix. A strong estimate may duplicate another; a weak one may omit an important
gesture. Reconcile shared content before rendering it as another part, revisiting
ownership as evidence changes. Full-mix measurements describe combined activity
until a narrower interpretation is supported.

A separated synth estimate can contain several voices and effects. Choose a
representation from behavior across the phrase:

| Source behavior | Editable representation |
| --- | --- |
| Independently moving melody, harmony or response | Notes and a distinct voice when supported. |
| Oscillators, harmonics or detune within one gesture | Instrument layers sharing the performance. |
| Continuing amplitude, filter or pitch movement | Controls, envelopes or modulation. |
| Delayed responses and spatial decay | Effects and their automation. |

Several model notes may describe one sound; one estimate may contain several
parts. Harmonic spacing alone neither proves a separate voice nor justifies
deleting an octave. Compare attacks, co-movement, envelopes and exposed repeats.

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
| Why does a new instrument feel different? | Notes, controller routing, excitation, partial relationships, envelopes and release. | Correct notes do not validate a sound model; the performer must realize the gesture. |
| Why is the mix thin, muddy or crowded? | Original and rebuilt phrases in ensemble, then contributing parts, levels and returns. | Added layers or a matched average spectrum can conceal omitted, duplicated or misrepresented gestures. |

Automation locates passages, exposes evidence and executes understood operations.
The primary agent must inspect the relevant time- and frequency-domain views,
comparing the original, separated estimates and rebuilt passage. A plot saved to disk, a
summary metric or decoded MIDI does not perform that comparison. Use auditory
perception when available; viewing plots or playing audio does not establish hearing.

Inspect complete phrases, their development and transitions. Focus close analysis
on distinct gestures and ambiguities; check returns before reusing a recovered
pattern. Zoom into individual attacks, durations, overlapping voices and partials
where needed, then verify their relationships in the complete phrase. Use solos
to diagnose; judge their contribution in ensemble.

For a persistent mismatch, locate where source behavior diverges: separated
evidence, musical interpretation, instrument response or mix interaction. Test
that explanation against the source before changing parameters. If the model
cannot express the gesture, revise its representation before compensating with
gain, equalization or additional layers. Keep the supporting passage, cause and
material uncertainty with the track so work can resume.

[Tooling](tooling.md) defines analysis units and runtimes. Keep file seconds,
excerpt offsets, frame times, and MIDI ticks distinct. A small spectrogram hop
does not undo long-window smearing, and separately normalized excerpts can hide
the relative levels that matter in the mix.

Basic Pitch and fusion produce candidates. Detection thresholds, cross-model
agreement and event counts do not certify fidelity. Without ground-truth notes,
do not report a note-recovery percentage. See [decoder limits](tooling.md#separation-and-transcription)
when candidate notes appear incomplete or implausibly dense.

## First audition

Present a coherent performance of the commissioned scope once its defining
phrases, principal voices, groove and entrances/exits have supported
interpretations, and demonstrated material mismatches have been corrected.
Check from the original toward the reconstruction for content no implemented
part explains. Neither a fixed number of analysis passes nor a similarity score
decides readiness.

Include the timbral movement and articulation that carry musical identity:
bass breathing, synth pulses, drum weight and spatial responses can matter as
much as pitch. Prioritize differences that alter identity, groove or development;
quiet supporting detail should retain its role in the source. Exact presets or
fine effect tails can remain approximate where they do not change the gesture.
Disclose unresolved material uncertainty.
Continue close investigation where it could change the performance; do not
delay a useful audition solely to reproduce every synthesis detail. The human
judges the result; the agent owns evidence-based corrections before delivery.

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
a new one, read [Sound, gesture and control](../.agents/skills/setloom-expressive-arrangement/references/expressive-controls.md).
