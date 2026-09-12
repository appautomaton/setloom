<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Tooling

Tool interfaces, analysis units and local runtimes. The active workstation is
macOS; use [Workflow](workflow.md) for production stages and
[Reconstruction](reconstruction.md) for musical interpretation.

## The stack

Core Python tools:

| Package | Role |
| --- | --- |
| `soundfile` | Read and write audio as NumPy arrays. |
| `scipy.signal` | Deterministic DSP: filters, resampling, envelopes, convolution. |
| `pedalboard` | Scriptable effects chains, and optional plug-in hosting. |
| `pyloudnorm` | LUFS measurement and loudness normalization. |
| `librosa` | Analysis: tempo, onset, chroma, spectral features. |
| `mido` | MIDI read and write for every part. |

SoX and FFmpeg handle conversion and export. SuperCollider renders programmed
instruments.

## Artwork storage

Prefer a compact, high-quality retained format such as WebP for covers and their
necessary source images. Preserve dimensions/color profiles and inspect lettering
and detail after conversion. Do not keep permanent PNG/JPEG equivalents or
pre-generate upload variants. Convert in scratch only when a selected destination
actually requires another format.

## Audio files

Use `setloom.audio.write_audio(path, audio, sample_rate=sr, subtype="FLOAT")`
for float32 stems; the existing `PCM_24` default suits delivery renders. WAV
writes automatically leave exact zero-byte regions sparse where the filesystem
supports it. Dense audio keeps the native writer. Samples, headroom, duration
and ordinary audio readers are unchanged; no silence threshold or extra codec
is involved. CLI separation and direct Python export share this writer.

Sparse allocation reduces disk use, not the size of a fully decoded array or
model computation. Logical file size stays unchanged; check allocated size when
measuring disk use. Copies may expand the holes. Keep using bounded reads and
remove obsolete reproducible scratch instead of retaining duplicate renders.

### Mastering loudness

Set `target_lufs` and the true-peak ceiling explicitly in each production. Choose
loudness against relevant reference recordings and the intended musical dynamics;
a previous render's level is not an implicit project standard. Use the same meter
and full-song scope for reference/output comparisons, and distinguish the requested
target from the achieved level after limiting. Report Integrated LUFS, true peak
and loudness range together when evaluating a master. Decoded MP3 peaks are not
a delivery ceiling to copy. Raising gain alone does not establish a good louder mix.

`setloom.audio.measure_loudness(path)` supplies consistent whole-file FFmpeg
measurements for references and encoded exports: `integrated_lufs`,
`true_peak_dbtp`, and `loudness_range_lu`. Below-gate loudness or silent peaks
are `None`. Processing-side `integrated_lufs(array)` still uses pyloudnorm;
small meter differences are expected, so use the file meter on both sides of an A/B.

For explicit mastering chains, `gain_db(audio, drive)` followed by
`limit_peak_lookahead(...)` provides stereo-linked, delay-compensated FFmpeg
limiting at 4x sample rate with a post-resampling peak check. Input gain,
lookahead and release are production choices; the limiter does not chase LUFS.
`limit_peak()` uses array-based gain smoothing; `master()` combines loudness
normalization with that stage. Current retained productions still use them.
Their hold window is not equivalent to lookahead: changing the limiter is a
per-production mastering revision, not a mechanical parameter rename.

`write_master(path, audio, **settings)` combines that explicit drive/limiter chain,
PCM24 export, encoded-file measurement and target/ceiling checks. Pulsus,
Remissionem and Anti Gravitational Wave share it; their musical mix preparation
and level choices stay in their own source. No hash ledger or stem cache is
required by this delivery path.

## Visual audio inspection

`setloom inspect` runs on CPU and reads only the selected audio frames (rhythm
analysis also reads bounded filter/smoothing context). It can
show waveform, spectrogram, spectrum, stereo correlation/width, and aligned A/B
views. Images default to `tmp/inspection/`; use `--out` to put them in the current
track's working directory. For example:

```bash
uv run --no-sync setloom inspect synth.wav --start 200 --end 204 \
  --view spectrogram --signal left --grid off \
  --min-freq 100 --max-freq 5000 --fft-size 8192 --hop-size 256 \
  --pitch-labels --out tmp/inspection/synth-partials.png
```

Use a longer FFT window to distinguish nearby partials, and a shorter one
(for example 1024 samples at 44.1 kHz) to inspect fast attacks. A small hop gives
more frame positions; it does not undo the window's time smearing. Tiny audio
windows shorten the FFT window automatically. Pitch labels are frequency
references at A4=440 Hz: a ridge can be a harmonic or effect, not a played note.

