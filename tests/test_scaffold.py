# SPDX-License-Identifier: AGPL-3.0-only
"""Tests for track scaffolding and playback commands."""

import pytest
import yaml

from setloom.cli import main
from setloom.scaffold import assemble_template, create_track, spec_template


def test_spec_template_is_valid_yaml():
    text = spec_template("T06", "test-track", 130.0, "D minor")
    data = yaml.safe_load(text)
    assert data["id"] == "T06"
    assert data["title"] == "test-track"
    assert data["bpm"] == 130.0
    assert data["key"] == "D minor"
    assert sum(data["sections"].values()) == data["duration_bars"]


def test_assemble_template_has_track_id_and_title():
    text = assemble_template("T07", "my-track")
    assert "T07" in text
    assert "my-track" in text
    assert "load_spec" in text
    assert "write_part_midi" in text
    assert "write_audio" in text


def test_create_track_writes_three_files(tmp_path):
    track_dir = create_track("T06", "test-track", root=tmp_path)
    assert (track_dir / "spec.yml").is_file()
    assert (track_dir / "assemble.py").is_file()
    assert (track_dir / "listening-notes.yml").is_file()


def test_create_track_rejects_existing(tmp_path):
    create_track("T06", "first", root=tmp_path)
    with pytest.raises(FileExistsError):
        create_track("T06", "second", root=tmp_path)


def test_cli_new_creates_validatable_spec(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main(["new", "T06", "--title", "test-track", "--bpm", "130", "--key", "D minor"])
    assert rc == 0
    spec_path = tmp_path / "music/tracks/T06/spec.yml"
    assert spec_path.is_file()

    # Validate the scaffolded spec
    rc = main(["validate", str(spec_path)])
    assert rc == 0


def test_cli_new_rejects_duplicate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["new", "T06"]) == 0
    assert main(["new", "T06"]) == 1


def test_cli_play_missing_file(tmp_path):
    rc = main(["play", str(tmp_path / "nonexistent.wav")])
    assert rc == 1


def test_cli_play_runs_afplay(tmp_path):
    """Play a tiny silent wav and verify afplay is invoked."""
    import wave
    from array import array

    wav_path = tmp_path / "silence.wav"
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(array("h", [0] * 100).tobytes())

    rc = main(["play", str(wav_path)])
    assert rc == 0
