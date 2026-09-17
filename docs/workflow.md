<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Workflow

Production stages and continuity. Musical responsibilities are in
[AGENTS.md](../AGENTS.md); task skills guide the production work.

```text
musical intent → temporary audition → listening feedback → revision or promotion
```

## Working stages

| Location | Purpose |
| --- | --- |
| `music/` | Editable productions the user has chosen to retain or promote there. |
| `tmp/<track>/` | New source, MIDI, analysis, separated estimates, experiments, working renders and auditions, including named versions. |
| `local/reconstructions/` | User-approved reconstruction baselines: editable notes/MIDI, patches, retained performances and supporting references for later reinterpretation. |
| `local/candidates/` | Candidates the user considers good enough to retain for the longer term. |
| `local/releases/` | Release assets within the commissioned release scope. |
| `local/corpus/` | Original recordings and reference assets the user has chosen to retain. New separated estimates stay in `tmp`. |

Once a production is retained under `music/`, that directory is its sole editable
source of truth. Keep the score, instruments and necessary artwork source there;
remove matching local candidates, source clones and obsolete derived caches after
checking dependencies. Unique publication assets can live beside the production
under `published/`, ignored by Git. They are historical exports, not another SOT.

Promotion is a quality and scope decision informed by the brief, listening
feedback, and existing authorization. Supplied originals keep their existing
location; new derivatives begin in `tmp`. A filename, technical check or relative
improvement does not authorize promotion. Use the user's acceptance and scope
already given without imposing a fixed approval phrase or repeated confirmation.
Approval of a part applies to that part; retention does not authorize publication.

An approved reconstruction's retained notes and performance become the baseline
for further work. Keep reference analysis distinct from that accepted source;
rerunning a transcription must not silently replace it. Develop new
interpretations in `tmp/<track>/` until the user chooses to retain them.

Keep directory placement, renderer defaults, links, and current state consistent.
When moving a version, preserve its identity; an old reviewed file must not
silently acquire different audio. Temporary material can remain necessary for
active feedback or rebuilds. Clean it up when those dependencies are resolved.

## Listening and continuity

Deliver identifiable audio within playback preferences; for reconstruction use
the [first-audition guidance](reconstruction.md#first-audition).

Keep a concise current record in the track's existing README or working note:
the commissioned scope, editable source, reviewed/rendered artifact, stage,
scoped listening verdict, and next unresolved musical question with its relevant
passage or evidence. Update this record instead of creating parallel status
ledgers. Keep raw events and historical trials in supporting files.

Distinguish user reports, direct observations and hypotheses. A later clarification
governs current state; earlier feedback stays with its reviewed artifact.
Technical reports must not reset the listening verdict.

Feedback normally steers the commissioned work. Answer questions, incorporate
corrections and continue independent work. Pause when the user explicitly asks,
or when a missing decision or authorization blocks the dependent action.

Preserve editable notes, controls, patches, source, and credits needed to reproduce
useful work. Keep track-specific preferences and failure details with that track.
Shared guidance should retain reusable distinctions, not a history of each attempt.
