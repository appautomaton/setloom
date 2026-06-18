# SPDX-License-Identifier: AGPL-3.0-only
"""Keyboard-first CLI for Setloom.

Three commands: ``validate`` (spec contract + technical-hygiene gate),
``anatomize`` and ``score`` (opt-in reference diagnostics). Musical
composition lives in per-track code, not in this harness.
"""

import argparse
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from setloom.schema import TrackSpec, load_spec


def _format_validation_error(exc: ValidationError) -> str:
    lines = ["spec validation failed:"]
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"]) or "(root)"
        lines.append(f"  {loc}: {err['msg']}")
    return "\n".join(lines)


def _load_spec_or_fail(spec_path: Path) -> TrackSpec | None:
    try:
        return load_spec(spec_path)
    except ValidationError as exc:
        print(_format_validation_error(exc), file=sys.stderr)
        return None
    except (OSError, yaml.YAMLError, ValueError) as exc:
        print(f"spec validation failed: {exc}", file=sys.stderr)
        return None


def _gate_warnings(spec: TrackSpec) -> list[str]:
    """Run the style pack's technical-hygiene gate; return non-fatal warnings.

    The gate owns hygiene only (bpm lane, duration window, mixable edges,
    short-edit identity). Missing or partial pack rules are acceptable during a
    pack rebuild, so violations are reported as warnings, not hard failures.
    """
    from setloom.stylepack import evaluate_gate, load_style_pack

    try:
        pack = load_style_pack(spec.style_pack)
    except FileNotFoundError:
        return [f"style pack '{spec.style_pack}' not found; hygiene gate skipped"]
    try:
        result = evaluate_gate(spec, pack)
    except ValueError as exc:
        return [f"hygiene gate could not run: {exc}"]
    return [f"gate {v.rule_id}: {v.message}" for v in result.blocking]


def _cmd_validate(args: argparse.Namespace) -> int:
    spec = _load_spec_or_fail(Path(args.spec))
    if spec is None:
        return 1

    for warning in _gate_warnings(spec):
        print(f"warning: {warning}", file=sys.stderr)
    print(f"OK: {spec.id} '{spec.title}' ({spec.bpm:g} BPM, {spec.key}, {spec.duration_bars} bars)")
    return 0


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


def _cmd_score(args: argparse.Namespace) -> int:
    from setloom.anatomy.score import report_lines, score_track
    from setloom.stylepack import load_style_pack

    audio = Path(args.audio)
    if not audio.is_file():
        print(f"score failed: {audio} is not a file", file=sys.stderr)
        return 1
    try:
        pack = load_style_pack(args.pack)
    except FileNotFoundError as exc:
        print(f"score failed: {exc}", file=sys.stderr)
        return 1
    try:
        report, score_path = score_track(audio, pack, out_dir=Path(args.out))
    except RuntimeError as exc:
        print(f"score failed: {exc}", file=sys.stderr)
        return 1
    print("\n".join(report_lines(report)))
    print(f"score: {score_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="setloom", description="Setloom track and set harness")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate a track spec YAML file")
    p_validate.add_argument("spec", help="path to the track spec YAML")
    p_validate.set_defaults(func=_cmd_validate)

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

    p_score = sub.add_parser(
        "score", help="write a technical diagnostic report for an anatomized track"
    )
    p_score.add_argument("audio", help="audio file to score from an existing quick dossier")
    p_score.add_argument(
        "--pack",
        default="melodic-progressive-techno",
        help="style pack id (default melodic-progressive-techno)",
    )
    p_score.add_argument(
        "--out", default="local/corpus/dossiers", help="dossier root (default local/corpus/dossiers)"
    )
    p_score.set_defaults(func=_cmd_score)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def run() -> None:
    raise SystemExit(main())
