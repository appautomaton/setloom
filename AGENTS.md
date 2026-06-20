<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# AGENTS.md

Setloom is an open-source, keyboard-first tool and agentic harness for generating, tuning, mixing, and sequencing club tracks and DJ sets. The human is the taste owner: agents create and revise candidates and explain tradeoffs; the human makes every listening decision. Progress is shipped specs and working harness behavior, never time estimates.

Setloom is not yet a general automatic melodic-techno generator. Current value
comes from disciplined iteration: agents convert human feedback into concrete
source changes quickly, use external research when useful, render/listen/inspect,
and keep the workspace clean enough that the next pass can continue without
forensics. Do not pretend the harness has solved composition.

## Tool Drawer

The harness is a small, unopinionated toolkit plus opt-in diagnostics. It never composes the music — all musical composition lives in per-track source under `music/tracks/TNN/` or a named production harness such as `music/T5-lux-in-umbra/`.

- `setloom validate <spec>` — check a track spec against the schema and run the built-in technical-hygiene gate.
- `setloom new <id>` — scaffold a new track directory with a minimal spec, runnable `assemble.py`, and listening-notes template.
- `setloom play <audio>` — play an audio file for the listening gate (macOS `afplay`).
- `setloom anatomize [path] --layers` — 53-stem reference lens and technical dossiers.
- Importable primitives for per-track code: `setloom.midi` (MIDI read/write, tick/bar math, `NoteEvent`), `setloom.audio` (DSP hygiene: loudness, mono-safety, clip, filters, envelopes), `setloom.conductor` (music-theory math: key/scale parsing, chord-tone and scale-degree helpers).
- `scripts/generate_candidate.py`, `scripts/magenta_smoke.py` — local genai experiments into `local/candidates/genai/`; they require explicit track-specific prompts.

## Context Routing

- Orient with `docs/README.md`, then read only the referenced file needed for the task.
- `docs/workflow.md` covers the candidate-to-gate loop; `docs/tooling.md` covers tool policy.
- For policy-sensitive changes, read `LICENSE`, `LICENSES/`, `CONTRIBUTING.md`, and `TRADEMARKS.md`.

## Musical Rules

- The harness owns **technical hygiene only**: mono safety, clip prevention, loudness target, mixable edges. Everything else — groove character, kick pattern, bass profile, rhythmic identity, energy arc, timbre — belongs to the track spec and the taste owner.
- Code is unopinionated tooling. The harness ships primitives (MIDI, DSP hygiene, music-theory math) and opt-in diagnostics; it composes nothing. Each track's own source assembles the music. Opinion lives in the track spec, sheet/source files, and listening notes.
- Producer judgment comes before rendering. Name the groove spine, motif cell, energy move, palette, and intended omissions before writing the track's render code.
- GenAI excels at melody, motif, atmosphere, timbre, and variation, including novel groove ideas: seeded rhythmic identities, syncopated kick figures, unconventional bass motion. Per-track composition may call genai, external MIDI, scratch synthesis, and the toolkit primitives.
- Motifs are musical cells, not full-track obligations. Extract the smallest useful idea, place it against the track's tempo and form, then vary density, register, attack, and silence by section.
- Deletion is a production move. If a hat, clap, shaker, ride, riser, patch, or bus chain adds preset sheen or weakens the track, cut it. Do not defend a bad lane by turning it down.
- Reference study starts with listening notes. Machine reports are navigation aids only; delete or replace any harness output that starts acting like musical authority. Use measurements to ask better listening questions; never reuse one global kick/bass pattern across songs.
- Nothing is final without the human listening gate; machine reports and plots are diagnostics, never the taste verdict.
- Never imitate named artists; references exist to study abstract moves and review vocabulary.
- Favor club-functional arrangements: mixable edges, clear phrase structure, controlled low end, long-form energy flow.

## Harness Skepticism

- Treat existing harness behavior as an implementation candidate, not authority.
- Reason from the current situation before acting. Check the actual files,
  candidate state, user goal, and workspace cleanliness; do not operate from a
  stale mental model or a previous-track habit.
- Do not worship automation. Use code to make rendering reproducible and edits
  auditable, but do not prematurely freeze musical imagination into a generic
  generator, style recipe, or rigid abstraction.
