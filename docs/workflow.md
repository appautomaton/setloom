<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Workflow

Setloom uses an agentic co-production loop.

```text
spec -> candidates (deterministic MIDI or genai audio) -> render/separate -> anatomize -> score -> human listening -> typed revision -> next candidates
```

## Human Role

The human is the taste owner.

The human does not need to click through a DAW, browse folders, operate a plug-in UI, or understand every studio engineering term. The human must be able to listen, decide, and give typed direction.

The listening gate is no-click capable. Agents should use Python and CLI automation to prepare, route, and play audition audio when possible, then ask for comments. Candidate reports are still useful records, but they are not a substitute for agent-operated playback.

Logic Pro and other user-owned proprietary tools are local reference surfaces only, never the Setloom output path; the full policy lives in `docs/tooling.md`.

Example notes:

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
  - "Render four new variants."
```

## Candidate States

- keep: this candidate can move forward.
- revise: this candidate has useful material but needs changes.
- reject: this candidate should not be used.

## Artifact Shape

Current layout:

```text
tracks/TNN/spec.yml                     # committed track specs, briefs, and listening notes
candidates/                             # all candidates (gitignored): TNN/ deterministic MIDI + renders
candidates/genai/                       # genai audio candidates; never enter the corpus summary
releases/TNN/                           # frozen release packages: master, artwork, upload notes (gitignored)
anatomy/<artist>/                       # local reference audio (gitignored)
anatomy/_dossiers/<track>.quick.yml     # anatomize dossiers (.quick/.stems/.layers/.score)
anatomy/_stems/                         # stem separation cache
models/                                 # model weights: generation and separation (gitignored)
```

The fuller `renders/`–`reports/`–`sets/` companions remain the Spec 7-era target; `tracks/` already follows the spec-plus-notes shape.

## Review Gates

Automated checks can catch technical and structural problems. `setloom score` is the shipped technical check: grammar distance against the style-pack targets, with provenance per metric. It is never a taste verdict.

Human listening catches musical judgment.

Both are required.
