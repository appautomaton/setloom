<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# AGENTS.md

Setloom is an open-source, keyboard-first tool and agentic harness for generating, tuning, mixing, and sequencing club tracks and DJ sets.

The working GitHub target is `appautomaton/setloom`; public branding is `Setloom by AppAutomaton`. The first style grammar is melodic/progressive techno, expanding toward house, tech house, and adjacent electronic lanes.

## Product Posture

- Setloom is a tool and agentic harness, not a traditional DAW clone, and not a one-click music generator.
- Setloom is built for rhythm-aware creators who have taste and listening judgment, but do not want to learn a full professional DAW workflow before creating.
- The human is the taste owner. Agents create candidates, revise them, and explain tradeoffs.
- Progress is roadmap progress: shipped specs, schemas, harness behavior, tests, renders, and review gates — never a human-compatible time estimate.
- Write everything — docs, prompts, specs, schemas, comments, public copy — in clear, direct, high-signal English; define domain terms without turning docs into theory lectures.

## Working Surfaces

- `setloom validate <spec>` — check a track spec YAML against schema and style pack.
- `setloom generate <spec>` — deterministic MIDI candidate variants into `candidates/`.
- `setloom anatomize [path]` — stem separation and anatomy dossiers into `anatomy/_dossiers/`; `--layers` adds the 53-stem lens.
- `setloom score <audio>` — grammar distance against the style pack, written beside the dossier.
- `scripts/generate_candidate.py`, `scripts/magenta_smoke.py` — local genai candidates into `candidates/genai/`.

## Context Routing

- Read `docs/README.md` first when orienting; `docs/project-charter.md` for product intent, audience, and non-goals.
- Read `docs/roadmap.md` before adding or changing roadmap scope.
- Read `docs/style-grammar.md` and `style-packs/*/style.yml` for music-generation behavior.
- Read `docs/workflow.md` for candidate, render, review, and listening-gate flow.
- Read `research/melodic-progressive-techno/dossier-guide.md` to interpret anatomize and score output.
- Read `research/melodic-progressive-techno/generation-recipes.md` before genai generation or model-store work.
- Read `research/melodic-progressive-techno/component-glossary.md` and `research/melodic-progressive-techno/taste-lexicon.md` for listening-note and review vocabulary.
- Read `docs/licensing.md`, `CONTRIBUTING.md`, and `TRADEMARKS.md` for policy-sensitive changes.

## Musical Rules

- Use GenAI primarily for melody, motif, harmonic direction, atmosphere, and variation.
- Use deterministic or rule-based systems for groove, kick, bass, timing, arrangement structure, and low-end safety.
- Never treat a generated mix as final without a human listening gate. Scores are technical distance, never the taste verdict.
- Do not imitate named artists. Use reference artists only to extract style grammar and review vocabulary.
- Favor club-functional arrangements: mixable intros/outros, clear phrase structure, controlled low end, and long-form energy flow.
- Treat `style-packs/*/style.yml` as executable style grammar. Treat `docs/style-grammar.md` as explanatory context.

## Tooling Rules

- Prefer open-source, CLI-controllable tools for the public core workflow; Python is the control plane. Paid tools the user already owns may serve local, ignored candidate artifacts.
- Proprietary DAWs (Logic Pro, Ableton Live, Pro Tools) are never required; they are local reference surfaces only, never the Setloom output path. Do not add other GUI tools without explicit approval. Full policy: `docs/tooling.md`.
- Do not install new Homebrew packages. Use the repo-local `uv` environment for Python work; keep any Node tooling inside this project.
- Keep the workflow keyboard-first: prefer Python, CLI, file import/export, MIDI, and scripts over manual clicking.
- The human listening gate must be no-click capable: agents prepare, route, and play audition audio; the human only listens and types comments.
- Generated artifacts should be file-based and reproducible: specs, MIDI, stems, renders, reports, and listening notes.

## ML Environment

- One repo-local `uv` environment for everything; models join through dependency groups (`anatomy`, `genai`). Never create per-model virtualenvs.
- Model weights live in the gitignored `models/` store; never commit audio, MIDI, or weights. Never override `HF_HOME` — it holds the user's Hugging Face login.
- `.references/` upstream clones are read-only working aids.
- Serialize heavy ML jobs — separation, generation, transcription — one at a time.
- Committed configs pin stock PyPI `torch`; machine-tuned wheels are local-only installs behind capability checks.
- Genai candidates go to `candidates/genai/` and never enter the corpus summary. Routing details and recipes: `docs/tooling.md`, `research/melodic-progressive-techno/generation-recipes.md`.

## Licensing Rules

- Core code, harness prompts, schemas, style grammars, and automation logic are AGPL-3.0-only unless explicitly marked otherwise.
- Project documentation is CC BY-SA 4.0 unless explicitly marked otherwise.
- Generated audio, MIDI, stems, arrangements, and sets belong to their creator, subject to third-party inputs they choose to use.
- Do not add proprietary samples, unclear sample packs, or model assets to the repo.
- Hosted services must comply with AGPL network source obligations and may not imply official status without permission.
- Contributions should use DCO sign-off unless the project later adopts a different policy.

## Agent Workflow

1. Read the local spec before changing behavior.
2. Keep edits scoped to the roadmap item being implemented.
3. Prefer schemas, prompts, tests, and file formats over vague prose.
4. When generating candidates, produce multiple options and a compact review report.
5. When reviewing candidates, separate technical checks from human taste decisions.
6. Do not hide uncertainty. If a musical choice requires listening, say so and route it to the listening gate.
7. Implement only the design stage the human commissioned; an approved artifact is not permission to start the next stage.
8. Never hoard. The tree carries only what serves current context — git history is the bookkeeping, generated artifacts are regenerable from spec, seed, and recipe, and every name says what a thing is today, not what it was scaffolded to be.
