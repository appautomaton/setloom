# SPDX-License-Identifier: AGPL-3.0-only
"""53-stem layer-lens pass: extraction, keep-manifest, and melodic transcription.

This module is torch-heavy and must only be imported lazily (the ``--layers``
path in ``pipeline.run``). Model weights download on demand to a gitignored
cache; the upstream checkpoint license is unstated, so the weights are for
local analysis only — never redistributed, never committed.

Layer stems are overlapping extractions, not a partition: the same content can
appear in several stems (the synth stem carries the bassline too, which is why
melodic prep high-passes it). Energy-accounting metrics stay on the demucs
partition in ``pipeline.stem_pass``.
"""

from __future__ import annotations

import urllib.request
import warnings
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from setloom.anatomy import analysis as an
from setloom.anatomy.pipeline import SR, Grid, _write_yaml_if_changed, write_bass_midi
from setloom.anatomy.roformer import infer

MODEL_NAME = "mvsep_mega_bs_roformer_53_stems_v1"
_RELEASE = (
    "https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download/v1.0.21"
)
CONFIG_URL = f"{_RELEASE}/mvsep_mega_model_bs_roformer_53_stems.yaml"
CKPT_URL = f"{_RELEASE}/mvsep_mega_model_bs_roformer_53_stems_v1.ckpt"

DEFAULT_MODELS = Path("anatomy/_models")
DEFAULT_LAYER_STEMS = Path("anatomy/_stems53")

KEEP_RMS_DBFS = -40.0  # calibrated on Magma: keeps real layers, drops orchestral bleed
MELODIC_LAYERS = ("synth", "keys")  # transcription targets when present
HP_CUTOFF_HZ = 120.0  # synth stem duplicates the bassline; strip it before f0
ACTIVE_RMS = 1e-3  # 1 s windows above -60 dBFS count as active
FCPE_VOICED_MIN = 0.4


def _device() -> str:
    return "mps" if torch.backends.mps.is_available() else "cpu"


def fetch_model(models_dir: Path = DEFAULT_MODELS) -> tuple[Path, Path]:
    """Download config + checkpoint once into the gitignored cache."""
    models_dir.mkdir(parents=True, exist_ok=True)
    config_path = models_dir / Path(CONFIG_URL).name
    ckpt_path = models_dir / Path(CKPT_URL).name
    for url, path in ((CONFIG_URL, config_path), (CKPT_URL, ckpt_path)):
        if not path.is_file():
            tmp = path.with_suffix(path.suffix + ".part")
            urllib.request.urlretrieve(url, tmp)  # noqa: S310 (pinned https release URL)
            tmp.rename(path)
    return config_path, ckpt_path


_BUNDLE: tuple | None = None


def _model_bundle(models_dir: Path) -> tuple:
    """(model, config, instrument names, device) — loaded once per process."""
    global _BUNDLE
    if _BUNDLE is None:
        config_path, ckpt_path = fetch_model(models_dir)
        config = infer.load_config(config_path)
        model = infer.build_model(config)
        infer.load_weights(model, ckpt_path)
        device = _device()
        model = model.to(device)
        _BUNDLE = (model, config, infer.instruments(config), device)
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
    model, config, names, device = _model_bundle(models_dir)
    mix, _ = _load_stereo_44k(audio_path)
    inference = config["inference"]
    return infer.separate(
        model,
        mix,
        names,
        chunk_size=int(inference["chunk_size"]),
        num_overlap=int(inference["num_overlap"]),
        batch_size=int(inference.get("batch_size", 1)),
        device=device,
    )


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


def _prep_melodic(y: np.ndarray, sr: int, layer: str) -> np.ndarray:
    """High-pass the synth layer (it duplicates the bassline) and clamp.

    Clamping to [-1, 1] is load-bearing: filtfilt overshoot trips torchfcpe's
    mel extractor on MPS (probe finding, 2026-06-10).
    """
    import scipy.signal as ss

    if layer == "synth":
        sos = ss.butter(4, HP_CUTOFF_HZ, "hp", fs=sr, output="sos")
        y = ss.sosfiltfilt(sos, y)
    peak = float(np.max(np.abs(y)))
    if peak > 1.0:
        y = y / peak
    return np.ascontiguousarray(y, dtype=np.float32)


