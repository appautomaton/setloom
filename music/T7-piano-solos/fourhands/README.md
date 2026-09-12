# T7 — four hands

Completed duet-reconstruction source. The harness infers upper PRIMO and lower
SECONDO strata from a shared recording, shapes their dynamics and re-performs
on the Salamander grand while preserving captured ensemble timing.

## Performance

Kong supplies notes and pedal. An adaptive register seam with voice continuity
assigns two musical strata; it does not recover four literal hand staves.
Dynamic shaping includes per-player velocity variation. Note onsets retain the
players' timing, and a stable assignment near the seam keeps interlocking figures
together.

## Run

```sh
uv run --group kong python music/T7-piano-solos/fourhands/reconstruct.py PATH/TO/duet.mp3
```

The gitignored `tmp/t7-piano-fourhands/<slug>/` contains `notes.raw.mid`, `primo.mid`, `secondo.mid`,
`humanized.mid`, and three renders: mechanical, humanized and humanized-panned.
The panned diagnostic places SECONDO left and PRIMO right. Remove the raw MIDI
cache when changing the source or checkpoint.

Options: `--lufs` (default -16), `--k-macro` (1.4), `--noise` (velocity jitter),
`--blip-ms` (20), `--seed` and `--out`.

Kong is called directly to retain pedal; `mido` preserves free-timing events.
Fluidsynth and the shared checkpoint/soundfont are required. See
[runtime assets](../README.md#runtime-assets) for the required paths.
