#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-only
"""Generate an instrumental melodic-techno candidate with ACE-Step 1.5.

A documented local experiment recipe, not a product surface: candidates are
audition material for the taste owner. Technical diagnostics are optional; the
listening gate judges. See music/packs/melodic-progressive-techno/generation-recipes.md.

Run from the repo root (requires the genai dependency group):

    uv run --no-sync python scripts/generate_candidate.py --caption TEXT
        --bpm BPM --keyscale KEY [--name NAME] [--seed N] [--duration SECONDS]

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

CANDIDATES = ROOT / "local" / "candidates" / "genai"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--name", default="acestep-candidate-01", help="output stem name")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--duration", type=float, default=360.0, help="seconds (club length)")
    parser.add_argument("--bpm", type=int, required=True, help="track-specific BPM")
    parser.add_argument("--keyscale", required=True, help="track-specific key/scale")
    parser.add_argument(
        "--caption",
        required=True,
        help="track-specific musical thesis; no pack-level default prompt is provided",
    )
    parser.add_argument(
        "--lyrics-file",
        default=None,
        help="path to a lyrics text file; presence switches to vocal generation",
    )
    parser.add_argument(
        "--vocal-language",
        default="unknown",
        help="language code for vocals (e.g. la, en); used only with --lyrics-file",
    )
    parser.add_argument("--no-thinking", action="store_true", help="skip the 5Hz LM pass")
    parser.add_argument(
        "--dit-config",
        default="acestep-v15-turbo",
        help="DiT config name (e.g. acestep-v15-xl-turbo for the XL renderer)",
    )
    parser.add_argument(
        "--lm-model",
        default=None,
        help="5Hz LM model name (e.g. acestep-5Hz-lm-4B); default: package default",
    )
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
    print(f"Initializing DiT ({args.dit_config})...")
    dit.initialize_service(
        project_root=str(ROOT),
        config_path=args.dit_config,
        device="auto",
    )

    llm = LLMHandler()
    if not args.no_thinking:
        lm_model = args.lm_model or DEFAULT_LM_MODEL
        print(f"Initializing 5Hz LM ({lm_model}, mlx backend)...")
        llm.initialize(
            checkpoint_dir=str(ckpt),
            lm_model_path=lm_model,
            backend="mlx",
            device="auto",
        )

    lyrics = Path(args.lyrics_file).read_text(encoding="utf-8") if args.lyrics_file else ""
    params = GenerationParams(
        caption=args.caption,
        lyrics=lyrics,
        instrumental=not lyrics,
        vocal_language=args.vocal_language,
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
    print("next: write a listening note before deciding what to inspect")
    print("reminder: technical diagnostics are optional; the listening gate judges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
