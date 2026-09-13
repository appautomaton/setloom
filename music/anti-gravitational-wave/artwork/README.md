# Anti Gravitational Wave cover

`cover-master.webp` is the retained 3000 x 3000 cover. The 1254 x 1254
text-free source is `source/anti-gravitational-wave-art.webp`; its exact
generation prompt is `source/prompt.txt`. Both images now use high-quality
lossy WebP with their color profiles preserved. Dimensions were not reduced.

`source/compose_cover.py` applies the existing Helvetica Neue typography and
exports a WebP cover. The export is resized source
art, not native 3000-pixel generated detail. From the repository root:

```sh
uv run --no-sync python -B music/anti-gravitational-wave/artwork/source/compose_cover.py \
  --out-dir tmp/anti-gravitational-wave-cover
```

The output directory must not contain existing cover exports. The historical
publication cover remains under `../published/`; this directory holds artwork source.
