# SPDX-License-Identifier: AGPL-3.0-only
"""Package an explicitly selected WAV with its retained WebP cover; no upload."""

from pathlib import Path
import argparse
import filecmp
import json
import shutil

from PIL import Image
import soundfile as sf

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
STEM = "App-Automaton-Pulsus-Noctis-Setloom-Remix"


def main():
    parser = argparse.ArgumentParser(
        description="Package an explicitly selected Pulsus mix with its WebP cover."
    )
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    audio_source = args.audio.resolve()
    OUT = args.out_dir.resolve()
    if not audio_source.is_file():
        raise FileNotFoundError(audio_source)
    OUT.mkdir(parents=True, exist_ok=True)
    if any(OUT.iterdir()):
        raise ValueError("Choose an empty package directory")
    master = SOURCE / "cover.webp"
    cover = OUT / (STEM + "-cover.webp")
    shutil.copyfile(master, cover)
    with Image.open(cover) as image:
        image.verify()
    with Image.open(cover) as image:
        assert image.mode == "RGB" and image.width == image.height and image.width >= 800
        width, height = image.size
    assert cover.stat().st_size < 2_000_000
    audio = OUT / (STEM + ".wav")
    shutil.copyfile(audio_source, audio)
    assert filecmp.cmp(audio, audio_source, shallow=False)
    info = sf.info(audio)
    assert info.samplerate == 44100 and info.channels == 2 and info.subtype == "PCM_24"
    description = (SOURCE / "description.txt").read_text()
    assert len(description) <= 4000
    (OUT / "description.txt").write_text(description)
    metadata = {
        "title": "Pulsus Noctis (Setloom Remix)",
        "artist": "App Automaton",
        "genre": "Melodic Techno",
        "tags": ["piano", "instrumental", "Setloom", "App Automaton"],
        "bpm": 121,
        "edition": "Setloom Remix",
        "production_tool": "Setloom",
        "description": description,
        "cover_file": cover.name,
        "audio_file": audio.name,
    }
    (OUT / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    manifest = {
        "status": "local preparation; not uploaded",
        "generation": "built-in image_gen, complete cover including lettering",
        "master": {"path": str(master.relative_to(ROOT))},
        "cover": {
            "width": width,
            "height": height,
            "format": "WebP",
            "mode": "RGB",
            "bytes": cover.stat().st_size,
        },
        "audio": {
            "source": str(audio_source),
            "sample_rate": info.samplerate,
            "frames": info.frames,
            "subtype": info.subtype,
            "processing": "unprocessed copy of the explicitly selected input mix",
        },
        "typography_source": "Integrated image-model lettering; revise with the saved prompt.txt and complete cover reference",
    }
    (OUT / "preparation.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "cover": manifest["cover"],
                "audio": manifest["audio"],
                "description_characters": len(description),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
