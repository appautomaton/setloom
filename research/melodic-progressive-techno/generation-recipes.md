<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Generation Recipes: Local Candidates from the Unified Environment

Documented local experiment paths, not product surfaces. Generated audio is reference material and candidate input for the taste owner — scored by `setloom score`, judged at the listening gate, never committed.

## The environment contract

All generation models live in setloom's **one uv environment** via the `genai` dependency group — no per-model venvs. `.references/` clones are read-only reference code. Install:

```sh
uv sync --group anatomy --group genai
```

Weights download on first use into the gitignored **project model store**:

| Path | What | Routed by |
| --- | --- | --- |
| `models/acestep/` | ACE-Step 1.5 checkpoints (DiT, VAE, embedder, 5Hz LM) | `ACESTEP_CHECKPOINTS_DIR` (set by the script) |
| `models/magenta/` | Magenta RT 2 checkpoints | `MAGENTA_HOME` (set by the script) |
| `models/hf/` | Hugging Face hub cache for generation pulls | `HF_HUB_CACHE` (set by the script) |

`HF_HOME` is never overridden, so an existing `hf auth login` keeps working. **Serialize heavy model runs** — never run generation concurrently with separation or another model (M5 Max unified-memory rule). On this machine the local `torch-2.12.0+m5max` wheel may replace stock torch (`uv sync --no-install-package torch`, then install the wheel); int8-on-MPS paths stay gated behind `"+m5max" in torch.__version__`.

## Recipe 1 — ACE-Step 1.5: full-track instrumental candidate (songwriter pillar)

```sh
uv run --no-sync python scripts/generate_candidate.py --seed 42 --duration 360
uv run --no-sync setloom score "anatomy/_candidates/acestep-candidate-01.wav"
```

The script pins the style brief: instrumental, 123 bpm, minor key, hypnotic-pedal caption mirroring the grammar (no named artists). Candidates land in `anatomy/_candidates/` — structurally exempt from `corpus-summary.yml`, so scoring them never pollutes the corpus aggregate. Iterate by seed and caption; the score report says where each candidate sits against the grammar, and your ears say whether it matters.

Reproducibility contract (verified 2026-06-10):

- The script passes `use_random_seed=False` + explicit `seeds`; the upstream config default silently discards the seed otherwise.
- `--no-thinking` runs are byte-reproducible per seed, and the caption reaches the DiT verbatim.
- Thinking runs are **one-offs**: the 5Hz LM's MLX sampler is unseeded upstream, and the LM rewrites the caption by design ("query rewrite"; observed drift: melodic-techno brief → deep-house/oud/vocal-chop caption).
- **Default to thinking for musical candidates.** The LM is the composition engine (upstream capability table: CoT metas, query rewrite, composition); DiT-only is upstream's low-VRAM fallback. Retention means keeping the WAV — revision flows from saved artifacts (repaint/retake/cover tasks), not from re-running seeds. Reach for `--no-thinking` only for engineering runs (determinism tests, knob attribution) or as a brief-fidelity fallback when the rewrite keeps drifting the mood.
- Quality levers above the current `acestep-5Hz-lm-1.7B` + 2B turbo DiT: the 4B LM ("strong" composition tier) and the XL DiT both fit this machine's unified memory; trying them is its own change.

## Recipe 1b — Vocal lane: generate the voice, only the voice

Taste-owner rule (2026-06-10): when the target is a vocal lead, do not generate
a full band around it. Caption an a cappella take ("solo female vocal, a
cappella, minimal atmosphere") with `--lyrics-file` and `--vocal-language`,
and size `--duration` to the lyric (a 4-line stanza needs ~45-60 s, not 120 s).
Voice-only takes are cheaper, faster to audition, and need no stem separation —
the artifact tax disappears when there is no band to peel away. Full-mix vocal
generation (the T04 take-3 path) remains the fallback when the composer needs
band context to phrase against.

## Recipe 2 — Magenta RT 2: jam-pillar smoke clip

```sh
uv run --no-sync python scripts/magenta_smoke.py --duration 16
```

A short MLX-generated clip proving the realtime pillar runs in this env. Lane assignment (2026-06-10): Magenta RT 2 owns the **sound-design / ambient / pad lane** — textures, beds, and pads — alongside its future realtime-jam role. Magenta RT 2 has **no PyTorch path** — it is MLX (plus a C++ engine) on Apple Silicon. The actual jam workflow (live audio routing, MIDI steering from an instrument) is its own future change; do not score smoke clips against full-track grammar.

## Licensing and provenance

- ACE-Step 1.5: MIT code, model-card-licensed training data (v1.5). Pinned in `pyproject.toml` at the upstream rev; its stale `<3.13` Python cap is overridden there with a documented `[[tool.uv.dependency-metadata]]` block.
- Magenta RT 2: Apache-2.0 code, CC-BY model weights, from PyPI (`magenta-rt[mlx]`).
- Stable Audio 3 is **deferred**: hard pins (`python <3.11`, `torch==2.7.1`) cannot join the unified env today; it returns as a dedicated porting effort. Until then, Magenta RT 2 covers its sound-design lane.
- Generated audio belongs to its creator subject to each model's terms; treat outputs as local experiment material with non-commercial intent.

## The loop this enables

```
generate (recipe) → separate → anatomize → score → listen (gate) → revise prompt/seed
```

`anatomize` and `score` do not care whether audio is a reference track or model output — the same instrument that dissected the corpus grades every candidate.
