<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Setloom

Setloom, by AppAutomaton, is an open-source collection of music-production tools
and agent guidance. The agent is responsible for musical taste, creative
judgment and production quality. The human gives direction, hears the result
and decides whether it succeeds. Rejected work needs substantive revision.

## Working with music

Start with the intended effect and the actual recording or performance. Inspect
complete phrases, identify the relevant notes, articulation, modulation and
sound, then implement and evaluate a musical decision. Continue patiently across
the commissioned scope. Code makes understood operations repeatable; it does
not remove this work or turn a successful render into a successful song.

Keep musical decisions and editable performance data with each track. Shared
code supplies analysis, MIDI, DSP and rendering primitives. There is no required
sequence of CLI commands and no fixed arrangement template to complete first.

## Tools

Initialize the repo-local environment with `uv sync --group transcription`.
Additional dependency groups and model setup are in [Tooling](docs/tooling.md).

| Operation | Available path |
| --- | --- |
| Inspect a passage | `setloom inspect`: waveform, spectra, rhythm, stereo and aligned comparisons. |
| Query pitch and onset evidence | Native MLX FP32 Basic Pitch API; `setloom transcribe` exports note candidates. |
| Separate reference audio | `setloom separate`: all model estimates as float WAVs. Outputs overlap and need musical interpretation. |
| Edit and perform music | Per-track MIDI, controls and patches using Python, SuperCollider or authorized DAW tools. |
| Play a requested file | `setloom play`; honor the user's playback preference. |

For example, when a particular passage needs inspection:

```bash
uv run --no-sync setloom inspect reference.wav --start 60 --end 68 \
  --view spectrogram --fft-size 8192 --hop-size 256 --grid off \
  --out tmp/study/partials.png
```

When note candidates will help answer a pitch or timing question:

```bash
MLX_ENABLE_TF32=0 uv run --no-sync setloom transcribe reference.wav \
  --out tmp/study/note-proposals.mid --events tmp/study/note-proposals.json
```

These operations do not determine which detections are independent voices,
harmonics, effects, retriggers or continuing modulation. That interpretation
belongs to the musical work. See [tooling](docs/tooling.md) for units, runtimes
and limits, and [reconstruction](docs/reconstruction.md) for reference work.

## Files and stages

| Location | Purpose |
| --- | --- |
| `tmp/<track>/` | New source, MIDI, separated estimates, studies, renders and auditions. |
| `music/` | Editable productions the user has chosen to retain or promote there. |
| `local/` | Audio and other assets the user considers good enough for longer-term retention. |
| `local/reconstructions/` | Approved reconstruction notes/MIDI, patches, performances and supporting references. |
| `models/` | Gitignored model weights. |
| `src/setloom/` | Reusable audio, MIDI, analysis and runtime code. |
| `docs/` and project skills | Concise context and guidance for using the tools. |

A file category, completed script or relative improvement does not confer
retention or publication approval. Supplied originals already in `local/corpus/`
keep their existing location; new derivatives begin in `tmp`.
See [working stages](docs/workflow.md#working-stages).

## Existing productions

- [Anti Gravitational Wave](music/anti-gravitational-wave/): editable multitrack
  MIDI, controller data and instrument reinterpretation.
- [Remissionem](music/remissionem/): retained score, instruments and release source.
- [Pulsus Noctis](music/pulsus-noctis/): independent MIDI performance, instruments and reference-informed mastering.
- [T7](music/T7-piano-solos/): completed piano work with captured timing and pedal.

These are examples, not recipes for the next track. Follow the current brief
and the user's scoped listening feedback.

## License and credits

- Code, prompts, schemas and harness logic: AGPL-3.0-only.
- Documentation: CC BY-SA 4.0 unless marked otherwise.
- Music outputs belong to you, subject to the third-party samples, models and inputs used.
- Third-party software attribution: [NOTICE](LICENSES/NOTICE).

See [LICENSE](LICENSE), [CONTRIBUTING.md](CONTRIBUTING.md),
[license texts](LICENSES/) and [trademarks](LICENSES/TRADEMARKS.md).
Audio, model weights and proprietary samples remain outside Git.
