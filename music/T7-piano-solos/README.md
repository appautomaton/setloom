# T7 — piano solos

Completed piano-reconstruction work. This retained harness transcribes notes and
sustain pedal, removes brief transcription artifacts and performs the captured
timing on a sampled grand. Engraved notation is outside this implementation.

## Performance

| Stage | Behavior |
| --- | --- |
| Transcribe | Kong on MPS→CPU; retain notes, free timing and CC64 sustain |
| Clean | Remove sub-30 ms note blips and debounce sub-60 ms pedal flutter; no grid quantization |
| Render | Fluidsynth + Salamander; faithful and expressive room treatments |
| Master | `setloom.audio.master` for loudness and true-peak limiting |

The MIDI retains timing and pedal that a note-only notation export would omit.
`mido` handles the free-timing events directly; the bar-grid `setloom.midi` helper
is not used. Kong is called directly because the transcription CLI exports
notes without its sustain-pedal data.

## Run

Use the shared environment with the `kong` group and `fluidsynth` on `PATH`:

```sh
uv run --group kong python music/T7-piano-solos/reconstruct.py PATH/TO/piano.mp3
```

Retained raw and cleaned MIDI lives under `performances/<slug>/`. New outputs
and scratch MIDI go to `tmp/t7-piano-solos/<slug>/`; the renderer seeds its raw
MIDI cache from the retained performance when available. Clearing scratch does not discard the retained performance; deliberately revise
the retained MIDI when changing that musical source. Options include
`--lufs` (default -16), `--min-note-ms` (30) and `--min-pedal-ms` (60).

Published masters, artwork and upload records are retained locally under `published/`.
They are exports, not a second production source. No piano performance was
regenerated during this directory cleanup.
The [four-hands variant](fourhands/README.md) uses the same model and soundfont.

## Runtime assets

- Checkpoint: `models/piano-transcription/note_F1=0.9677_pedal_F1=0.8658.pth`
- Soundfont: `models/soundfonts/SalamanderGrandPiano-V3.sf2`

Source recordings and model/sample binaries remain local. Kong's pedal estimate
is binary, with no half-pedaling, and can be unreliable in dense passages. The fixed piano timbre
and room approximate the source instrument; additional melodic voicing and
phrase shaping are not implemented by this solo renderer.
