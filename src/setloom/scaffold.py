# SPDX-License-Identifier: AGPL-3.0-only
"""Track scaffolding: create a minimal, runnable track directory."""

from __future__ import annotations

from pathlib import Path


def spec_template(track_id: str, title: str, bpm: float, key: str) -> str:
    return f"""# SPDX-License-Identifier: AGPL-3.0-only
# {track_id} '{title}'. Edit everything below — these are starting defaults.

id: {track_id}
title: {title}
style_pack: melodic-progressive-techno
duration_profile: club_extended
seed: 0
bpm: {bpm:g}
key: {key}
energy: 5
duration_bars: 128

intent:
  summary: "Describe the musical thesis here."
  avoid: []

sections:
  intro: 16
  groove_a: 32
  break: 16
  drop: 32
  peak: 16
  outro: 16

palette: {{}}

style_vector:
  darkness: 5
  melodic_emotion: 5
  groove_hypnosis: 5
  cinematic_tension: 5
  bass_aggression: 5
  arrangement_patience: 5
  hook_density: 5
  vocal_presence: 0
  organic_texture: 5
  peak_time_pressure: 5

render_targets:
  midi: []
  stems: []
  demo_mix: true

human_gate:
  required: true
"""


def assemble_template(track_id: str, title: str) -> str:
    return f'''# SPDX-License-Identifier: AGPL-3.0-only
"""{track_id} '{title}' assembly.

Starting skeleton — fill in the musical content. The harness provides
primitives; this file owns the composition.

Run from the repo root:
    uv run --no-sync python music/tracks/{track_id}/assemble.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from setloom.audio import write_audio
from setloom.conductor import SCALES, chord_tones, degree_note, parse_key
from setloom.midi import DRUM_CHANNEL, NoteEvent, TICKS_PER_BAR, section_layout, write_part_midi
from setloom.schema import load_spec

ROOT = Path(__file__).resolve().parents[3]
SPEC = Path(__file__).with_name("spec.yml")
OUT = ROOT / "local/candidates/{track_id}"
SR = 44100


def main() -> int:
    spec = load_spec(SPEC)
    out_dir = OUT / f"seed-{{spec.seed}}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- MIDI ---
    # Build NoteEvent lists and write them with write_part_midi.
    # Each event is (channel, note, velocity, start_tick, duration_ticks).
    # Use section_layout(spec) for (start_bar, bars) per section.
    # Use parse_key(spec.key) + degree_note() for scale-degree pitches.
    # Example (commented out — uncomment and adapt):
    #   kick = [
    #       NoteEvent(DRUM_CHANNEL, 36, 110, bar * TICKS_PER_BAR, 120)
    #       for _, (start, bars) in section_layout(spec).items()
    #       for bar in range(start, start + bars)
    #   ]
    #   write_part_midi(out_dir / "kick.mid", spec, kick)

    # --- Audio ---
    # Render stems and demo mix using setloom.audio primitives.
    # See: write_audio, normalize_lufs, mono_below, highpass, lowpass, beat_pump_envelope.
    duration_s = spec.duration_bars * 4 * 60.0 / spec.bpm
    length = int(duration_s * SR)
    demo = np.zeros((length, 2), dtype=np.float32)
    write_audio(out_dir / "demo.wav", demo)

    print(f"wrote {{out_dir}}")
    print("reminder: candidates require human listening notes before approval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def listening_notes_template() -> str:
    return """# SPDX-License-Identifier: AGPL-3.0-only
# Listening notes for the human gate. Edit after each audition.

take: take-001
decision: revise
notes:
  groove: ""
  melody: ""
  energy: ""
requests: []
"""


def create_track(
    track_id: str,
    title: str,
    *,
    bpm: float = 128.0,
    key: str = "A minor",
    root: str | Path = ".",
) -> Path:
    """Create a minimal track directory with spec, assemble.py, and notes."""
    track_dir = Path(root) / "music/tracks" / track_id
    if track_dir.exists():
        raise FileExistsError(f"{track_dir} already exists")
    track_dir.mkdir(parents=True)
    (track_dir / "spec.yml").write_text(
        spec_template(track_id, title, bpm, key), encoding="utf-8"
    )
    (track_dir / "assemble.py").write_text(
        assemble_template(track_id, title), encoding="utf-8"
    )
    (track_dir / "listening-notes.yml").write_text(
        listening_notes_template(), encoding="utf-8"
    )
    return track_dir
