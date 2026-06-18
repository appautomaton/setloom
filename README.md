<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

<div align="center">

# Setloom

**Producer-first agentic tools for club music.**

Turn musical intent into editable tracks, stems, renders, and listening notes.

[Charter](docs/project-charter.md) ·
[Workflow](docs/workflow.md) ·
[Tooling](docs/tooling.md) ·
[Roadmap](docs/roadmap.md)

</div>

---

Setloom is a local, keyboard-first co-production harness for electronic music.
It gives AI agents a structured place to help with production: track specs,
MIDI, stems, renders, reference studies, technical checks, and revision notes.

The point is not to replace taste. The point is to make iteration faster while
keeping the human in charge of the music.

## Vision

Setloom is built around a simple idea:

```text
AI can move quickly.
The producer still decides what is music.
```

We want a studio surface where a creator can describe the track's intent, ask
agents to prepare options, listen without ceremony, and keep only what earns its
place.

Club music is the proving ground because it is unforgiving. The groove has to
hold. The low end has to behave. The arrangement has to move. A prompt cannot
fake that.

Setloom is still iterating.

## How It Works

```text
intent
  -> candidate material
  -> technical checks
  -> listening gate
  -> revision
```

Agents prepare the work. The human keeps, rejects, or redirects it.

## Principles

| Principle | Meaning |
| --- | --- |
| Producer-first | Musical intent comes before tools, scores, or generators. |
| Human taste gate | Nothing is final until a human listener says it works. |
| Local by default | Audio, candidates, references, and model weights stay on the machine. |
| Evidence, not authority | Analysis helps ask better questions; it does not decide taste. |
| Editable artifacts | MIDI, stems, specs, and notes matter as much as the final WAV. |

## Tool Drawer

These commands are available when they serve the track.

```sh
setloom validate <spec>
setloom generate <spec>
setloom anatomize <audio> --layers
setloom score <audio>
```

They are tools, not a required pipeline.

## Repository Map

| Path | Purpose |
| --- | --- |
| `AGENTS.md` | Operating rules for coding agents. |
| `docs/` | Charter, workflow, tooling, roadmap, and licensing. |
| `music/packs/` | Lane scaffolds, review vocabulary, and reset notes. |
| `music/tracks/` | Track-specific specs, briefs, production files, and notes. |
| `src/setloom/` | Python package: CLI, generators, render helpers, anatomy, scoring. |
| `scripts/` | Local utilities and experiments. |
| `tests/` | Technical checks for the harness. |
| `local/` | Machine-local audio, candidates, corpus, and releases. |
| `models/` | Machine-local model weights. |

`local/` and `models/` are gitignored. Reference audio, generated candidates,
model weights, and proprietary assets stay local.

## What It Is Not

- Not a DAW replacement.
- Not a one-click song machine.
- Not a style-law engine.
- Not a named-artist imitation system.
- Not a hosted music service.

## License

Core code, harness prompts, schemas, executable lane packs, and automation logic
are licensed under AGPL-3.0-only.

Project documentation is licensed under CC BY-SA 4.0 unless explicitly marked
otherwise.

Generated music outputs belong to the user who creates them, subject to the
user's own third-party samples, models, and inputs.

See [docs/licensing.md](docs/licensing.md).
