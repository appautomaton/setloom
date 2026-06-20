# SPDX-License-Identifier: AGPL-3.0-only
"""Keyboard-first CLI for Setloom.

Commands: ``new`` (scaffold a track), ``play`` (audition audio), ``inspect``
(waveform/spectrum/spectrogram plots), and ``anatomize`` (opt-in diagnostics).
Musical composition lives in per-track code, not in this harness.
"""

import argparse
import sys
from pathlib import Path


def _cmd_anatomize(args: argparse.Namespace) -> int:
    from setloom.anatomy.pipeline import collect_audio, run as run_anatomy

    target = Path(args.path)
    if not target.exists():
        print(f"anatomize failed: {target} does not exist", file=sys.stderr)
        return 1
    if not collect_audio(target):
        print(f"anatomize failed: no audio files under {target}", file=sys.stderr)
        return 1
    statuses = run_anatomy(
        target,
        out_dir=Path(args.out),
        layers=args.layers,
        layer_stems_dir=Path(args.layer_stems_dir),
        models_dir=Path(args.models_dir),
    )
    for track, status in statuses.items():
        print(f"{track}: {', '.join(status)}")
    print(f"dossiers: {args.out}")
    print("reminder: dossiers are technical evidence; musical judgment stays with the listening gate")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    from setloom.inspection import run as run_inspection

    return run_inspection(args)


def _cmd_new(args: argparse.Namespace) -> int:
    from setloom.scaffold import create_track

    title = args.title or args.id.lower()
    try:
        track_dir = create_track(
            args.id, title, bpm=args.bpm, key=args.key, root="."
        )
    except FileExistsError as exc:
        print(f"new failed: {exc}", file=sys.stderr)
        return 1
    print(f"created {track_dir}")
    print(f"  spec:             {track_dir / 'spec.yml'}")
    print(f"  assemble:         {track_dir / 'assemble.py'}")
    print(f"  listening notes:  {track_dir / 'listening-notes.yml'}")
    print("edit the spec, then run the assembler from the repo root:")
    print(f"  uv run --no-sync python {track_dir / 'assemble.py'}")
    return 0


def _cmd_play(args: argparse.Namespace) -> int:
    import shutil
    import subprocess

    audio = Path(args.audio)
    if not audio.is_file():
        print(f"play failed: {audio} is not a file", file=sys.stderr)
        return 1
    player = shutil.which("afplay")
    if player is None:
        print("play failed: afplay not found (macOS built-in)", file=sys.stderr)
        return 1
    print(f"playing: {audio}")
    subprocess.run([player, str(audio)])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="setloom", description="Setloom track and set harness")
    sub = parser.add_subparsers(dest="command", required=True)

    p_anatomize = sub.add_parser(
        "anatomize", help="dissect local reference audio into anatomy dossiers"
    )
    p_anatomize.add_argument(
        "path", nargs="?", default="local/corpus/audio", help="audio file or directory (default local/corpus/audio/)"
    )
    p_anatomize.add_argument(
        "--out", default="local/corpus/dossiers", help="dossier output root (default local/corpus/dossiers)"
    )
    p_anatomize.add_argument(
        "--layers",
        action="store_true",
        help="run the 53-stem layer lens (downloads ~1.3 GB weights on first use)",
    )
    p_anatomize.add_argument(
        "--layer-stems-dir",
        dest="layer_stems_dir",
        default="local/corpus/stems53",
        help="53-stem layer cache root (default local/corpus/stems53)",
    )
    p_anatomize.add_argument(
        "--models-dir",
        dest="models_dir",
        default="models/roformer",
        help="53-stem model cache root (default models/roformer)",
    )
    p_anatomize.set_defaults(func=_cmd_anatomize)

    p_inspect = sub.add_parser(
        "inspect",
        help="render waveform, spectrum, spectrogram, and stereo inspection plots",
    )
    from setloom.inspection import configure_parser as configure_inspection_parser

    configure_inspection_parser(p_inspect)
    p_inspect.set_defaults(func=_cmd_inspect)

    p_new = sub.add_parser("new", help="scaffold a new track directory")
    p_new.add_argument("id", help="track id, e.g. T06")
    p_new.add_argument("--title", help="track title (defaults to id lowercased)")
    p_new.add_argument("--bpm", type=float, default=128.0, help="tempo (default 128)")
    p_new.add_argument("--key", default="A minor", help="key, e.g. 'D minor' (default 'A minor')")
    p_new.set_defaults(func=_cmd_new)

    p_play = sub.add_parser("play", help="play an audio file for the listening gate")
    p_play.add_argument("audio", help="path to the audio file")
    p_play.set_defaults(func=_cmd_play)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def run() -> None:
    raise SystemExit(main())
