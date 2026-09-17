# STRIDULATION (Setloom Mix)

**App Automaton · 150 BPM · 3:20.** The user reported publishing the song on
SoundCloud and explicitly authorized promotion. This directory is the sole
editable production source. The exact public track URL has not been supplied.

The structure follows the existing songs: source, artwork source and a song
README. For this song the user explicitly requested no rendered audio or cover
images in music/. Those deliverables remain under local/releases/stridulation.

## What to share

Share this whole directory, including source/*.npz and source/*.mid. It contains
code, note data, measured synthesis controls and text prompts, but no WAV, MP3,
M4A, sampled source recording or cover image. No ZIP is created by this workflow.

The two NPZ archives store oscillator amplitudes, tuning, and stereo control
curves. These small control arrays are required to reproduce the performance;
Python files alone would not reproduce the accepted instrument sound.

| Location | Purpose |
| --- | --- |
| rebuild.py | Complete synthesis → mix → master → WAV/AAC entry point |
| source/STRIDULATION.mid | The performed notes, timing and velocity |
| source/midi/ | Individual-part MIDI exports |
| source/performance.json | Event/control associations and score provenance |
| source/instruments.py, source/voice.py | Instruments and synthetic voice |
| source/*-controls.npz | Expressive and stereo control data |
| source/mix-design.json | Accepted source balance and resonance replies |
| source/mix-stage.json | Accepted whole-song EQ, balance and spatial movement |
| source/voice-score.json | Voice patches, phrase expression and effects |
| source/delivery.json | Mastering drive, limiting and delivery metadata |
| source/audio_runtime.py | Frozen project DSP helpers for this reproducible snapshot |
| artwork/ | Exact image-generation and subtitle-edit prompts |
| requirements.txt, environment.json | Python dependencies and the verified tool versions |
| verification.json | Full-rebuild identity check against the release files |

## Rebuild in Setloom

From the repository root, with the existing project environment:

```sh
uv run --no-sync python -B music/stridulation/rebuild.py \
  --out tmp/stridulation/rebuilt
```

Use a new or empty output directory. The entry point rejects any audio destination
inside this source directory. It renders all notes and synthesizes the sounds;
it does not read local/candidates, local/corpus, prior WAV files or a render cache.

Outputs are the final WAV, AAC M4A and rebuild-report.json. Intermediates are
removed after success; add --keep-intermediates to retain the mix and parts.
No playback, network request or publishing occurs.

Optional cover embedding uses a supplied image outside this source directory:

```sh
uv run --no-sync python -B music/stridulation/rebuild.py \
  --out tmp/stridulation/rebuilt-with-cover \
  --cover "local/releases/stridulation/artwork/stridulation-setloom-mix-cover.png"
```

The image is optional for rebuilding audio. Supply the exact retained cover to
reproduce the artwork-bearing M4A container as well.

## Rebuild after copying this folder elsewhere

Use a Python environment with the packages in requirements.txt and FFmpeg on
PATH. This directory has no import dependency on the rest of the Setloom repo.
Run from the copied directory, with an output directory outside it:

```sh
python -B rebuild.py --out ../stridulation-render
```

Environment.json records the versions used for byte-identical verification.
Different encoders or numerical-library versions may produce different bytes;
the report records the resulting files and loudness measurements.

## Editing

Normal rebuilding reads the combined MIDI without regenerating it. Edit that
MIDI directly, or edit performance.json and explicitly run source/midi_io.py to
export new combined and per-part MIDI. Preserve event identifiers that associate
notes with their controls. Reconcile direct MIDI edits before exporting from JSON.

The current arrangement, resonance replies and voice are the approved Mix 01
performance. Source/render_instruments.py recreates it; source/render.py applies
the whole-song mixing stage. All audio-render entry points require an output
folder outside this directory. Artwork prompts preserve the visual concept, but
image generation is nondeterministic and is not part of audio rebuilding.

## Verified release

A complete regeneration produced byte-identical WAV and M4A files on the recorded
environment, using the retained cover. WAV: -8.90 LUFS, -2.16 dBTP; AAC: -8.91 LUFS,
-1.83 dBTP. Both are stereo 44.1 kHz and exactly 200 seconds. The WAV is PCM24;
the AAC target is 320 kbps. The source migration changed no musical content.

The SoundCloud release was reported by the user; it was not uploaded or verified
online by this agent. Publication files and copy remain in local/releases; older
listening comparisons and existing source archives are historical evidence.
