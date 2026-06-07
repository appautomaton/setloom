# SPDX-License-Identifier: AGPL-3.0-only
"""Musical invariant tests for the six part generators (SPEC AC7 + AC4 v2)."""

from collections import Counter
from pathlib import Path

import mido
import pytest

from setloom import midi
from setloom.parts import ALL_PARTS, part_rng
from setloom.parts.bass import (
    BASE_WEIGHTS,
    HIGH_PRESSURE_WEIGHTS,
    LOW_PRESSURE_WEIGHTS,
    articulation_weights,
    select_articulation_profile,
)
from setloom.parts.drums import PERC
from setloom.schema import load_spec

REPO_ROOT = Path(__file__).resolve().parents[1]
T01 = REPO_ROOT / "examples" / "tracks" / "T01" / "spec.yml"

KICK = 36

PROFILE_SEED_SWEEP = range(40)  # covers all three bass profiles per vector

# Style-vector classes exercising every articulation-weight branch.
VECTOR_UPDATES = {
    "mid_pressure": {},  # T01 default: bass_aggression 6, peak_time_pressure 6
    "high_pressure": {"bass_aggression": 9, "peak_time_pressure": 8},
    "low_pressure": {"bass_aggression": 2, "peak_time_pressure": 1},
}


@pytest.fixture(scope="module")
def spec():
    return load_spec(T01)


def _events(spec, part: str, seed: int | None = None, variant: int = 0):
    rng = part_rng(spec.seed if seed is None else seed, variant, part)
    return ALL_PARTS[part].generate(spec, rng)


def _kick_onsets(spec) -> set[int]:
    return {e.start_tick for e in _events(spec, "drums") if e.note == KICK}


def _vector_spec(spec, updates: dict[str, int]):
    """Copy of ``spec`` with style-vector fields overridden."""
    if not updates:
        return spec
    return spec.model_copy(
        update={"style_vector": spec.style_vector.model_copy(update=updates)}
    )


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


# --- Generator v2 invariants (SPEC AC4) ---


def test_articulation_weights_follow_style_vector(spec) -> None:
    assert articulation_weights(spec.style_vector) == BASE_WEIGHTS
    high = _vector_spec(spec, VECTOR_UPDATES["high_pressure"]).style_vector
    low = _vector_spec(spec, VECTOR_UPDATES["low_pressure"]).style_vector
    assert articulation_weights(high) == HIGH_PRESSURE_WEIGHTS
    assert articulation_weights(low) == LOW_PRESSURE_WEIGHTS
    assert max(HIGH_PRESSURE_WEIGHTS, key=HIGH_PRESSURE_WEIGHTS.get) == "rolling_16th_sub"
    assert min(LOW_PRESSURE_WEIGHTS, key=LOW_PRESSURE_WEIGHTS.get) == "rolling_16th_sub"


@pytest.mark.parametrize("vector_name", sorted(VECTOR_UPDATES))
def test_bass_never_on_kick_ticks_across_all_profiles(spec, vector_name) -> None:
    """Bass onsets avoid beat ticks (kick onsets) for every articulation profile."""
    variant_spec = _vector_spec(spec, VECTOR_UPDATES[vector_name])
    profiles_seen = set()
    for seed in PROFILE_SEED_SWEEP:
        profile = select_articulation_profile(variant_spec, part_rng(seed, 0, "bass"))
        profiles_seen.add(profile)
        events = _events(variant_spec, "bass", seed=seed)
        assert events, f"{vector_name} seed {seed}: bass produced no events"
        for event in events:
            assert event.start_tick % midi.PPQ != 0, (
                f"{vector_name}/{profile} seed {seed}: bass onset on a beat tick: {event}"
            )
    assert profiles_seen == {
        "rolling_16th_sub",
        "offbeat_eighth_pulse",
        "syncopated_pedal",
    }, f"{vector_name}: seed sweep missed a profile: {profiles_seen}"


