<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Workflow

A Setloom track is made in a loop, not a pipeline. The human sets a direction,
the agent makes a move, the human listens, and the direction sharpens. No fixed
command sequence is required; the tools used depend on the question being asked.

```text
track thesis → candidate or reference study → listening note → revision
```

So far, exactly one track's production is open here as a worked example:
[Lux in Umbra](../music/T5-lux-in-umbra/). Treat it as a starting point, not a
template set in stone. Setloom is early, and club music is where it begins on
purpose: of all the music worth making, electronic production is the most
programmatic, which makes it the natural first proving ground for an agent-driven
studio. The best practices are still being found, one track at a time.

## The producer pass

Before a serious render, the musical move is made explicit:

```text
groove spine → motif cell → energy arc → palette → what to cut
```

This pass is short, but it decides everything downstream. Naming the spine, the
motif, the arc, the palette (and what to leave out) is what separates a track
with a point of view from a pile of loops. Often the strongest choice is *less*:
no hat bed, no clap, no inherited bus. Silence is an arrangement decision.

## Reference study

References exist to study abstract moves and sharpen review vocabulary, never to
imitate a named artist. When a reference is worth studying, listening comes
first: timestamped notes in your own words. Measurement comes later, and only
when a specific reference raises a concrete technical question. A spectrogram can
show you where the energy sits; it can't tell you whether the track is any good.

## The human's role

The human is the taste owner, and that is the only role the human has to play.

You do not need to click through a DAW, browse folders, operate a plug-in, or
know what every studio term means. You need to listen, decide, and say what you
think in plain words. The listening gate is no-click by design: the agent
prepares and plays the audio; you only listen and type.

A listening note is just honest reaction, structured enough to act on:

```yaml
take: take-003
decision: revise
notes:
  groove: "Kick works. Bass is too busy in the first 32 bars."
  melody: "Motif is good, but the break is too sentimental."
  energy: "Drop needs more lift without becoming too EDM."
requests:
  - "Simplify the bass before the first break."
  - "Make the arp darker and less bright."
  - "Shorten the break by 16 bars."
```

Every candidate lands in one of three states:

- **keep:** this can move forward.
- **revise:** useful material, needs changes.
- **reject:** set it aside.

## What gets kept

Setloom keeps editable source, not opaque bounces. A track in progress is its
recipe:

```text
spec + source/MIDI + stems + render code + listening notes
```

Reference audio, samples, and model weights stay out of version control. Renders
and scratch analysis are disposable. Anything that matters can be regenerated
from the spec, the seed, and the code that made it.

## Diagnostics and listening

Setloom can measure a lot: loudness, spectra, stereo width, even a 53-stem
breakdown of a reference. Those measurements are navigation aids: they help you
ask a sharper listening question. They are never the verdict.

The verdict is a person listening. Both the measurement and the ear have a job;
only one of them decides.
