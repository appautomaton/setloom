<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Tooling

Setloom is open-source first and keyboard-first for its public core. Python is the control plane for alignment, MIDI, analysis, automation, render orchestration, candidate routing, reports, and listening-gate handoff.

User-owned proprietary tools can be useful as references, but they must not silently become the Setloom output path. Logic Pro may be inspected as a local reference surface for timbre vocabulary, preset categories, and short audition targets when the user has it installed. Logic Pro is not the Setloom final renderer, project-output chain, or required production dependency.

Do not add tacky third-party GUI synths, preset browsers, or DAWs just to search for timbre. If a GUI reference check is unavoidable and the user has Logic Pro, prefer Logic Pro over introducing another application. Prefer Python packages, CLI tools, MIDI files, scripts, and file-based automation over manual clicking.

Do not install new Homebrew packages for this project. Python work must use the repo-local `uv` environment. If Node tooling is needed, install and resolve it through this project's `node_modules`, not a global toolchain.

## Core Tooling Direction

| Layer | Preferred Tools | Purpose |
| --- | --- | --- |
| MIDI generation | Python, Mido, pretty_midi, music21 | Generate editable drums, bass, chords, arps, motifs, and fills. |
| Alignment and automation | Python packages, CLI scripts, file-based manifests | Analyze timing, route candidates, prepare audition files, and keep the human gate no-click capable. |
| Pattern systems | TidalCycles, Strudel | Explore club-functional rhythm and phrase patterns. |
| Synthesis and rendering | Headless, scriptable renderers orchestrated by Python | Render reproducible stems and demo mixes without a required DAW export path. |
| DSP and mixing | Python audio packages, Faust, LV2 plugins, SoX, FFmpeg | Build and apply effects, meters, exports, and checks. |
| DAW/reference surface | Optional Logic Pro inspection when installed; scriptable open-source paths when needed | Reference timbre categories and audition targets. Do not treat DAW bounces as Setloom core output. |

## Python Audio Stack

Setloom uses Python as the control plane for production automation. The first production-grade audio package set is:

| Package | Role |
| --- | --- |
| `soundfile` | Read and write audio as NumPy arrays. |
| `scipy.signal` | Filters, resampling, envelopes, convolution, and deterministic DSP primitives. |
| `pedalboard` | Scriptable effects chains: filters, compression, distortion, delay, reverb, limiting, and optional plug-in hosting. |
| `pyloudnorm` | LUFS measurement and loudness normalization for candidate reports and mastering checks. |
| `librosa` | Music/audio analysis: tempo, onset, chroma, spectral features, and reference diagnostics. |

Use this stack before reaching for ad hoc shell-only processing. SoX and FFmpeg remain useful export and inspection tools, but they should not be the only mix architecture.

## GenAI Boundary

Use GenAI for melody, motifs, harmonic direction, atmosphere, and variation.

Do not rely on GenAI audio as the primary source for kick, bass, groove, or low-end timing. Those parts need deterministic control.

For high-aesthetic lead timbre, especially vocal-substitute toplines, do not rely on scratch synthesis as the default. Use validated timbre references and automated, file-based render paths. Logic Pro can help name and audition the target sound class, but the Setloom candidate should still be produced by the harness unless the user explicitly asks for a separate Logic experiment. Procedural synthesis remains appropriate for kicks, basses, percussion, meters, rough textures, and deterministic tests.
