# Remissionem cover

The sculpture and lettering were generated together. The retained complete
1254 x 1254 source is `source/remissionem-cover-generated.webp`; the supplied
visual reference is `source/remissionem-art.webp`. Their exact prompts remain
in `source/prompt.txt` and `source/art-prompt.txt`.

`cover-master.webp` retains the 3000 x 3000 delivery layout. The images use
high-quality lossy WebP with embedded color profiles and unchanged dimensions.
The 3000-pixel export is enlarged from the native source.

The Python/Pillow exporter only resizes and encodes; it adds no visual elements:

```sh
uv run --no-sync python -B music/remissionem/artwork/source/export_cover.py \
  --out-dir tmp/remissionem-cover
```

It writes a WebP cover with the color profile.
Existing exports are not overwritten. The historical publication cover is retained
under `../published/`.
