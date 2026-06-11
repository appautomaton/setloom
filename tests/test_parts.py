# SPDX-License-Identifier: AGPL-3.0-only
"""Musical invariant tests for the part generators (SPEC AC7 + AC4 v2 + roster AC1)."""

from collections import Counter
from pathlib import Path

import mido
import pytest

from setloom import midi
from setloom.parts import ALL_PARTS, part_rng
from setloom.parts.base import parse_key, root_note
from setloom.parts.bass import (
    BASE_WEIGHTS,
    HIGH_PRESSURE_WEIGHTS,
    LOW_PRESSURE_WEIGHTS,
    articulation_weights,
    bass_generation_label,
    select_articulation_profile,
)
from setloom.parts.clap_ride import CLAP, RIDE
from setloom.parts.drums import PERC
from setloom.parts.fx import IMPACT_OCTAVE, IMPACT_VELOCITY, RISER_BARS
from setloom.schema import load_spec

REPO_ROOT = Path(__file__).resolve().parents[1]
T01 = Path(__file__).resolve().parent / "fixtures" / "spec-t01.yml"
T02 = Path(__file__).resolve().parent / "fixtures" / "spec-t02.yml"
T04 = REPO_ROOT / "music/tracks/T04/spec.yml"

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


def _events_with_pack(spec, part: str, pack, seed: int | None = None, variant: int = 1):
    rng = part_rng(spec.seed if seed is None else seed, variant, part)
    return ALL_PARTS[part].generate(spec, rng, pack=pack)


def _kick_onsets(spec) -> set[int]:
    return {e.start_tick for e in _events(spec, "drums") if e.note == KICK}


def _vector_spec(spec, updates: dict[str, int]):
    """Copy of ``spec`` with style-vector fields overridden."""
    if not updates:
        return spec
    return spec.model_copy(
        update={"style_vector": spec.style_vector.model_copy(update=updates)}
    )


def _bar_signatures(events) -> set[tuple[tuple[int, int, int, int], ...]]:
    by_bar: dict[int, list[tuple[int, int, int, int]]] = {}
    for event in events:
        bar, offset = divmod(event.start_tick, midi.TICKS_PER_BAR)
        step = offset // midi.SIXTEENTH_TICKS
        by_bar.setdefault(bar, []).append((step, event.note, event.duration_ticks, event.velocity))
    return {tuple(sorted(rows)) for rows in by_bar.values()}


def test_all_parts_registered_and_nonempty(spec) -> None:
    assert set(ALL_PARTS) == {
        "drums",
        "bass",
        "chords",
        "arp",
        "lead",
        "counterline",
        "fills",
        "pad",
        "shaker",
        "clap_ride",
        "fx",
    }
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


