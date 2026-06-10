#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-only
"""Generate an instrumental melodic-techno candidate with ACE-Step 1.5.

A documented local experiment recipe, not a product surface: candidates are
reference material for the taste owner, scored by ``setloom score`` and judged
at the listening gate. See research/melodic-progressive-techno/generation-recipes.md.

Run from the repo root (requires the genai dependency group):

    uv run --no-sync python scripts/generate_candidate.py [--name NAME] [--seed N]
        [--duration SECONDS] [--caption TEXT]

Weights download on first use to the project model store (gitignored):
ACE-Step checkpoints -> models/acestep, HF hub cache -> models/hf. The user's
HF login stays in the default HF_HOME. Heavy model runs are serialized: do not
run this concurrently with separation or other model inference.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("ACESTEP_CHECKPOINTS_DIR", str(ROOT / "models" / "acestep"))
os.environ.setdefault("HF_HUB_CACHE", str(ROOT / "models" / "hf"))

CANDIDATES = ROOT / "anatomy" / "_candidates"

# Style grammar in prose: hypnotic pedal groove, dark pads, motif, midpoint
# break — mirrors style.yml targets without naming artists.
DEFAULT_CAPTION = (
    "hypnotic melodic techno, instrumental club mix, steady four-on-the-floor kick, "
    "rolling sixteenth-note bass pedal locked to the root, dark evolving analog pads, "
    "arpeggiated minor-key synth motif, long atmospheric breakdown near the middle "
    "of the track, climactic drop, mixable intro and outro, controlled low end"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--name", default="acestep-candidate-01", help="output stem name")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--duration", type=float, default=360.0, help="seconds (club length)")
    parser.add_argument("--bpm", type=int, default=123)
    parser.add_argument("--keyscale", default="A minor")
    parser.add_argument("--caption", default=DEFAULT_CAPTION)
    parser.add_argument("--no-thinking", action="store_true", help="skip the 5Hz LM pass")
    args = parser.parse_args()

    # Heavy imports after env routing so weights land in the project store.
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler
    from acestep.model_downloader import (
        DEFAULT_LM_MODEL,
        ensure_main_model,
        get_checkpoints_dir,
    )

    ckpt = get_checkpoints_dir()
    ok, msg = ensure_main_model(checkpoints_dir=ckpt)
    print(msg)
    if not ok:
        return 1

    dit = AceStepHandler()
    print("Initializing DiT (acestep-v15-turbo)...")
    dit.initialize_service(
        project_root=str(ROOT),
        config_path="acestep-v15-turbo",
        device="auto",
    )

    llm = LLMHandler()
    if not args.no_thinking:
        print(f"Initializing 5Hz LM ({DEFAULT_LM_MODEL}, mlx backend)...")
        llm.initialize(
            checkpoint_dir=str(ckpt),
            lm_model_path=DEFAULT_LM_MODEL,
            backend="mlx",
            device="auto",
        )

    params = GenerationParams(
        caption=args.caption,
        instrumental=True,
        bpm=args.bpm,
        keyscale=args.keyscale,
        duration=args.duration,
        seed=args.seed,
        thinking=not args.no_thinking,
    )
    # use_random_seed=False + explicit seeds: the config default (True) silently
    # discards params.seed and rolls a fresh seed every run.
    config = GenerationConfig(
        batch_size=1,
        audio_format="wav",
        use_random_seed=False,
        seeds=[args.seed],
    )

    CANDIDATES.mkdir(parents=True, exist_ok=True)
    result = generate_music(dit, llm, params, config, save_dir=str(CANDIDATES))
    if not result.success:
        print(f"generation failed: {result.error}", file=sys.stderr)
        return 1

    out = CANDIDATES / f"{args.name}.wav"
    src = Path(result.audios[0]["path"])
    if src != out:
        shutil.move(src, out)
    print(f"candidate: {out}")
    print(f"seed: {result.audios[0]['params'].get('seed')}")
    print("next: uv run setloom score " + str(out.relative_to(ROOT)))
    print("reminder: scores are the technical half; the listening gate judges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