@pytest.mark.parametrize("vector_name", sorted(VECTOR_UPDATES))
def test_bass_notes_leave_sidechain_gap(spec, vector_name) -> None:
    """Every bass note ends strictly before the next beat tick (kick-duck space)."""
    variant_spec = _vector_spec(spec, VECTOR_UPDATES[vector_name])
    for seed in PROFILE_SEED_SWEEP:
        for event in _events(variant_spec, "bass", seed=seed):
            next_beat = (event.start_tick // midi.PPQ + 1) * midi.PPQ
            end = event.start_tick + event.duration_ticks
            assert end < next_beat, (
                f"{vector_name} seed {seed}: bass note crosses into the next kick: {event}"
            )


def test_fills_only_in_final_two_bars_of_sections(spec) -> None:
    windows = []
    for _, (start_bar, bars) in midi.section_layout(spec).items():
        lo = midi.bar_to_tick(start_bar + max(0, bars - 2))
        hi = midi.bar_to_tick(start_bar + bars)
        windows.append((lo, hi))
    for seed in range(10):
        for event in _events(spec, "fills", seed=seed):
            assert any(lo <= event.start_tick < hi for lo, hi in windows), (
                f"seed {seed}: fill outside a section's final two bars: {event}"
            )


def test_perc_pattern_repeats_within_section(spec) -> None:
    """Percussion uses one repeating 2/4/8-bar pattern per section, off beat ticks."""
    perc_steps_by_bar: dict[int, set[int]] = {}
    for event in _events(spec, "drums"):
        if event.note != PERC:
            continue
        assert event.start_tick % midi.PPQ != 0, f"perc on a beat tick: {event}"
        bar, offset = divmod(event.start_tick, midi.TICKS_PER_BAR)
        perc_steps_by_bar.setdefault(bar, set()).add(offset // midi.SIXTEENTH_TICKS)
    for section, (start_bar, bars) in midi.section_layout(spec).items():
        for bar_in_section in range(bars - 8):
            bar = start_bar + bar_in_section
            assert perc_steps_by_bar.get(bar, set()) == perc_steps_by_bar.get(bar + 8, set()), (
                f"{section}: perc pattern not repeating between bars {bar} and {bar + 8}"
            )


def test_chords_follow_a_progression_in_drops(spec) -> None:
    """An 8-bar drop window carries >= 2 distinct chord root pitch classes."""
    by_onset: dict[int, list[int]] = {}
    for event in _events(spec, "chords"):
        by_onset.setdefault(event.start_tick, []).append(event.note)
    drop_sections = [
        (name, layout)
        for name, layout in midi.section_layout(spec).items()
        if name.startswith("drop")
    ]
    assert drop_sections, "T01 spec must contain a drop section"
    for name, (start_bar, _) in drop_sections:
        lo = midi.bar_to_tick(start_bar)
        hi = midi.bar_to_tick(start_bar + 8)
        roots = {min(notes) % 12 for tick, notes in by_onset.items() if lo <= tick < hi}
        assert len(roots) >= 2, f"{name}: static harmony, roots {roots}"


def test_arp_rests_at_phrase_boundaries(spec) -> None:
    """The last two 16ths of every full 16-bar arp phrase are silent."""
    onsets = {e.start_tick for e in _events(spec, "arp")}
    assert onsets, "arp produced no events"
    checked = 0
    for section, (start_bar, bars) in midi.section_layout(spec).items():
        if not section.startswith(("drop", "peak")):
            continue
        for phrase_start in range(0, bars - 15, 16):
            last_bar = start_bar + phrase_start + 15
            for step in (14, 15):
                tick = midi.bar_to_tick(last_bar) + step * midi.SIXTEENTH_TICKS
                assert tick not in onsets, f"{section}: no rest at phrase boundary tick {tick}"
                checked += 1
    assert checked, "T01 spec must contain a full 16-bar arp phrase"


def test_lead_motif_repeats_then_varies(spec) -> None:
    """Each full 16-bar lead phrase repeats one 2-bar statement, then varies it."""
    lead_events = _events(spec, "lead")
    assert lead_events, "lead produced no events"
    slot_ticks = 2 * midi.TICKS_PER_BAR
    phrases_checked = 0
    for section, (start_bar, bars) in midi.section_layout(spec).items():
        if not section.startswith(("break", "peak")):
            continue
        for phrase_start in range(0, bars - 15, 16):
            phrase_lo = midi.bar_to_tick(start_bar + phrase_start)
            phrase_hi = phrase_lo + 16 * midi.TICKS_PER_BAR
            statements: dict[int, list[tuple[int, int, int]]] = {}
            for event in lead_events:
                if not phrase_lo <= event.start_tick < phrase_hi:
                    continue
                slot, offset = divmod(event.start_tick - phrase_lo, slot_ticks)
                statements.setdefault(slot, []).append(
                    (offset, event.note, event.duration_ticks)
                )
            fingerprints = Counter(tuple(sorted(notes)) for notes in statements.values())
            assert fingerprints, f"{section}: empty 16-bar lead phrase at bar {phrase_start}"
            assert fingerprints.most_common(1)[0][1] >= 2, (
                f"{section}: motif not repeated within the phrase at bar {phrase_start}"
            )
            assert len(fingerprints) >= 2, (
                f"{section}: motif never varied within the phrase at bar {phrase_start}"
            )
            phrases_checked += 1
    assert phrases_checked, "T01 spec must contain a full 16-bar lead phrase"
