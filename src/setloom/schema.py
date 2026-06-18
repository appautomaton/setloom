# SPDX-License-Identifier: AGPL-3.0-only
"""Track spec schema (Spec 3).

Formalizes the track-spec shape (canonical fixture: tests/fixtures/spec-t01.yml).
Validation errors point at the offending field; grammar-level checks
(style-pack ranges) live in the CLI and style-pack loader, not here.

Some fields are declared ahead of consumption: `energy`, `intent`, `palette`,
and `human_gate` are not read by any generator yet, and only `bass_aggression`
and `peak_time_pressure` from `style_vector` steer generation today. They
document creator intent and reserve the contract for future wiring.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    avoid: list[str] = []


class StyleVector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    darkness: int = Field(ge=0, le=10)
    melodic_emotion: int = Field(ge=0, le=10)
    groove_hypnosis: int = Field(ge=0, le=10)
    cinematic_tension: int = Field(ge=0, le=10)
    bass_aggression: int = Field(ge=0, le=10)
    arrangement_patience: int = Field(ge=0, le=10)
    hook_density: int = Field(ge=0, le=10)
    vocal_presence: int = Field(ge=0, le=10)
    organic_texture: int = Field(ge=0, le=10)
    peak_time_pressure: int = Field(ge=0, le=10)


class RenderTargets(BaseModel):
    model_config = ConfigDict(extra="forbid")

    midi: list[str]
    stems: list[str] = []
    demo_mix: bool = False


class HumanGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required: bool = True


class BassGroovePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = "track-bass"
    phrase_bars: int = Field(default=8, gt=0)
    velocity_swell_per_bar: int = Field(default=0, ge=0)
    bars: list[list[tuple[int, int, int]]]
    phrase_end_bar: list[tuple[int, int, int]] | None = None
    neighbor_steps: list[int] = Field(default_factory=list)
    neighbor_interval: int = -2
    first_phrase_tonic: bool = True

    @model_validator(mode="after")
    def _bass_steps_are_safe(self) -> "BassGroovePlan":
        if not self.bars:
            raise ValueError("bass groove requires at least one bar")

        def validate_note(name: str, note: tuple[int, int, int]) -> None:
            step, velocity, length = note
            if not 0 <= step < 16:
                raise ValueError(f"{name} step {step} must be in the 0..15 sixteenth grid")
            if step % 4 == 0:
                raise ValueError(f"{name} step {step} is on a beat tick reserved for kick space")
            if not 1 <= velocity <= 127:
                raise ValueError(f"{name} velocity {velocity} must be in 1..127")
            if length <= 0:
                raise ValueError(f"{name} length {length} must be positive")

        for bar_index, bar in enumerate(self.bars):
            if not bar:
                raise ValueError(f"bass bars[{bar_index}] must contain at least one note")
            for note in bar:
                validate_note(f"bass bars[{bar_index}]", note)
        for note in self.phrase_end_bar or []:
            validate_note("bass phrase_end_bar", note)
        for step in self.neighbor_steps:
            if not 0 <= step < 16:
                raise ValueError(f"bass neighbor step {step} must be in the 0..15 sixteenth grid")
            if step % 4 == 0:
                raise ValueError(
                    f"bass neighbor step {step} is on a beat tick reserved for kick space"
                )
        return self


class DrumsGroovePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = "track-drums"
    phrase_bars: int | None = Field(default=None, gt=0)
    percussion_patterns: list[list[list[int]]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _percussion_steps_are_safe(self) -> "DrumsGroovePlan":
        for pattern_index, pattern in enumerate(self.percussion_patterns):
            if not pattern:
                raise ValueError(f"percussion pattern {pattern_index} must contain at least one bar")
            for bar_index, bar in enumerate(pattern):
                for step in bar:
                    if not 0 <= step < 16:
                        raise ValueError(
                            f"percussion pattern {pattern_index} bar {bar_index} step {step} "
                            "must be in the 0..15 sixteenth grid"
                        )
                    if step % 4 == 0:
                        raise ValueError(
                            f"percussion pattern {pattern_index} bar {bar_index} step {step} "
                            "is on a beat tick reserved for kick space"
                        )
        return self


class ChordsGrooveSectionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["silent", "sustain", "stabs", "bed_and_stabs"]
    color: Literal["conductor", "triad", "sus2", "sus4", "add9"] = "conductor"
    octave: int = Field(default=4, ge=2, le=6)
    bed_velocity: int = Field(default=50, ge=1, le=127)
    stab_velocity: int = Field(default=60, ge=1, le=127)
    duration_steps: int = Field(default=2, gt=0)
    bed_lift: int = 0
    stab_steps: list[int] = Field(default_factory=list)
    stab_patterns: list[list[int]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _stab_steps_are_safe(self) -> "ChordsGrooveSectionPlan":
        patterns = self.stab_patterns or ([self.stab_steps] if self.stab_steps else [])
        for pattern_index, pattern in enumerate(patterns):
            for step in pattern:
                if not 0 <= step < 16:
                    raise ValueError(
                        f"chord stab pattern {pattern_index} step {step} must be in the 0..15 sixteenth grid"
                    )
                if step % 4 == 0:
                    raise ValueError(
                        f"chord stab pattern {pattern_index} step {step} is on a beat tick reserved for kick space"
                    )
        return self


class ChordsGroovePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = "track-chords"
    sections: dict[str, ChordsGrooveSectionPlan]

    @model_validator(mode="after")
    def _sections_are_present(self) -> "ChordsGroovePlan":
        if not self.sections:
            raise ValueError("chords groove requires at least one section plan")
        return self


class ArpGrooveSectionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["mute", "dark_pulse"] = "mute"
    octave: int = Field(default=4, ge=2, le=6)
    velocity: int = Field(default=46, ge=1, le=127)
    duration_steps: int = Field(default=1, gt=0)
    steps: list[int] = Field(default_factory=list)
    patterns: list[list[int]] = Field(default_factory=list)
    tone_indices: list[int] = Field(default_factory=lambda: [0, 2, 3])

    @model_validator(mode="after")
    def _pulse_steps_are_safe(self) -> "ArpGrooveSectionPlan":
        patterns = self.patterns or ([self.steps] if self.steps else [])
        for pattern_index, pattern in enumerate(patterns):
            for step in pattern:
                if not 0 <= step < 16:
                    raise ValueError(
                        f"arp pattern {pattern_index} step {step} must be in the 0..15 sixteenth grid"
                    )
                if step % 4 == 0:
                    raise ValueError(
                        f"arp pattern {pattern_index} step {step} is on a beat tick reserved for kick space"
                    )
        if not self.tone_indices:
            raise ValueError("arp tone_indices must not be empty")
        return self


class ArpGroovePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = "track-arp"
    sections: dict[str, ArpGrooveSectionPlan]

    @model_validator(mode="after")
    def _sections_are_present(self) -> "ArpGroovePlan":
        if not self.sections:
            raise ValueError("arp groove requires at least one section plan")
        return self


class HarmonyGroovePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = "track-harmony"
    progression: list[int] | None = None
    chord_color: Literal["triad", "sus2", "sus4", "add9"] | None = None
    harmonic_rhythm: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _progression_is_usable(self) -> "HarmonyGroovePlan":
        if self.progression is not None:
            if len(self.progression) < 2:
                raise ValueError("harmony progression must contain at least two degrees")
            if any(degree < 0 for degree in self.progression):
                raise ValueError("harmony progression degrees must be non-negative")
        for section, bars in self.harmonic_rhythm.items():
            if bars <= 0:
                raise ValueError(f"harmony harmonic_rhythm[{section}] must be positive")
        return self


class PadGroovePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = "track-pad"
    mode: Literal["tonic_power_stack", "conductor_bed"] = "tonic_power_stack"
    octave: int = Field(default=3, ge=1, le=6)
    note_bars: int | None = Field(default=None, gt=0)
    velocity: int = Field(default=50, ge=1, le=127)
    peak_velocity: int = Field(default=58, ge=1, le=127)


class ShakerGroovePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = "track-shaker"
    mode: Literal["continuous_16th", "phrase_gated"] = "continuous_16th"
    phrase_bars: int = Field(default=8, gt=0)
    active_steps: list[int] = Field(default_factory=list)
    rest_last_bar: bool = False

    @model_validator(mode="after")
    def _active_steps_are_safe(self) -> "ShakerGroovePlan":
        for step in self.active_steps:
            if not 0 <= step < 16:
                raise ValueError(f"shaker active step {step} must be in the 0..15 sixteenth grid")
        return self


class FxGroovePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = "track-fx"
    mode: Literal["entry_riser_impact", "phrase_marks", "mute"] = "entry_riser_impact"
    riser_bars: int = Field(default=4, ge=1)
    mark_every_bars: int = Field(default=8, gt=0)
    mark_velocity: int = Field(default=72, ge=1, le=127)
    impact_velocity: int = Field(default=120, ge=1, le=127)


class GroovePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = ""
    harmony: HarmonyGroovePlan | None = None
    bass: BassGroovePlan | None = None
    drums: DrumsGroovePlan | None = None
    chords: ChordsGroovePlan | None = None
    arp: ArpGroovePlan | None = None
    pad: PadGroovePlan | None = None
    shaker: ShakerGroovePlan | None = None
    fx: FxGroovePlan | None = None


class TrackSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    style_pack: str
    duration_profile: str = "club_extended"  # product form; windows live in the style pack
    seed: int = Field(ge=0)
    bpm: float = Field(gt=0)
    key: str
    energy: int = Field(ge=0, le=10)
    duration_bars: int = Field(gt=0)
    intent: Intent
    sections: dict[str, int]
    palette: dict[str, str]
    style_vector: StyleVector
    groove: GroovePlan | None = None
    render_targets: RenderTargets
    human_gate: HumanGate

    @model_validator(mode="after")
    def _sections_match_duration(self) -> "TrackSpec":
        total = sum(self.sections.values())
        if total != self.duration_bars:
            raise ValueError(
                f"sections total {total} bars but duration_bars is {self.duration_bars}"
            )
        return self

    @model_validator(mode="after")
    def _sections_positive(self) -> "TrackSpec":
        for name, bars in self.sections.items():
            if bars <= 0:
                raise ValueError(f"section '{name}' must have a positive bar count")
        return self


def load_spec(path: str | Path) -> TrackSpec:
    """Load and validate a track spec YAML file."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: spec file must contain a YAML mapping")
    return TrackSpec.model_validate(raw)
