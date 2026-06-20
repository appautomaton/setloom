# MIDI Exports

These MIDI files are exported from the tracked JSON source in this folder.

- `full-arrangement.mid` - one format-1 MIDI with piano, pluck, support, bass,
  and kick tracks.
- `lane-piano.mid`
- `lane-pluck.mid`
- `lane-support.mid`
- `lane-bass.mid`
- `lane-kick.mid`

They are not external reference MIDI. They are auditable exports of our final
track source, regenerated with:

```bash
PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=tmp/uv-cache uv run --no-sync python music/T5-lux-in-umbra/export_midi.py
```
