<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# AGENTS.md

Setloom is an open-source music-production tool and agentic harness. Agents own
musical taste, creative judgment and production quality. The human directs and
judges the result; rejection requires substantive revision regardless of metrics.
Current user instructions take precedence over historical task contracts.

## Working principles

- **First principles:** start from the intended musical effect and the actual
  recording, performance, and sound. Choose tools after understanding the
  question. Historical reports are leads, not a substitute for fresh reasoning.
- **Long-term compounding:** carry forward supported musical decisions, editable
  performances and proven tools, including why and where they worked. Add
  abstractions after demonstrated reuse; leave room for musical judgment.
- Complete authorized work through patient internal revisions. Resolve routine
  uncertainty; ask when missing direction or authorization changes the outcome,
  while continuing independent work. Genre and past choices are examples,
  not musical defaults.
- Automation gathers evidence and executes understood operations. Examine
  passages for content the current explanation misses; revise failed explanations.
  Pipeline completion does not establish musical quality.
- Reference reconstruction stays with the primary agent. Do not delegate source
  comparison, musical inference or fidelity review to subagents.
- Keep composition, voice grouping, articulation and sound design in per-track
  source. Shared code supplies MIDI, DSP, analysis and rendering primitives.
- Inspect actual waveform, spectral, rhythm and stereo evidence where useful.
  Use auditory perception when available; plots or playback do not establish
  hearing. Honor playback preferences; no autoplay without authorization.
- The human directs and listens. Correct demonstrated flaws before auditions;
  do not require the user to operate the studio or inspect MIDI and charts.

## Context routing

Open the relevant skill or document section directly; use
[docs/README.md](docs/README.md) when the route is unclear. Load references for
the current question and reuse inspected context unless it has changed.

Skills hold reusable task guidance; tool references hold capabilities and units.
Read the production's current source and listening record before history or other
songs. Query large scores and analysis files by part, time range and needed
fields; keep raw events on disk.
Use `setloom <command> --help` for options. For license/policy changes, read
`LICENSE`, `CONTRIBUTING.md`, and `LICENSES/`.

## Tools and execution

- Prefer open, CLI/API-controllable tools for the public core. Python is the
  control plane. Authorized computer use is available when it serves the task;
  preserve editable source and the settings needed to repeat the result.
- Add CLI operations when they demonstrably save repeated code, without fixing
  a musical workflow in a wrapper.
- Full-song generative experiments are opt-in.
- For artwork, use the currently available image-generation skill/capabilities.
  Verify the delivered file and inspect it. Retain the prompt, source image,
  and editable typography/export work needed for later changes.
- Preserve existing user work. Approval of an artifact does not authorize a new
  stage or unrelated external action; follow the scope already commissioned.

## Environment and resources

- Use the one repo-local `uv` environment and dependency groups. Do not create
  side environments. Keep Node tooling in-project. System package installs need
  user authorization; project Python dependencies may be added when justified.
- Keep one torch version, currently **2.12.0**. Do not downgrade or fork it for
  an older dependency; port the dependency's inference code when necessary.
  Basic Pitch uses the native MLX FP32 runtime described in `docs/tooling.md`.
- Check actual resource pressure before heavy work. Serialize heavy separation,
  generation, transcription, and rendering jobs across PyTorch/MPS and MLX/Metal;
  both consume unified memory. Installed RAM is not an allocation budget.
- Weights live in gitignored `models/`; `.references/` clones are read-only.
  Do not override `HF_HOME`, which holds the user's login.

## Files and continuity

- Keep new track source, MIDI, analysis, separated reference estimates, renders
  and auditions under `tmp/<track>/`. Retained work uses the authorized stage
  under `local/` or `music/`; see [Workflow](docs/workflow.md#working-stages).
  Originals in `local/corpus/` do not confer retained status on derivatives.
  Naming, technical success or relative praise alone does not imply promotion.
  Audio, weights, and proprietary samples stay out of Git. MIDI is committable
  as track input; machine-local MIDI under `local/` or `tmp/` stays ignored.
- Tie listening feedback to the reviewed artifact; technical reports cannot
  invent or reset its verdict. Distinguish current state from history and direct
  observations from user reports.
- Keep temporary material needed for feedback or rebuilds. Remove obsolete
  scratch, rejected duplicates and instructions only after checking callers,
  rebuild inputs, asset provenance and ownership. Preserve useful source and
  credits; do not turn history into the next agent's task list.
