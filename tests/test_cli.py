# SPDX-License-Identifier: AGPL-3.0-only
"""CLI boundaries and playback dispatch without starting an audio player."""

import pytest
from types import SimpleNamespace

from setloom.cli import build_parser, main


@pytest.mark.parametrize("command", ["new", "anatomize"])
def test_removed_workflows_do_not_create_output(tmp_path, monkeypatch, command):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as error:
        main([command, "T06"])
    assert error.value.code == 2
    assert list(tmp_path.iterdir()) == []


def test_help_lists_tool_operations(capsys):
    build_parser().print_help()
    help_text = capsys.readouterr().out
    assert "inspect" in help_text
    assert "transcribe" in help_text
    assert "separate" in help_text
    assert "scaffold" not in help_text


def test_cli_play_missing_file(tmp_path):
    assert main(["play", str(tmp_path / "nonexistent.wav")]) == 1


def test_cli_play_dispatches_to_player(tmp_path, monkeypatch):
    path = tmp_path / "audition.wav"
    path.write_bytes(b"placeholder; player invocation is mocked")
    calls = []
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/afplay")
    monkeypatch.setattr("subprocess.run", lambda command: (calls.append(command), SimpleNamespace(returncode=0))[1])
    assert main(["play", str(path)]) == 0
    assert calls == [["/usr/bin/afplay", str(path)]]


def test_player_failure_is_reported(tmp_path, monkeypatch):
    path = tmp_path / "audition.wav"
    path.touch()
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/afplay")
    monkeypatch.setattr("subprocess.run", lambda command: SimpleNamespace(returncode=7))
    assert main(["play", str(path)]) == 7
