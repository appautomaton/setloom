# SPDX-License-Identifier: AGPL-3.0-only
"""Offline page assembly; no audio generation, copying, or web service."""

from __future__ import annotations

import base64
import html
import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

CONTROLLER_VERSION = 2


@dataclass(frozen=True)
class AudioOption:
    """One prepared listening view, positioned in session seconds.

    ``offset`` is the session time at the start of the file. ``gain`` is a
    playback attenuation, not a loudness target; use 1 for baked preview gain.
    A view may be a mix, solo, excerpt, or diagnostic combination.
    """

    id: str
    label: str
    path: str
    offset: float = 0
    gain: float = 1


@dataclass(frozen=True)
class Session:
    """An explicit set of available choices; no assumed version/part matrix."""

    title: str
    options: tuple[AudioOption, ...]
    default: str


def _local_file(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Asset must be a child of the audition root: {relative}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"Missing or out-of-root asset: {relative}")
    return resolved


def _duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type:format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    info = json.loads(result.stdout)
    if not info.get("streams"):
        raise ValueError(f"No audio stream: {path.name}")
    duration = float(info["format"]["duration"])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"Invalid audio duration: {path.name}")
    return duration


class _LocalPage(HTMLParser):
    """Check assembled references without executing the track's JavaScript."""

    def __init__(self, root: Path):
        super().__init__()
        self.root = root

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "base":
            raise ValueError("Audition resources must resolve from the page's root")
        if tag == "script" and ("src" in attrs or attrs.get("type") == "module"):
            raise ValueError("Audition scripts must be inline classic JavaScript")
        for name in ("src", "href"):
            value = attrs.get(name)
            if not value or value.startswith(("#", "data:")):
                continue
            url = urlsplit(value)
            if url.scheme or url.netloc:
                if tag == "a" and url.scheme in ("http", "https"):
                    continue  # Optional research links are not runtime dependencies.
                raise ValueError(f"External page dependency: {value}")
            _local_file(self.root, unquote(url.path))


def build_page(
    root: Path,
    session: Session,
    *,
    template: str | None = None,
    styles: str = "",
    script: str = "",
    presentation: dict | None = None,
    exports: tuple[str, ...] = (),
) -> Path:
    """Write and return ``root/index.html``, the listener's entry point.

    Custom templates use AUDITION_STYLE, AUDITION_AUDIO, and AUDITION_PLAYER
    comment slots; keep track-owned template files as ``audition/index.html.in``.
    They are authoring inputs, not assembled listening pages. The generated entry
    contains inline code/data and child media paths.
    ``presentation`` is opaque track-owned display data. Small
    MIDI/JSON exports are embedded for reliable downloads from file URLs.
    Required files are checked before replacing the existing page.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Audition root is not a directory: {root}")
    if not session.title.strip() or not session.options:
        raise ValueError("An audition needs a title and at least one option")
    options = []
    durations: dict[Path, float] = {}
    ids = set()
    for option in session.options:
        if not option.id or option.id in ids or not option.label.strip():
            raise ValueError(f"Empty or repeated option ID/label: {option.id}")
        ids.add(option.id)
        if not math.isfinite(option.offset) or option.offset < 0:
            raise ValueError(f"Invalid session offset: {option.id}")
        if not math.isfinite(option.gain) or not 0 < option.gain <= 1:
            raise ValueError(f"Playback gain must be in (0, 1]: {option.id}")
        path = _local_file(root, option.path)
        if path not in durations:
            durations[path] = _duration(path)
        options.append(
            dict(
                id=option.id,
                label=option.label,
                path=quote(option.path, safe="/"),
                offset=option.offset,
                gain=option.gain,
                duration=durations[path],
            )
        )
    if session.default not in ids:
        raise ValueError(f"Default option is unavailable: {session.default}")
    download_data = {}
    for relative in dict.fromkeys(exports):
        path = _local_file(root, relative)
        if path.suffix not in (".mid", ".json"):
            raise ValueError(f"Only MIDI and JSON are embedded exports: {relative}")
        download_data[relative] = dict(
            mime="audio/midi" if path.suffix == ".mid" else "application/json",
            base64=base64.b64encode(path.read_bytes()).decode("ascii"),
        )
    payload = dict(
        controller_version=CONTROLLER_VERSION,
        session=dict(title=session.title, options=options, default=session.default),
        presentation=presentation or {},
        exports=download_data,
    )
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    data = data.replace("<", "\\u003c")
    package = files("setloom.audition")
    if template is None:
        template = package.joinpath("default.html").read_text()
        styles = package.joinpath("default.css").read_text() + "\n" + styles
        script = package.joinpath("default.js").read_text() + "\n" + script
    controller = package.joinpath("transport.js").read_text()
    if "</script" in (controller + script).lower() or "</style" in styles.lower():
        raise ValueError("Inline code must not contain a closing script/style tag")
    default = next(option for option in options if option["id"] == session.default)
    audio = (
        '<audio id="audition-audio" controls preload="metadata" '
        f'src="{html.escape(default["path"], quote=True)}"></audio>'
    )
    replacements = {
        "<!-- AUDITION_STYLE -->": f"<style>\n{styles}\n</style>",
        "<!-- AUDITION_AUDIO -->": audio,
        "<!-- AUDITION_PLAYER -->": (
            '<script id="setloom-audition-data" type="application/json">'
            + data
            + "</script>\n<script>\n"
            + controller
            + "\n</script>\n<script>\n"
            + script
            + "\n</script>"
        ),
    }
    template = template.replace("{{TITLE}}", html.escape(session.title))
    for marker, replacement in replacements.items():
        if template.count(marker) != 1:
            raise ValueError(f"Template needs exactly one {marker}")
        template = template.replace(marker, replacement)
    checker = _LocalPage(root)
    checker.feed(template)
    checker.close()
    target = root / "index.html"
    # Replace only after validation, including when the root is a moved artifact.
    pending = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix=".audition-", suffix=".html", dir=root, delete=False
        ) as file:
            pending = Path(file.name)
            file.write(template)
        pending.replace(target)
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
    return target
