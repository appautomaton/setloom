<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Generation Recipes: Reset for Rebuild

The previous recipes are deprecated as musical guidance. They are retained only
as environment notes for local experiments.

## Environment Contract

All generation models live in the repo-local `uv` environment. Model weights
stay in gitignored `models/`; do not create per-model virtualenvs and do not
override `HF_HOME`.

```sh
uv sync --group anatomy --group genai
```

| Store | Path |
| --- | --- |
| ACE-Step weights | `models/acestep/` |
| Magenta RT weights | `models/magenta/` |
| Hugging Face hub cache | `models/hf/` |
| 53-stem BS-RoFormer weights | `models/roformer/` |

Serialize heavy jobs: do not run generation, separation, transcription, or GPU
rendering concurrently.

## Current Policy

Do not start a new track from a pack-level music prompt such as "123 BPM dark
hypnotic melodic techno." That path produced generic output and overfit stale
pack assumptions.

Start from a track-specific musical thesis:

```text
intent -> groove/rhythm thesis -> palette/timbre thesis -> motif behavior
       -> short audition -> listening note -> revision
```

Reference audio, MIDI, and separated stems are raw material for producer
decisions. They are not a route to copying a song. Extract the smallest useful
cell, choose the low-end spine, rebuild the form at the target BPM, and decide
what should disappear.

Good generation work may bypass stale patches, preset drum lanes, or the mix
bus entirely. A scratch synth in `tmp/` is acceptable when it exposes a better
sound. Promote only the idea that survives listening, not the experiment that
found it.

Use deletion early. If hats, claps, rides, shakers, risers, or inherited effects
make the result cheaper, remove them instead of polishing them.

Generated audio is candidate material only. It is scored for technical
diagnostics when useful, then judged by listening.

## Deprecated Recipes

| Recipe | Status |
| --- | --- |
| ACE-Step full-track instrumental from pack prompt | Deprecated as musical guidance |
| Vocal-only generation notes | Keep as local experiment provenance only |
| Magenta RT smoke clip | Keep as runtime smoke only |
| Groove-first catalog contrast | Superseded by per-track thesis work |

The next recipe file should be written after the local corpus and reference
study rebuild.
