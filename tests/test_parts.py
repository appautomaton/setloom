# SPDX-License-Identifier: AGPL-3.0-only
"""Musical invariant tests for the six part generators (SPEC AC7)."""

from pathlib import Path

import mido
import pytest

from setloom import midi
from setloom.parts import ALL_PARTS, part_rng
from setloom.schema import load_spec

REPO_ROOT = Path(__file__).resolve().parents[1]
T01 = REPO_ROOT / "examples" / "tracks" / "T01" / "spec.yml"

KICK = 36


@pytest.fixture(scope="module")
def spec():
    return load_spec(T01)


def _events(spec, part: str, seed: int | None = None, variant: int = 0):
    rng = part_rng(spec.seed if seed is None else seed, variant, part)
    return ALL_PARTS[part].generate(spec, rng)


def _kick_onsets(spec) -> set[int]:
    return {e.start_tick for e in _events(spec, "drums") if e.note == KICK}


def test_all_parts_registered_and_nonempty(spec) -> None:
    assert set(ALL_PARTS) == {"drums", "bass", "chords", "arp", "lead", "fills"}
    for part in ALL_PARTS:
        assert _events(spec, part), f"{part} produced no events for T01"


def test_kick_on_every_beat_in_drop_and_peak(spec) -> None:
    kicks = _kick_onsets(spec)
    for section, (start_bar, bars) in midi.section_layout(spec).items():
        if not section.startswith(("drop", "peak")):
            continue
        for bar in range(start_bar, start_bar + bars):
            for beat in range(4):
                tick = midi.beat_to_tick(bar, beat)
                assert tick in kicks, f"missing kick at {section} bar {bar} beat {beat}"


def test_bass_never_shares_tick_with_kick_in_drops(spec) -> None:
    kicks = _kick_onsets(spec)
    bass_onsets = {e.start_tick for e in _events(spec, "bass")}
    for section, (start_bar, bars) in midi.section_layout(spec).items():
        if not section.startswith("drop"):
            continue
        lo = midi.bar_to_tick(start_bar)
        hi = midi.bar_to_tick(start_bar + bars)
        drop_bass = {t for t in bass_onsets if lo <= t < hi}
        assert drop_bass, f"no bass onsets in {section}"
        assert not (drop_bass & kicks), f"bass collides with kick in {section}"


def test_events_inside_grid(spec) -> None:
    end = midi.total_ticks(spec)
    for part in ALL_PARTS:
        for event in _events(spec, part):
            assert event.start_tick >= 0, f"{part}: onset before tick 0: {event}"
            assert event.start_tick + event.duration_ticks <= end, f"{part}: past end: {event}"
            assert event.start_tick % midi.SIXTEENTH_TICKS == 0, f"{part}: off grid: {event}"


def test_written_files_span_all_bars(spec, tmp_path) -> None:
    end = midi.total_ticks(spec)
    for part in ALL_PARTS:
        path = tmp_path / f"{part}.mid"
        midi.write_part_midi(path, spec, _events(spec, part))
        loaded = mido.MidiFile(str(path))
        assert loaded.ticks_per_beat == midi.PPQ
        tick = 0
        end_of_track_tick = None
        for message in loaded.tracks[0]:
            tick += message.time
            if message.type == "end_of_track":
                end_of_track_tick = tick
        assert end_of_track_tick == end, f"{part}: end_of_track {end_of_track_tick} != {end}"


def test_determinism_same_seed_identical(spec) -> None:
    for part in ALL_PARTS:
        assert _events(spec, part) == _events(spec, part), f"{part} not deterministic"


def test_seed_divergence(spec) -> None:
    other = spec.seed + 1
    drums_differ = _events(spec, "drums") != _events(spec, "drums", seed=other)
    lead_differs = _events(spec, "lead") != _events(spec, "lead", seed=other)
    assert drums_differ or lead_differs
