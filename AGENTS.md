<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# AGENTS.md

Setloom is an open-source, keyboard-first tool and agentic harness for generating, tuning, mixing, and sequencing club tracks and DJ sets. The human is the taste owner: agents create and revise candidates and explain tradeoffs; the human makes every listening decision. Progress is shipped specs and working harness behavior, never time estimates.

## Working Surfaces

- `setloom validate <spec>` — check a track spec against schema and style pack. Specs live in `music/tracks/TNN/`.
- `setloom generate <spec>` — deterministic MIDI candidate variants into `local/candidates/`.
- `setloom anatomize [path]` — stem separation and dossiers into `local/corpus/dossiers/`; `--layers` adds the 53-stem lens.
- `setloom score <audio>` — grammar distance against the style pack, written beside the dossier.
- `scripts/generate_candidate.py`, `scripts/magenta_smoke.py` — local genai candidates into `local/candidates/genai/`.

## Context Routing

- Orient with `docs/README.md`; product intent and audience live in `docs/project-charter.md`; scope changes start at `docs/roadmap.md`.
- `music/packs/*/style.yml` is executable grammar (`docs/style-grammar.md` explains it). Each pack carries its own evidence and guides: `music/packs/*/dossier-guide.md` to read anatomize/score output, `music/packs/*/generation-recipes.md` before genai or model-store work, `music/packs/*/component-glossary.md` and `music/packs/*/taste-lexicon.md` for review vocabulary.
- `docs/workflow.md` for the candidate-to-gate loop; `docs/tooling.md` for tool policy; `docs/licensing.md`, `CONTRIBUTING.md`, and `TRADEMARKS.md` before policy-sensitive changes.

## Musical Rules

- GenAI owns melody, motif, atmosphere, and variation; deterministic systems own groove, kick, bass, timing, structure, and low-end safety.
- Style packs provide grammar, constraints, and review vocabulary; each track spec owns song-specific groove/generator choices. Do not claim a bespoke groove unless `spec.yml` or the generator path actually differs for that track.
- Reference anatomy is evidence, not a loop library. Convert it into constraints and track-level plans, never into one global kick/bass template reused across songs.
- Nothing is final without the human listening gate; scores are technical distance, never the taste verdict.
- Never imitate named artists; references exist to extract grammar and review vocabulary.
- Favor club-functional arrangements: mixable edges, clear phrase structure, controlled low end, long-form energy flow.

## Tooling Rules

- Open-source, CLI-controllable tools for the public core; Python is the control plane; keyboard-first, never manual clicking.
- Proprietary DAWs are local reference surfaces only — never required, never the output path (`docs/tooling.md`).
- No new Homebrew packages; one repo-local `uv` environment for everything; Node tooling stays in-project.
- The listening gate is no-click: agents prepare and play short audition audio; the human only listens and types.
- Everything generated is file-based and reproducible: specs, MIDI, stems, renders, reports, notes.

## ML Environment

- Models join the one `uv` env via dependency groups (`anatomy`, `genai`); never per-model virtualenvs. `.references/` clones are read-only.
- Weights live in gitignored `models/`; never commit audio, MIDI, weights, or proprietary samples. Never override `HF_HOME` — it holds the user's Hugging Face login.
- GPU use is allowed when it materially improves analysis or generation, but serialize heavy ML jobs — separation, generation, transcription, and GPU rendering — one at a time.
- Stage disposable ML/render scratch in `/tmp` or another temp root, then clean it after use; retain only named candidate artifacts in `local/candidates/`.
- Keep unified-memory headroom during heavy jobs and avoid workflows likely to approach the 80-90 GB danger zone on this machine.
- Committed configs pin stock PyPI `torch`; machine-tuned wheels stay local behind capability checks.
- Genai candidates land in `local/candidates/genai/` and never enter the corpus summary.

## Agent Workflow

1. Read the local spec before changing behavior; keep edits scoped to the roadmap item.
2. Prefer schemas, tests, and file formats over vague prose; write clear, high-signal English everywhere.
3. Generate multiple candidate options with a compact review report; separate technical checks from taste decisions.
4. Do not hide uncertainty — route musical judgment to the listening gate.
5. Implement only the design stage the human commissioned; an approved artifact is not permission to start the next stage.
6. Never hoard. The tree carries only what serves current context — git history is the bookkeeping, artifacts are regenerable from spec, seed, and recipe, and every name says what a thing is today.
