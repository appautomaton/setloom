<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Setloom

Producer-first agentic tools for weaving club tracks and DJ sets.

Setloom by AppAutomaton is a keyboard-first co-production harness for generating, tuning, mixing, and sequencing club tracks and DJ sets. It starts with melodic/progressive techno, then expands through lane packs for house, tech house, and adjacent electronic music lanes.

Setloom is built for creators with rhythm, taste, and rave intuition who want to type their way through music production without surrendering musical judgment to presets or stale automation.

## What It Is

- A file-based harness for track specs, lane packs, MIDI, stems, renders, review notes, and set plans.
- An agentic workflow where AI prepares candidates, the human owns taste, and every serious render starts with a producer decision.
- A practical bridge between algorithmic music tools, generative agents, and DJ-set-aware arrangement.

## What It Is Not

- Not a traditional DAW replacement.
- Not a one-click hit generator.
- Not a professional sound engineering course.
- Not a closed hosted music service.

## V1 Artifact

V1 targets editable outputs:

```text
MIDI + stems + review notes
```

The project should preserve control. A final WAV is useful, but the editable materials matter more.

## Core Principle

```text
Agents prepare candidates.
Technical checks protect playback and low end.
Producer judgment shapes the music.
Humans make the listening decision.
```

## Repository Map

```text
AGENTS.md             High-signal instructions for coding agents.
docs/                 Charter, roadmap, licensing, lane-pack contract, and workflow notes.
music/packs/          Per-lane packs: technical scaffolds, vocabulary, and rebuild notes.
music/tracks/         Track registry: spec, brief, and listening notes per track.
src/setloom/          Python toolkit: CLI (validate/anatomize/score), track-spec schema, hygiene gate, MIDI + audio-hygiene + music-theory primitives, and anatomy/score diagnostics.
scripts/              Local genai candidate and smoke-clip scripts.
tests/                Schema, gate, theory-helper, audio, and anatomy/score tests.
local/                Machine-local material (gitignored): corpus lab, candidates, releases.
models/               Model weights store (gitignored).
pyproject.toml        uv-managed Python package definition and CLI entry point.
LICENSE               AGPL-3.0-only text for the core project.
LICENSES/             Canonical license texts used by the project.
```

Start with [docs/README.md](docs/README.md) for context routing.

## License

Core code, harness prompts, schemas, executable lane packs, and automation logic are licensed under AGPL-3.0-only.

Project documentation is licensed under CC BY-SA 4.0 unless explicitly marked otherwise.

Generated music outputs belong to the user who creates them, subject to the user's own third-party samples, models, and inputs.

See [docs/licensing.md](docs/licensing.md).
