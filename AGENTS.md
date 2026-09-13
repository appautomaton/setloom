<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# AGENTS.md

Setloom is an open-source music-production tool and agentic harness. Agents are
responsible for musical taste, creative judgment, and production quality. The
human directs the work and judges whether the result succeeds. Rejected work
requires substantive revision; metrics or effort do not override that verdict.
Current user instructions take precedence over historical task contracts.

## Working principles

- **First principles:** start from the intended musical effect and the actual
  recording, performance, and sound. Choose tools after understanding the
  question. Historical reports are leads, not a substitute for fresh reasoning.
- **Long-term compounding:** carry forward supported musical decisions, editable
  performances, and tools that proved useful. Retain lessons that improve the
  next decision; add abstractions only when demonstrated reuse justifies them.
  Project guidance should supply missing context and reminders, leaving capable
  agents room to reason, design, and create. Carry forward why a method worked
  and where it applies; its previous implementation is not a musical default.
- Work patiently through concrete musical questions and complete the authorized
  scope. Use small internal passes without requiring approval of each fragment.
  Investigate routine uncertainty yourself; ask when missing direction or
  authorization materially changes the result, and continue independent work.
- Bring discerning taste and revise weak material proactively. Follow the brief
  whether it calls for faithful reconstruction, reinterpretation, or new music.
  Genre patterns and previous-track choices are examples, not global defaults.
- Use automation to gather evidence and execute understood operations. Inspect
  passages and challenge the musical explanation against content it does not
  yet account for. Revise the explanation when an approach keeps failing.
  A finished pipeline or passing technical check does not establish a good track.
- Keep composition, voice grouping, note selection, articulation, and sound
  design in per-track source. Shared code supplies reusable MIDI, DSP, analysis,
  and rendering primitives without imposing one musical recipe.
- Use available modalities deliberately: inspect waveforms, spectra, rhythm,
  and stereo behavior where they clarify the music, and use auditory perception
  when actually available. Playing audio for the human or inspecting plots does
  not mean you heard it. Honor playback preferences; do not autoplay without
  authorization.
- Keep the human's work to direction and listening. Own the production details
  and correct flaws evident from available source and render evidence before
  presenting an audition. Human listening is not routine technical QA; do not
  require MIDI or chart inspection.

## Context routing

Read [docs/README.md](docs/README.md), then only the material the task needs.
Shared guidance holds portable decision principles; tool/setup references hold
capabilities and operating limits; each production holds its musical decisions,
evidence and listening state. Examples answer specific implementation questions.
Use `setloom <command> --help` for available options. For license/policy changes,
read `LICENSE`, `CONTRIBUTING.md`, and `LICENSES/`.

## Tools and execution

- A CLI entry earns its place by exposing a consistent, convenient operation
  that demonstrably saves repeated code. Avoid wrappers that add choreography
  or substitute a fixed workflow for musical reasoning.
- Prefer open, CLI/API-controllable tools for the public core. Python is the
  control plane. Authorized computer use is available when it serves the task;
  preserve editable source and the settings needed to repeat the result.
- Choose tools for the current problem. Keep full-song generative experiments
  opt-in; they are not the default reference-reconstruction path.
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
  and auditions under `tmp/<track>/`, including named versions. `music/` holds
  productions the user has chosen to retain or promote there.
  Reserve `local/` for material the user considers good enough to retain in the
  project for the longer term. `local/reconstructions/` holds user-approved
  reconstruction baselines for later reinterpretation. User-supplied recordings
  already in `local/corpus/`
  do not confer that status on new derivatives. Retained candidates and releases
  use `local/candidates/` and `local/releases/` within their authorized scope. Follow
  the user's current stage direction and [Workflow](docs/workflow.md#working-stages);
  naming, technical success, or relative praise alone does not imply promotion.
  Audio, weights, and proprietary samples stay out of Git. MIDI is committable
  as track input; machine-local MIDI under `local/` or `tmp/` stays ignored.
- Keep temporary material while active feedback or rebuilds depend on it.
  Remove obsolete scratch after checking ownership and dependencies.
- Keep current state distinct from dated history. Associate listening feedback
  with the reviewed artifact; technical reports must not invent or reset that
  verdict. Record whether external state was observed or reported by the user.
- Remove rejected duplicates and obsolete instructions after checking callers,
  rebuild inputs, asset provenance, and other work's ownership. Preserve useful
  source and credits; do not keep a history pile as the next agent's task list.
