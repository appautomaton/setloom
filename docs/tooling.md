<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Tooling

Setloom is open-source and keyboard-first. Python is the control plane:
composition, analysis, rendering, and the handoff to the listening gate all run
as code, so every step is scriptable, inspectable, and reproducible. The active
workstation target is macOS.

The guiding principle is simple: prefer open, scriptable tools over manual
clicking. A track should be buildable from files and commands, not from a
sequence of mouse gestures no one can replay.

## The stack

The audio work rests on a small, production-grade Python stack:

| Package | Role |
| --- | --- |
| `soundfile` | Read and write audio as NumPy arrays. |
| `scipy.signal` | Deterministic DSP: filters, resampling, envelopes, convolution. |
| `pedalboard` | Scriptable effects chains, and optional plug-in hosting. |
| `pyloudnorm` | LUFS measurement and loudness normalization. |
| `librosa` | Analysis: tempo, onset, chroma, spectral features. |
| `mido` | MIDI read and write for every part. |

SoX and FFmpeg handle conversion and export. SuperCollider drives scriptable
synth lanes: the [Lux in Umbra](../music/T5-lux-in-umbra/) harness routes
`scsynth` from source-controlled patches. Where heavier DSP helps, Faust and LV2
plug-ins are fair game. The list grows as tracks demand it, not before.

## Reference surfaces

User-owned tools like Logic Pro are welcome as *reference* surfaces, for checking
a timbre, auditioning a target, or browsing a sample library. They are not the
Setloom output path. The render that ships comes from source-controlled code, so
anyone with the repo can rebuild it; a DAW bounce can't be. Keeping that line
clear is what keeps the project reproducible.

## Generative models

Setloom is built to call generative models where they shine (melody, motif,
atmosphere, timbre, and fresh groove ideas) alongside deterministic rendering for
the parts that need exact control: mono-safe low end, clip prevention, phrase
alignment, reproducible stems.

The boundary that matters is not which tool you use; it's who decides. A model
can propose a hook, deterministic code can execute a mixdown, and neither one
owns the musical call. That belongs to the track's spec and, finally, to the
person at the listening gate.

ACE-Step and Magenta remain opt-in local generation experiments. The reference
tools offer these separate paths in the shared `uv` environment:

| Path | Dependency groups | Output and limits |
| --- | --- | --- |
| `transcribe --engine basic-pitch` | `transcription` | CoreML note candidates and pitch bends on macOS; no sustain pedal. |
| `transcribe --engine kong` | `kong` | Piano note candidates; the CLI exports notes only. T7 calls Kong directly to retain pedal. |
| `transcribe --engine fusion` | `kong`, `transcription` | Experimental note fusion; merges nearby attacks and suppresses suspected octave artifacts. Review timing and pitch by ear. |
| `anatomize --layers` | `anatomy` | MLX 53-stem separation on Apple Silicon. Overlapping stems are analysis lenses. |
| `anatomize --transcribe` | `anatomy`, `transcription` | Also exports per-stem and combined MIDI. The default mono route quantizes to sixteenth notes; `--transcriber bass=poly` selects Basic Pitch instead. |

Separation downloads and converts upstream weights once; inference uses the
cached MLX weights. Transcription caches track stem file metadata, routing,
timing, model root, and requested output formats. Remove the transcription
dossier after replacing model files in place.

`pitch-probes`, `pianist`, `supercollider`, and `ableton-mcp` support specific
local experiments or integrations. Enable them only when the corresponding
source needs them. Basic Pitch's `transcription` group stays CoreML-only.
Model locations and hardware limits live in [AGENTS.md](../AGENTS.md).