Spectrum and spectrogram levels are window-normalized, one-sided **bin amplitude
in dBFS**, not LUFS or a power spectral density. A bin-centered sine of peak 0.1
reads -20 dBFS. Noise floors and off-bin peaks still depend on resolution. A/B
spectrograms share their color scale; individual plots autoscale, so compare
colorbar values rather than colors across separately generated images.

Time labels are absolute file seconds. No tempo is assumed: grids need an
explicit `--bpm`. Set `--grid-origin` to the known beat-zero time in seconds;
it defaults to file zero. `--grid subdivisions --subdivisions 4` draws sixteenth
notes. `--bar-start` and `--bar-end` require BPM and count zero-based 4/4 bars
from that origin. Grid alignment does not move or quantize the audio. Mid/side
views are derived signals and should be cross-checked with left/right; they do
not isolate musical voices.

### Rhythm evidence

`--view rhythm` shows per-band RMS envelopes and independent envelope maxima.
With `--bpm`, it also measures pre-attack, attack, tail, and local-peak timing
around each subdivision. `--report` saves those measurements and their input
timing and settings as JSON. For example, after establishing
a 150 BPM grid whose beat zero is at 0.234 seconds:

```bash
uv run --no-sync setloom inspect reference.wav --compare rebuilt.wav \
  --compare-label-a Original --compare-label-b Rebuilt --view rhythm \
  --start 0.2 --end 3.5 --bpm 150 --grid-origin 0.234 \
  --grid subdivisions --subdivisions 4 --band high:6500:14000 \
  --out tmp/inspection/intro-rhythm.png --report tmp/inspection/intro-rhythm.json
```

Use `overlay` or `stack` comparison. A/B uses the same absolute file window;
align cropped excerpts to their source timeline before comparing. The command
does not align, loudness-match, export, or play audio. Labels include filenames.
`--grid off` hides lines only; a supplied BPM still enables JSON grid sampling.

The Python API is `setloom.rhythm.analyze_rhythm(path, start=..., end=...,
bpm=..., grid_origin=..., bands=(FrequencyBand("high", 6500, 14000),))`.
Both `analyze_rhythm` and `FrequencyBand` are imported from `setloom.rhythm`.
It returns a JSON-ready dictionary without creating files or loading ML models.
Use this API in per-track scripts instead of copying DSP from scratch reports.

Interpretation limits:

- Default bands are low (30–150 Hz), low-mid (150–700), mid (700–6000), and high
  (6500–14000). They are observation ranges, not instrument identities. Defaults
  truncate/omit bands above 95% of Nyquist; reports record the actual bounds.
  Repeat `--band NAME:LOW:HIGH` to specify other ranges explicitly.
- Channels are averaged in power, preserving energy that could cancel in a mono
  fold-down. Levels are **RMS dBFS**, not spectrogram bin amplitude or LUFS. A
  peak-0.1 sine in a flat passband has approximately -23.01 dBFS RMS.
- The order-3 causal bandpass has frequency-dependent delay. Its maxima are
  acoustic landmarks, not exact onsets. The centered envelope defaults to 8 ms
  with a 2 ms sampling hop; change these with `--envelope-ms` and
  `--envelope-hop-ms`. A small hop does not remove smoothing.
- `--peak-distance-ms` defaults to 30 ms. Peak prominence/floor use fractions of
  the selected envelope's 95th percentile, so changing the inspection window can
  change the detected maxima. No instrument, confidence score, or MIDI is inferred.
- Grid measurements use -30 to -8 ms before the grid position, 0–40 ms for the
  attack, and 40–90 ms for the tail. These fixed observation windows can overlap
  neighboring events at dense tempos. Incomplete windows are `null`, not silence.
  A continuing voice or effect can produce a maximum without a fresh note.

The measurement-to-performance workflow is in [reconstruction.md](reconstruction.md).

## Reference surfaces

See [DAW control](daw-control.md) for the locally checked Ableton and Logic
interfaces, their current gaps, and the division between scripting and UI work.

## Separation and transcription

ACE-Step and Magenta remain opt-in local generation experiments. The reference
tools offer these separate paths in the shared `uv` environment:

