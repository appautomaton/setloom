<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# AGENTS.md

Setloom is an open-source, keyboard-first tool and agentic harness for generating, tuning, mixing, and sequencing club tracks and DJ sets. The human is the taste owner: agents create and revise candidates and explain tradeoffs; the human makes every listening decision. Progress is shipped specs and working harness behavior, never time estimates.

## Tool Drawer

These are available tools, not a required music-understanding pipeline.

- `setloom validate <spec>` — check a track spec against schema and lane pack. Specs live in `music/tracks/TNN/`.
- `setloom generate <spec>` — deterministic MIDI candidate variants into `local/candidates/`.
- `setloom anatomize [path] --layers` — 53-stem reference lens and technical dossiers.
- `setloom score <audio>` — optional technical diagnostic report beside the dossier; scores are not taste, truth, or style distance.
- `scripts/generate_candidate.py`, `scripts/magenta_smoke.py` — local genai experiments into `local/candidates/genai/`; they require explicit track-specific prompts.

## Context Routing

- Orient with `docs/README.md`; product intent and audience live in `docs/project-charter.md`; scope changes start at `docs/roadmap.md`.
- `music/packs/*/style.yml` is executable lane/hygiene scaffolding (`docs/style-grammar.md` explains the reset). Each pack carries its own evidence and guides: `music/packs/*/dossier-guide.md` to read anatomize/score output, `music/packs/*/generation-recipes.md` before genai or model-store work, `music/packs/*/component-glossary.md` and `music/packs/*/taste-lexicon.md` for review vocabulary.
- `docs/workflow.md` for the candidate-to-gate loop; `docs/tooling.md` for tool policy; `docs/licensing.md`, `CONTRIBUTING.md`, and `TRADEMARKS.md` before policy-sensitive changes.

## Musical Rules

- The harness owns **technical hygiene only**: mono safety, clip prevention, loudness target, mixable edges, phrase-grid alignment. Everything else — groove character, kick pattern, bass profile, rhythmic identity, energy arc, timbre — is a musical decision that belongs to the track spec and the taste owner, not the harness.
- The harness is mostly language: taste routing, producer judgment, and workflow discipline. Code paths are instruments on the desk. They are not doctrine.
- Producer judgment comes before rendering. Name the groove spine, motif cell, energy move, palette, and intended omissions before asking a generator to speak.
- GenAI excels at melody, motif, atmosphere, timbre, and variation. GenAI is also capable of novel groove ideas: seeded rhythmic identities, syncopated kick figures, unconventional bass motion. Deterministic generators are execution tools, not taste owners. Do not conflate "we render groove deterministically" with "groove cannot be creative."
- Style packs provide lane routing, technical-hygiene scaffolding, and review vocabulary; each track spec owns all song-specific musical choices. Do not apply pack defaults as musical constraints.
- Motifs are musical cells, not full-track obligations. Extract the smallest useful idea, place it against the track's tempo and form, then vary density, register, attack, and silence by section.
- Deletion is a production move. If a hat, clap, shaker, ride, riser, patch, or bus chain adds preset sheen or weakens the track, cut it. Do not defend a bad lane by turning it down.
- Reference study starts with listening notes. Low-confidence machine reports are navigation aids only; delete or replace any harness output that starts acting like musical authority. Reference anatomy is evidence, not a template. Use measurements to ask better listening questions; never reuse one global kick/bass pattern across songs. If the anatomy corpus is dominated by a single artist, treat its measurements as that artist's fingerprint, not genre law.
- Nothing is final without the human listening gate; scores are diagnostics, never the taste verdict.
- Never imitate named artists; references exist to study abstract moves and review vocabulary.
- Favor club-functional arrangements: mixable edges, clear phrase structure, controlled low end, long-form energy flow.

## Harness Skepticism

- Treat existing harness behavior as an implementation candidate, not authority.
- Before using any command, report, cache, pack rule, prompt, patch, bus chain, or generator path, decide whether it fits the current musical objective. If it does not, bypass it, deprecate it, or replace it.
- Do not preserve a tool just because it exists. Proof-of-concept paths stay explicit and opt-in until they prove they serve the current workflow.
- Harness scaffolding may provide events, form, or file routing while the sound itself comes from a scratch synth, external experiment, or hand-shaped process. That is valid when it serves the track.
- When tool suitability is uncertain, stop and use the question tool to ask the human for feedback or a directional choice. Do not silently continue, and do not keep the human in the dark.
- State confidence and provenance for machine-derived claims. Keep uncertain outputs in `/tmp` or another scratch root until they earn a durable place.

## Track Differentiation

When writing or finalizing a release spec, each new track must establish a distinct sonic fingerprint from everything already in the catalog. Before release-spec approval:

1. **Check prior track specs** — compare BPM, key, bass profile, kick pattern, energy arc, and style vector values.
2. **Diverge on at least three primary axes.** Same BPM + same bass profile across consecutive releases is a failure mode, not a safe default.
3. **Name the departure angle in the spec's `intent` block.** State explicitly how this track differs from prior releases. "Darker version of T04" is not a valid departure angle.

The corpus is evidence for study, not a lawbook. Your track must say something distinct, and the listening gate decides whether it works.

## Tooling Rules

- Open-source, CLI-controllable tools for the public core; Python is the control plane; keyboard-first, never manual clicking.
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
4. Do not hide uncertainty. If the uncertainty is about tool suitability, ask the human with the question tool before proceeding; if it is about taste, route it to the listening gate.
5. Implement only the design stage the human commissioned; an approved artifact is not permission to start the next stage.
6. Never hoard. The tree carries only what serves current context — git history is the bookkeeping, artifacts are regenerable from spec, seed, and recipe, and every name says what a thing is today.
