# SPDX-License-Identifier: AGPL-3.0-only
"""Ten rule-based part generators behind a shared PartGenerator Protocol."""

from setloom.parts.arp import ArpGenerator
from setloom.parts.base import PartGenerator, part_rng
from setloom.parts.bass import BassGenerator
from setloom.parts.chords import ChordsGenerator
from setloom.parts.clap_ride import ClapRideGenerator
from setloom.parts.counterline import CounterlineGenerator
from setloom.parts.drums import DrumsGenerator
from setloom.parts.fills import FillsGenerator
from setloom.parts.fx import FxGenerator
from setloom.parts.lead import LeadGenerator
from setloom.parts.pad import PadGenerator
from setloom.parts.shaker import ShakerGenerator

ALL_PARTS: dict[str, PartGenerator] = {
    generator.name: generator
    for generator in (
        DrumsGenerator(),
        BassGenerator(),
        ChordsGenerator(),
        ArpGenerator(),
        LeadGenerator(),
        CounterlineGenerator(),
        FillsGenerator(),
        PadGenerator(),
        ShakerGenerator(),
        ClapRideGenerator(),
        FxGenerator(),
    )
}

__all__ = ["ALL_PARTS", "PartGenerator", "part_rng"]
