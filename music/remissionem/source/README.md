# Source and rebuilding

Remissionem has fourteen independently performed MIDI parts. `performance.mid`
is the rendering input; `performance.json` retains the authoring score and
instrument assignments. The complete renderer does not read release stems,
manifests, reference recordings or any prior rendered song.

From the repository root:

```sh
UV_CACHE_DIR=tmp/uv-cache uv run --no-sync python -B \
  music/remissionem/source/render.py --out-dir tmp/remissionem-next
```

The default destination is `tmp/remissionem/`. Use an empty scratch directory.
Outputs are `Remissionem (Setloom Remix).wav` and `render.json`; temporary piano
MIDI/audio is removed. `--keep-premaster` optionally retains a float mix for
mastering revisions. Normal rendering does not create a stem cache or re-author MIDI.

For score edits, change `performance.json` and deliberately run `author_midi.py`
to update the complete MIDI, individual MIDI files and arrangement index.
Alternatively edit `performance.mid` directly; the renderer reads those events.
Do not run the authoring command after direct MIDI edits unless its score has
also been updated.

Instrument and bus choices remain in `patch.json` and the instrument modules.
The `mastering` section is the only delivery loudness configuration: target,
input drive, peak ceiling, lookahead and release. `render.json` uses the shared
FFmpeg file meter to report requested and achieved values separately. The current
master measures -8.63 LUFS, -1.00 dBTP and 6.1 LU LRA against a -8.5 LUFS target.

Dependencies are the repository Python environment, FFmpeg, FluidSynth and the
Salamander soundfont declared in `patch.json`. The complete production passed
with macOS denying access to all of `local/`, including the release manifest
and stems. Historical publication exports are retained under `../published/`; the only
editable production source is here. Published audio is not a runtime dependency.
No playback or publication is part of this renderer.
