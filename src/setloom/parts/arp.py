# SPDX-License-Identifier: AGPL-3.0-only
"""Arp: phrase-gated rhythmic cells in drops and peak (channel 3).

One rhythmic cell is drawn per run: straight 16ths over ascending chord
tones, a 3-3-2 (dotted-8th feel) cell, or an octave-pedal alternation.
Each section ramps density: its first quarter plays every other onset,
the rest plays the full cell, and the last two 16ths of every 16-bar
phrase rest so phrases breathe (style.yml arrangement_tension
drop_entry_devices: arp_density_lift; counters the too_preset_arp critique).
"""

import random

from setloom.midi import SIXTEENTH_TICKS, STEPS_PER_BAR, NoteEvent, bar_to_tick, section_layout
from setloom.parts.base import TRIADS, parse_key
from typing import TYPE_CHECKING

from setloom.schema import TrackSpec

if TYPE_CHECKING:
    from setloom.stylepack import StylePack

ARP_OCTAVE = 5

PHRASE_BARS = 16
PHRASE_REST_STEPS = 2  # the last two 16ths of each phrase rest

CELLS = ("straight_16ths", "cell_332", "octave_pedal")

# 3-3-2 onset steps per bar (two 3-3-2 groups of eight 16ths).
CELL_332_STEPS = (0, 3, 6, 8, 11, 14)

# Velocity accents: beats for straight 16ths, group heads for 3-3-2,
# the high octave for the pedal alternation.
STRAIGHT_ACCENT, STRAIGHT_BASE = 84, 72
CELL_ACCENT, CELL_BASE = 84, 74
PEDAL_HIGH, PEDAL_LOW = 80, 70


def _track_arp_plan(spec: TrackSpec):
    groove = getattr(spec, "groove", None)
    if groove is None or groove.arp is None:
        return None
    return groove.arp


def _section_plan(plan, section: str):
    kind = section.rstrip("0123456789_")
    return plan.sections.get(section) or plan.sections.get(kind)


class ArpGenerator:
    name = "arp"

    def generate(
        self, spec: TrackSpec, rng: random.Random, pack: "StylePack | None" = None
    ) -> list[NoteEvent]:
        pitch_class, quality = parse_key(spec.key)
        root = 12 * (ARP_OCTAVE + 1) + pitch_class
        tones = TRIADS[quality] + (12,)  # root, third, fifth, octave, ascending
        track_plan = _track_arp_plan(spec)
        if track_plan is not None:
            events: list[NoteEvent] = []
            for section, (start_bar, bars) in section_layout(spec).items():
                planned_section = _section_plan(track_plan, section)
                if planned_section is None or planned_section.mode == "mute":
                    continue
                section_root = 12 * (planned_section.octave + 1) + pitch_class
                patterns = planned_section.patterns or (
                    [planned_section.steps] if planned_section.steps else []
                )
                if not patterns:
                    continue
                duration = planned_section.duration_steps * SIXTEENTH_TICKS
                for bar_in_section in range(bars):
                    bar = start_bar + bar_in_section
                    steps = patterns[bar_in_section % len(patterns)]
                    for index, step in enumerate(steps):
                        tone_index = planned_section.tone_indices[index % len(planned_section.tone_indices)]
                        note = section_root + tones[tone_index % len(tones)]
                        tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
                        events.append(
                            NoteEvent(3, note, planned_section.velocity, tick, duration)
                        )
            return events
        # Exactly one rng draw per run keeps draw counts structural.
        cell = rng.choice(CELLS)
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            if not section.startswith(("drop", "peak")):
                continue
            sparse_bars = max(1, bars // 4)  # density ramp: first quarter sparse
            for bar_in_section in range(bars):
                bar = start_bar + bar_in_section
                steps = CELL_332_STEPS if cell == "cell_332" else tuple(range(STEPS_PER_BAR))
                for index, step in enumerate(steps):
                    if bar_in_section < sparse_bars and step % 2 == 1:
                        continue  # sparse ramp: every other 16th only
                    phrase_rest = (
                        bar_in_section % PHRASE_BARS == PHRASE_BARS - 1
                        and step >= STEPS_PER_BAR - PHRASE_REST_STEPS
                    )
                    if phrase_rest:
                        continue  # rest at the 16-bar phrase boundary
                    if cell == "octave_pedal":
                        high = step % 2 == 1
                        note = root + (12 if high else 0)
                        velocity = PEDAL_HIGH if high else PEDAL_LOW
                    elif cell == "cell_332":
                        note = root + tones[index % len(tones)]
                        velocity = CELL_ACCENT if step in (0, 8) else CELL_BASE
                    else:
                        note = root + tones[step % len(tones)]
                        velocity = STRAIGHT_ACCENT if step % 4 == 0 else STRAIGHT_BASE
                    tick = bar_to_tick(bar) + step * SIXTEENTH_TICKS
                    events.append(NoteEvent(3, note, velocity, tick, SIXTEENTH_TICKS))
        return events
