# T7 — piano-solos

End-to-end solo-piano reconstruction. Raw piano audio in, our piano out.

You give it a solo-piano recording; it transcribes the performance, tidies the note and
pedal data, and plays it back on a sampled grand. The result keeps the original
performance's expressive timing and pedal. This is an audio-to-audio harness, **not** a
notation tool: there is no sheet music, and none is needed to hear it.

Status: working local audio reconstruction example. Each new recording still needs a
listening gate. Engraved sheet music remains out of scope.

## Pipeline

| Stage | Does | Tool |
|-------|------|------|
| 1. transcribe | audio -> raw MIDI with notes + sustain pedal | Kong (ByteDance MAESTRO), GPU mps->cpu |
| 2. clean | drop sub-30ms note blips; debounce sub-60ms pedal flutter | local, `mido` |
| 3. render | cleaned MIDI -> grand piano (faithful + expressive) | `fluidsynth` + Salamander, `pedalboard` room |
| 4. master | LUFS-normalize (stereo BS.1770) + true-peak limit | `setloom.audio.master` |

Two renders per piece: `*.faithful.piano.wav` (fluidsynth's own room) and
`*.expressive.piano.wav` (effects off, then a tasteful room + gentle top tame). The
two are audition options for the listening gate.

## The two lessons baked in

1. **Render the raw MIDI, never a notation export.** Kong captures the sustain pedal (CC64)
   and the rubato; the music21 note-only path silently drops both, which sounds dry and
   wrong. This harness goes audio -> MIDI -> audio and never touches notation.
2. **Clean, don't quantize.** The transcription is already clean (a handful of note blips,
   some pedal flutter). We remove only those. We never snap timing to a grid, because the
   grid is what kills the human feel.

## Run

From the repo root, in the shared uv env with the `kong` group. The `fluidsynth`
executable must be on `PATH`, and the checkpoint and soundfont below must exist:

```
uv run --group kong python music/T7-piano-solos/reconstruct.py PATH/TO/piano.mp3
```

Outputs land in `music/T7-piano-solos/out/<slug>/` (gitignored): `notes.raw.mid`,
`notes.clean.mid`, and the two renders. Transcription reuses an existing raw MIDI;
delete it when changing the source recording or checkpoint. Audition with
`uv run setloom play music/T7-piano-solos/out/<slug>/<slug>.expressive.piano.wav`.

Local release packages, artwork, and upload notes live under
`local/releases/T7-piano-solos/`; this source directory carries the reconstruction recipe.

Flags: `--lufs` (loudness target, default -16: dynamics-first for solo piano), `--min-note-ms`
(blip floor, default 30), `--min-pedal-ms` (pedal-flutter floor, default 60).

## Seams with setloom

- `setloom.audio` owns the loudness master (the harness's actual job: technical hygiene).
- Kong is called **directly**, not via `setloom transcribe`, because that path is pedal-blind.
- `mido` is used **directly**, not `setloom.midi`, because the latter is 4/4 PPQ-480 bar-grid
  only and cannot represent free-timing piano with pedal.

Heavy ML stays in the one shared uv env via the `kong` group; weights and the soundfont stay
in the gitignored `models/`. The folder's code is self-contained; its dependencies are not
vendored, by project policy.

## Assets and provenance

- Kong checkpoint: `models/piano-transcription/note_F1=0.9677_pedal_F1=0.8658.pth` —
  ByteDance high-resolution piano transcription, MAESTRO v3, https://zenodo.org/record/4034264
- Soundfont: `models/soundfonts/SalamanderGrandPiano-V3.sf2` — FreePats Salamander Grand
  Piano V3 (Yamaha C5), CC-BY 3.0, original by Alexander Holm.

Target compositions (public-domain repertoire) are study material; source recordings are
local only and never committed.

## Known limits

- Kong's pedal is binary on/off (no half-pedaling), and pedal estimation is the weakest link
  on dense, heavily-pedaled passages.
- The Salamander grand is one fixed timbre and room; it will not match the original
  recording's instrument.
- Expression beyond what Kong captured (melody voicing, phrase arcs) is not yet applied; it
  is the natural next lever if a piece sounds too even.