- External musical reasoning is allowed and often useful. Grok/search/reference
  research can inform choices, but the agent must translate that advice into
  clear local source changes and listening tests; do not paste research as if it
  were execution.
- Before using any command, report, cache, prompt, patch, or tool path, decide whether it fits the current musical objective. If it does not, bypass it, deprecate it, or replace it.
- Do not preserve a tool just because it exists. Proof-of-concept paths stay explicit and opt-in until they prove they serve the current workflow.
- Do not make unilateral decisions when placement, scope, tool suitability,
  cleanup policy, or musical direction is uncertain. Use the question tool to
  ask for a directional choice and keep the human guiding the solution.
- State confidence and provenance for machine-derived claims. Keep uncertain outputs in project-local `./tmp/` until they earn a durable place.

## Track Differentiation

When writing or finalizing a release spec, each new track must establish a distinct sonic fingerprint from everything already in the catalog. Before release-spec approval:

1. **Check prior track specs** — compare BPM, key, bass profile, kick pattern, energy arc, and style vector values.
2. **Diverge on at least three primary axes.** Same BPM + same bass profile across consecutive releases is a failure mode, not a safe default.
3. **Name the departure angle in the spec's `intent` block.** State explicitly how this track differs from prior releases. "Darker version of T04" is not a valid departure angle.

The corpus is evidence for study, not a lawbook. Your track must say something distinct, and the listening gate decides whether it works.

## Tooling Rules

- Open-source, CLI-controllable tools for the public core; Python is the control plane; keyboard-first, never manual clicking.
- Agents do not unilaterally install system packages (Homebrew, global npm); propose the package and reason, and get human approval first. Prefer the one repo-local `uv` environment for Python; keep Node tooling in-project.
- Run Python through the repo-local `uv` project. Do not create side virtualenvs
  or scatter dependency state across the machine.
- The listening gate is no-click: agents prepare and play short audition audio; the human only listens and types.
- Everything generated is file-based and reproducible: specs, MIDI, stems, renders, reports, notes.

## ML Environment

- Models join the one `uv` env via dependency groups (`anatomy`, `genai`); never per-model virtualenvs. `.references/` clones are read-only.
- Weights live in gitignored `models/`; never commit audio, MIDI, weights, or proprietary samples. Never override `HF_HOME` — it holds the user's Hugging Face login.
- GPU use is allowed when it materially improves analysis or generation, but serialize heavy ML jobs — separation, generation, transcription, and GPU rendering — one at a time.
- Stage disposable ML/render scratch in project-local `./tmp/`, then clean it up after use; retain only named candidate artifacts in `local/candidates/`. Gitignored directories are not dumping grounds: keep `local/` organized under its named subdirs (`corpus/`, `candidates/`, `releases/`) and `./tmp/` for scratch. Never create ad-hoc top-level scratch dirs or hide scratch in system temp when project-local scratch is appropriate.
- Keep unified-memory headroom during heavy jobs and avoid workflows likely to approach the 80-90 GB danger zone on this machine.
- Committed configs pin stock PyPI `torch`; machine-tuned wheels stay local behind capability checks.
- Genai candidates land in `local/candidates/genai/` and never enter the corpus summary.

## Agent Workflow

1. Read the local spec or candidate source before changing behavior; keep edits scoped to the commissioned task.
2. Prefer schemas, tests, and file formats over vague prose; write clear, high-signal English everywhere.
3. Prepare multiple candidate options — per-track code, genai, external MIDI — with a compact review report; separate technical checks from taste decisions.
4. Do not hide uncertainty. If the uncertainty affects the path forward, ask the
   human with the question tool before proceeding; if it is about taste, route
   it to the listening gate.
5. Implement only the design stage the human commissioned; an approved artifact is not permission to start the next stage.
6. Never hoard. The tree carries only what serves current context — git history is the bookkeeping, artifacts are regenerable from spec, seed, and recipe, and every name says what a thing is today.
7. Clean rejected work promptly. If the human kills a candidate, failed render,
   stale doc, or misleading helper, remove or demote it instead of preserving it
   as workspace clutter.
