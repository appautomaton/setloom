# App Automaton — Anti Gravitational Wave

Current editable production: **3:45.034**, with electric piano and the newly composed ending. The user described this version as ethereal, accepted it, and authorized replacing the production source on 10 September 2026. The previously published **5:45.838** audio is retained under `published/`. This directory is the sole editable production source.

`performance.mid` is the single editable 17-track performance. It contains the conductor, synth/body/bass/texture parts, percussion and FX, the later acoustic-piano pair, recovered intro percussion, and the new electric-piano lane. Normal rendering reads this MIDI directly; no composition or reconstruction script regenerates it.

The percussion opening develops for about 29 seconds. Electric piano fades in with the upper synth at 0:29.034, supports the actual Am/F/E phrasing with voiced chords and broken figures, and releases across the drum withdrawal at 0:51.434. The main kick return remains at 1:55.434. The last bass/drum return keeps its impact at 3:25.034; the EP reprises at 3:31.434, percussion withdraws in stages, and a held low A and final Am/add9 chord resolve the track after the last grounded accent at 3:41.034.

Rebuild from the repository root using the existing environment and an empty output directory:

```sh
UV_CACHE_DIR=tmp/uv-cache uv run --no-sync python -B music/anti-gravitational-wave/render.py \
  --out-dir tmp/anti-gravitational-wave-next
```

The default is `tmp/anti-gravitational-wave/`. The renderer writes `Anti Gravitational Wave.wav`
and `render.json`, then removes its intermediate MIDI/audio. `--keep-premaster` optionally
retains the float mix for mastering revisions. There is no playback or publishing.

`controls.json` carries fixed-second automation; `patch.json`, `piano-patch.json` and `electric-piano-patch.json` carry the instrument settings; `recipe.json` carries the piano mix gains and one `mastering` configuration. `render.py` projects the score into temporary synth and acoustic-piano inputs, adds the MIDI-driven FM/additive electric piano, and preserves the existing intermediate quantization and pre-master stereo processing. Per-track synthesis/import and mix preparation remain here; the shared `write_master` handles limiting, file export and measurement. The accepted notes, velocities, envelopes and gains are retained.

The [new full master](../../tmp/anti-gravitational-wave/Anti%20Gravitational%20Wave.wav)
measures -8.48 LUFS, -1.02 dBTP and 5.6 LU LRA, against a -8.5 LUFS target.
Its configured drive is +5.5 dB with 3 ms lookahead and 60 ms release. Requested
settings and actual encoded-file measurements are reported separately. MIDI,
instrument settings, piano bus gains and control curves were preserved. This
master is awaiting listening feedback; the earlier arrangement verdict remains
attached to its reviewed audio.

The full renderer passed under macOS restrictions denying reads from `local/`,
including corpus, candidates and releases. The published edition is not an input.

Runtime dependencies are the repository UV environment and `setloom.audio`, the existing FluidSynth CLI, and `models/soundfonts/SalamanderGrandPiano-V3.sf2`. The local electric-piano instrument needs no samples. The later acoustic-piano pair uses Alexander Holm's Salamander Grand Piano (Yamaha C5), FreePats SF2 conversion by Roberto, v3+20200602, licensed CC BY 3.0. Credits accompany the installed soundfont in `models/soundfonts/SalamanderGrandPiano-V3.readme.txt`. No candidate source, original recording, separated recording or earlier WAV is a rendering dependency.

`artwork/` retains the accepted cover and its editable export source. `published/`
holds historical publication exports and records, ignored by Git. Neither is a
second musical production or a rendering input. Corresponding local candidates,
source copies and stem caches have been removed.
