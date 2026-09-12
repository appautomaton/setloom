# SPDX-License-Identifier: AGPL-3.0-only
"""Export the retained complete cover without adding typography or other artwork."""

import argparse
from pathlib import Path

from PIL import Image, ImageCms

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    output = parser.parse_args().out_dir
    preview = output / "cover.webp"
    if preview.exists():
        raise FileExistsError("Cover exports already exist; choose another directory.")
    preview.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(HERE / "remissionem-cover-generated.webp") as image:
        if image.width != image.height:
            raise ValueError("Expected square cover art.")
        profile = (
            image.info.get("icc_profile")
            or ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        )
        cover = image.convert("RGB").resize((3000, 3000), Image.Resampling.LANCZOS)
    cover.save(preview, quality=94, method=6, icc_profile=profile)
    print(f"Exported {preview}")


if __name__ == "__main__":
    main()
