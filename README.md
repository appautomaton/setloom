<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Setloom

Setloom by AppAutomaton is a keyboard-first harness for building club-track
source, rendering auditions, inspecting audio, and keeping agent/human music
work organized.

It is not a solved automatic melodic-techno generator. The useful loop today is
disciplined iteration: human listening feedback, focused source edits, optional
external research, reproducible renders, and visual/audio checks. The harness
helps agents move faster; it does not replace producer judgment.

## What It Is

- A small Python toolkit for per-track source, MIDI, audio helpers, theory
  helpers, playback, audio inspection, and opt-in reference anatomy.
- A file-based workflow for per-track source, sheet music, config, renders,
  stems, listening notes, and release assets.
- A collaboration surface where agents prepare candidates and the human owns
  every taste decision.

## What It Is Not

- Not a DAW replacement.
- Not a one-click music generator.
- Not a reusable genre rulebook.
- Not a place to archive failed candidates or scratch files.

## Current Workflow

```text
producer thesis
  -> per-track source edit
  -> render audition
  -> play / inspect waveform + spectrum
  -> human listening note
  -> revise or promote
```

Use project-local `./tmp/` for disposable work. Keep durable candidates under
`local/candidates/`, release assets under `local/releases/`, and production
source under `music/`.

## Core Commands

```bash
uv run setloom new T06 --title my-track --bpm 123 --key "E minor"
uv run setloom play path/to/audio.wav
uv run setloom inspect path/to/audio.wav --view all --out tmp/inspect.png
uv run setloom anatomize local/corpus/audio --layers
```

All Python work should go through the repo-local `uv` project. Do not create
side virtualenvs or install global tools for normal Setloom work.

## Repository Map

```text
AGENTS.md                  Instructions for coding agents.
docs/                      Short workflow and tooling notes.
music/tracks/              Older TNN track notes and per-track source.
music/T5-lux-in-umbra/     Production source harness for Lux in Umbra.
src/setloom/               Reusable CLI, MIDI/audio/theory, inspection,
                           scaffold, schema-loader, and anatomy primitives.
scripts/                   Local genAI and plotting helpers.
tests/                     Behavior tests for the reusable toolkit.
local/                     Gitignored corpus, candidates, releases, and lab data.
models/                    Gitignored model weights.
tmp/                       Gitignored scratch space for temporary experiments.
```

## Release Artifacts

The project values editable source over opaque bounces:

```text
sheet/source JSON + MIDI + stems + render code + listening notes
```

Audio files, proprietary samples, model weights, and disposable renders are not
committed unless a specific release workflow says otherwise.

## License

Core code, harness prompts, schemas, and automation logic are licensed under
AGPL-3.0-only.

Project documentation is licensed under CC BY-SA 4.0 unless explicitly marked
otherwise.

Generated music outputs belong to the user who creates them, subject to the
user's own third-party samples, models, and inputs.

Canonical license texts live in [LICENSE](LICENSE) and [LICENSES/](LICENSES/).