def test_perc_pattern_keeps_kick_lane_clear(spec) -> None:
    """Percussion may vary by track, but it must stay off beat ticks."""
    perc_steps_by_bar: dict[int, set[int]] = {}
    for event in _events(spec, "drums"):
        if event.note != PERC:
            continue
        assert event.start_tick % midi.PPQ != 0, f"perc on a beat tick: {event}"
        bar, offset = divmod(event.start_tick, midi.TICKS_PER_BAR)
        perc_steps_by_bar.setdefault(bar, set()).add(offset // midi.SIXTEENTH_TICKS)
    assert perc_steps_by_bar


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


def test_lead_period_has_phrase_level_question_answer_structure(spec) -> None:
    """Each full 16-bar lead period has four 4-bar phrases with repeat variation."""
    lead_events = _events(spec, "lead")
    assert lead_events, "lead produced no events"
    phrase_ticks = 4 * midi.TICKS_PER_BAR
    phrases_checked = 0
    for section, (start_bar, bars) in midi.section_layout(spec).items():
        if not section.startswith(("break", "peak")):
            continue
        for phrase_start in range(0, bars - 15, 16):
            period_lo = midi.bar_to_tick(start_bar + phrase_start)
            period_hi = period_lo + 16 * midi.TICKS_PER_BAR
            statements: dict[int, list[tuple[int, int, int]]] = {}
            for event in lead_events:
                if not period_lo <= event.start_tick < period_hi:
                    continue
                slot, offset = divmod(event.start_tick - period_lo, phrase_ticks)
                statements.setdefault(slot, []).append(
                    (offset, event.note, event.duration_ticks)
                )
            assert set(statements) == {0, 1, 2, 3}, (
                f"{section}: incomplete 16-bar lead period at bar {phrase_start}"
            )
            fingerprints = Counter(tuple(sorted(notes)) for notes in statements.values())
            assert len(fingerprints) >= 2, (
                f"{section}: period never varies across A/A'/B/A'' at bar {phrase_start}"
            )
            assert max(
                duration for notes in statements.values() for _offset, _note, duration in notes
            ) >= 8 * midi.SIXTEENTH_TICKS
            phrases_checked += 1
    assert phrases_checked, "T01 spec must contain a full 16-bar lead period"


def test_counterline_answers_in_lead_rest_windows(spec) -> None:
    lead = _events(spec, "lead")
    counter = _events(spec, "counterline")
    assert counter, "counterline produced no events"
    overlaps = 0
    for answer in counter:
        for event in lead:
            if event.start_tick < answer.start_tick + answer.duration_ticks and answer.start_tick < event.start_tick + event.duration_ticks:
                overlaps += 1
                break
    assert overlaps / len(counter) <= 0.30


def test_sub_bass_stays_on_tonic_pedal(spec) -> None:
    tonic = root_note(spec.key, 2) % 12
    bass = _events(spec, "bass")
    assert bass
    for section, (start_bar, bars) in midi.section_layout(spec).items():
        if not section.startswith(("groove", "drop", "peak")):
            continue
        checked = 0
        for bar in range(start_bar, min(start_bar + bars, start_bar + 8)):
            notes = [event.note % 12 for event in bass if midi.bar_to_tick(bar) <= event.start_tick < midi.bar_to_tick(bar + 1)]
            assert notes, f"no bass in {section} bar {bar}"
            assert set(notes) == {tonic}
            checked += 1
        assert checked


# --- Part roster expansion invariants (roster SPEC AC1) ---
#
# T01's render_targets.midi still lists six parts at this point; these tests
# drive the new generators directly through ALL_PARTS with load_spec(T01).


def _section_windows(spec, prefixes: tuple[str, ...]) -> list[tuple[int, int]]:
    """Tick windows [lo, hi) of every section whose name starts with a prefix."""
    return [
        (midi.bar_to_tick(start_bar), midi.bar_to_tick(start_bar + bars))
        for section, (start_bar, bars) in midi.section_layout(spec).items()
        if section.startswith(prefixes)
    ]


def test_pad_sustained_quality_neutral_bed(spec) -> None:
    """Pad notes sustain >= 2 bars, live only in break/drop/peak, and omit the third."""
    pitch_class, _ = parse_key(spec.key)
    allowed = {pitch_class, (pitch_class + 7) % 12, (pitch_class + 2) % 12}  # root/fifth/ninth
    windows = _section_windows(spec, ("break", "drop", "peak"))
    events = _events(spec, "pad")
    assert events, "pad produced no events"
    for event in events:
        assert event.duration_ticks >= 2 * midi.TICKS_PER_BAR, f"pad note too short: {event}"
        end = event.start_tick + event.duration_ticks
        assert any(lo <= event.start_tick and end <= hi for lo, hi in windows), (
            f"pad note outside break/drop/peak: {event}"
        )
        assert event.note % 12 in allowed, f"pad pitch class outside root/fifth/ninth: {event}"


def test_shaker_texture_bed_with_nonflat_contour(spec) -> None:
    """Shaker plays only in groove/drop/peak and its velocity contour is nonflat."""
    windows = _section_windows(spec, ("groove", "drop", "peak"))
    for seed in range(10):
        events = _events(spec, "shaker", seed=seed)
        assert events, f"seed {seed}: shaker produced no events"
        assert len({e.velocity for e in events}) >= 2, f"seed {seed}: flat shaker contour"
        for event in events:
            assert any(lo <= event.start_tick < hi for lo, hi in windows), (
                f"seed {seed}: shaker outside groove/drop/peak: {event}"
            )


def test_clap_shadow_and_ride_peak_only(spec) -> None:
    """Shadow-backbeat contract (mix-architecture review + take-7, 2026-06-07):
    claps are a peak-only phrase accent on beats 2 & 4 of every 4th bar — never
    an every-bar backbeat; ride stays inside peak."""
    peak = _section_windows(spec, ("peak",))
    events = _events(spec, "clap_ride")
    assert events, "clap_ride produced no events"
    clap_onsets = set()
    for event in events:
        assert any(lo <= event.start_tick < hi for lo, hi in peak), (
            f"clap_ride event outside peak: {event}"
        )
        if event.note == CLAP:
            assert event.start_tick % midi.TICKS_PER_BAR in (midi.PPQ, 3 * midi.PPQ), (
                f"clap off the backbeat: {event}"
            )
            clap_onsets.add(event.start_tick)
        else:
            assert event.note == RIDE, f"unexpected clap_ride note: {event}"
    for lo, hi in peak:
        bars = [lo + i * midi.TICKS_PER_BAR for i in range((hi - lo) // midi.TICKS_PER_BAR)]
        for index, bar_tick in enumerate(bars):
            has_clap = any(bar_tick + beat * midi.PPQ in clap_onsets for beat in (1, 3))
            assert has_clap == (index % 4 == 0), (
                f"clap shadow cadence broken at bar index {index}"
            )


def test_fx_only_around_drop_and_peak_entries(spec) -> None:
    """FX stay inside [entry - 4 bars, entry + 1 bar); impacts land, risers ramp up."""
    entries = [
        start_bar
        for section, (start_bar, _) in midi.section_layout(spec).items()
        if section.startswith(("drop", "peak"))
    ]
    assert entries, "T01 spec must contain drop/peak sections"
    windows = [
        (midi.bar_to_tick(max(0, entry - RISER_BARS)), midi.bar_to_tick(entry + 1))
        for entry in entries
    ]
    impact_note = root_note(spec.key, IMPACT_OCTAVE)
    for seed in range(10):
        events = _events(spec, "fx", seed=seed)
        assert events, f"seed {seed}: fx produced no events"
        for event in events:
            end = event.start_tick + event.duration_ticks
            assert any(lo <= event.start_tick and end <= hi for lo, hi in windows), (
                f"seed {seed}: fx outside an entry window: {event}"
            )
        onsets = {(e.start_tick, e.note, e.velocity) for e in events}
        for entry in entries:
            assert (midi.bar_to_tick(entry), impact_note, IMPACT_VELOCITY) in onsets, (
                f"seed {seed}: missing impact at entry bar {entry}"
            )
        for entry in entries:
            if entry < RISER_BARS:
                continue
            lo = midi.bar_to_tick(entry - RISER_BARS)
            hi = midi.bar_to_tick(entry)
            run = sorted(
                (e for e in events if lo <= e.start_tick < hi), key=lambda e: e.start_tick
            )
            assert run, f"seed {seed}: missing riser before entry bar {entry}"
            velocities = [e.velocity for e in run]
            assert velocities == sorted(velocities), (
                f"seed {seed}: riser velocity not monotonic before bar {entry}"
            )
            notes = [e.note for e in run]
            assert notes == sorted(notes) and notes[-1] > notes[0], (
                f"seed {seed}: riser pitch does not rise before bar {entry}"
            )


def test_new_part_seed_divergence(spec) -> None:
    """A nearby seed flips at least one of the pad/shaker/fx structural draws."""
    diverged = any(
        _events(spec, part) != _events(spec, part, seed=spec.seed + offset)
        for part in ("pad", "shaker", "fx")
        for offset in range(1, 6)
    )
    assert diverged, "pad length, shaker contour, and fx speed all identical across seeds"


# --- Slice 2: peak richness (change 2026-06-07-part-roster-peak-richness) ---


def test_peak_chords_have_bed_and_stabs(spec) -> None:
    """At peak, chords carry both a sustained bed and offbeat stabs (dual texture)."""
    events = _events(spec, "chords")
    for start_tick, end_tick in _section_windows(spec, ("peak",)):
        in_peak = [e for e in events if start_tick <= e.start_tick < end_tick]
        sustained = [e for e in in_peak if e.duration_ticks >= midi.TICKS_PER_BAR]
        stabs = [e for e in in_peak if e.duration_ticks < midi.TICKS_PER_BAR]
        assert sustained, "peak lost its sustained harmonic bed"
        assert stabs, "peak lost its offbeat stabs"
        # The bed mirrors the stab chord an octave up (same degree, +12), so
        # the lowest bed note sits exactly an octave above the lowest stab.
        assert min(e.note for e in sustained) >= min(s.note for s in stabs) + 12


def test_peak_lead_development(spec) -> None:
    """Peak phrases use >= 3 distinct statements including an octave lift."""
    events = _events(spec, "lead")
    for start_tick, end_tick in _section_windows(spec, ("peak",)):
        in_peak = [e for e in events if start_tick <= e.start_tick < end_tick]
        assert in_peak, "peak has no lead content"
        slot_ticks = 2 * midi.TICKS_PER_BAR
        fingerprints = set()
        slot_notes: dict[int, list[int]] = {}
        for event in in_peak:
            slot = (event.start_tick - start_tick) // slot_ticks
            slot_notes.setdefault(slot, []).append(event.note)
            fingerprints.add(
                tuple(
                    sorted(
                        (e.start_tick - start_tick - slot * slot_ticks, e.note % 12)
                        for e in in_peak
                        if (e.start_tick - start_tick) // slot_ticks == slot
                    )
                )
            )
        assert len(fingerprints) >= 3, "peak needs M, V, V2/M8 distinct statements"
        all_notes = [e.note for e in in_peak]
        assert max(all_notes) - min(all_notes) >= 12, "peak octave lift missing"


# --- Groove vocabulary (pack-data-driven patterns, decision 2026-06-10) ---
#
# Pattern content lives in the style pack's groove.vocabulary; the engine
# enforces alignment invariants. Without a pack the generators reproduce
# their legacy hardcoded behavior.


@pytest.fixture(scope="module")
def pack():
    from setloom.stylepack import load_style_pack

    return load_style_pack("melodic-progressive-techno", root=REPO_ROOT)


@pytest.fixture(scope="module")
def t02_spec():
    return load_spec(T02)


@pytest.fixture(scope="module")
def t04_spec():
    return load_spec(T04)


def _bar_events(events, bar):
    lo, hi = midi.bar_to_tick(bar), midi.bar_to_tick(bar + 1)
    return [e for e in events if lo <= e.start_tick < hi]


def test_track_specific_bass_plan_is_reported(t04_spec, pack):
    label = bass_generation_label(t04_spec, part_rng(t04_spec.seed, 1, "bass"), pack)
    assert label == "track:t04-deep-sidechain-roller"


def test_t04_bass_generation_not_t02_template(t02_spec, t04_spec, pack):
    """T04 must not silently reuse the same generated bass cell set as T02."""
    t02 = _events_with_pack(t02_spec, "bass", pack, variant=1)
    t04 = _events_with_pack(t04_spec, "bass", pack, variant=1)
    assert _bar_signatures(t04) != _bar_signatures(t02)


def test_track_bass_plan_can_override_first_phrase_tonic_rule(t04_spec, pack):
    bass = _events_with_pack(t04_spec, "bass", pack, variant=1)
    tonic = root_note(t04_spec.key, 2) % 12
    layout = midi.section_layout(t04_spec)
    start_bar, _ = layout["groove_a"]
    first_phrase = [
        e
        for e in bass
        if midi.bar_to_tick(start_bar) <= e.start_tick < midi.bar_to_tick(start_bar + 8)
    ]
    assert any(e.note % 12 != tonic for e in first_phrase)


def test_t04_bass_plan_has_longer_sidechain_body(t04_spec, pack):
    bass = _events_with_pack(t04_spec, "bass", pack, variant=1)
    assert bass
    lengths = sorted(event.duration_ticks / midi.SIXTEENTH_TICKS for event in bass)
    median_len = lengths[len(lengths) // 2]
    assert median_len >= 1.75
    for event in bass:
        assert event.start_tick % midi.PPQ != 0
        next_beat = (event.start_tick // midi.PPQ + 1) * midi.PPQ
        assert event.start_tick + event.duration_ticks < next_beat


def test_t04_chords_use_section_plan_not_global_stab_loop(t04_spec, pack):
    chords = _events_with_pack(t04_spec, "chords", pack, variant=1)
    layout = midi.section_layout(t04_spec)
    break_start, _ = layout["break_1"]
    drop_start, _ = layout["drop_1"]
    peak_start, _ = layout["peak"]
    break_events = _bar_events(chords, break_start)
    drop_bar_0 = _bar_events(chords, drop_start)
    drop_bar_1 = _bar_events(chords, drop_start + 1)
    peak_events = _bar_events(chords, peak_start)
    assert any(event.duration_ticks >= midi.TICKS_PER_BAR for event in break_events)
    assert drop_bar_0 and not drop_bar_1
    assert any(event.duration_ticks >= midi.TICKS_PER_BAR for event in peak_events)
    assert any(event.duration_ticks < midi.TICKS_PER_BAR for event in peak_events)


def test_t04_arp_mutes_rejected_foreground_arp(t04_spec, pack):
    assert _events_with_pack(t04_spec, "arp", pack, variant=1) == []


def test_track_drum_plan_breaks_eight_bar_copy_loop(t04_spec, pack):
    drums = _events_with_pack(t04_spec, "drums", pack, variant=1)
    layout = midi.section_layout(t04_spec)
    start_bar, _ = layout["drop_1"]
    bar_0 = {e.start_tick % midi.TICKS_PER_BAR for e in _bar_events(drums, start_bar) if e.note == PERC}
    bar_8 = {
        e.start_tick % midi.TICKS_PER_BAR
        for e in _bar_events(drums, start_bar + 8)
        if e.note == PERC
    }
    assert bar_0 != bar_8


def test_vocab_bass_keeps_alignment_invariants(spec, pack):
    for seed in range(6):
        events = ALL_PARTS["bass"].generate(spec, part_rng(seed, 1, "bass"), pack=pack)
        for event in events:
            assert event.start_tick % midi.PPQ != 0, f"bass on a beat tick: {event}"
            to_next_beat = midi.PPQ - event.start_tick % midi.PPQ
            assert event.duration_ticks <= to_next_beat - 1, f"no sidechain gap: {event}"


def test_vocab_bass_phrase_end_varies_and_swells(spec, pack):
    events = ALL_PARTS["bass"].generate(spec, part_rng(7, 1, "bass"), pack=pack)
    layout = midi.section_layout(spec)
    for section, (start_bar, bars) in layout.items():
        if not section.startswith(("groove", "drop", "peak")) or bars < 8:
            continue
        mid_steps = {(e.start_tick - midi.bar_to_tick(start_bar)) // midi.SIXTEENTH_TICKS
                     for e in _bar_events(events, start_bar)}
        end_steps = {(e.start_tick - midi.bar_to_tick(start_bar + 7)) // midi.SIXTEENTH_TICKS
                     for e in _bar_events(events, start_bar + 7)}
        assert mid_steps != end_steps, f"{section}: phrase-end bar identical to bar 1"
        v_first = max(e.velocity for e in _bar_events(events, start_bar))
        v_later = max(e.velocity for e in _bar_events(events, start_bar + 6))
        assert v_later > v_first, f"{section}: no velocity swell across the phrase"


def test_vocab_bass_neighbor_only_after_first_phrase(spec, pack):
    tonic = root_note(spec.key, 2) % 12
    events = ALL_PARTS["bass"].generate(spec, part_rng(7, 1, "bass"), pack=pack)
    layout = midi.section_layout(spec)
    saw_neighbor = False
    for section, (start_bar, bars) in layout.items():
        if not section.startswith(("groove", "drop", "peak")):
            continue
        for bar_in_section in range(bars):
            notes = {e.note % 12 for e in _bar_events(events, start_bar + bar_in_section)}
            if bar_in_section < 8:
                assert notes <= {tonic}, f"{section} bar {bar_in_section}: non-tonic in first phrase"
            elif notes - {tonic}:
                saw_neighbor = True
                assert notes - {tonic} == {(tonic - 2) % 12}, f"unexpected pitch: {notes}"
    assert saw_neighbor, "no neighbor motion anywhere despite vocabulary"


def test_vocab_break_accent_kicks(spec, pack):
    events = ALL_PARTS["drums"].generate(spec, part_rng(7, 1, "drums"), pack=pack)
    layout = midi.section_layout(spec)
    for section, (start_bar, bars) in layout.items():
        kicks = [e for e in events if e.note == KICK
                 and midi.bar_to_tick(start_bar) <= e.start_tick < midi.bar_to_tick(start_bar + bars)]
        if section.startswith("break") and bars >= 6:
            assert 1 <= len(kicks) <= 2, f"{section}: expected lone accent kicks, got {len(kicks)}"
        elif section.startswith("break"):
            assert not kicks, f"{section}: short break should stay kick-free"


def test_vocab_determinism_and_legacy_fallback(spec, pack):
    a = ALL_PARTS["bass"].generate(spec, part_rng(5, 1, "bass"), pack=pack)
    b = ALL_PARTS["bass"].generate(spec, part_rng(5, 1, "bass"), pack=pack)
    assert a == b
    legacy = ALL_PARTS["bass"].generate(spec, part_rng(5, 1, "bass"))
    with_pack = ALL_PARTS["bass"].generate(spec, part_rng(5, 1, "bass"), pack=pack)
    assert legacy and with_pack and legacy != with_pack
