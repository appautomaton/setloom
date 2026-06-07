# SPDX-License-Identifier: AGPL-3.0-only
"""Generate CLI tests: layout, determinism, seed divergence, gate behavior (SPEC AC3-AC6)."""

import hashlib
from pathlib import Path

import pytest

from setloom import cli
from setloom.parts.base import parse_key, root_note

REPO_ROOT = Path(__file__).resolve().parents[1]
T01 = REPO_ROOT / "examples" / "tracks" / "T01" / "spec.yml"
GATE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gate-bpm-138.yml"
PARTS = ("drums", "bass", "chords", "arp", "lead", "fills")


@pytest.fixture(autouse=True)
def _run_from_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)  # style pack resolution is cwd-relative


def _generate(out: Path, *extra: str) -> int:
    return cli.main(
        ["generate", str(T01), "--variants", "3", "--seed", "1001", "--out", str(out), *extra]
    )


def _mid_hashes(out: Path) -> dict[str, str]:
    return {
        str(path.relative_to(out)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(out.rglob("*.mid"))
    }


def test_layout_three_variants_six_parts_plus_report(tmp_path: Path) -> None:
    assert _generate(tmp_path / "a") == 0
    run_dir = tmp_path / "a" / "T01" / "seed-1001"
    for index in (1, 2, 3):
        variant = run_dir / f"variant-{index:02d}"
        assert sorted(p.name for p in variant.glob("*.mid")) == sorted(f"{p}.mid" for p in PARTS)
    assert (run_dir / "report.md").is_file()


def test_determinism_byte_identical(tmp_path: Path) -> None:
    assert _generate(tmp_path / "a") == 0
    assert _generate(tmp_path / "b") == 0
    hashes_a = _mid_hashes(tmp_path / "a")
    hashes_b = _mid_hashes(tmp_path / "b")
    assert hashes_a and hashes_a == hashes_b


def test_different_seed_diverges(tmp_path: Path) -> None:
    assert _generate(tmp_path / "a") == 0
    assert (
        cli.main(
            ["generate", str(T01), "--variants", "3", "--seed", "2002", "--out", str(tmp_path / "b")]
        )
        == 0
    )
    names_a = {Path(k).name for k in _mid_hashes(tmp_path / "a")}
    names_b = {Path(k).name for k in _mid_hashes(tmp_path / "b")}
    assert names_a == names_b
    values_a = set(_mid_hashes(tmp_path / "a").values())
    values_b = set(_mid_hashes(tmp_path / "b").values())
    assert values_a != values_b


def test_gate_blocks_bpm_138_naming_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(["generate", str(GATE_FIXTURE), "--out", str(tmp_path)])
    assert code == 2
    err = capsys.readouterr().err
    assert "bpm-out-of-lane" in err
    assert not list(tmp_path.rglob("*.mid"))


def test_gate_override_passes_and_recorded_in_report(tmp_path: Path) -> None:
    code = cli.main(
        [
            "generate",
            str(GATE_FIXTURE),
            "--variants",
            "1",
            "--out",
            str(tmp_path),
            "--allow-override",
            "bpm-out-of-lane",
        ]
    )
    assert code == 0
    report = (tmp_path / "G01" / "seed-42" / "report.md").read_text(encoding="utf-8")
    assert "OVERRIDDEN bpm-out-of-lane" in report


def test_report_carries_human_gate_notice(tmp_path: Path) -> None:
    assert _generate(tmp_path) == 0
    report = (tmp_path / "T01" / "seed-1001" / "report.md").read_text(encoding="utf-8")
    assert "human listening notes" in report
    assert "keep" in report and "revise" in report and "reject" in report


# --- parse_key coverage (Slice 3 quality-review fold-in) ---


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("D minor", (2, "minor")),
        ("Bb minor", (10, "minor")),
        ("F# minor", (6, "minor")),
        ("Gb major", (6, "major")),
        ("C major", (0, "major")),
    ],
)
def test_parse_key_valid(key: str, expected: tuple[int, str]) -> None:
    assert parse_key(key) == expected


@pytest.mark.parametrize("key", ["Dm", "d minor", "H major", "D", "D dorian", ""])
def test_parse_key_invalid(key: str) -> None:
    with pytest.raises(ValueError, match="unsupported key"):
        parse_key(key)


def test_root_note_octave_convention() -> None:
    assert root_note("C major", 4) == 60  # C4 = 60
    assert root_note("D minor", 2) == 38  # bass register
