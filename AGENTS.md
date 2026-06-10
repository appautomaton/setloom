<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# AGENTS.md

Setloom is an open-source, keyboard-first tool and agentic harness for generating, tuning, mixing, and sequencing club tracks and DJ sets.

The working GitHub target is `appautomaton/setloom`. Public branding is `Setloom by AppAutomaton`.

Setloom starts with melodic/progressive techno as the first style grammar, then expands toward house, tech house, and adjacent electronic music lanes.

## Product Posture

- Setloom is a tool and agentic harness, not a traditional DAW clone.
- Setloom is not a one-click music generator.
- Setloom is built for rhythm-aware creators who have taste and listening judgment, but do not want to learn a full professional DAW workflow before creating.
- The human is the taste owner. Agents create candidates, revise them, and explain tradeoffs.
- Progress is roadmap progress: shipped specs, prompts, schemas, harness behavior, tests, renders, and review gates. Do not frame progress as a human-compatible time estimate.

## Language

- Project docs, prompts, specs, schemas, comments, and public-facing copy must be written in clear, elegant English.
- Keep writing direct and high-signal.
- Define domain terms when needed, but do not turn docs into music theory lectures.

## Context Routing

- Read `docs/README.md` first when orienting.
- Read `docs/project-charter.md` for product intent, audience, and non-goals.
- Read `docs/roadmap.md` before adding or changing roadmap scope.
- Read `docs/style-grammar.md` and `style-packs/*/style.yml` for music-generation behavior.
- Read `docs/workflow.md` for candidate, render, review, and listening-gate flow.
- Read `docs/licensing.md`, `CONTRIBUTING.md`, and `TRADEMARKS.md` for policy-sensitive changes.
- Read only the prompt file under `harness/prompts/` that matches the agent role being changed.

## Musical Rules

- Use GenAI primarily for melody, motif, harmonic direction, atmosphere, and variation.
- Use deterministic or rule-based systems for groove, kick, bass, timing, arrangement structure, and low-end safety.
- Never treat a generated mix as final without a human listening gate.
- Do not imitate named artists. Use reference artists only to extract style grammar and review vocabulary.
- Favor club-functional arrangements: mixable intros/outros, clear phrase structure, controlled low end, and long-form energy flow.
- Treat `style-packs/*/style.yml` as executable style grammar. Treat `docs/style-grammar.md` as explanatory context.

## Tooling Rules

- Prefer open-source, CLI-controllable tools for the public core workflow.
- Do not require Logic Pro, Ableton Live, Pro Tools, or other proprietary DAWs for the public core workflow.
- Use Python packages as the control plane for alignment, MIDI, analysis, automation, render orchestration, reports, and candidate routing.
- User-owned proprietary tools may be inspected as local reference surfaces when they help identify professional timbre vocabulary, preset categories, or audition targets. Logic Pro may be used this way when the user has it installed, but it is not the Setloom final renderer, project-output chain, or required production dependency.
- Do not describe Logic-rendered audio, Logic project exports, or DAW bounces as the core Setloom output path unless the user explicitly asks for that separate local experiment.
- Do not install, launch, or route work through tacky third-party GUI synths, preset browsers, or DAWs for timbre discovery without explicit user approval. If a GUI reference check is unavoidable, prefer the user's existing Logic Pro setup over adding another GUI tool.
- Do not install new Homebrew packages for this project. Use the repo-local `uv` environment only for Python work; if Node tooling is needed, keep `node_modules` inside this project.
- Keep the workflow keyboard-first where possible. Prefer Python, CLI, file import/export, MIDI, scripts, or other automation over manual clicking.
- The human listening gate must be no-click capable: agents prepare, route, and play audition audio when possible; the human only needs to listen and give typed comments.
- Open-source preference is not open-source purity: it must not block the user from using paid tools they already own for local, ignored candidate artifacts.
- Generated project artifacts should be file-based and reproducible where possible: specs, MIDI, stems, renders, reports, and listening notes.

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
