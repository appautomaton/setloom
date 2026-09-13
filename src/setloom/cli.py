# SPDX-License-Identifier: AGPL-3.0-only
"""Keyboard-first CLI for Setloom.

Commands: ``play`` (audition audio), ``inspect``
(waveform/spectrum/spectrogram plots), ``transcribe`` (audio-to-MIDI notes),
and ``separate`` (reference estimates). Musical composition lives in per-track
code, not in this harness.
"""

import argparse
import sys
from pathlib import Path


def _cmd_separate(args: argparse.Namespace) -> int:
    try:
        from setloom.anatomy.layers import write_separated_estimates

        paths = write_separated_estimates(Path(args.audio), Path(args.out), Path(args.model_root))
    except Exception as exc:
        print(f"separate failed: {exc}", file=sys.stderr)
        return 1
    print(f"estimates: {len(paths)}")
    print(f"output: {args.out}")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    from setloom.inspection import run as run_inspection

    return run_inspection(args)


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
    return subprocess.run([player, str(audio)]).returncode


def _cmd_transcribe(args: argparse.Namespace) -> int:
    try:
        notes, midi_path, events_path = _transcribe_with_engine(args)
    except Exception as exc:
        print(f"transcribe failed: {exc}", file=sys.stderr)
        return 1
    print(f"midi: {midi_path}")
    if events_path is not None:
        print(f"events: {events_path}")
    print(f"notes: {len(notes)}")
    return 0


def _transcribe_with_engine(args: argparse.Namespace):
    """Run the selected engine and return ``(notes, midi_path, events_path)``."""
    if args.engine in ("basic-pitch", "basic-pitch-mlx"):
        result = _run_basic_pitch(args)
        return result.notes, result.midi_path, result.events_path

    from setloom.transcription import write_note_events_json, write_transcription_midi
    from setloom.transcription.kong import transcribe_kong

    kong_kwargs = {"checkpoint_path": args.kong_checkpoint} if args.kong_checkpoint else {}
    kong_notes = transcribe_kong(args.audio, **kong_kwargs)
    if args.engine == "kong":
        notes = kong_notes
    else:  # fusion: Kong timing reconciled with Basic Pitch's pitches
        from tempfile import TemporaryDirectory

        from setloom.transcription import TranscriptionRequest, transcribe_audio
        from setloom.transcription.fusion import fuse_recall_first

        scratch_root = Path("tmp/transcription")
        scratch_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="fusion-", dir=scratch_root) as scratch:
            bp = transcribe_audio(
                TranscriptionRequest(
                    audio=args.audio,
                    out_midi=Path(scratch) / "basic-pitch.mid",
                    model_path=args.model_path,
                    model_root=args.model_root,
                )
            )
        notes = fuse_recall_first(kong_notes, bp.notes)

    midi_path = write_transcription_midi(notes, args.out, bpm=args.bpm, channel=args.channel)
    events_path = write_note_events_json(notes, args.events) if args.events else None
    return notes, midi_path, events_path


def _run_basic_pitch(args: argparse.Namespace):
    from setloom.transcription import TranscriptionRequest, transcribe_audio

    return transcribe_audio(
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
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="setloom", description="Setloom audio and MIDI tools")
    sub = parser.add_subparsers(dest="command", required=True)

    p_separate = sub.add_parser("separate", help="write all separated estimates as float WAVs")
    p_separate.add_argument("audio", help="input audio file")
    p_separate.add_argument("--out", required=True, help="output directory for separated estimates")
    p_separate.add_argument("--model-root", default="models/roformer", help="local model directory")
    p_separate.set_defaults(func=_cmd_separate)

    p_inspect = sub.add_parser(
        "inspect",
        help="render waveform, spectrum, spectrogram, and stereo inspection plots",
    )
    from setloom.inspection import configure_parser as configure_inspection_parser

    configure_inspection_parser(p_inspect)
    p_inspect.set_defaults(func=_cmd_inspect)

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
        "--engine",
        choices=("basic-pitch", "basic-pitch-mlx", "kong", "fusion"),
        default="basic-pitch",
        help="basic-pitch (default, MLX GPU FP32, needs --group transcription) | "
        "basic-pitch-mlx (alias for basic-pitch) | "
        "kong (piano, needs --group kong) | "
        "fusion (Kong timing + Basic Pitch pitch, needs --group kong --group transcription)",
    )
    p_transcribe.add_argument(
        "--kong-checkpoint",
        help="Kong checkpoint path (default models/piano-transcription/...pth)",
    )
    p_transcribe.add_argument(
        "--model-path",
        help="explicit Basic Pitch MLX model directory",
    )
    p_transcribe.add_argument(
        "--model-root",
        default="models/basic-pitch-mlx/icassp_2022",
        help="MLX model asset root (default models/basic-pitch-mlx/icassp_2022)",
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
