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


def _cmd_validate(args: argparse.Namespace) -> int:
    spec_path = Path(args.spec)
    try:
        spec = load_spec(spec_path)
    except ValidationError as exc:
        print(_format_validation_error(exc), file=sys.stderr)
        return 1
    except (OSError, yaml.YAMLError, ValueError) as exc:
        print(f"spec validation failed: {exc}", file=sys.stderr)
        return 1

    for warning in _grammar_warnings(spec, spec_path):
        print(f"warning: {warning}", file=sys.stderr)
    print(f"OK: {spec.id} '{spec.title}' ({spec.bpm:g} BPM, {spec.key}, {spec.duration_bars} bars)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="setloom", description="Setloom track and set harness")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate a track spec YAML file")
    p_validate.add_argument("spec", help="path to the track spec YAML")
    p_validate.set_defaults(func=_cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def run() -> None:
    raise SystemExit(main())
