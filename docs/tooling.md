<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Tooling

Setloom is open-source first and keyboard-first for its public core. Python is the control plane for MIDI, analysis, automation, candidate routing, reports, and listening-gate handoff.

User-owned proprietary tools can be useful as references, but they must not silently become the Setloom output path. Logic Pro may be inspected as a local reference surface for timbre vocabulary, preset categories, and short audition targets when the user has it installed. Logic Pro is not the Setloom final renderer, project-output chain, or required production dependency.

Do not add tacky third-party GUI synths, preset browsers, or DAWs just to search for timbre. If a GUI reference check is unavoidable and the user has Logic Pro, prefer Logic Pro over introducing another application. Prefer Python packages, CLI tools, MIDI files, scripts, and file-based automation over manual clicking.

Do not install new Homebrew packages for this project. Python work must use the repo-local `uv` environment. If Node tooling is needed, install and resolve it through this project's `node_modules`, not a global toolchain.

## Core Tooling Direction

| Layer | Preferred Tools | Purpose |
| --- | --- | --- |
| MIDI composition | Python, Mido, pretty_midi, music21 | Compose and edit MIDI for any part. |
| Alignment and automation | Python packages, CLI scripts, file-based manifests | Analyze timing, route candidates, prepare audition files, and keep the human gate no-click capable. |
| Synthesis and rendering | Headless, scriptable renderers orchestrated by Python | Render reproducible stems and demo mixes without a required DAW export path. |
| DSP and mixing | Python audio packages, Faust, LV2 plugins, SoX, FFmpeg | Build and apply effects, meters, exports, and checks. |
| DAW/reference surface | Optional Logic Pro inspection when installed; scriptable open-source paths when needed | Reference timbre categories and audition targets. Do not treat DAW bounces as Setloom core output. |

## Python Audio Stack

The production-grade audio package set is:

| Package | Role |
| --- | --- |
| `soundfile` | Read and write audio as NumPy arrays. |
| `scipy.signal` | Filters, resampling, envelopes, convolution, and deterministic DSP primitives. |
| `pedalboard` | Scriptable effects chains: filters, compression, distortion, delay, reverb, limiting, and optional plug-in hosting. |
| `pyloudnorm` | LUFS measurement and loudness normalization for candidate reports and mastering checks. |
| `librosa` | Music/audio analysis: tempo, onset, chroma, spectral features, and reference diagnostics. |

Use this stack before reaching for ad hoc shell-only processing. SoX and FFmpeg remain useful export and inspection tools, but they should not be the only mix architecture.

## ML Environment

All machine learning runs in the one repo-local `uv` environment. Model integrations join it through dependency groups (`uv sync --group anatomy --group genai`); per-model virtualenvs are never created.

Model weights live in the gitignored project store:

| Store | Path | Routed by |
| --- | --- | --- |
| ACE-Step weights | `models/acestep/` | `ACESTEP_CHECKPOINTS_DIR` |
| Magenta RT weights | `models/magenta/` | `MAGENTA_HOME` |
| Hugging Face hub cache | `models/hf/` | `HF_HUB_CACHE` |
| 53-stem BS-RoFormer weights | `models/roformer/` | active `anatomize --layers` reference lens |

Never override `HF_HOME`: it holds the user's Hugging Face login token. Route caches with `HF_HUB_CACHE` only.

Upstream reference clones under `.references/` are read-only working aids; their conflicting Python and torch pins are exactly why models are ported into this environment instead of run in theirs. Stale upstream pins are resolved in `pyproject.toml` (`[tool.uv] override-dependencies`, `[[tool.uv.dependency-metadata]]`) with the reasoning kept next to each override.

Committed configs pin stock PyPI `torch`; machine-tuned wheels are local installs only, with optimized code paths gated on capability checks (for example `"+m5max" in torch.__version__`). Heavy model jobs — 53-stem layer analysis, generation, transcription — run one at a time, never concurrently.

## GenAI Boundary

Use GenAI for musical ideas when it helps: melody, motifs, atmosphere, timbre, and groove directions. Do not let GenAI, deterministic code, or a style pack silently own the musical decision — that belongs to the track spec and the listening gate.

Deterministic rendering remains useful for execution and technical control: mono-safe low end, reproducible MIDI/stems, clip prevention, phrase alignment, and audition packaging.
