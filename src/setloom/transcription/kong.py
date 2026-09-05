# SPDX-License-Identifier: AGPL-3.0-only
"""ByteDance/Kong high-resolution piano transcription engine.

Kong is a solo-piano specialist (MAESTRO-trained onset/offset regression): excellent
rhythm, and on clean piano excellent pitch. In the harness it is the rhythm/timing source
for the fusion engine (:mod:`setloom.transcription.fusion`) and a standalone option for
clean piano. Heavy deps (``torch`` + ``piano_transcription_inference``) are imported
lazily, so importing this module costs nothing until a :class:`KongModel` is built.

Needs the ``kong`` dependency group and the checkpoint under ``models/piano-transcription/``:

    uv run --group kong setloom transcribe AUDIO --out OUT.mid --engine kong
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import librosa
import numpy as np

from setloom.transcription.basic_pitch import TranscribedNote

DEFAULT_KONG_CHECKPOINT = Path("models/piano-transcription/note_F1=0.9677_pedal_F1=0.8658.pth")
_DOWNLOAD_URL = "https://zenodo.org/record/4034264"


class KongModel:
    """Runner for the Kong piano transcription net (lazy ``torch`` + package import)."""

    def __init__(self, checkpoint_path: str | Path = DEFAULT_KONG_CHECKPOINT) -> None:
        self.checkpoint = Path(checkpoint_path)
        if not self.checkpoint.exists():
            raise FileNotFoundError(
                f"Kong checkpoint not found: {self.checkpoint}. Download it from "
                f"{_DOWNLOAD_URL} into models/piano-transcription/, or pass --kong-checkpoint."
            )
        try:
            import torch  # noqa: F401
            from piano_transcription_inference import PianoTranscription, sample_rate
        except ImportError as exc:
            raise RuntimeError(
                "Kong transcription needs the `kong` dependency group "
                "(torch + piano_transcription_inference). Run with, e.g.: "
                "uv run --group kong setloom transcribe AUDIO --out OUT.mid --engine kong"
            ) from exc
        self._PianoTranscription = PianoTranscription
        self._sample_rate = sample_rate

    def transcribe_to_notes(self, audio_path: str | Path) -> tuple[TranscribedNote, ...]:
        """Audio file -> Kong note list, run on MPS with a CPU fallback.

        Audio is loaded directly with librosa because the package's loader uses a
        removed API. Passing no MIDI destination avoids an unused scratch file.
        """
        import torch

        audio = librosa.load(str(audio_path), sr=self._sample_rate, mono=True)[0].astype(np.float32)
        last_error: Exception | None = None
        for device in ("mps", "cpu"):
            if device == "mps" and not torch.backends.mps.is_available():
                continue
            try:
                engine = self._PianoTranscription(device=device, checkpoint_path=str(self.checkpoint))
                output = engine.transcribe(audio, None)
                return _to_notes(output["est_note_events"])
            except Exception as exc:  # noqa: BLE001 -- fall through to the next device
                last_error = exc
        raise RuntimeError(f"Kong transcription failed on all devices: {last_error}")


def transcribe_kong(
    audio: str | Path,
    *,
    checkpoint_path: str | Path = DEFAULT_KONG_CHECKPOINT,
    model: KongModel | None = None,
) -> tuple[TranscribedNote, ...]:
    """Transcribe an audio file to a note list with Kong.

    A pre-built ``model`` reuses runner configuration; each transcription loads
    its inference engine.
    """
    audio_path = Path(audio)
    if not audio_path.is_file():
        raise FileNotFoundError(f"audio file not found: {audio_path}")
    runner = model if model is not None else KongModel(checkpoint_path)
    return runner.transcribe_to_notes(audio_path)


def _to_notes(events: Sequence[dict]) -> tuple[TranscribedNote, ...]:
    """Map Kong's ``est_note_events`` to ``TranscribedNote``.

    Velocity scale is detected defensively (0..1 floats vs 0..127 ints) and clamped to
    1..127; confidence carries the normalized velocity.
    """
    peak = max((float(ev["velocity"]) for ev in events), default=1.0)
    scale = 127.0 if peak <= 1.0 else 1.0
    notes = []
    for ev in events:
        velocity = int(np.clip(round(float(ev["velocity"]) * scale), 1, 127))
        onset = float(ev["onset_time"])
        notes.append(
            TranscribedNote(
                start_s=onset,
                end_s=max(float(ev["offset_time"]), onset),
                pitch=int(ev["midi_note"]),
                velocity=velocity,
                confidence=velocity / 127.0,
            )
        )
    notes.sort(key=lambda n: (n.start_s, n.pitch))
    return tuple(notes)
