<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Workflow

Setloom uses an agentic co-production loop.

```text
spec -> candidates -> render -> automated review -> human listening -> typed revision -> next candidates
```

## Human Role

The human is the taste owner.

The human does not need to click through a DAW or understand every studio engineering term. The human must listen, decide, and give direction.

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
tracks/T01/reviews/listening-notes.yml
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

