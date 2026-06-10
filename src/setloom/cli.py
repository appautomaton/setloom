# SPDX-License-Identifier: AGPL-3.0-only
"""Keyboard-first CLI for Setloom."""

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


def _grammar_warnings(spec: TrackSpec, spec_path: Path) -> list[str]:
    """Non-fatal style-grammar checks against the spec's style pack."""
    warnings: list[str] = []
    pack_path = Path("style-packs") / spec.style_pack / "style.yml"
    if not pack_path.is_file():
        warnings.append(f"style pack '{spec.style_pack}' not found at {pack_path}; grammar checks skipped")
        return warnings
    pack = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    bpm_range = (pack.get("generation_defaults") or {}).get("bpm_range")
    if bpm_range and not (bpm_range[0] <= spec.bpm <= bpm_range[1]):
        warnings.append(
            f"bpm {spec.bpm:g} is outside {spec.style_pack} bpm_range "
            f"[{bpm_range[0]}, {bpm_range[1]}] (generation will gate on this)"
        )
    return warnings


def _load_spec_or_fail(spec_path: Path) -> TrackSpec | None:
    try:
        return load_spec(spec_path)
    except ValidationError as exc:
        print(_format_validation_error(exc), file=sys.stderr)
        return None
    except (OSError, yaml.YAMLError, ValueError) as exc:
        print(f"spec validation failed: {exc}", file=sys.stderr)
        return None


def _cmd_validate(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec)
    spec = _load_spec_or_fail(spec_path)
    if spec is None:
        return 1

    for warning in _grammar_warnings(spec, spec_path):
        print(f"warning: {warning}", file=sys.stderr)
    print(f"OK: {spec.id} '{spec.title}' ({spec.bpm:g} BPM, {spec.key}, {spec.duration_bars} bars)")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    from setloom.generate import GateError, generate_candidates
    from setloom.stylepack import load_style_pack

    spec = _load_spec_or_fail(Path(args.spec))
    if spec is None:
        return 1
    try:
        pack = load_style_pack(spec.style_pack)
    except FileNotFoundError as exc:
        print(f"generation failed: {exc}", file=sys.stderr)
        return 1

    try:
        result = generate_candidates(
            spec,
            pack,
            out_dir=args.out,
            variants=args.variants,
            seed=args.seed,
            allow_overrides=set(args.allow_override or []),
        )
    except GateError as exc:
        print(f"generation rejected: {exc}", file=sys.stderr)
        for violation in exc.result.blocking:
            print(f"  {violation.rule_id}: {violation.message}", file=sys.stderr)
        print("  (use --allow-override <rule-id> to override deliberately)", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"generation failed: {exc}", file=sys.stderr)
        return 1

    for variant in result.variants:
        print(f"wrote {variant.directory} ({len(variant.note_counts)} parts)")
    print(f"report: {result.report_path}")
    print("reminder: candidates require human listening notes before approval")
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
        stems_dir=Path(args.stems_dir),
        separate=not args.no_separate,
        layers=args.layers,
    )
    for track, status in statuses.items():
        print(f"{track}: {', '.join(status)}")
    print(f"dossiers: {args.out}")
    print("reminder: dossiers are technical evidence; musical judgment stays with the listening gate")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="setloom", description="Setloom track and set harness")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate a track spec YAML file")
    p_validate.add_argument("spec", help="path to the track spec YAML")
    p_validate.set_defaults(func=_cmd_validate)

    p_generate = sub.add_parser("generate", help="generate MIDI candidate variants from a spec")
    p_generate.add_argument("spec", help="path to the track spec YAML")
    p_generate.add_argument("--variants", type=int, default=3, help="number of variants (default 3)")
    p_generate.add_argument("--seed", type=int, default=None, help="override the spec seed")
    p_generate.add_argument("--out", default="candidates", help="output root (default candidates/)")
    p_generate.add_argument(
        "--allow-override",
        action="append",
        metavar="RULE_ID",
        help="override a named rejection rule (repeatable); overrides are recorded in the report",
    )
    p_generate.set_defaults(func=_cmd_generate)

    p_anatomize = sub.add_parser(
        "anatomize", help="dissect local reference audio into anatomy dossiers"
    )
    p_anatomize.add_argument(
        "path", nargs="?", default="anatomy", help="audio file or directory (default anatomy/)"
    )
    p_anatomize.add_argument(
        "--out", default="anatomy/_dossiers", help="dossier output root (default anatomy/_dossiers)"
    )
    p_anatomize.add_argument(
        "--stems-dir",
        dest="stems_dir",
        default="anatomy/_stems",
        help="stem cache root (default anatomy/_stems)",
    )
    p_anatomize.add_argument(
        "--layers",
        action="store_true",
        help="also run the 53-stem layer lens (downloads ~1.3 GB weights on first use)",
    )
    p_anatomize.add_argument(
        "--no-separate",
        action="store_true",
        help="skip stem separation when stems are missing (full-mix pass only)",
    )
    p_anatomize.set_defaults(func=_cmd_anatomize)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def run() -> None:
    raise SystemExit(main())
