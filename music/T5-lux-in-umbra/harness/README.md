# Harness

Production render harness for `T5 Lux in Umbra`.

The package is intentionally local to this track. Shared Setloom utilities stay
small and technical; this folder owns the musical rendering choices for this
specific track.

Module map:

- `context.py` - source paths, timing constants, source JSON loading.
- `events.py` - typed lane events decoded from `source/score.json`.
- `dsp.py` - deterministic DSP helpers.
- `kick.py` - strict 123 BPM kick synthesis from `source/kick-synth.json`.
- `bass.py` - final remapped bass score rendering.
- `piano.py` - piano lane rendering, with a deterministic fallback voice.
- `pluck.py` - SuperCollider pluck lane rendering and timbre scenes.
- `texture.py` - support pad and space-return lanes.
- `bed.py` - kick/bass bed processing and returns.
- `runner.py` - top-level orchestration and render report.
