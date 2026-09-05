# SPDX-License-Identifier: AGPL-3.0-only
"""53-stem layer-lens pass: separation and keep-manifest.

This is the separation half of the layer lens: run the MLX 53-stem RoFormer over a
track, keep the stems above the energy threshold, and write a manifest. Note
extraction (turning kept stems into MIDI) lives in :mod:`setloom.anatomy.transcribe`
(the ``--transcribe`` path), so this module stays torch-free and depends only on the
MLX backend. Imported lazily (the ``--layers`` path in ``pipeline.run``).

Model weights download on demand to a gitignored cache; the upstream checkpoint
license is unstated, so the weights are for local analysis only, never redistributed,
never committed. Layer stems are overlapping extractions, not a partition: the same
content can appear in several stems, so do not use them for energy accounting.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

from setloom.anatomy.pipeline import _write_yaml_if_changed
from setloom.anatomy.roformer import separate as separation

MODEL_NAME = "mvsep_mega_bs_roformer_53_stems_v1"
MODEL_STEM = "bs-roformer-53stem-mlx-bf16"  # flat file stem under models/roformer
_RELEASE = (
    "https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download/v1.0.21"
)
CONFIG_URL = f"{_RELEASE}/mvsep_mega_model_bs_roformer_53_stems.yaml"
CKPT_URL = f"{_RELEASE}/mvsep_mega_model_bs_roformer_53_stems_v1.ckpt"

DEFAULT_MODELS = Path("models/roformer")
DEFAULT_LAYER_STEMS = Path("local/corpus/stems53")

KEEP_RMS_DBFS = -40.0  # calibrated on Magma: keeps real layers, drops orchestral bleed
ACTIVE_RMS = 1e-3  # 1 s windows above -60 dBFS count as active


def _download(url: str, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)  # noqa: S310 (pinned https release URL)
    tmp.rename(path)


def fetch_model(models_dir: Path = DEFAULT_MODELS) -> tuple[Path, Path]:
    """Return (config, MLX weights) paths, converting from upstream once if absent.

    The at-rest format is a single MLX ``.safetensors`` plus its ``.yaml`` config,
    flat under ``models/roformer`` and named by model. On a fresh machine the
    upstream torch checkpoint is downloaded once, converted, and then discarded so
    only MLX weights remain.
    """
    models_dir.mkdir(parents=True, exist_ok=True)
    config_path = models_dir / f"{MODEL_STEM}.yaml"
    weights_path = models_dir / f"{MODEL_STEM}.safetensors"
    if not config_path.is_file():
        _download(CONFIG_URL, config_path)
    if not weights_path.is_file():
        ckpt_tmp = models_dir / f"{MODEL_STEM}.upstream.ckpt"
        _download(CKPT_URL, ckpt_tmp)
        separation.convert(ckpt_tmp, weights_path)
        ckpt_tmp.unlink()
    return config_path, weights_path


_BUNDLE: tuple | None = None


def _model_bundle(models_dir: Path) -> tuple:
    """(model, config) — loaded once per process.

    MLX runs on the Metal device implicitly, so there is no device to thread
    through; weights load from the converted bf16 ``.safetensors`` and never touch
    torch (the model then runs bf16-mixed automatically).
    """
    global _BUNDLE
    if _BUNDLE is None:
        config_path, weights_path = fetch_model(models_dir)
        _BUNDLE = separation.load_model(weights_path, config_path)
    return _BUNDLE


def _stem_stats(x: np.ndarray, sr: int) -> tuple[float, float]:
    """(rms_dbfs, active_fraction) for a mono or stereo stem array."""
    mono = x.mean(axis=0) if x.ndim > 1 else x
    rms = float(np.sqrt(np.mean(mono**2)))
    rms_db = float(20 * np.log10(max(rms, 1e-12)))
    win = sr
    n = len(mono) // win
    active = (
        float(
            np.mean(
                [np.sqrt(np.mean(mono[i * win : (i + 1) * win] ** 2)) > ACTIVE_RMS for i in range(n)]
            )
        )
        if n
        else 0.0
    )
    return round(rms_db, 1), round(active, 2)


def _keep(rms_db: float) -> bool:
    return rms_db > KEEP_RMS_DBFS


def _load_stereo_44k(path: Path) -> tuple[np.ndarray, int]:
    import librosa

    sr_model = 44100
    y, _ = librosa.load(str(path), sr=sr_model, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y])
    return y.astype(np.float32), sr_model


def _extract_stems(audio_path: Path, models_dir: Path) -> dict[str, np.ndarray]:
    """Run the 53-stem model over a full track. One model in flight at a time."""
    model, config = _model_bundle(models_dir)
    mix, _ = _load_stereo_44k(audio_path)
    return separation.separate_track(model, config, mix)


def extract_layers(audio_path: Path, layer_dir: Path, models_dir: Path = DEFAULT_MODELS) -> dict:
    """Separate, write kept stems + manifest. Cached when manifest exists."""
    manifest_path = layer_dir / "manifest.yml"
    if manifest_path.is_file():
        import yaml

        return yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    stems = _extract_stems(audio_path, models_dir)
    layer_dir.mkdir(parents=True, exist_ok=True)
    sr_model = 44100
    entries = []
    for name, x in stems.items():
        rms_db, active = _stem_stats(x, sr_model)
        kept = _keep(rms_db)
        entries.append({"layer": name, "rms_dbfs": rms_db, "active": active, "kept": kept})
        if kept:
            sf.write(layer_dir / f"{name}.wav", x.T, sr_model)
    manifest = {
        "model": MODEL_NAME,
        "keep_rms_dbfs": KEEP_RMS_DBFS,
        "stems": sorted(entries, key=lambda e: -e["rms_dbfs"]),
    }
    _write_yaml_if_changed(manifest_path, manifest)
    return manifest


def layer_pass(
    audio_path: Path,
    track: str,
    out_dir: Path,
    layer_stems_dir: Path = DEFAULT_LAYER_STEMS,
    models_dir: Path = DEFAULT_MODELS,
) -> list[str]:
    """Separate a track, write kept stems + manifest + a kept-layers dossier.

    Returns status tokens for the CLI report. Note extraction is a separate pass
    (``setloom.anatomy.transcribe``), reached via ``--transcribe``.
    """
    layer_dir = layer_stems_dir / track
    layers_yml = out_dir / f"{track}.layers.yml"
    if (layer_dir / "manifest.yml").is_file() and layers_yml.is_file():
        return ["layers:cached"]

    manifest = extract_layers(audio_path, layer_dir, models_dir)
    kept = [e["layer"] for e in manifest["stems"] if e["kept"]]
    dossier = {
        "track": track,
        "model": MODEL_NAME,
        "note": "layers are overlapping extractions, not a partition; "
        "do not use layer stems for energy accounting",
        "kept_layers": kept,
    }
    _write_yaml_if_changed(layers_yml, dossier)
    return ["layers:analyzed"]
