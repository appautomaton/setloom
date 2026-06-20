# Source Notes

Source-of-truth files for `T5 Lux in Umbra`.

- `manifest.json`
- `score.json`
- `pluck-synth.json`
- `kick-synth.json`
- `mix-plan.json`
- `remapped-bass-events.json`
- `midi/`

`score.json` is the sheet music/lane score. It contains the piano events, pluck
events, support notes, harmony cycle, and section role map. The renderer must
read this file; the score is not meant to live only in Python code.

`pluck-synth.json` records the SuperCollider pluck patch parameters, per-note
mapping, and section-aware timbre scenes. The SynthDef implementation lives in
`../harness/pluck.py`, but the patch configuration lives here.

`kick-synth.json` records the deterministic strict 123 BPM kick voice and 8-bar
rendering process. The renderer generates the kick from this source file; it
does not need a frozen kick WAV input.

`mix-plan.json` records lane gain, filter, bed, low-end, return, and
section-envelope configuration consumed by `../render.py`.

`remapped-bass-events.json` is the final bass score consumed by the renderer.
The renderer does not require external MIDI or candidate-local audio files.

`midi/` contains final MIDI exports generated from the tracked JSON score and
bass score. These files are for sharing, audit, and DAW inspection; they are not
external reference MIDI.
