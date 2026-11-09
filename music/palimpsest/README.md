<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Palimpsest

**appautomaton** — an original piece in G minor. 138 BPM, 176 bars, 5:06.087.

Released on [Bandcamp](https://appautomaton.bandcamp.com/track/palimpsest).

This directory is the sole editable source. The song is composed in
`source/score.json` and synthesized from fresh oscillators, seeded grain and
generated reverberation; no recorded audio is read.

## Source

| File | Holds |
| --- | --- |
| `source/score.json` | The composition: phrases, harmony, pulse cells, percussion, levels and colour over the form. |
| `source/patches.json` | Instrument, space and balance settings, including three kick designs. |
| `source/instruments.py` | The instruments. |
| `source/render.py` | Compiles the score into events, performs every part and writes the mixes. |
| `source/mastering.json`, `mastering.py` | Target, drive and limiter settings, and the mastering stage. |
| `palimpsest.mid` | The performance as MIDI, rewritten by each render. |
| `artwork/cover-prompt.txt` | The cover's final brief. |

The released song uses the Round kick. Defined and Soft remain in the patches
and render as alternative mixes.

| Part | Role |
| --- | --- |
| Kick | The low pulse. |
| Bass | The G foundation and its changing presence. |
| Main synth | The central gesture, its replies and resolution. |
| Harmony | Played harmonic phrases and their rests. |
| Inner texture | Resonant gestures within the harmonic field. |
| Percussion | Short strokes and softer brush accents. |
| Atmosphere | A slowly moving upper field. |
| Air | Fine grain above the groove. |
| Space | Shared reflections and longer decaying tails. |

## Render

From the repository root, using the existing environment, run the two stages in order:

```sh
uv run --no-sync python -B music/palimpsest/source/render.py
uv run --no-sync python -B music/palimpsest/source/mastering.py
```

Rendering takes about two minutes and writes float mixes and parts, their AAC
previews and a manifest under `tmp/palimpsest/`. Mastering then writes
`tmp/palimpsest/master/palimpsest.flac` and its AAC preview. That master is
sample-identical to the released one: -11.15 LUFS integrated, -1.28 dBTP, 13.5 LU.

Required tools are the repository's Python packages and FFmpeg.

## Release files

The cover image, lossless master, listening page and earlier revisions are
machine-local under `local/candidates/palimpsest/`.
