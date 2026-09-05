# SPDX-License-Identifier: AGPL-3.0-only
"""Hermetic tests for the fusion engine and `transcribe --engine` routing.

No torch / CoreML / weights / network: the recall-first logic is exercised on synthetic
note-lists, and the CLI routing is tested with Kong + Basic Pitch monkeypatched. Importing
the transcription package is safe (torch loads only inside KongModel, CoreML only inside
BasicPitchModel).
"""

from pathlib import Path

import pytest

from setloom import cli
from setloom.conductor import SCALES
from setloom.transcription import TranscriptionResult, fusion
from setloom.transcription.basic_pitch import TranscribedNote

ALL_PCS = frozenset(range(12))  # neutralize the key prior in pure-logic tests


def _n(start: float, end: float, pitch: int, vel: int = 100) -> TranscribedNote:
    return TranscribedNote(start, end, pitch, vel, vel / 127.0)


# --- fusion logic ----------------------------------------------------------


def test_frozen_constants() -> None:
    assert fusion.RECALL_FIRST == {
        "tol_support": 0.07, "tol_merge": 0.05, "chord_win": 0.04,
        "min_dur": 0.035, "min_vel": 20, "floor": 0.40, "octave_win": 0.12,
    }


def test_merge_preserves_repeats_and_combines_duplicates() -> None:
    # same pitch struck twice 0.30 s apart (> tol_merge) -> two notes survive
    repeats = fusion.fuse_recall_first(
        [_n(0.0, 0.2, 60), _n(0.3, 0.5, 60)], [], scale_pcs=ALL_PCS
    )
    assert [n.start_s for n in repeats] == [0.0, 0.3]

    # the same strike seen by both engines (onsets within tol_merge) -> one note, vel = max
    dup = fusion.fuse_recall_first([_n(1.0, 1.2, 64, 90)], [_n(1.02, 1.25, 64, 110)], scale_pcs=ALL_PCS)
    assert len(dup) == 1
    assert dup[0].pitch == 64 and dup[0].velocity == 110 and dup[0].end_s == pytest.approx(1.25)


def test_cross_support_keeps_otherwise_weak_note() -> None:
    scale = frozenset({0, 4, 5, 7, 9})  # excludes pc 2 (pitch 62) and pc 3 (pitch 63)
    weak = [_n(0.0, 0.05, 62, 25)]  # out-of-scale, low vel/dur: below the floor alone
    assert fusion.fuse_recall_first([], weak, scale_pcs=scale) == ()
    # a rhythm note within +/-1 semitone and tol_support corroborates it -> kept
    kept = fusion.fuse_recall_first([_n(0.0, 0.05, 63, 100)], weak, scale_pcs=scale)
    assert 62 in {n.pitch for n in kept}


def test_octave_ghost_suppression() -> None:
    lower = _n(0.0, 0.5, 48, 110)  # strong fundamental, pc 0
    # (a) uncorroborated weaker upper octave -> dropped
    out = fusion.fuse_recall_first([lower], [_n(0.0, 0.4, 60, 40)], scale_pcs=ALL_PCS)
    assert {n.pitch for n in out} == {48}
    # (b) a cross-supported (musical) octave is kept
    out = fusion.fuse_recall_first([lower, _n(0.0, 0.4, 60, 40)], [_n(0.0, 0.4, 60, 40)], scale_pcs=ALL_PCS)
    assert {n.pitch for n in out} == {48, 60}
    # (c) a stronger upper octave is kept (rhythm-tagged, high velocity vs a weak lower)
    out = fusion.fuse_recall_first([_n(0.0, 0.5, 60, 120)], [_n(0.0, 0.4, 48, 30)], scale_pcs=ALL_PCS)
    assert 60 in {n.pitch for n in out}


def test_artifact_floor_hard_drops() -> None:
    # sub-min_dur blip dropped even when corroborated and in-scale
    assert fusion.fuse_recall_first([_n(0.0, 0.02, 60)], [_n(0.0, 0.02, 60)], scale_pcs=ALL_PCS) == ()
    # sub-min_vel dropped
    assert fusion.fuse_recall_first([], [_n(0.0, 0.2, 60, 10)], scale_pcs=ALL_PCS) == ()
    # clears hard drops but support below the floor (out-of-scale, low vel, no corroboration)
    assert fusion.fuse_recall_first([], [_n(0.0, 0.05, 61, 21)], scale_pcs=frozenset({0, 4, 7})) == ()


