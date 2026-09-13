<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Semantics

This is the reasoning history behind Setloom: how making music changed what we
mean by reconstruction, automation, expression and progress. It preserves the
turning points that should inform future decisions. Current production state
belongs with each song; operating guidance lives in [AGENTS.md](../AGENTS.md)
and [Workflow](workflow.md).

## A sound we could re-perform

During the Gravitational Wave work, a convincing resemblance prompted a more
fundamental question: was the result actually playing recovered musical
information? The answer mattered because the ambition was to learn how to make
and reinterpret this music. Replaying pieces of the recording would not provide
that freedom.

The durable result became an editable performance: notes, timing, dynamics,
articulation, controllers, instruments and effects. MIDI carries part of this
information; the score and instrument code carry the rest. The human need not
inspect these intermediates. Their value appears when a voice can be revised,
replaced or performed again coherently.

We also became more precise about fidelity. A successful reconstruction is a
supported musical interpretation, with convincing resemblance where the brief
requires it. It does not establish that we recovered the producer's original
MIDI, instrument routing or session. An accepted reconstruction gives us a useful
working foundation that remains open to musical revision.

## The work inside automation

Earlier attempts relied too heavily on a single transcription pass and extensive
processing around its output. They could produce files and pass engineering
checks while losing movement, duplicating harmonic evidence or inventing a
melody that failed the reference.

First-principles reasoning meant returning to the intended musical effect and
the actual evidence whenever an implementation stopped making sense.
Progress required patient work inside particular phrases: inspecting the actual
waveforms and spectra, tracing onsets and partials, testing competing explanations,
and revising instruments in context. Producing a chart was only preparation;
someone still had to examine it. Visual evidence can expose errors, but cannot
establish every aspect of hearing or taste. Playback for the human does not give
the agent auditory perception.

For the human, the whole production process can be automated. For the agent,
that means owning the musical work through completion. Scripts execute understood
operations and make useful evidence accessible. Small internal passes let the
agent reason carefully without making the human approve every fragment.

## Parts and gestures

A separator's track label describes an estimate. Its contents still require
interpretation. A synth estimate may contain several interacting voices and
effect returns; two estimates may share the same musical evidence. Treating a
label as an instrument assignment can erase a part or sound it twice.

The piano reinterpretations exposed another distinction: preserving a gesture
can require a different performance. A held synth note may contain pulses that a
piano needs to articulate as strikes. Equal MIDI note counts cannot guarantee
equal musical movement.

Accretion made control within a part equally concrete. Separating the bass's
foundation from its moving texture helped preserve weight while reducing rough
edges. Keeping the approved amplitude tremolo on the upper voice while refining
pitch motion on its echoes allowed articulation and space to be judged separately.
These were useful distinctions for those sounds, rather than a mandatory layer
layout for future songs.

## The composition decision

A new name became a question about musical character. Uniform transposition
changed absolute pitch while preserving relationships the human wanted developed.
A brighter relative-major direction then missed the intended darker character.
The correction involved the relationship between harmony, register, melody and
sound design; changing a key label had never resolved that question.

The percussion revisions sharpened this further. Variation needed an audible
role: a weighted arrival, a shorter continuation, a reply in a phrase gap, or a
build that gathers force toward a return. Sparse placement still needed present,
confident strikes. Making every supporting part quieter would have weakened the
result. The ensemble was the place to judge those choices, with clear labels for
solo versus full-mix comparisons and comparable listening loudness.

The later Cybernova and Sierra interpretations extend this question: what gives
the starting piece its identity, and what can develop into a new one? Replacing
a vocal role with an authored instrument line is a compositional choice. Its
success depends on how that line works with the surrounding parts.

## Taste, feedback and trust

The phrase "the human owns taste" proved inadequate. The agent is responsible
for taste, creative judgment and production quality. The human directs the work
and judges whether it succeeds. A rejected result calls for substantive revision;
effort and measurements cannot overturn the listening verdict.

The human's performance experience also made clear that precise judgment does
not require production terminology. Descriptions such as "too smooth," "buried,"
"hesitant" or "one stick hitting the same way" are useful musical evidence.
The agent must investigate their meaning. A question about why something sounds
wrong deserves an explanation before an unsolicited fix.

Trust also depends on continuity. Approval must reach the actual working MIDI,
settings and audio. A current file should reflect the accepted decisions, and
discarded experiments should stop competing with it for attention.

## What compounds

The useful inheritance is a playable score, repeatable instruments, supported
decisions and an understanding of why they worked. A CLI or abstraction earns
its place when it makes recurring work clearer and easier. More wrappers, hashes
or reports cannot supply missing musical understanding.

Skills carry the distinctions that improve decisions, with technical detail
available when needed. Song-specific recipes remain with the song, allowing the
next production to develop its own structure and character.

Cleaning the workspace became part of maintaining that understanding. Clear
ownership and a current source of truth reduce the chance that the next agent
follows a rejected idea or mistakes an old render for the approved performance.

Continue this page when experience changes a concept or a decision principle.
Preserve the pressure that exposed the problem, what changed in our understanding,
and the musical consequence. Routine render history and current listening
verdicts stay with the production. The aim is to carry forward better judgment
while leaving room for the next piece to demand a different answer.
