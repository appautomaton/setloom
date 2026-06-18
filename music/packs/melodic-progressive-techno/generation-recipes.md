<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Generation Recipes

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

Start from a track-specific musical thesis, not a pack-level prompt:

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