def test_chord_coordination_anchors_on_first_start() -> None:
    notes = [_n(0.0, 0.5, 60), _n(0.02, 0.5, 62), _n(0.04, 0.5, 64), _n(0.10, 0.5, 67)]
    out = {n.pitch: n.start_s for n in fusion.fuse_recall_first(notes, [], scale_pcs=ALL_PCS)}
    assert out[60] == pytest.approx(0.02)  # cluster [0.00,0.02,0.04] snaps to its median
    assert out[62] == pytest.approx(0.02)
    assert out[64] == pytest.approx(0.02)
    assert out[67] == pytest.approx(0.10)  # 0.10 starts a new (span-capped) cluster


def test_detect_key_reuses_conductor() -> None:
    assert fusion.detect_key([]) == ("C major", frozenset(SCALES["major"]))
    notes = [_n(i * 0.5, i * 0.5 + 0.4, p) for i in range(4) for p in (60, 64, 67)]
    label, pcs = fusion.detect_key(notes)
    assert len(pcs) == 7 and label.split()[1] in ("major", "minor")


# --- CLI engine routing (Kong + Basic Pitch mocked) ------------------------


@pytest.fixture
def _in_process(monkeypatch):
    """Short-circuit the subprocess TMPDIR rerun guard so the CLI runs in-process."""
    monkeypatch.setenv("SETLOOM_TRANSCRIPTION_TMPDIR_READY", "1")


def test_cli_engine_kong_routes_to_kong(tmp_path, _in_process, monkeypatch) -> None:
    audio = tmp_path / "a.wav"
    audio.touch()
    seen = {}

    def fake_kong(audio, **k):
        seen["kong"] = True
        return (_n(0.0, 0.5, 60),)

    monkeypatch.setattr("setloom.transcription.kong.transcribe_kong", fake_kong)

    def no_bp(*a, **k):
        raise AssertionError("Basic Pitch must not run for --engine kong")

    monkeypatch.setattr("setloom.transcription.transcribe_audio", no_bp)
    out = tmp_path / "o.mid"
    rc = cli.main(["transcribe", str(audio), "--out", str(out), "--engine", "kong"])
    assert rc == 0 and seen.get("kong") and out.is_file()


def test_cli_engine_fusion_runs_both(tmp_path, _in_process, monkeypatch) -> None:
    audio = tmp_path / "a.wav"
    audio.touch()
    monkeypatch.setattr(
        "setloom.transcription.kong.transcribe_kong", lambda audio, **k: (_n(0.0, 0.5, 60, 100),)
    )
    monkeypatch.setattr(
        "setloom.transcription.transcribe_audio",
        lambda req: TranscriptionResult(Path(req.out_midi), None, (_n(0.0, 0.5, 60, 90),)),
    )
    out, events = tmp_path / "o.mid", tmp_path / "o.json"
    rc = cli.main(
        ["transcribe", str(audio), "--out", str(out), "--events", str(events), "--engine", "fusion"]
    )
    assert rc == 0 and out.is_file() and events.is_file()


def test_cli_engine_basic_pitch_default(tmp_path, _in_process, monkeypatch) -> None:
    audio = tmp_path / "a.wav"
    audio.touch()
    seen = {}

    def fake_bp(req):
        seen["out_midi"] = req.out_midi
        Path(req.out_midi).write_bytes(b"")
        return TranscriptionResult(Path(req.out_midi), None, (_n(0.0, 0.5, 60),))

    monkeypatch.setattr("setloom.transcription.transcribe_audio", fake_bp)

    def no_kong(*a, **k):
        raise AssertionError("Kong must not run by default")

    monkeypatch.setattr("setloom.transcription.kong.transcribe_kong", no_kong)
    out = tmp_path / "o.mid"
    rc = cli.main(["transcribe", str(audio), "--out", str(out)])
    assert rc == 0 and seen["out_midi"] == str(out)


def test_cli_kong_missing_checkpoint_clean_error(tmp_path, _in_process, monkeypatch, capsys) -> None:
    audio = tmp_path / "a.wav"
    audio.touch()

    def raise_fnf(audio, **k):
        raise FileNotFoundError("Kong checkpoint not found: x")

    monkeypatch.setattr("setloom.transcription.kong.transcribe_kong", raise_fnf)
    rc = cli.main(["transcribe", str(audio), "--out", str(tmp_path / "o.mid"), "--engine", "kong"])
    assert rc == 1
    assert "transcribe failed" in capsys.readouterr().err
