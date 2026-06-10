# SPDX-License-Identifier: AGPL-3.0-only
"""Stem separation: the only module allowed to touch demucs/torch.

Stems are saved with soundfile. `torchaudio.save` is forbidden here: it
delegates to torchcodec, which needs a system FFmpeg. Keeping the model
behind this one boundary makes an upstream fork swap a one-file change.
"""

from __future__ import annotations

from pathlib import Path

import soundfile as sf

STEM_NAMES = ("drums", "bass", "other", "vocals")
MODEL_NAME = "htdemucs"

_MODEL = None


def stems_present(stem_dir: Path) -> bool:
    return all((stem_dir / f"{name}.wav").is_file() for name in STEM_NAMES)


def _model():
    global _MODEL
    if _MODEL is None:
        from demucs.pretrained import get_model

        _MODEL = get_model(MODEL_NAME)
        _MODEL.eval()
    return _MODEL


def separate_track(audio_path: Path, stem_dir: Path) -> Path:
    """Separate one track into drums/bass/other/vocals under stem_dir."""
    import torch
    from demucs.apply import apply_model

    model = _model()
    wav, sr = sf.read(audio_path, always_2d=True)
    if sr != model.samplerate:
        import librosa

        wav = librosa.resample(wav.T, orig_sr=sr, target_sr=model.samplerate).T
        sr = model.samplerate
    if wav.shape[1] == 1:
        wav = wav.repeat(2, axis=1)

    mix = torch.from_numpy(wav.T).float()[None]
    ref = mix.mean(1)
    mean, std = ref.mean(), ref.std()
    normalized = (mix - mean) / (1e-8 + std)
    with torch.no_grad():
        sources = apply_model(
            model, normalized, device="cpu", shifts=0, split=True, overlap=0.25, progress=False
        )[0]
    sources = sources * std + mean

    stem_dir.mkdir(parents=True, exist_ok=True)
    for name, src in zip(model.sources, sources):
        sf.write(stem_dir / f"{name}.wav", src.numpy().T, sr)
    return stem_dir
