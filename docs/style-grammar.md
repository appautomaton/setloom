<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Lane Pack Contract

Status: reset for rebuild.

The first melodic/progressive techno pack overfit a small evidence pass and
turned static observations into musical rules. That was the wrong abstraction.
Setloom no longer treats a style pack as a generator authority.

## Current Contract

```text
track spec + human listening -> musical decisions
style pack                  -> lane routing + technical hygiene scaffolding
local corpus                -> evidence for future studies, not rules by itself
```

The harness may block or repair technical problems: clipping, unsafe low end,
missing mixable edges when the form asks for them, broken file outputs, or
phrase-grid incoherence. It should not choose BPM, bass profile, kick pattern,
groove identity, motif behavior, or arrangement shape from pack defaults.

## Rebuild Direction

The next pack must be built from reference studies, not scalar summaries.

| Layer | Required Shape |
| --- | --- |
| Listening | Timestamped human notes on movement, tension, release, groove, and timbre |
| Signal evidence | Stems, layers, transcription, loudness, timing, and spectrum used to explain notes |
| Abstraction | Reusable musical moves that do not copy named artists |
| Execution | Per-track specs choose a musical thesis; the harness renders and checks hygiene |

## Forbidden Pattern

```text
small corpus measurement -> global style rule -> silent generator default
```

That path produced generic and over-restricted candidates. Future packs must
keep evidence, hypothesis, taste, and executable gates separate.
