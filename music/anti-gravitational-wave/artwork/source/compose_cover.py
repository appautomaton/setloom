"""Rebuild the cover typography and delivery exports from the retained artwork."""

import argparse
from pathlib import Path

from PIL import Image, ImageCms, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
SIZE = 3000
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"
PAPER = (238, 236, 229)


def tracked(draw, text, x, y, size, spacing, index=10):
    font = ImageFont.truetype(FONT, size, index=index)
    for char in text:
        draw.text((round(x), y), char, font=font, fill=PAPER, anchor="lt")
        x += draw.textlength(char, font=font) + spacing
    return x


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Explicit export directory, normally under project tmp",
    )
    output = parser.parse_args().out_dir
    if (output / "cover.webp").exists():
        raise FileExistsError("Cover exports already exist; choose another output directory.")
    output.mkdir(parents=True, exist_ok=True)
    art = Image.open(ROOT / "source/anti-gravitational-wave-art.webp")
    if art.width != art.height:
        raise ValueError("The source artwork must be square; do not silently crop it.")
    cover = art.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(cover)
    tracked(draw, "APP AUTOMATON", 180, 176, 64, 10)
    tracked(draw, "ANTI GRAVITATIONAL", 172, 2440, 157, 0, index=1)
    tracked(draw, "WAVE", 172, 2630, 157, 0, index=1)
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    cover.save(output / "cover.webp", quality=94, method=6, icc_profile=profile)
    print(f"Saved 3000 x 3000 RGB WebP in {output}")


if __name__ == "__main__":
    main()
