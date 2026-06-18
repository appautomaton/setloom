# SPDX-License-Identifier: AGPL-3.0-only
"""Music-theory helper tests: key parsing and scale-degree/chord-tone math."""

import pytest

from setloom.conductor import SCALES, chord_tones, degree_note, parse_key, scale_offset


def test_parse_key_returns_pitch_class_and_quality() -> None:
    assert parse_key("D minor") == (2, "minor")
    assert parse_key("A minor") == (9, "minor")
    assert parse_key("C major") == (0, "major")


def test_parse_key_rejects_unsupported() -> None:
    with pytest.raises(ValueError, match="unsupported key"):
        parse_key("H dorian")


def test_scale_offset_wraps_octaves() -> None:
    minor = SCALES["minor"]
    assert scale_offset(minor, 0) == 0
    assert scale_offset(minor, 4) == 7  # fifth
    assert scale_offset(minor, 7) == 12  # tonic, one octave up


def test_degree_note_places_tonic_in_octave() -> None:
    # D minor tonic in octave 3 is MIDI 50.
    assert degree_note(2, SCALES["minor"], 0, 3) == 50


def test_chord_tones_voicings() -> None:
    minor = SCALES["minor"]
    assert chord_tones(minor, 0) == (0, 3, 7)  # triad default
    assert chord_tones(minor, 0, "sus2") == (0, 2, 7)
    assert chord_tones(minor, 0, "sus4") == (0, 5, 7)
    assert chord_tones(minor, 0, "add9") == (0, 3, 7, 14)
