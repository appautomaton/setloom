# T7 four-hands

End-to-end piano-**duet** reconstruction. Raw four-hands audio in, our piano out. Sibling to the
solo `../reconstruct.py`.

A four-hands recording is two players merged into one audio stream. This harness estimates two
player strata, shapes their dynamics, and re-performs on
the Salamander grand, while **preserving the real ensemble timing** (the two players' actual
asynchrony) -- which is the four-hands feel.

## Pipeline

| Stage | Does | Tool |
|-------|------|------|
| 1. transcribe | audio -> flat MIDI (notes + pedal) | Kong (ByteDance MAESTRO), mps->cpu |
| 2. stratify | flat MIDI -> PRIMO (upper) + SECONDO (lower) | adaptive register seam + voice continuity |
| 3. ensemble | per-player dynamic shaping + small independent jitter; onsets preserved | local, numpy |
| 4. render | mechanical + humanized + panned aid | fluidsynth + Salamander, `setloom.audio` master |

**Two-stratum recovery** (not literal four-hand staves) and **dynamics-not-timing** humanization
are the load-bearing choices, from a Grok + Codex consult: on dense, constantly-crossing duet
textures full per-hand labels are under-determined, and the real ensemble timing is already
human, so the human touch goes into dynamics. The split is cell-sticky near the seam (voice
continuity) so an interlocking figure stays with one player.

## Run

```
uv run --group kong python music/T7-piano-solos/fourhands/reconstruct.py PATH/TO/duet.mp3
```

Outputs in `music/T7-piano-solos/fourhands/out/<slug>/` (gitignored):
`notes.raw.mid`, `primo.mid`, `secondo.mid`,
`humanized.mid`, and three renders -- `*.mechanical.piano.wav` (the strict split reference),
`*.humanized.piano.wav`, `*.humanized-panned.piano.wav` (a diagnostic placing
SECONDO left / PRIMO right). A/B the mechanical and humanized renders at the listening gate.
As in the solo harness, delete the cached raw MIDI when changing the source or checkpoint;
`fluidsynth` and the shared model assets are required.

Flags: `--lufs` (default -16), `--k-macro` (build amount, default 1.4), `--noise` (per-player
jitter sigma), `--blip-ms` (default 20), `--seed`, `--out`.

## Source notes

The output is our own rendering and does not redistribute the source recording. Reconstruct
works you have the right to use; clear the composition's status as appropriate for your release.

## Seams with setloom

`setloom.audio` owns the loudness master (stereo BS.1770 + true-peak limiter). Kong is called
directly (pedal-aware); `mido` directly (free-timing duet playing is not a 4/4 grid). Weights
and the soundfont live in the gitignored `models/`, shared with the solo harness.
