# SPDX-License-Identifier: AGPL-3.0-only
"""T04 'Nova Flamma' production assembly.

The song design lives in ``production.yml`` beside this file. This script is
the deterministic renderer for that manifest: engine stems + genai atmosphere
+ locked female vocal -> premaster, master, no-voice twin, and listening clips.

Run from the repo root:

    uv run --no-sync python music/tracks/T04/assemble.py
"""

from __future__ import annotations

import argparse
import copy
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import yaml
from scipy.signal import butter, sosfiltfilt

ROOT = Path(__file__).resolve().parents[3]
PRODUCTION = Path(__file__).with_name("production.yml")
PIECES = ROOT / "local/candidates/T04/voice/pieces"

SR = 44100
PAD_XFADE_BARS = 2.0
PAD_EDGE_FADE_BARS = 1.0


def load_production(path: Path = PRODUCTION) -> dict[str, Any]:
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"{path}: production manifest must be a mapping")
    validate_production(manifest)
    return manifest


def with_runtime_overrides(
    manifest: dict[str, Any],
    *,
    output_root: str | Path | None = None,
    variant_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Return a manifest copy with scratch/final render paths overridden."""
    runtime = copy.deepcopy(manifest)
    if variant_dir is not None:
        runtime["sources"]["variant_dir"] = str(variant_dir)
    if output_root is not None:
        root = Path(output_root)
        runtime["render"]["mix_dir"] = str(root / "mix")
        runtime["render"]["audition_dir"] = str(root / "auditions")
        runtime["render"]["pieces_dir"] = str(root / "voice-pieces")
    validate_production(runtime)
    return runtime


def validate_production(manifest: dict[str, Any]) -> None:
    required = ("version", "bpm", "total_bars", "sources", "render", "sections", "automation")
    for key in required:
        if key not in manifest:
            raise ValueError(f"production manifest missing {key}")
    if "T02" in yaml.safe_dump(manifest):
        raise ValueError("T04 production manifest must not reference T02")

    total_bars = int(manifest["total_bars"])
    cursor = 0
    for section in manifest["sections"]:
        if int(section["start_bar"]) != cursor:
            raise ValueError(f"section {section['name']} starts at {section['start_bar']}, expected {cursor}")
        end = int(section["end_bar"])
        if end <= cursor:
            raise ValueError(f"section {section['name']} must advance the timeline")
        cursor = end
    if cursor != total_bars:
        raise ValueError(f"sections end at {cursor}, expected total_bars {total_bars}")

    lanes = manifest["automation"].get("lanes", {})
    if not lanes:
        raise ValueError("production manifest requires automation.lanes")
    for lane_name, lane in lanes.items():
        stem = str(lane.get("stem", ""))
        if not stem:
            raise ValueError(f"lane {lane_name} missing stem")
        if stem.startswith("lead"):
            raise ValueError("rejected scrender lead bus must not be a production lane")
    pieces = set((manifest.get("voice") or {}).get("pieces", {}))
    for placement in (manifest.get("voice") or {}).get("placements", []):
        if placement.get("piece") not in pieces:
            raise ValueError(f"voice placement references unknown piece {placement.get('piece')}")
        if not 0 <= float(placement["bar"]) < total_bars:
            raise ValueError(f"voice placement bar out of range: {placement}")


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def pieces_dir(manifest: dict[str, Any]) -> Path:
    return repo_path((manifest.get("render") or {}).get("pieces_dir", PIECES))


def bpm(manifest: dict[str, Any]) -> float:
    return float(manifest["bpm"])


def bar_s(manifest: dict[str, Any]) -> float:
    return 4 * 60 / bpm(manifest)


def bar_to_sample(manifest: dict[str, Any], bar: float) -> int:
    return int(round(bar * bar_s(manifest) * SR))


def load_stereo(path: Path) -> np.ndarray:
    y, sr = sf.read(path, always_2d=True)
    if sr != SR:
        raise ValueError(f"{path}: {sr} != {SR}")
    if y.shape[1] == 1:
        y = np.repeat(y, 2, axis=1)
    return y.astype(np.float64)


def highpass(y: np.ndarray, hz: float) -> np.ndarray:
    sos = butter(4, hz, btype="highpass", fs=SR, output="sos")
    return sosfiltfilt(sos, y, axis=0)


def crossfade_loop(manifest: dict[str, Any], src: np.ndarray, length: int, offset: int) -> np.ndarray:
    """Tile ``src`` to ``length`` samples with equal-power crossfades."""
    xf = bar_to_sample(manifest, PAD_XFADE_BARS)
    src = np.roll(src, -offset, axis=0)
    hop = max(1, len(src) - xf)
    out = np.zeros((length + len(src), 2))
    t = np.linspace(0, np.pi / 2, xf)[:, None]
    fade_in, fade_out = np.sin(t), np.cos(t)
    pos = 0
    while pos < length:
        piece = src.copy()
        if pos > 0:
            piece[:xf] *= fade_in
        piece[-xf:] *= fade_out
        out[pos : pos + len(piece)] += piece
        pos += hop
    return out[:length]


def edge_fades(manifest: dict[str, Any], y: np.ndarray, fade_bars: float) -> np.ndarray:
    n = min(len(y) // 2, bar_to_sample(manifest, fade_bars))
    if n <= 0:
        return y
    env = np.ones(len(y))
    env[:n] = np.linspace(0, 1, n)
    env[-n:] = np.linspace(1, 0, n)
    return y * env[:, None]


def section_value_envelope(
    manifest: dict[str, Any],
    section_values: dict[str, float],
    fallback: float,
    length: int,
) -> np.ndarray:
    env = np.full(length, fallback, dtype=np.float64)
    for section in manifest["sections"]:
        name = section["name"]
        value = float(section_values.get(name, fallback))
        lo = bar_to_sample(manifest, float(section["start_bar"]))
        hi = min(length, bar_to_sample(manifest, float(section["end_bar"])))
        env[lo:hi] = value

    ramp = bar_to_sample(manifest, float(manifest["automation"].get("ramp_bars", 1.0)))
    for section in manifest["sections"][1:]:
        center = bar_to_sample(manifest, float(section["start_bar"]))
        lo, hi = max(0, center - ramp // 2), min(length, center + ramp // 2)
        if hi > lo:
            left = env[lo - 1] if lo else env[lo]
            right = env[hi - 1]
            env[lo:hi] = np.linspace(left, right, hi - lo)
    return env


def duck_envelope(manifest: dict[str, Any], length: int) -> np.ndarray:
    env = np.ones(length, dtype=np.float64)
    edge = bar_to_sample(manifest, 0.5)
    pre_roll = int(float(manifest["voice"].get("pre_roll_s", 0.0)) * SR)
    for placement in manifest["voice"].get("placements", []):
        depth_db = float(placement.get("duck_db", 0.0))
        bars = float(placement.get("duck_bars", 0.0))
        if depth_db >= 0 or bars <= 0:
            continue
        dip = 10 ** (depth_db / 20)
        s0 = max(0, bar_to_sample(manifest, float(placement["bar"])) - pre_roll)
        s1 = min(length, s0 + bar_to_sample(manifest, bars))
        env[s0:s1] = np.minimum(env[s0:s1], dip)

        pre0 = max(0, s0 - edge)
        if s0 > pre0:
            env[pre0:s0] = np.minimum(env[pre0:s0], np.linspace(1, dip, s0 - pre0))
        post1 = min(length, s1 + edge)
        if post1 > s1:
            env[s1:post1] = np.minimum(env[s1:post1], np.linspace(dip, 1, post1 - s1))
    return env


def apply_width(y: np.ndarray, width: np.ndarray) -> np.ndarray:
    width = width[: len(y)]
    mid = (y[:, 0] + y[:, 1]) * 0.5
    side = (y[:, 0] - y[:, 1]) * 0.5 * width
    return np.column_stack((mid + side, mid - side))


def expand_voice_chain(piece: dict[str, Any], body_eq: list[Any]) -> list[str]:
    chain: list[str] = []
    for item in piece["chain"]:
        if item == "{body_eq}":
            chain.extend(str(x) for x in body_eq)
        else:
            chain.append(str(item))
    return chain


def cut_voice_pieces(manifest: dict[str, Any]) -> None:
    voice = repo_path(manifest["sources"]["voice"])
    body_eq = manifest["voice"].get("body_eq", [])
    out_dir = pieces_dir(manifest)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, piece in manifest["voice"]["pieces"].items():
        out = out_dir / f"{name}.wav"
        cmd = [
            "sox",
            str(voice),
            str(out),
            "trim",
            str(piece["trim_start_s"]),
            str(piece["trim_len_s"]),
            "fade",
            "t",
            "0.03",
            "0",
            str(piece.get("fade_out_s", 1.2)),
            *expand_voice_chain(piece, body_eq),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)


def mix_engine_lanes(
    manifest: dict[str, Any],
    length: int,
    duck: np.ndarray,
) -> np.ndarray:
    variant_dir = repo_path(manifest["sources"]["variant_dir"])
    mix = np.zeros((length, 2), dtype=np.float64)
    duck_lanes = set(manifest["automation"].get("duck_lanes", []))
    for lane_name, lane_cfg in manifest["automation"]["lanes"].items():
        stem_path = variant_dir / f"stem-{lane_cfg['stem']}.wav"
        lane = load_stereo(stem_path) * float(lane_cfg.get("gain", 1.0))
        db_env = section_value_envelope(
            manifest, lane_cfg.get("section_db", {}), 0.0, len(lane)
        )
        lane *= (10 ** (db_env / 20))[:, None]
        if lane_name in duck_lanes:
            lane *= duck[: len(lane), None]
        width_env = section_value_envelope(
            manifest,
            lane_cfg.get("section_width", {}),
            float(lane_cfg.get("width", 1.0)),
            len(lane),
        )
        lane = apply_width(lane, width_env)
        mix[: len(lane)] += lane
    return mix


def mix_genai_pads(
    manifest: dict[str, Any],
    length: int,
    duck: np.ndarray,
) -> np.ndarray:
    genai_dir = repo_path(manifest["sources"]["genai_dir"])
    mix = np.zeros((length, 2), dtype=np.float64)
    for index, span in enumerate(manifest.get("genai_pads", [])):
        s0 = bar_to_sample(manifest, float(span["start_bar"]))
        s1 = min(length, bar_to_sample(manifest, float(span["end_bar"])))
        if s1 <= s0:
            continue
        src = load_stereo(genai_dir / f"{span['asset']}.wav")
        bed = crossfade_loop(manifest, src, s1 - s0, offset=index * 7 * SR % len(src))
        bed = highpass(bed, float(span.get("highpass_hz", 180.0)))
        bed = edge_fades(manifest, bed, PAD_EDGE_FADE_BARS)
        bed = apply_width(bed, np.full(len(bed), float(span.get("width", 1.0))))
        bed *= duck[s0:s1, None]
        mix[s0:s1] += bed * float(span.get("gain", 1.0))
    return mix


def place_voice(manifest: dict[str, Any], length: int) -> np.ndarray:
    mix = np.zeros((length, 2), dtype=np.float64)
    pre_roll = int(float(manifest["voice"].get("pre_roll_s", 0.0)) * SR)
    voice_pieces = pieces_dir(manifest)
    for placement in manifest["voice"].get("placements", []):
        y = load_stereo(voice_pieces / f"{placement['piece']}.wav")
        start = bar_to_sample(manifest, float(placement["bar"])) - pre_roll
        if start >= length:
            continue
        src0 = max(0, -start)
        dst0 = max(0, start)
        dst1 = min(length, dst0 + len(y) - src0)
        if dst1 <= dst0:
            continue
        mix[dst0:dst1] += y[src0 : src0 + dst1 - dst0] * float(placement.get("gain", 1.0))
    return mix


def raw_mix(manifest: dict[str, Any], include_voice: bool) -> np.ndarray:
    total = bar_to_sample(manifest, float(manifest["total_bars"]))
    variant_dir = repo_path(manifest["sources"]["variant_dir"])
    stem_lengths = [
        len(load_stereo(variant_dir / f"stem-{lane['stem']}.wav"))
        for lane in manifest["automation"]["lanes"].values()
    ]
    length = max(total, *stem_lengths)
    duck = duck_envelope(manifest, length)
    mix = mix_engine_lanes(manifest, length, duck)
    mix += mix_genai_pads(manifest, length, duck)
    if include_voice:
        mix += place_voice(manifest, length)
    return mix


def peak_normalize(y: np.ndarray, peak_db: float) -> tuple[np.ndarray, float]:
    peak = float(np.abs(y).max())
    if peak <= 0:
        return y, 1.0
    gain = 10 ** (peak_db / 20) / peak
    return y * gain, gain


def master(manifest: dict[str, Any], premaster: Path, master_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(premaster),
            "-af",
            manifest["master"]["ffmpeg_chain"],
            "-c:a",
            "pcm_s24le",
            str(master_path),
        ],
        check=True,
    )


def write_auditions(manifest: dict[str, Any], master_path: Path) -> list[Path]:
    y = load_stereo(master_path)
    out_dir = repo_path(manifest["render"]["audition_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for clip in manifest.get("auditions", []):
        s0 = bar_to_sample(manifest, float(clip["start_bar"]))
        s1 = min(len(y), s0 + bar_to_sample(manifest, float(clip["bars"])))
        out = out_dir / f"{clip['name']}.wav"
        sf.write(out, y[s0:s1], SR, subtype="PCM_24")
        written.append(out)
    return written


def render(manifest: dict[str, Any]) -> tuple[Path, Path, Path, list[Path]]:
    cut_voice_pieces(manifest)
    out_dir = repo_path(manifest["render"]["mix_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    mix = raw_mix(manifest, include_voice=True)
    novoice = raw_mix(manifest, include_voice=False)
    normalized, gain = peak_normalize(mix, float(manifest["master"]["normalize_peak_db"]))
    premaster = out_dir / manifest["render"]["premaster_name"]
    novoice_path = out_dir / manifest["render"]["novoice_name"]
    master_path = out_dir / manifest["render"]["master_name"]
    sf.write(premaster, normalized, SR, subtype="PCM_24")
    sf.write(novoice_path, novoice * gain, SR, subtype="PCM_24")
    master(manifest, premaster, master_path)
    auditions = write_auditions(manifest, master_path)
    return premaster, master_path, novoice_path, auditions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the T04 production manifest")
    parser.add_argument("--production", default=str(PRODUCTION), help="production manifest path")
    parser.add_argument("--variant-dir", default=None, help="override sources.variant_dir")
    parser.add_argument("--output-root", default=None, help="override render outputs under this root")
    args = parser.parse_args(argv)

    manifest = with_runtime_overrides(
        load_production(Path(args.production)),
        output_root=args.output_root,
        variant_dir=args.variant_dir,
    )
    premaster, master_path, novoice, auditions = render(manifest)
    print(f"wrote premaster: {premaster}")
    print(f"wrote master: {master_path}")
    print(f"wrote no-voice twin: {novoice}")
    for clip in auditions:
        print(f"wrote audition: {clip}")
    print("reminder: candidates require human listening notes before approval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
