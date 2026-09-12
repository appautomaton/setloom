<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Pulsus Noctis

**App Automaton** — 121 BPM, fourteen parts, 3:13.432.

[`Pulsus Noctis.mid`](Pulsus%20Noctis.mid) is the current independent performance:
4,122 notes plus piano phrasing and bowed-line expression as MIDI CC11. The
renderer reads this file directly. `instruments.json` holds instrument settings,
levels, bass pulse/section controls, duration and mastering. `instruments.py`
implements the instruments; `render.py` performs and mixes the song.

## Render

From the repository root, using the existing environment and an empty output directory:

```sh
UV_CACHE_DIR=tmp/uv-cache uv run --no-sync python -B music/pulsus-noctis/render.py \
  --out-dir tmp/pulsus-noctis-next
```

Outputs are `Pulsus Noctis.wav`, fourteen aligned float stems under `stems/`, and
`render.json` with signal measurements. There is no playback or DAW launch.

| Parts | Instrument |
| --- | --- |
| 01 keyboard harmony, 04 lead piano | FluidSynth / Salamander Grand Piano |
| 02 bass, 03 pitched percussion, 05 kick, 06 low drums | Programmed oscillators and envelopes |
| 07–11 percussion | Installed Logic instrument samples, played from MIDI |
| 12–13 bowed lines | VSCO 2 CE violin zones, including tuning, sustain loops and expression |
| 14 analog pluck | Saw oscillator, closing low-pass envelope and short release |

The piano's seventeen phrase rests are post-instrument CC11 expression gestures,
including the lift and re-entry; they do not add a new attack after each rest.
The bass pulse continues where its sustained notes require movement even when
the kick is absent. The master uses Setloom's shared lookahead limiting and file loudness meter.

## Mastering

The `mastering` section of `instruments.json` separates the intended output
level from the chosen processing: -9 LUFS target, +8 dB input drive, -0.6 dBTP
ceiling, 3 ms lookahead and 60 ms release. The target is a delivery check, not
an automatic gain command; changing it requires revisiting drive and dynamics.
This first reference-informed master uses the quieter end of the measured
techno corpus rather than inheriting the earlier -15.1 LUFS rendition.

The [current master](../../tmp/pulsus-noctis-mastering/Pulsus%20Noctis.wav)
measures -9.06 Integrated LUFS, -0.60 dBTP and 5.3 LU loudness range with FFmpeg.
`render.json` records requested settings, actual encoded-file measurements,
target error and peak compliance. The user approved this master on 12 September 2026 ("we are good on this one").
Earlier working renders have been removed after acceptance.

## Inputs and continuity

Required tools: repository Python packages, FluidSynth and FFmpeg. Independent
instrument assets live in `models/soundfonts/`, `models/vsco2-ce/` and the installed
Logic sample-library paths declared in `instruments.json`. `--assets` can point
to another models directory. Logic is not required to run or export this song.
Instrument notices are in [LICENSES/NOTICE](../../LICENSES/NOTICE).

The early [`gaia-original.mid`](gaia-original.mid) remains reference evidence.
Its retained keyboard, bass and percussion performances were carried forward;
the later six replacement parts were inherited from their existing MIDI. The
subsequent piano arrangement and two bowed lines had only audio preserved, so
those changes were recovered into this score. The old reference MIDI and all
previous song WAVs are excluded from the rendering chain.

The previous upload source is retained under `tmp/pulsus-noctis/soundcloud/`;
current acceptance applies to the reference-informed master linked above.

The complete renderer passed in an isolated directory with macOS explicitly
denying reads of Gaia MIDI, old stems, Logic track exports, corpus audio and
earlier test renders. Subsequent mastering regenerated the same instrumental
samples from MIDI. Obsolete auditions and stem copies have been removed; normal
rendering regenerates all fourteen stems.
