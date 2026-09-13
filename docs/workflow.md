<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Workflow

Work from the intended musical effect and the actual performance. The agent
owns production details and judgment; the human directs the work and judges
the result. Tools support that exchange:

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

Deliver audio the user can judge without operating a DAW or inspecting MIDI.
Resolve mismatches demonstrable with available evidence internally; do not make
the human confirm missing content, incorrect timing or other already-visible
defects. Updates should convey consequential findings or changes of direction,
not require approval of internal passes. Honor playback preferences and identify
the artifact under discussion. Keep a concise current record: artifact, stage,
scoped listening verdict, and next musical
question. Distinguish user reports from agent observations. A later clarification
governs current state; retain earlier feedback with the artifact it described.
Technical reports must not reset that verdict.

Feedback normally steers the commissioned work. Answer questions, incorporate
corrections and continue independent work. Pause when the user explicitly asks,
or when a missing decision or authorization blocks the dependent action.

Preserve editable notes, controls, patches, source, and credits needed to reproduce
useful work. Keep track-specific preferences and failure details with that track.
Shared guidance should retain reusable distinctions, not a history of each attempt.
