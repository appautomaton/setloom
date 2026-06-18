#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-only
"""Magenta RT 2 smoke proof: a short MLX-generated clip from the unified env.

Proves the jam pillar runs in setloom's one environment — not the realtime jam
workflow (live audio routing and MIDI steering are a future change). See
music/packs/melodic-progressive-techno/generation-recipes.md.

Run from the repo root (requires the genai dependency group):

    uv run --no-sync python scripts/magenta_smoke.py --prompt TEXT [--duration 16]

Weights download on first use to the project model store (gitignored):
MAGENTA_HOME -> models/magenta. Heavy model runs are serialized: do not run
this concurrently with generation or separation.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("MAGENTA_HOME", str(ROOT / "models" / "magenta"))
os.environ.setdefault("HF_HUB_CACHE", str(ROOT / "models" / "hf"))

OUT_DIR = ROOT / "local" / "candidates" / "genai"


def _ensure_model(size: str = "mrt2_base") -> None:
    """Fetch shared resources and the exported MLX model on first use."""
    import subprocess

    mlxfn = (
        Path(os.environ["MAGENTA_HOME"]) / "magenta-rt-v2" / "models" / size / f"{size}.mlxfn"
    )
    if mlxfn.is_file():
        return
    print(f"{mlxfn} missing; downloading via mrt models init/download...")
    subprocess.run(["mrt", "models", "init"], check=True)
    subprocess.run(["mrt", "models", "download", size], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--prompt",
        required=True,
        help="track-specific smoke prompt; no pack-level default prompt is provided",
    )
    parser.add_argument("--duration", type=float, default=16.0, help="seconds")
    parser.add_argument("--name", default="magenta-smoke")
    args = parser.parse_args()

    from scipy.io import wavfile

    from magenta_rt import MagentaRT2Mlxfn

    _ensure_model()

    mrt = MagentaRT2Mlxfn()
    style = mrt.embed_style(args.prompt, use_mapper=True)

    frames = int(args.duration * 25)  # 25 fps token rate
    start = time.time()
    wav, _ = mrt.generate(style=style, frames=frames)
    elapsed = time.time() - start
    print(f"generated {args.duration:.0f}s in {elapsed:.1f}s ({frames / elapsed:.1f} steps/s)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.name}.wav"
    wavfile.write(str(out), wav.sample_rate, wav.samples)
    print(f"smoke output: {out}")
    print("reminder: a smoke clip, not a club track; the listening gate judges all audio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
