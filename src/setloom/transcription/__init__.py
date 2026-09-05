# SPDX-License-Identifier: AGPL-3.0-only
"""Audio-to-MIDI transcription utilities owned by Setloom."""

from setloom.transcription.basic_pitch import (
    BasicPitchActivations,
    BasicPitchModel,
    TranscribedNote,
    TranscriptionRequest,
    TranscriptionResult,
    predict_activations,
    transcribe_audio,
    transcribe_audio_to_midi,
    write_note_events_json,
    write_transcription_midi,
)
from setloom.transcription.fusion import RECALL_FIRST, detect_key, fuse_recall_first
from setloom.transcription.kong import KongModel, transcribe_kong

__all__ = [
    "BasicPitchActivations",
    "BasicPitchModel",
    "KongModel",
    "RECALL_FIRST",
    "TranscribedNote",
    "TranscriptionRequest",
    "TranscriptionResult",
    "detect_key",
    "fuse_recall_first",
    "predict_activations",
    "transcribe_audio",
    "transcribe_audio_to_midi",
    "transcribe_kong",
    "write_note_events_json",
    "write_transcription_midi",
]
