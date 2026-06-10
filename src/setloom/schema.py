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
