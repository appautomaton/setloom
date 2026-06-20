# SPDX-License-Identifier: AGPL-3.0-only
"""Keyboard-first CLI for Setloom.

Commands: ``new`` (scaffold a track), ``play`` (audition audio), ``inspect``
(waveform/spectrum/spectrogram plots), ``transcribe`` (audio-to-MIDI notes),
and ``anatomize`` (opt-in diagnostics). Musical composition lives in per-track
code, not in this harness.
"""

import argparse
import os
import re
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


def _cmd_transcribe(args: argparse.Namespace) -> int:
    rerun = _rerun_with_transcription_tmpdir()
    if rerun is not None:
        return rerun

    from setloom.transcription import TranscriptionRequest, transcribe_audio

    try:
        result = transcribe_audio(
            TranscriptionRequest(
                audio=args.audio,
                out_midi=args.out,
                out_events=args.events,
                model_path=args.model_path,
                model_root=args.model_root,
                onset_threshold=args.onset_threshold,
                frame_threshold=args.frame_threshold,
                minimum_note_length_ms=args.min_note_ms,
                minimum_frequency=args.min_frequency,
                maximum_frequency=args.max_frequency,
                midi_tempo=args.bpm,
                channel=args.channel,
                melodia=not args.no_melodia,
                infer_onsets=not args.no_infer_onsets,
                energy_tol=args.energy_tol,
                include_pitch_bends=not args.no_pitch_bends,
                multiple_pitch_bends=args.multiple_pitch_bends,
            )
        )
    except Exception as exc:
        print(f"transcribe failed: {exc}", file=sys.stderr)
        return 1
    print(f"midi: {result.midi_path}")
    if result.events_path is not None:
        print(f"events: {result.events_path}")
    print(f"notes: {len(result.notes)}")
    return 0


def _rerun_with_transcription_tmpdir() -> int | None:
    """Start transcription CLI runs with project-local temp space."""
    target = str((Path("tmp") / "transcription").resolve())
    if os.environ.get("SETLOOM_TRANSCRIPTION_TMPDIR_READY") == "1":
        return None
    if os.environ.get("TMPDIR") == target:
        return None
    import subprocess

    Path(target).mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TMPDIR"] = target
    env["SETLOOM_TRANSCRIPTION_TMPDIR_READY"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "setloom.cli", *sys.argv[1:]],
        env=env,
        text=True,
        capture_output=True,
    )
    if completed.stdout:
        output = (
            _clean_success_output(completed.stdout)
            if completed.returncode == 0
            else completed.stdout
        )
        print(output, end="")
    if completed.returncode != 0 and completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return completed.returncode


def _clean_success_output(output: str) -> str:
    return re.sub(
        r'E5RT encountered an STL exception\. msg = filesystem error: '
        r'in create_directories: Operation not permitted \["[^"]+"\]\.',
        "",
        output,
    )


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

    p_transcribe = sub.add_parser(
        "transcribe",
        help="recover note events from audio and write MIDI",
    )
    p_transcribe.add_argument("audio", help="input audio file")
    p_transcribe.add_argument("--out", required=True, help="output MIDI path")
    p_transcribe.add_argument("--events", help="optional output note-events JSON path")
    p_transcribe.add_argument(
        "--model-path",
        help="explicit Basic Pitch model path",
    )
    p_transcribe.add_argument(
        "--model-root",
        default="models/basic-pitch/icassp_2022",
        help="model asset root (default models/basic-pitch/icassp_2022)",
    )
    p_transcribe.add_argument("--bpm", type=float, default=120.0, help="MIDI tempo")
    p_transcribe.add_argument("--channel", type=int, default=0, help="MIDI channel")
    p_transcribe.add_argument("--onset-threshold", type=float, default=0.5)
    p_transcribe.add_argument("--frame-threshold", type=float, default=0.3)
    p_transcribe.add_argument("--min-note-ms", type=float, default=127.7)
    p_transcribe.add_argument("--min-frequency", type=float)
    p_transcribe.add_argument("--max-frequency", type=float)
    p_transcribe.add_argument("--no-melodia", action="store_true")
    p_transcribe.add_argument(
        "--no-infer-onsets",
        action="store_true",
        help="disable onset inference from frame-amplitude jumps",
    )
    p_transcribe.add_argument(
        "--energy-tol",
        type=int,
        default=11,
        help="frames tolerated below frame-threshold before a note ends (default 11)",
    )
    p_transcribe.add_argument(
        "--no-pitch-bends",
        action="store_true",
        help="omit pitch-bend estimation from the contour output",
    )
    p_transcribe.add_argument(
        "--multiple-pitch-bends",
        action="store_true",
        help="keep bends on overlapping notes (writes one MIDI track per pitch)",
    )
    p_transcribe.set_defaults(func=_cmd_transcribe)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
