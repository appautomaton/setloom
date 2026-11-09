<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Umklapp

**appautomaton** — an original techno piece. 134 BPM, 208 bars, ten voices, 6:18.537.

Released on [Bandcamp](https://appautomaton.bandcamp.com/track/umklapp-setloom-mix).
The [listening edition](https://umklapp.setloom.pages.dev/) offers the mix and
each voice alone.

This directory is the sole editable source. `source/render.py` synthesizes every
sound; it reads no sample, reference recording or external instrument.

## Source

The renderer reads four files:

| File | Holds |
| --- | --- |
| `source/Umklapp.mid` | Timing, pitch and velocity of every gesture. Each note carries a text ID. |
| `source/performance.json` | Form, sections, each voice's role, and the articulation for each note ID. |
| `source/patches.json` | Instruments, space, faders, phrase-level foreground curves and mastering. |
| `source/automation.npz` | Sampled control curves for timbre, pitch motion and form. |

Keep a note's text ID when editing MIDI; a gesture without matching articulation
stops the render. `source/mix_dsp.py` holds the voice and return processing.

The remaining files describe that performance and are not render inputs:
`source/midi/` exports each voice, `automation.json` and `form-motion.json`
record the keyframes and form behind the sampled curves, `arrangement.json`
repeats the score header, and `engineering.json` states the intent of the
foreground curves now stored in the patch. `score_io.py` writes MIDI and curves
when a change is authored in code.

| Voice | Role |
| --- | --- |
| Elastic kick | A centered A1 tail and the four-beat clock. |
| Low engine | A D1 clock that develops through stroke length and rare A1 turns. |
| Bending signal | The lead gesture: it falls, recoils and opens into connected phrase bends. |
| Metal lattice | Replies inside the signal's motion, then takes the foreground and hands it back. |
| Resonant drums | One interlocking membrane and rim phrase in the sixteenth-note pocket. |
| Metallic grain | Offbeat articulation and sparse quiet subdivisions. |
| Pressure gestures | Filtered noise and D-related resonance at selected transitions. |
| Residual field | D/A space, with one F color in the long suspension. |
| Relay murmurs | A soft reed-pluck that answers the two-bar cell. |
| Phase veil | Slow D/A voicings behind the moving surfaces. |

## Render

From the repository root, using the existing environment:

```sh
uv run --no-sync python -B music/umklapp/source/render.py
```

The full performance takes under a minute and writes `Umklapp.wav`, the float
premaster, ten stems and `report.json` to `tmp/umklapp/render/`. Its master is
sample-identical to the released one: -12.45 LUFS integrated, -1.30 dBTP, 6.3 LU.
`--start`, `--end` and `--out` render a bounded passage elsewhere; `--mix-only`
reapplies faders and mastering to voices already performed.

Required tools are the repository's Python packages and FFmpeg.

## Artwork and release files

[`artwork/cover-prompt-v1.txt`](artwork/cover-prompt-v1.txt) is the cover's
generation brief. The cover image, lossless master, listening-page source and
publication package are machine-local under `local/candidates/umklapp/`.
