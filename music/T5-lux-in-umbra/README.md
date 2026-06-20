# T5 Lux in Umbra

Production source harness for `Lux in Umbra`.

`Lux in Umbra` means "light in shadow": piano/pluck melody emerging from a
dark, strict 123 BPM low-end bed.

This folder is the git-tracked source of truth for generating the track. It
contains code, sheet music, synth configuration, and mix configuration. It does
not track rendered sound files.

## Source Files

- `render.py` - small entrypoint.
- `export_midi.py` - exports auditable MIDI from the tracked JSON score.
- `harness/` - lane renderers and deterministic DSP.
- `source/score.json` - piano, pluck, support, harmony, and section roles.
- `source/pluck-synth.json` - SuperCollider pluck patch and timbre scenes.
- `source/kick-synth.json` - deterministic 123 BPM kick voice.
- `source/mix-plan.json` - lane gains, bed processing, section envelopes.
- `source/remapped-bass-events.json` - final bass score used by the renderer.
- `source/midi/` - final MIDI exports generated from the tracked JSON source.
- `source/manifest.json` - source recovery manifest and hashes.
- `artwork/cover-spec.md` - cover-art direction and generation note.

## Render

```bash
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=tmp/uv-cache uv run --no-sync python music/T5-lux-in-umbra/render.py
```

Generated audio lands in `music/T5-lux-in-umbra/render/` and is intentionally
ignored by git.

Expected render outputs:

- `render/full-mix.wav`
- `render/bed.wav`
- `render/stem-piano.wav`
- `render/stem-pluck.wav`
- `render/stem-support.wav`
- `render/stem-space.wav`
- `render/stem-bass.wav`
- `render/stem-kick.wav`
- `render/stem-top.wav`
- `render/render-report.txt`

## MIDI

```bash
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=tmp/uv-cache uv run --no-sync python music/T5-lux-in-umbra/export_midi.py
```

Tracked MIDI exports:

- `source/midi/full-arrangement.mid`
- `source/midi/lane-piano.mid`
- `source/midi/lane-pluck.mid`
- `source/midi/lane-support.mid`
- `source/midi/lane-bass.mid`
- `source/midi/lane-kick.mid`

These are exported from our source score. They are not external reference MIDI.

## Runtime Assets

The source harness is tracked here, but two machine-local runtime assets are
declared rather than vendored:

- SuperCollider `scsynth` at `/Applications/SuperCollider.app/Contents/Resources/scsynth`
- Logic Steinway sample folder at `/Users/ac/Music/Logic Pro Library.bundle/Samples/Keyboard/Acoustic Piano/Other`

If the piano samples are unavailable, the harness falls back to its deterministic
synthetic piano voice.

## Current Musical Contract

- Tempo: 123 BPM.
- Length: 120 bars, about 3:54.
- Key center: E minor.
- Main form: separated piano / pluck / support / space lanes with strict low-end
  bed and late peak.
- Pluck motif identity is preserved while timbre changes by section.
- Bass score preserves the approved rhythmic feel while using remapped pitches
  that support the E-minor lane plan.