| Path | Dependency groups | Output and limits |
| --- | --- | --- |
| `transcribe --engine basic-pitch` | `transcription` | Native MLX GPU FP32 note candidates and pitch bends on Apple Silicon; no sustain pedal. |
| `transcribe --engine kong` | `kong` | Piano note candidates; the CLI exports notes only. T7 calls Kong directly to retain pedal. |
| `transcribe --engine fusion` | `kong`, `transcription` | Experimental note fusion; merges nearby attacks and suppresses suspected octave artifacts. Candidates require independent timing and pitch review. |
| `separate audio --out directory` | `anatomy` | Native MLX separation into every model estimate, as float WAVs. No energy pruning, note decoding or diagnostic-report workflow. |

For example, `uv run --no-sync setloom separate reference.mp3 --out
tmp/track/reference-stems` writes the model estimates directly. Interpret and
select them from the actual recording; the command does not infer instrument
presence. The existing Python diagnostic pipeline remains a legacy caller and
is not the production entry point.

Separation downloads and converts upstream weights once; inference uses the
cached MLX weights. Transcription cache validity depends on input, routing,
timing, runtime/model identity and requested output formats; a cached result
does not establish that its notes are musically correct.

`pitch-probes`, `pianist`, `supercollider`, and `ableton-mcp` support specific
local experiments or integrations. Enable them only when the corresponding
source needs them. Basic Pitch's `transcription` group contains MLX and safetensors.
Model locations and hardware limits live in [AGENTS.md](../AGENTS.md).

## Native Basic Pitch on MLX

`transcribe` defaults to `basic-pitch`, now native FP32 inference on the Apple
Silicon GPU. `basic-pitch-mlx` remains an alias for the same path. Public
`BasicPitchModel`, activation queries, fusion, and per-stem poly transcription
all use this runtime with the existing windowing, decoder, pitch bends and file
writers. CoreML packages and `compute_units` are no longer accepted by these
APIs. The native runtime requires GPU access; it does not silently fall back.

The `transcription` dependency group provides runtime dependencies. The
compatibility group `transcription-mlx` includes it plus ONNX and ONNX Runtime
for conversion/validation. Inference loads local `.safetensors` weights without
CoreML or ONNX Runtime. BF16 experiments remain confined to
`scripts/validate_basic_pitch_mlx.py` and are not promoted.

Convert the upstream ONNX asset from the read-only reference checkout, then
run transcription:

```bash
uv run --no-sync python scripts/convert_basic_pitch_mlx.py \
  --source .references/basic-pitch/basic_pitch/saved_models/icassp_2022/nmp.onnx \
  --output models/basic-pitch-mlx/icassp_2022
MLX_ENABLE_TF32=0 uv run --no-sync setloom transcribe input.wav \
  --out tmp/transcription/input.mid --events tmp/transcription/input.json
```

Use `--model-path` or `--model-root` to select another converted MLX model
directory; `--model-path` takes precedence. Existing threshold, frequency-range,
onset-inference, and pitch-bend CLI options also apply to MLX. Weights stay in
gitignored `models/`; scratch audio, MIDI, and validation reports stay in `tmp/`.

The FP32 baseline requires `MLX_ENABLE_TF32=0` before importing MLX. On GPUs with
dedicated matrix-multiplication units, MLX can otherwise use reduced-precision
arithmetic for FP32 convolutions and matrix multiplication; FP32 tensor storage alone does not
guarantee FP32 computation. See the official
[MLX numerical precision documentation](https://ml-explore.github.io/mlx/build/html/usage/precision.html).
The native runner sets the flag before its lazy MLX import when it is unset.
The anatomy pipeline sets it before separation when transcription is requested.
It rejects an explicitly conflicting flag, or an MLX import that already
occurred without the flag. For Python scripts and notebooks that use other
MLX packages, launch a fresh process with the flag set, for example
`MLX_ENABLE_TF32=0 uv run --no-sync python analysis.py`.

For runtime or conversion changes, use
[`validate_basic_pitch_mlx.py`](../scripts/validate_basic_pitch_mlx.py) and
[`convert_basic_pitch_mlx.py`](../scripts/convert_basic_pitch_mlx.py).

## Local vocal word timing

The optional `vocal-alignment` dependency group supplies `mlx-whisper` for local
phrase and word timing. Keep its weights in `models/` and pass their local path
to the [MLX Whisper API](https://github.com/ml-explore/mlx-examples/tree/main/whisper).
Use this alongside vocal pitch, envelopes and the original recording when
reviewing singing-to-instrument articulation. Singing timestamps can drift and
speech-duration heuristics can shorten held vowels; they are context, not a
musical note grid. For bounded passage work, crop the input explicitly and record
the original-file offset.
