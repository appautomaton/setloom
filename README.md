<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Setloom

Open-source agentic tools for weaving club tracks and DJ sets.

Setloom by AppAutomaton is a keyboard-first tool and agentic harness for generating, tuning, mixing, and sequencing club tracks and DJ sets. It starts with melodic/progressive techno, then expands through style grammars for house, tech house, and adjacent electronic music lanes.

Setloom is built for creators with rhythm, taste, and rave intuition who want to type their way through music production instead of learning a full professional DAW workflow.

## What It Is

- A file-based harness for track specs, style grammars, MIDI, stems, renders, review notes, and set plans.
- An agentic workflow where AI proposes candidates and the human approves, rejects, or redirects by typing.
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
Agents generate candidates.
Rules protect groove and low end.
Humans make the listening decision.
```

## Repository Map

```text
AGENTS.md             High-signal instructions for coding agents.
docs/                 Charter, roadmap, licensing, style grammar, and workflow notes.
harness/prompts/      Initial prompt specs for the agentic harness.
style-packs/          Executable style grammar files.
research/             Reference corpus, findings, and review memos for style packs.
src/setloom/          Python harness package: CLI, schemas, generators, parts, anatomy and scoring, render orchestration and synth patches.
scripts/              Local genai candidate and smoke-clip scripts.
examples/             Example track specs and listening notes.
tests/                Schema, gate, generator, conductor, audio, part, and render tests.
pyproject.toml        uv-managed Python package definition and CLI entry point.
LICENSE               AGPL-3.0-only text for the core project.
LICENSES/             Canonical license texts used by the project.
```

Start with [docs/README.md](docs/README.md) for context routing.

## License

Core code, harness prompts, schemas, style grammars, and automation logic are licensed under AGPL-3.0-only.

Project documentation is licensed under CC BY-SA 4.0 unless explicitly marked otherwise.

Generated music outputs belong to the user who creates them, subject to the user's own third-party samples, models, and inputs.

See [docs/licensing.md](docs/licensing.md).
