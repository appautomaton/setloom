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
- Serialize heavy ML jobs — separation, generation, transcription — one at a time.
- Committed configs pin stock PyPI `torch`; machine-tuned wheels stay local behind capability checks.
- Genai candidates land in `local/candidates/genai/` and never enter the corpus summary.

## Agent Workflow

1. Read the local spec before changing behavior; keep edits scoped to the roadmap item.
2. Prefer schemas, tests, and file formats over vague prose; write clear, high-signal English everywhere.
3. Generate multiple candidate options with a compact review report; separate technical checks from taste decisions.
4. Do not hide uncertainty — route musical judgment to the listening gate.
5. Implement only the design stage the human commissioned; an approved artifact is not permission to start the next stage.
6. Never hoard. The tree carries only what serves current context — git history is the bookkeeping, artifacts are regenerable from spec, seed, and recipe, and every name says what a thing is today.
