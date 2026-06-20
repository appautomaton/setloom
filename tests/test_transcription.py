# SPDX-License-Identifier: AGPL-3.0-only

import json

import mido
import numpy as np

from setloom.transcription import (
    TranscribedNote,
    write_note_events_json,
    write_transcription_midi,
)
from setloom.transcription.basic_pitch import (
    TranscriptionRequest,
    _decode_notes,
    _get_pitch_bends,
    _midi_pitch_to_contour_bin,
)

N_NOTE_BINS = 88
N_CONTOUR_BINS = 264
MIDI_OFFSET = 21


def _model_output(n_frames, *, notes=(), onset_peaks=(), contour=None):
    note = np.zeros((n_frames, N_NOTE_BINS), dtype=np.float32)
    onset = np.zeros((n_frames, N_NOTE_BINS), dtype=np.float32)
    for pitch_idx, start, end, value in notes:
        note[start:end, pitch_idx] = value
    for pitch_idx, frame, value in onset_peaks:
        onset[frame, pitch_idx] = value
    if contour is None:
        contour = np.zeros((n_frames, N_CONTOUR_BINS), dtype=np.float32)
    return {"note": note, "onset": onset, "contour": contour}


def _request(**overrides):
    base = dict(audio="x.wav", out_midi="x.mid", include_pitch_bends=False)
    base.update(overrides)
    return TranscriptionRequest(**base)


def _pitches(notes):
    return {note.pitch for note in notes}


def test_transcription_writers_emit_midi_and_json(tmp_path) -> None:
    notes = (
        TranscribedNote(start_s=0.0, end_s=0.5, pitch=60, velocity=96, confidence=0.76),
        TranscribedNote(start_s=0.25, end_s=0.75, pitch=64, velocity=88, confidence=0.69),
    )
    midi_path = write_transcription_midi(notes, tmp_path / "notes.mid", bpm=120)
    events_path = write_note_events_json(notes, tmp_path / "notes.json")

    midi = mido.MidiFile(midi_path)
    note_ons = [
        message
        for message in midi.tracks[0]
        if message.type == "note_on" and message.velocity > 0
    ]
    events = json.loads(events_path.read_text(encoding="utf-8"))

    assert [message.note for message in note_ons] == [60, 64]
    assert events[0]["pitch"] == 60
    assert events[1]["velocity"] == 88


def test_infer_onsets_recovers_notes_independent_of_melodia() -> None:
    # Pitch A (idx 30) has an explicit onset; pitch B (idx 50) only a frame jump.
    mo = _model_output(
        60,
        notes=[(30, 10, 45, 0.8), (50, 15, 45, 0.8)],
        onset_peaks=[(30, 10, 0.9)],
    )
    with_infer = _decode_notes(mo, _request(infer_onsets=True, melodia=False))
    without_infer = _decode_notes(mo, _request(infer_onsets=False, melodia=False))

    assert _pitches(with_infer) == {30 + MIDI_OFFSET, 50 + MIDI_OFFSET}
    assert _pitches(without_infer) == {30 + MIDI_OFFSET}


def test_melodia_recovers_notes_independent_of_infer_onsets() -> None:
    mo = _model_output(
        60,
        notes=[(30, 10, 45, 0.8), (50, 15, 45, 0.8)],
        onset_peaks=[(30, 10, 0.9)],
    )
    with_melodia = _decode_notes(mo, _request(infer_onsets=False, melodia=True))
    without_melodia = _decode_notes(mo, _request(infer_onsets=False, melodia=False))

    assert _pitches(with_melodia) == {30 + MIDI_OFFSET, 50 + MIDI_OFFSET}
    assert _pitches(without_melodia) == {30 + MIDI_OFFSET}


def test_energy_tol_controls_note_extension() -> None:
    # One pitch with a 5-frame energy gap mid-note.
    mo = _model_output(
        60,
        notes=[(40, 10, 25, 0.8), (40, 30, 45, 0.8)],
        onset_peaks=[(40, 10, 0.9)],
    )
    wide = _decode_notes(mo, _request(energy_tol=11, melodia=False, infer_onsets=False))
    narrow = _decode_notes(mo, _request(energy_tol=2, melodia=False, infer_onsets=False))

    assert len(wide) == 1 and len(narrow) == 1
    # A larger tolerance bridges the gap, so the note ends later.
    assert wide[0].end_s > narrow[0].end_s


def test_get_pitch_bends_returns_python_ints_of_correct_length() -> None:
    pitch_midi = 61
    center = int(round(_midi_pitch_to_contour_bin(pitch_midi)))
    contour = np.zeros((30, N_CONTOUR_BINS), dtype=np.float32)
    contour[5:20, center + 2] = 1.0  # salient bin two contour bins sharp

    (_, _, _, _, bends) = _get_pitch_bends(contour, [(5, 20, pitch_midi, 0.8)])[0]

    assert len(bends) == 15
    assert all(isinstance(b, int) for b in bends)
    assert set(bends) == {2}


def test_pitch_bends_serialize_to_json(tmp_path) -> None:
    note = TranscribedNote(0.5, 0.78, 64, 88, 0.69, pitch_bends=(-1, 0, 1))
    path = write_note_events_json([note], tmp_path / "n.json")
    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert loaded[0]["pitch_bends"] == [-1, 0, 1]
    assert all(isinstance(b, int) for b in loaded[0]["pitch_bends"])


def _pitchwheels(midi):
    return [m for track in midi.tracks for m in track if m.type == "pitchwheel"]


def test_single_track_emits_pitchwheel(tmp_path) -> None:
    note = TranscribedNote(0.0, 0.5, 60, 100, 0.8, pitch_bends=(0, 1, 2, 3))
    midi = mido.MidiFile(write_transcription_midi([note], tmp_path / "n.mid", bpm=120))
    wheels = _pitchwheels(midi)

    assert len(wheels) == 4
    assert all(-8192 <= m.pitch <= 8191 for m in wheels)
    assert any(m.pitch != 0 for m in wheels)


def test_overlapping_notes_drop_bends_single_track(tmp_path) -> None:
    notes = [
        TranscribedNote(0.0, 0.5, 60, 100, 0.8, pitch_bends=(1, 2, 3)),
        TranscribedNote(0.25, 0.75, 64, 90, 0.7, pitch_bends=(1, 2, 3)),
    ]
    midi = mido.MidiFile(write_transcription_midi(notes, tmp_path / "n.mid", bpm=120))

    assert _pitchwheels(midi) == []


def test_multiple_pitch_bends_keeps_bends_on_overlap(tmp_path) -> None:
    notes = [
        TranscribedNote(0.0, 0.5, 60, 100, 0.8, pitch_bends=(1, 2, 3)),
        TranscribedNote(0.25, 0.75, 64, 90, 0.7, pitch_bends=(1, 2, 3)),
    ]
    midi = mido.MidiFile(
        write_transcription_midi(
            notes, tmp_path / "n.mid", bpm=120, multiple_pitch_bends=True
        )
    )

    assert len(midi.tracks) >= 2
    assert len(_pitchwheels(midi)) > 0


def test_clean_onset_yields_one_note_with_bounded_velocity() -> None:
    mo = _model_output(60, notes=[(40, 10, 40, 0.8)], onset_peaks=[(40, 10, 0.9)])
    notes = _decode_notes(mo, _request())

    assert len(notes) == 1
    assert notes[0].pitch == 40 + MIDI_OFFSET
    assert 1 <= notes[0].velocity <= 127
