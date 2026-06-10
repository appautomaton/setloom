<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Workflow

Setloom uses an agentic co-production loop.

```text
spec -> candidates -> render -> automated review -> human listening -> typed revision -> next candidates
```

## Human Role

The human is the taste owner.

The human does not need to click through a DAW, browse folders, operate a plug-in UI, or understand every studio engineering term. The human must be able to listen, decide, and give typed direction.

The listening gate is no-click capable. Agents should use Python and CLI automation to prepare, route, and play audition audio when possible, then ask for comments. Candidate reports are still useful records, but they are not a substitute for agent-operated playback.

When the user has Logic Pro installed, agents may inspect it as a local reference surface for timbre vocabulary, preset categories, or short audition targets. Logic Pro is not the Setloom final renderer or candidate-output chain unless the user explicitly asks for that separate local experiment. Avoid routing the user through additional third-party GUI tools for timbre discovery; prefer Python automation and file-based handoff.

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

Target layout:

```text
tracks/T01/spec.yml
tracks/T01/listening-notes.yml
renders/T01/takes/take-001/
renders/T01/takes/take-001/stems/
renders/T01/takes/take-001/demo.wav
reports/T01/take-001.md
sets/S01/spec.yml
sets/S01/sequence.yml
```

## Review Gates

Automated checks can catch technical and structural problems.

Human listening catches musical judgment.

Both are required.
