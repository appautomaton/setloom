# SPDX-License-Identifier: AGPL-3.0-only
"""Lead: one 2-bar motif family, repeated then varied per phrase (channel 4).

One motif family is drawn per run. Each break and peak section is walked in
16-bar phrases of eight 2-bar slots; the phrase plan states the motif,
repeats it, then plays a seeded variation (transpose, displacement, or tail
alteration — one transform draw per phrase). Breaks reveal the motif from
bar 4 of the section; peak keeps medium density with repetition (style.yml
harmony_and_melody.lead_density and motif_policy: repeat_then_vary).
"""

import random

from setloom.midi import SIXTEENTH_TICKS, NoteEvent, bar_to_tick, section_layout
from setloom.parts.base import SCALES, parse_key
from setloom.schema import TrackSpec

LEAD_OCTAVE = 5
LEAD_VELOCITY = 84

PHRASE_BARS = 16
SLOT_BARS = 2
SLOTS_PER_PHRASE = PHRASE_BARS // SLOT_BARS
REVEAL_DELAY_SLOTS = 2  # breaks reveal the motif from bar 4 of the section

# Motif bank: 2-bar motifs of (scale_degree, start_16th in 0-31, dur_16ths).
# Every note keeps start + duration <= 31 so a one-step displacement stays
# inside the 2-bar slot.
MOTIF_FAMILIES = (
    ((0, 0, 3), (3, 4, 3), (2, 8, 4), (0, 16, 6), (4, 24, 6)),
    ((4, 0, 2), (2, 4, 2), (0, 8, 6), (1, 16, 4), (2, 20, 4), (0, 24, 6)),
    ((7, 0, 4), (5, 6, 2), (4, 8, 6), (2, 16, 4), (0, 22, 8)),
    ((0, 0, 2), (2, 2, 2), (4, 4, 6), (7, 16, 4), (5, 20, 4), (4, 24, 6)),
)

Motif = tuple[tuple[int, int, int], ...]

# Phrase plans over eight 2-bar slots: "M" states the motif, "V" plays the
# phrase's variation, None rests. Breaks open with a 4-bar reveal delay.
BREAK_FIRST_PLAN = (None, None, "M", "M", "V", "M", "M", "V")
BREAK_PLAN = ("M", "M", "V", "M", "M", "V", "M", "V")
PEAK_PLAN = ("M", "M", None, "V", "M", "M", None, "V")

TRANSFORMS = ("transpose_up", "displace", "tail_lift")


def _vary(motif: Motif, transform: str) -> Motif:
    """Apply one small seeded transformation to the 2-bar motif."""
    if transform == "transpose_up":
        return tuple((degree + 1, start, dur) for degree, start, dur in motif)
    if transform == "displace":
        return tuple((degree, start + 1, dur) for degree, start, dur in motif)
    *head, (degree, start, dur) = motif  # tail_lift: raise the final note a third
    return (*head, (degree + 2, start, dur))


class LeadGenerator:
    name = "lead"

    def generate(self, spec: TrackSpec, rng: random.Random) -> list[NoteEvent]:
        pitch_class, quality = parse_key(spec.key)
        scale = SCALES[quality]
        base = 12 * (LEAD_OCTAVE + 1) + pitch_class
        # One family draw per run, one transform draw per phrase: draw counts
        # stay structural (they depend on the spec only, never on outcomes).
        motif = rng.choice(MOTIF_FAMILIES)
        events: list[NoteEvent] = []
        for section, (start_bar, bars) in section_layout(spec).items():
            is_break = section.startswith("break")
            if not (is_break or section.startswith("peak")):
                continue
            for phrase_start in range(0, bars, PHRASE_BARS):
                transform = rng.choice(TRANSFORMS)
                varied = _vary(motif, transform)
                if is_break:
                    plan = BREAK_FIRST_PLAN if phrase_start == 0 else BREAK_PLAN
                else:
                    plan = PEAK_PLAN
                for slot, kind in enumerate(plan):
                    slot_bar = phrase_start + slot * SLOT_BARS
                    if kind is None or slot_bar + SLOT_BARS > bars:
                        continue
                    statement = motif if kind == "M" else varied
                    slot_tick = bar_to_tick(start_bar + slot_bar)
                    for degree, start_16th, dur_16ths in statement:
                        note = base + 12 * (degree // len(scale)) + scale[degree % len(scale)]
                        tick = slot_tick + start_16th * SIXTEENTH_TICKS
                        events.append(
                            NoteEvent(4, note, LEAD_VELOCITY, tick, dur_16ths * SIXTEENTH_TICKS)
                        )
        return events