_FCPE = None


def _f0_track(y: np.ndarray, sr: int) -> np.ndarray:
    """Frame-rate f0 in Hz (0 where unvoiced) via torchfcpe."""
    global _FCPE
    from torchfcpe import spawn_bundled_infer_model

    device = _device()
    if _FCPE is None:
        _FCPE = spawn_bundled_infer_model(device=device)
    audio = torch.from_numpy(y).unsqueeze(0).unsqueeze(-1).to(device)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f0 = _FCPE.infer(audio, sr=sr, decoder_mode="local_argmax", threshold=0.006)
    return f0.squeeze().cpu().numpy()


def _f0_steps(f0: np.ndarray, duration: float, grid: Grid) -> np.ndarray:
    """Median-voiced f0 per 16th step -> MIDI pitch array (-1 = rest)."""
    times = np.linspace(0.0, duration, len(f0), endpoint=False)
    step = grid.bar_dur / 16.0
    n_steps = grid.n_bars * 16
    step_pitch = np.full(n_steps, -1, dtype=int)
    for s in range(n_steps):
        t_start = grid.t0 + s * step
        sel = (times >= t_start) & (times < t_start + step)
        if not sel.any():
            continue
        voiced = f0[sel] > 0
        if voiced.mean() < FCPE_VOICED_MIN:
            continue
        hz = float(np.median(f0[sel][voiced]))
        if hz > 0:
            step_pitch[s] = int(round(69 + 12 * np.log2(hz / 440.0)))
    return step_pitch


def transcribe_layers(track: str, layer_dir: Path, grid: Grid, out_dir: Path) -> dict:
    """Note stats + MIDI for each melodic layer present in the kept stems."""
    import librosa

    layers: dict[str, dict] = {}
    for layer in MELODIC_LAYERS:
        wav = layer_dir / f"{layer}.wav"
        if not wav.is_file():
            continue
        y, _ = librosa.load(str(wav), sr=SR, mono=True)
        y = _prep_melodic(y, SR, layer)
        f0 = _f0_track(y, SR)
        step_pitch = _f0_steps(f0, len(y) / SR, grid)
        notes = an.segment_notes(step_pitch)
        write_bass_midi(notes, out_dir / f"{track}.{layer}.mid", grid.bpm)
        stats = an.note_stats(notes, grid.n_bars * 16)
        stats["transcription"] = "monophonic dominant line (torchfcpe); polyphony collapses"
        layers[layer] = stats
    return layers


def layer_pass(
    audio_path: Path,
    track: str,
    grid: Grid,
    out_dir: Path,
    layer_stems_dir: Path = DEFAULT_LAYER_STEMS,
    models_dir: Path = DEFAULT_MODELS,
) -> list[str]:
    """Full per-track layer lens. Returns status tokens for the CLI report."""
    layer_dir = layer_stems_dir / track
    layers_yml = out_dir / f"{track}.layers.yml"
    if (layer_dir / "manifest.yml").is_file() and layers_yml.is_file():
        return ["layers:cached"]

    manifest = extract_layers(audio_path, layer_dir, models_dir)
    melodic = transcribe_layers(track, layer_dir, grid, out_dir)
    kept = [e["layer"] for e in manifest["stems"] if e["kept"]]
    dossier = {
        "track": track,
        "model": MODEL_NAME,
        "note": "layers are overlapping extractions, not a partition; "
        "energy accounting stays on the demucs stems",
        "kept_layers": kept,
        "melodic": melodic,
    }
    _write_yaml_if_changed(layers_yml, dossier)
    return ["layers:analyzed"]
