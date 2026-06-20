# SPDX-License-Identifier: AGPL-3.0-only
#
# The note-decoding and pitch-bend algorithms below are ported from Basic Pitch
# (https://github.com/spotify/basic-pitch), Copyright 2022 Spotify AB, originally
# licensed under Apache-2.0. This is a reimplementation on Setloom's stack (mido,
# not pretty_midi); the algorithm design and constants are credited to Spotify AB.
# See LICENSES/NOTICE.
"""Setloom-owned Basic Pitch transcription path.

This module keeps Setloom's macOS audio-to-MIDI surface local and small: load
the local Basic Pitch model asset, decode model output into note events, and
write Setloom-friendly MIDI/JSON artifacts.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

import librosa
import mido
import numpy as np
from scipy import signal

from setloom.midi import PPQ

FFT_HOP = 256
AUDIO_SAMPLE_RATE = 22_050
AUDIO_WINDOW_LENGTH = 2
AUDIO_N_SAMPLES = AUDIO_SAMPLE_RATE * AUDIO_WINDOW_LENGTH - FFT_HOP
ANNOTATIONS_FPS = AUDIO_SAMPLE_RATE // FFT_HOP
ANNOTATION_FRAMES = ANNOTATIONS_FPS * AUDIO_WINDOW_LENGTH
DEFAULT_OVERLAPPING_FRAMES = 30
DEFAULT_ONSET_THRESHOLD = 0.5
DEFAULT_FRAME_THRESHOLD = 0.3
DEFAULT_MINIMUM_NOTE_LENGTH_MS = 127.7
MIDI_OFFSET = 21
MAX_FREQ_IDX = 87
DEFAULT_ENERGY_TOLERANCE = 11
MAGIC_ALIGNMENT_OFFSET = 0.0018
DEFAULT_MODEL_ROOT = Path("models/basic-pitch/icassp_2022")
MODEL_ASSET_NAME = "nmp.mlpackage"

# Contour / pitch-bend constants (ported from Basic Pitch's note_creation.py).
CONTOURS_BINS_PER_SEMITONE = 3
ANNOTATIONS_BASE_FREQUENCY = 27.5  # Hz, lowest piano key (A0)
N_FREQ_BINS_CONTOURS = 264  # 88 semitones * 3 contour bins per semitone
N_PITCH_BEND_TICKS = 8192  # MIDI pitch-wheel half-range
PITCH_BEND_SCALE = 4096  # ticks per semitone at the default GM +/-2 semitone range
DEFAULT_N_BINS_TOLERANCE = 25

# MIDI channels used to spread overlapping notes when multiple_pitch_bends is set;
# channel 9 is reserved for percussion, so it is skipped.
_PITCH_BEND_CHANNELS = [c for c in range(16) if c != 9]


@dataclass(frozen=True)
class TranscribedNote:
    """One recovered note from audio transcription."""

    start_s: float
    end_s: float
    pitch: int
    velocity: int
    confidence: float
    pitch_bends: tuple[int, ...] | None = None


@dataclass(frozen=True)
class TranscriptionRequest:
    """Self-contained request for one audio-to-MIDI transcription pass."""

    audio: str | Path
    out_midi: str | Path
    out_events: str | Path | None = None
    model_path: str | Path | None = None
    model_root: str | Path = DEFAULT_MODEL_ROOT
    onset_threshold: float = DEFAULT_ONSET_THRESHOLD
    frame_threshold: float = DEFAULT_FRAME_THRESHOLD
    minimum_note_length_ms: float = DEFAULT_MINIMUM_NOTE_LENGTH_MS
    minimum_frequency: float | None = None
    maximum_frequency: float | None = None
    midi_tempo: float = 120.0
    channel: int = 0
    melodia: bool = True
    infer_onsets: bool = True
    energy_tol: int = DEFAULT_ENERGY_TOLERANCE
    include_pitch_bends: bool = True
    multiple_pitch_bends: bool = False


@dataclass(frozen=True)
class TranscriptionResult:
    """Files and note events written by a transcription pass."""

    midi_path: Path
    events_path: Path | None
    notes: tuple[TranscribedNote, ...]


class BasicPitchModel:
    """Small runner for the bundled Basic Pitch model asset."""

    def __init__(self, model_path: str | Path) -> None:
        self.path = Path(model_path)
        if not self.path.exists():
            raise FileNotFoundError(
                f"Basic Pitch model not found: {self.path}. "
                "Place the model under models/basic-pitch/icassp_2022/ or pass --model-path."
            )
        model_tmp = Path("tmp/transcription").resolve()
        model_tmp.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("TMPDIR", str(model_tmp))
        try:
            import coremltools as ct
        except ImportError as exc:
            raise RuntimeError(
                "coremltools is required for the current Setloom Basic Pitch implementation. "
                "Run with the transcription dependency group enabled."
            ) from exc

        self._model = ct.models.MLModel(str(self.path), compute_units=ct.ComputeUnit.CPU_ONLY)

    def predict(self, audio_window: np.ndarray) -> dict[str, np.ndarray]:
        result = self._model.predict({"input_2": audio_window.astype(np.float32)})
        return {
            "note": result["Identity_1"],
            "onset": result["Identity_2"],
            "contour": result["Identity"],
        }


def default_model_path(model_root: str | Path = DEFAULT_MODEL_ROOT) -> Path:
    return Path(model_root) / MODEL_ASSET_NAME


def _request_from_audio(
    audio: str | Path | TranscriptionRequest,
    **overrides: Any,
) -> TranscriptionRequest:
    if isinstance(audio, TranscriptionRequest):
        if overrides:
            raise TypeError("overrides are not accepted when passing TranscriptionRequest")
        return audio
    valid_fields = {field.name for field in fields(TranscriptionRequest)}
    unknown = set(overrides) - valid_fields
    if unknown:
        names = ", ".join(sorted(unknown))
        raise TypeError(f"unknown transcription option(s): {names}")
    return TranscriptionRequest(audio=audio, **overrides)


def _read_audio_windows(audio_path: Path) -> tuple[list[np.ndarray], int]:
    audio, _ = librosa.load(str(audio_path), sr=AUDIO_SAMPLE_RATE, mono=True)
    original_length = int(audio.shape[0])
    overlap_len = DEFAULT_OVERLAPPING_FRAMES * FFT_HOP
    hop_size = AUDIO_N_SAMPLES - overlap_len
    padded = np.concatenate(
        [np.zeros((overlap_len // 2,), dtype=np.float32), audio.astype(np.float32)]
    )
    windows: list[np.ndarray] = []
    for start in range(0, padded.shape[0], hop_size):
        window = padded[start : start + AUDIO_N_SAMPLES]
        if len(window) < AUDIO_N_SAMPLES:
            window = np.pad(window, pad_width=[0, AUDIO_N_SAMPLES - len(window)])
        windows.append(window.reshape(1, AUDIO_N_SAMPLES, 1).astype(np.float32))
    return windows, original_length


def _unwrap_model_output(output: np.ndarray, audio_length: int) -> np.ndarray:
    if output.ndim != 3:
        raise ValueError(f"expected batched model output with 3 dims, got {output.shape}")
    hop_size = AUDIO_N_SAMPLES - DEFAULT_OVERLAPPING_FRAMES * FFT_HOP
    overlap_frames = DEFAULT_OVERLAPPING_FRAMES // 2
    if overlap_frames > 0:
        output = output[:, overlap_frames:-overlap_frames, :]
    output_shape = output.shape
    unwrapped = output.reshape(output_shape[0] * output_shape[1], output_shape[2])
    expected_windows = audio_length / hop_size
    frames_per_window = AUDIO_WINDOW_LENGTH * ANNOTATIONS_FPS - DEFAULT_OVERLAPPING_FRAMES
    return unwrapped[: int(expected_windows * frames_per_window), :]


def _run_model(audio_path: Path, model: BasicPitchModel) -> dict[str, np.ndarray]:
    windows, audio_length = _read_audio_windows(audio_path)
    output: dict[str, list[np.ndarray]] = {"note": [], "onset": [], "contour": []}
    for window in windows:
        prediction = model.predict(window)
        for name in output:
            output[name].append(prediction[name])
    return {
        name: _unwrap_model_output(np.concatenate(chunks), audio_length)
        for name, chunks in output.items()
    }


def _frequency_bounds(
    onsets: np.ndarray,
    frames: np.ndarray,
    minimum_frequency: float | None,
    maximum_frequency: float | None,
) -> tuple[np.ndarray, np.ndarray]:
    min_idx = 0 if minimum_frequency is None else int(round(librosa.hz_to_midi(minimum_frequency) - MIDI_OFFSET))
    max_idx = onsets.shape[1] if maximum_frequency is None else int(
        round(librosa.hz_to_midi(maximum_frequency) - MIDI_OFFSET)
    )
    min_idx = max(0, min_idx)
    max_idx = min(onsets.shape[1], max_idx)
    onsets = onsets.copy()
    frames = frames.copy()
    onsets[:, :min_idx] = 0
    frames[:, :min_idx] = 0
    onsets[:, max_idx:] = 0
    frames[:, max_idx:] = 0
    return onsets, frames


def _inferred_onsets(onsets: np.ndarray, frames: np.ndarray, n_diff: int = 2) -> np.ndarray:
    diffs = []
    for offset in range(1, n_diff + 1):
        prefixed = np.concatenate([np.zeros((offset, frames.shape[1])), frames])
        diffs.append(prefixed[offset:, :] - prefixed[:-offset, :])
    frame_diff = np.min(diffs, axis=0)
    frame_diff[frame_diff < 0] = 0
    frame_diff[:n_diff, :] = 0
    max_frame_diff = np.max(frame_diff)
    if max_frame_diff > 0:
        frame_diff = np.max(onsets) * frame_diff / max_frame_diff
    return np.max([onsets, frame_diff], axis=0)


def _frame_times(n_frames: int) -> np.ndarray:
    original_times = librosa.core.frames_to_time(
        np.arange(n_frames),
        sr=AUDIO_SAMPLE_RATE,
        hop_length=FFT_HOP,
    )
    window_numbers = np.floor(np.arange(n_frames) / ANNOTATION_FRAMES)
    window_offset = (FFT_HOP / AUDIO_SAMPLE_RATE) * (
        ANNOTATION_FRAMES - (AUDIO_N_SAMPLES / FFT_HOP)
    )
    return original_times - ((window_offset + MAGIC_ALIGNMENT_OFFSET) * window_numbers)


def _midi_pitch_to_contour_bin(pitch_midi: int) -> float:
    """Map a MIDI pitch to its (fractional) bin in the contour matrix."""
    pitch_hz = float(librosa.midi_to_hz(pitch_midi))
    return 12.0 * CONTOURS_BINS_PER_SEMITONE * np.log2(pitch_hz / ANNOTATIONS_BASE_FREQUENCY)


def _get_pitch_bends(
    contours: np.ndarray,
    note_events: list[tuple[int, int, int, float]],
    n_bins_tolerance: int = DEFAULT_N_BINS_TOLERANCE,
) -> list[tuple[int, int, int, float, tuple[int, ...] | None]]:
    """Estimate a per-frame pitch-bend sequence for each note from the contour map.

    Ported from Basic Pitch's ``get_pitch_bends``. Each bend value is in units of
    1/3 of a semitone (one contour bin) and is coerced to a Python ``int`` so the
    note-events JSON stays serializable (raw ``np.argmax`` output is ``np.int64``).
    """
    window_length = n_bins_tolerance * 2 + 1
    freq_gaussian = signal.windows.gaussian(window_length, std=5)
    notes_with_bends: list[tuple[int, int, int, float, tuple[int, ...] | None]] = []
    for start_idx, end_idx, pitch_midi, amplitude in note_events:
        freq_idx = int(round(_midi_pitch_to_contour_bin(pitch_midi)))
        freq_start_idx = max(freq_idx - n_bins_tolerance, 0)
        freq_end_idx = min(N_FREQ_BINS_CONTOURS, freq_idx + n_bins_tolerance + 1)
        gaussian_start = max(0, n_bins_tolerance - freq_idx)
        gaussian_end = window_length - max(
            0, freq_idx - (N_FREQ_BINS_CONTOURS - n_bins_tolerance - 1)
        )
        pitch_bend_submatrix = (
            contours[start_idx:end_idx, freq_start_idx:freq_end_idx]
            * freq_gaussian[gaussian_start:gaussian_end]
        )
        pb_shift = n_bins_tolerance - max(0, n_bins_tolerance - freq_idx)
        bends = tuple(int(b) for b in (np.argmax(pitch_bend_submatrix, axis=1) - pb_shift))
        notes_with_bends.append((start_idx, end_idx, pitch_midi, amplitude, bends))
    return notes_with_bends


def _decode_notes(
    model_output: dict[str, np.ndarray],
    request: TranscriptionRequest,
) -> tuple[TranscribedNote, ...]:
    frames = model_output["note"]
    onsets = model_output["onset"]
    min_note_frames = int(
        round(request.minimum_note_length_ms / 1000.0 * (AUDIO_SAMPLE_RATE / FFT_HOP))
    )
    onsets, remaining_energy = _frequency_bounds(
        onsets,
        frames,
        request.minimum_frequency,
        request.maximum_frequency,
    )
    if request.infer_onsets:
        onsets = _inferred_onsets(onsets, remaining_energy)

    peak_matrix = np.zeros(onsets.shape)
    peaks = signal.argrelmax(onsets, axis=0)
    peak_matrix[peaks] = onsets[peaks]
    onset_idx = np.where(peak_matrix >= request.onset_threshold)
    onset_times = onset_idx[0][::-1]
    onset_pitches = onset_idx[1][::-1]
    times = _frame_times(frames.shape[0])

    raw_notes: list[tuple[int, int, int, float]] = []
    for start_idx, pitch_idx in zip(onset_times, onset_pitches):
        if start_idx >= frames.shape[0] - 1:
            continue
        end_idx = _find_note_end(
            remaining_energy, start_idx, pitch_idx, request.frame_threshold, request.energy_tol
        )
        if end_idx - start_idx <= min_note_frames:
            continue
        _clear_note_energy(remaining_energy, start_idx, end_idx, pitch_idx)
        raw_notes.append(
            (
                start_idx,
                end_idx,
                pitch_idx + MIDI_OFFSET,
                float(np.mean(frames[start_idx:end_idx, pitch_idx])),
            )
        )

    if request.melodia:
        raw_notes.extend(
            _decode_remaining_energy(
                remaining_energy, frames, request.frame_threshold, min_note_frames, request.energy_tol
            )
        )

    if request.include_pitch_bends:
        notes_with_bends = _get_pitch_bends(model_output["contour"], raw_notes)
    else:
        notes_with_bends = [(start, end, pitch, conf, None) for start, end, pitch, conf in raw_notes]

    notes = [
        TranscribedNote(
            start_s=max(0.0, float(times[start])),
            end_s=max(float(times[start]), float(times[end])),
            pitch=int(pitch),
            velocity=int(np.clip(round(127 * confidence), 1, 127)),
            confidence=float(confidence),
            pitch_bends=bends,
        )
        for start, end, pitch, confidence, bends in notes_with_bends
    ]
    notes.sort(key=lambda note: (note.start_s, note.pitch, note.end_s))
    return tuple(notes)


def _find_note_end(
    energy: np.ndarray,
    start_idx: int,
    pitch_idx: int,
    frame_threshold: float,
    energy_tol: int,
) -> int:
    idx = start_idx + 1
    below_count = 0
    while idx < energy.shape[0] - 1 and below_count < energy_tol:
        if energy[idx, pitch_idx] < frame_threshold:
            below_count += 1
        else:
            below_count = 0
        idx += 1
    return idx - below_count


def _clear_note_energy(energy: np.ndarray, start_idx: int, end_idx: int, pitch_idx: int) -> None:
    energy[start_idx:end_idx, pitch_idx] = 0
    if pitch_idx < MAX_FREQ_IDX:
        energy[start_idx:end_idx, pitch_idx + 1] = 0
    if pitch_idx > 0:
        energy[start_idx:end_idx, pitch_idx - 1] = 0


def _decode_remaining_energy(
    energy: np.ndarray,
    frames: np.ndarray,
    frame_threshold: float,
    min_note_frames: int,
    energy_tol: int,
) -> list[tuple[int, int, int, float]]:
    notes: list[tuple[int, int, int, float]] = []
    while np.max(energy) > frame_threshold:
        middle_idx, pitch_idx = np.unravel_index(np.argmax(energy), energy.shape)
        energy[middle_idx, pitch_idx] = 0

        end_idx = middle_idx + 1
        below_count = 0
        while end_idx < energy.shape[0] - 1 and below_count < energy_tol:
            below_count = below_count + 1 if energy[end_idx, pitch_idx] < frame_threshold else 0
            _clear_note_energy(energy, end_idx, end_idx + 1, pitch_idx)
            end_idx += 1
        end_idx = end_idx - 1 - below_count

        start_idx = middle_idx - 1
        below_count = 0
        while start_idx > 0 and below_count < energy_tol:
            below_count = below_count + 1 if energy[start_idx, pitch_idx] < frame_threshold else 0
            _clear_note_energy(energy, start_idx, start_idx + 1, pitch_idx)
            start_idx -= 1
        start_idx = start_idx + 1 + below_count

        if end_idx - start_idx <= min_note_frames:
            continue
        notes.append(
            (
                start_idx,
                end_idx,
                pitch_idx + MIDI_OFFSET,
                float(np.mean(frames[start_idx:end_idx, pitch_idx])),
            )
        )
    return notes


def _seconds_to_tick(seconds: float, bpm: float) -> int:
    return max(0, round(seconds * bpm / 60.0 * PPQ))


# Equal-tick ordering ranks: a note_off frees a pitch and a pitchwheel sets up the
# channel bend before a same-tick note_on begins, so each note starts in a clean state.
_RANK_NOTE_OFF = 0
_RANK_PITCH_WHEEL = 1
_RANK_NOTE_ON = 2


def _note_messages(
    note: TranscribedNote, channel: int, bpm: float
) -> list[tuple[int, int, mido.Message]]:
    """Build (abs_tick, rank, message) tuples for one note, including any pitch bends."""
    start_tick = _seconds_to_tick(note.start_s, bpm)
    end_tick = max(start_tick + 1, _seconds_to_tick(note.end_s, bpm))
    events: list[tuple[int, int, mido.Message]] = [
        (
            start_tick,
            _RANK_NOTE_ON,
            mido.Message("note_on", channel=channel, note=note.pitch, velocity=note.velocity, time=0),
        ),
        (
            end_tick,
            _RANK_NOTE_OFF,
            mido.Message("note_off", channel=channel, note=note.pitch, velocity=0, time=0),
        ),
    ]
    if note.pitch_bends:
        bend_times = np.linspace(note.start_s, note.end_s, len(note.pitch_bends))
        for bend, when in zip(note.pitch_bends, bend_times):
            value = int(round(bend * PITCH_BEND_SCALE / CONTOURS_BINS_PER_SEMITONE))
            value = max(-N_PITCH_BEND_TICKS, min(N_PITCH_BEND_TICKS - 1, value))
            events.append(
                (
                    _seconds_to_tick(float(when), bpm),
                    _RANK_PITCH_WHEEL,
                    mido.Message("pitchwheel", channel=channel, pitch=value, time=0),
                )
            )
    return events


def _emit_track(
    events: list[tuple[int, int, mido.Message]], bpm: float, *, include_tempo: bool
) -> mido.MidiTrack:
    """Delta-encode absolute-tick events into one MIDI track."""
    track = mido.MidiTrack()
    if include_tempo:
        track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    cursor = 0
    for tick, _rank, message in sorted(events, key=lambda item: (item[0], item[1])):
        message.time = tick - cursor
        cursor = tick
        track.append(message)
    track.append(mido.MetaMessage("end_of_track", time=0))
    return track


def _drop_overlapping_pitch_bends(notes: list[TranscribedNote]) -> list[TranscribedNote]:
    """Null out pitch bends on time-overlapping notes (ported from Basic Pitch).

    MIDI pitch bend is per-channel, so on a single track only non-overlapping notes
    can carry independent bends without bleeding into one another.
    """
    ordered = sorted(notes, key=lambda note: (note.start_s, note.end_s, note.pitch))
    for i in range(len(ordered) - 1):
        for j in range(i + 1, len(ordered)):
            if ordered[j].start_s >= ordered[i].end_s:
                break
            ordered[i] = replace(ordered[i], pitch_bends=None)
            ordered[j] = replace(ordered[j], pitch_bends=None)
    return ordered


def write_transcription_midi(
    notes: tuple[TranscribedNote, ...] | list[TranscribedNote],
    path: str | Path,
    *,
    bpm: float = 120.0,
    channel: int = 0,
    multiple_pitch_bends: bool = False,
) -> Path:
    """Write recovered note events as a Setloom-compatible MIDI file.

    Pitch bends are emitted as ``pitchwheel`` messages. In the default single-track
    mode, bends on time-overlapping notes are dropped (they would share one channel's
    pitch wheel); set ``multiple_pitch_bends`` to keep every note's bends by writing
    one track per distinct pitch. No wheel reset is emitted between notes, matching
    upstream Basic Pitch, so a bend can persist on a channel until the next one.
    """
    midi_path = Path(path)
    midi_path.parent.mkdir(parents=True, exist_ok=True)
    midi_file = mido.MidiFile(type=1, ticks_per_beat=PPQ)

    if multiple_pitch_bends:
        by_pitch: dict[int, list[TranscribedNote]] = defaultdict(list)
        for note in notes:
            by_pitch[note.pitch].append(note)
        include_tempo = True
        for index, pitch in enumerate(sorted(by_pitch)):
            track_channel = _PITCH_BEND_CHANNELS[index % len(_PITCH_BEND_CHANNELS)]
            events: list[tuple[int, int, mido.Message]] = []
            for note in by_pitch[pitch]:
                events.extend(_note_messages(note, track_channel, bpm))
            midi_file.tracks.append(_emit_track(events, bpm, include_tempo=include_tempo))
            include_tempo = False
        if not midi_file.tracks:
            midi_file.tracks.append(_emit_track([], bpm, include_tempo=True))
    else:
        events = []
        for note in _drop_overlapping_pitch_bends(list(notes)):
            events.extend(_note_messages(note, channel, bpm))
        midi_file.tracks.append(_emit_track(events, bpm, include_tempo=True))

    midi_file.save(str(midi_path))
    return midi_path


def write_note_events_json(
    notes: tuple[TranscribedNote, ...] | list[TranscribedNote],
    path: str | Path,
) -> Path:
    events_path = Path(path)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.write_text(
        json.dumps([asdict(note) for note in notes], indent=2) + "\n",
        encoding="utf-8",
    )
    return events_path


def transcribe_audio(audio: str | Path | TranscriptionRequest, **overrides: Any) -> TranscriptionResult:
    """Transcribe an audio file into MIDI and optional note-event JSON."""
    request = _request_from_audio(audio, **overrides)
    audio_path = Path(request.audio)
    if not audio_path.is_file():
        raise FileNotFoundError(f"audio file not found: {audio_path}")
    model_path = (
        Path(request.model_path)
        if request.model_path is not None
        else default_model_path(request.model_root)
    )
    model = BasicPitchModel(model_path)
    model_output = _run_model(audio_path, model)
    notes = _decode_notes(model_output, request)
    midi_path = write_transcription_midi(
        notes,
        request.out_midi,
        bpm=request.midi_tempo,
        channel=request.channel,
        multiple_pitch_bends=request.multiple_pitch_bends,
    )
    events_path = (
        write_note_events_json(notes, request.out_events) if request.out_events is not None else None
    )
    return TranscriptionResult(midi_path=midi_path, events_path=events_path, notes=notes)


def transcribe_audio_to_midi(
    audio: str | Path,
    out_midi: str | Path,
    **overrides: Any,
) -> TranscriptionResult:
    """Convenience API for one audio file to one MIDI file."""
    return transcribe_audio(audio, out_midi=out_midi, **overrides)
