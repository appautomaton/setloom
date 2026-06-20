<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Workflow

Setloom uses an agentic co-production loop. The exact tools used depend on the
question being asked; no command sequence is mandatory.

```text
track thesis -> candidate or reference study -> listening note
             -> selective technical evidence when useful -> revision
```

## Producer Pass

Before a serious render, make the musical move explicit:

```text
groove spine -> motif cell -> energy arc -> palette -> what to cut
```

This pass is short, but it matters. The agent writes the track's own code and
decides what to keep, cut, tile, halve, stab, lift, mute, fade, or bypass,
then renders only the parts that serve that move.

The right answer may be less material: no hat bed, no clap, no ride, no shaker,
no inherited bus, no stale patch. Silence is an arrangement choice.

For reference study, timestamped listening notes come first. Machine reports
must not be read as style evidence or promoted into durable musical contracts.
`setloom anatomize --layers` comes later, only when the selected reference
raises a concrete technical question.

The track spec and its per-track code are the authority for song-specific
musical choices. If a candidate is described as a custom groove, the track's
own code must show that custom bass/drum plan.

## Harness Judgment

The harness is a working surface, not a source of truth. Existing commands,
reports, caches, prompts, and tools must be judged against the current
musical objective before use.

```text
use it       -> when it fits the current question
bypass it    -> when it is irrelevant or too coarse
replace it   -> when it creates misleading authority
ask          -> when suitability is unclear
```

When suitability is unclear, the agent asks the human with the question tool
before proceeding. Scratch analysis stays in `tmp/` until confidence and purpose
are explicit.

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
music/tracks/TNN/                # committed per-track spec, brief, and listening notes
local/corpus/audio/<artist>/     # reference audio (copyrighted, never committed)
local/corpus/notes/              # listening notes and low-confidence scratch reports
local/corpus/stems53/            # active 53-stem layer cache
local/corpus/dossiers/           # anatomize dossiers and the corpus summary
local/candidates/                # TNN/ per-track MIDI + renders; genai/ generated audio (corpus-exempt)
local/releases/TNN/              # frozen release packages: master, artwork, upload notes
models/                          # model weights: generation and separation (gitignored)
```

## Diagnostics And Listening

Automated checks can catch technical and structural problems. `setloom anatomize`
is an optional reference lens, not a taste verdict or style authority.

Human listening catches musical judgment.

Both are required.
