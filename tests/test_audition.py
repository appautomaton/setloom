# SPDX-License-Identifier: AGPL-3.0-only
"""Direct-file assembly and resource boundaries, using real local audio fixtures."""

import base64
import json
import re
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from setloom.audition import AudioOption, Session, build_page


@pytest.fixture
def root(tmp_path):
    audio = tmp_path / "audio"
    audio.mkdir()
    with wave.open(str(audio / "one.wav"), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(8000)
        file.writeframes(b"\x00\x00" * 8000)
    return tmp_path


def session(*options, default="one"):
    return Session(
        "A local audition", tuple(options) or (AudioOption("one", "One", "audio/one.wav"),), default
    )


def payload(page):
    return json.loads(
        re.search(
            r'<script id="setloom-audition-data" type="application/json">(.*?)</script>',
            page.read_text(),
            re.S,
        ).group(1)
    )


def test_one_option_needs_no_original_midi_or_server(root):
    before = (root / "audio/one.wav").read_bytes()
    page = build_page(root, session())
    text = page.read_text()
    assert '<audio id="audition-audio" controls preload="metadata"' in text
    assert 'src="audio/one.wav"' in text
    assert 'type="module"' not in text and "fetch(" not in text
    assert payload(page)["session"]["options"][0]["duration"] == 1
    assert (root / "audio/one.wav").read_bytes() == before
    assert sorted(path.name for path in root.iterdir()) == ["audio", "index.html"]


def test_safe_data_and_paths_preserve_actual_filenames(root):
    special = root / "audio" / "L'été #1.wav"
    (root / "audio/one.wav").rename(special)
    title = "A </script> & an <opening>"
    page = build_page(
        root,
        Session(title, (AudioOption("one", title, "audio/L'été #1.wav"),), "one"),
        presentation={"question": title},
    )
    assert payload(page)["presentation"]["question"] == title
    assert payload(page)["session"]["options"][0]["path"] == "audio/L%27%C3%A9t%C3%A9%20%231.wav"
    assert "<title>A &lt;/script&gt; &amp; an &lt;opening&gt;</title>" in page.read_text()


@pytest.mark.parametrize("path", ["../outside.wav", "/absolute.wav", "audio/missing.wav"])
def test_missing_or_escaping_audio_does_not_replace_page(root, path):
    target = root / "index.html"
    target.write_text("Existing audition")
    with pytest.raises(ValueError):
        build_page(root, session(AudioOption("one", "One", path)))
    assert target.read_text() == "Existing audition"


def test_symlink_cannot_escape_root(root, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "track.wav"
    outside.write_bytes((root / "audio/one.wav").read_bytes())
    (root / "audio/link.wav").symlink_to(outside)
    with pytest.raises(ValueError, match="out-of-root"):
        build_page(root, session(AudioOption("one", "One", "audio/link.wav")))


@pytest.mark.parametrize(
    "options,default",
    [
        (
            (
                AudioOption("one", "One", "audio/one.wav"),
                AudioOption("one", "Again", "audio/one.wav"),
            ),
            "one",
        ),
        ((AudioOption("one", "One", "audio/one.wav", offset=float("nan")),), "one"),
        ((AudioOption("one", "One", "audio/one.wav", gain=1.1),), "one"),
        ((AudioOption("one", "One", "audio/one.wav"),), "missing"),
    ],
)
def test_invalid_selection_contract_is_rejected(root, options, default):
    with pytest.raises(ValueError):
        build_page(root, session(*options, default=default))


def test_shared_resource_is_probed_once_and_gain_is_explicit(root, monkeypatch):
    from setloom.audition import page

    calls = []
    probe = page._duration
    monkeypatch.setattr(page, "_duration", lambda path: (calls.append(path), probe(path))[1])
    data = payload(
        build_page(
            root,
            session(
                AudioOption("one", "Delivery level", "audio/one.wav"),
                AudioOption("matched", "Matched level", "audio/one.wav", gain=0.5, offset=10),
            ),
        )
    )
    assert len(calls) == 1
    assert data["session"]["options"][1]["gain"] == 0.5
    assert data["session"]["options"][1]["offset"] == 10


def test_exports_are_exact_deduplicated_and_folder_can_move(root, tmp_path):
    (root / "source").mkdir()
    midi = b"MThd\x00\x00\x00\x06"
    (root / "source/part.mid").write_bytes(midi)
    data = payload(build_page(root, session(), exports=("source/part.mid", "source/part.mid")))
    assert len(data["exports"]) == 1
    assert base64.b64decode(data["exports"]["source/part.mid"]["base64"]) == midi
    destination = tmp_path / "moved"
    destination.mkdir()
    for name in ["audio", "source", "index.html"]:
        shutil.move(str(root / name), destination / name)
    assert (
        destination / payload(destination / "index.html")["session"]["options"][0]["path"]
    ).exists()


def test_custom_template_keeps_song_presentation(root):
    template = """<!doctype html><title>{{TITLE}}</title><!-- AUDITION_STYLE -->
<h1>Track-owned presentation</h1><!-- AUDITION_AUDIO --><!-- AUDITION_PLAYER -->"""
    page = build_page(
        root,
        session(),
        template=template,
        styles="h1{color:teal}",
        script="globalThis.presentationLoaded = true;",
    )
    assert "Track-owned presentation" in page.read_text()
    assert "color:teal" in page.read_text()
    assert "presentationLoaded" in page.read_text()


def test_external_runtime_dependency_is_rejected(root):
    template = """<!-- AUDITION_STYLE --><script src="https://example.com/player.js"></script>
<!-- AUDITION_AUDIO --><!-- AUDITION_PLAYER -->"""
    with pytest.raises(ValueError, match="inline classic"):
        build_page(root, session(), template=template)


@pytest.mark.parametrize("element", ['<base href="audio/one.wav">', '<script src=""></script>'])
def test_template_cannot_rebase_resources_or_load_an_external_script(root, element):
    template = (
        "<!-- AUDITION_STYLE -->" + element + "<!-- AUDITION_AUDIO --><!-- AUDITION_PLAYER -->"
    )
    with pytest.raises(ValueError):
        build_page(root, session(), template=template)


def test_default_presentation_does_not_leak_names_into_custom_script(root):
    if not shutil.which("node"):
        pytest.skip("Node is unavailable for JavaScript syntax checks")
    page = build_page(root, session(), script="const payload = {custom: true};")
    scripts = re.findall(r"<script>(.*?)</script>", page.read_text(), re.S)
    subprocess.run(
        ["node", "--check"], input=scripts[-1], text=True, capture_output=True, check=True
    )


def test_transport_failure_sequences():
    # Existing Node is only a test runner; it creates no npm project or server.
    if not shutil.which("node"):
        pytest.skip("Node is unavailable for the offline transport tests")
    subprocess.run(
        ["node", "--test", str(Path(__file__).with_name("audition_transport.mjs"))],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
