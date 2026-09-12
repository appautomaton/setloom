# SPDX-License-Identifier: AGPL-3.0-only
"""Per-stem transcription: route each separated stem to the right note engine.

After the layer lens writes kept stems to disk, this pass reads each stem WAV and
turns it into notes, routed by instrument type:

- ``poly``: Basic Pitch (polyphonic, pitch bends) for chordal/pitched stems.
- ``mono``: FCPE single-line f0 (better low end, no octave slips) for bass and voices.
- ``drum``: onset detection mapped to one fixed GM note for percussion stems.

Because separation already isolates one instrument per stem, drum transcription is
just onset detection on that stem mapped to its GM note, not kit classification.

Output is one MIDI per stem plus a combined multi-track MIDI (one track per stem),
and optional per-stem note-events JSON. Routing has defaults and is overridable per
track (a ``<audio>.transcribe.yml`` sidecar) and per run (a CLI override string),
resolved ``defaults <- sidecar <- CLI``.

Heavy backends (Basic Pitch/MLX, torchfcpe/torch, librosa) import lazily, so the
module is cheap to import on non-transcription paths.
"""

from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import mido
from pydantic import BaseModel, ConfigDict, model_validator

from setloom.anatomy.pipeline import HOP, SR, Grid, _write_yaml_if_changed, write_bass_midi
from setloom.midi import DRUM_CHANNEL, PPQ, SIXTEENTH_TICKS, NoteEvent

DEFAULT_BP_MODEL_ROOT = Path("models/basic-pitch-mlx/icassp_2022")
BP_CACHE_BACKEND = "basic-pitch-mlx-fp32-v1"

HP_CUTOFF_HZ = 120.0   # the synth stem duplicates the bassline; strip it before f0
FCPE_VOICED_MIN = 0.4  # min voiced fraction of a 16th step to count as a note

# --- routing ---------------------------------------------------------------

ROUTE_POLY = "poly"   # Basic Pitch, polyphonic + pitch bends
ROUTE_MONO = "mono"   # FCPE monophonic f0, grid-quantized
ROUTE_DRUM = "drum"   # onset detection -> one GM note
ROUTE_SKIP = "skip"   # explicitly not transcribed
ROUTES = (ROUTE_POLY, ROUTE_MONO, ROUTE_DRUM, ROUTE_SKIP)
DEFAULT_UNKNOWN_ROUTE = ROUTE_POLY

# Single dominant lines and low end: mono f0 is cleaner here than polyphonic decode.
MONO_STEMS = frozenset({"bass", "double-bass", "vocal", "lead-vocal", "back-vocal"})

# Percussion stems -> the General MIDI note each maps to (also the drum-route stem set).
DRUM_GM_NOTE: dict[str, int] = {
    "kick": 36,        # acoustic bass drum
    "snare": 38,       # acoustic snare
    "hh": 42,          # closed hi-hat
    "toms": 45,        # low tom
    "congas": 64,      # low conga
    "tambourine": 54,
    "percussion": 39,  # hand clap (generic percussion)
    "triangle": 81,    # open triangle
    "wind-chimes": 81,
    "drums": 36,       # full drum bus, if kept alongside the parts
}
DEFAULT_DRUM_NOTE = 39  # fallback when a stem is forced to drum without a GM mapping

# Everything else (synth, keys, piano, guitars, strings, brass, winds, ...) is poly.


def default_route(stem: str) -> str:
    """Route for a stem from the static policy, or ``DEFAULT_UNKNOWN_ROUTE`` (poly)."""
    if stem in DRUM_GM_NOTE:
        return ROUTE_DRUM
    if stem in MONO_STEMS:
        return ROUTE_MONO
    return DEFAULT_UNKNOWN_ROUTE


def parse_transcriber_flag(spec: str) -> dict[str, str]:
    """Parse ``"bass=poly,percussion=drum"`` into ``{"bass": "poly", ...}``."""
    overrides: dict[str, str] = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        stem, sep, route = (part.strip() for part in pair.partition("="))
        if not sep or not stem or route not in ROUTES:
            raise ValueError(f"invalid override {pair!r} (expected stem=route, route in {ROUTES})")
        overrides[stem] = route
    return overrides


def resolve_routes(
    kept_stems: list[str],
    sidecar: dict[str, str] | None = None,
    cli_overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """One route per kept stem: ``defaults <- sidecar <- CLI`` (later wins).

    An override naming a stem that is not kept is warned and ignored (so a sidecar can
    pre-declare routes for stems that may or may not survive the keep gate). An unknown
    route token raises.
    """
    routes = {stem: default_route(stem) for stem in kept_stems}
    kept = set(kept_stems)
    for source in (sidecar or {}, cli_overrides or {}):
        for stem, route in source.items():
            if route not in ROUTES:
                raise ValueError(f"stem {stem!r}: unknown route {route!r} (expected {ROUTES})")
            if stem not in kept:
                warnings.warn(f"transcribe override for {stem!r} ignored: not a kept stem", stacklevel=2)
                continue
            routes[stem] = route
    return routes


# --- per-track sidecar config ---------------------------------------------


class TranscribeSpec(BaseModel):
    """Schema for a ``<audio>.transcribe.yml`` sidecar: a per-stem route map."""

    model_config = ConfigDict(extra="forbid")
    transcribe: dict[str, str] = {}

    @model_validator(mode="after")
    def _validate_routes(self) -> "TranscribeSpec":
        for stem, route in self.transcribe.items():
            if route not in ROUTES:
                raise ValueError(f"stem {stem!r}: unknown route {route!r} (expected {ROUTES})")
        return self


def _sidecar_path(audio_path: Path) -> Path:
    audio_path = Path(audio_path)
    return audio_path.parent / f"{audio_path.stem}.transcribe.yml"


def load_transcribe_sidecar(audio_path: Path) -> dict[str, str]:
    """Return the per-stem route map from ``<audio>.transcribe.yml``, or ``{}`` if absent."""
    import yaml

    path = _sidecar_path(audio_path)
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return TranscribeSpec.model_validate(raw).transcribe


# --- transcription results -------------------------------------------------


@dataclass
class StemTranscription:
    """One stem's transcription, normalized for the dossier and the assembler."""

    stem: str
    route: str
    midi_path: Path
    events_path: Path | None
    notes: list  # TranscribedNote (poly) or NoteEvent (mono / drum)
    is_drum: bool
    stats: dict = field(default_factory=dict)


def _steps_to_note_events(notes: list[tuple[int, int, int]], *, velocity: int = 96) -> list[NoteEvent]:
    """Convert ``(start_step, length_steps, midi)`` notes to absolute-tick NoteEvents.

    Matches ``pipeline.write_bass_midi``: 16th = ``SIXTEENTH_TICKS`` ticks, minus a 10
    tick release gap so adjacent notes retrigger.
    """
    events: list[NoteEvent] = []
    for start, length, pitch in notes:
        start_tick = start * SIXTEENTH_TICKS
        duration = max(1, length * SIXTEENTH_TICKS - 10)
        events.append(NoteEvent(0, pitch, velocity, start_tick, duration))
    return events


def _write_event_json(events: list[NoteEvent], path: Path) -> Path:
    import json

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([event._asdict() for event in events], indent=2) + "\n", encoding="utf-8"
    )
    return path


def _note_event_track(events: list[NoteEvent], bpm: float, *, channel: int, include_tempo: bool):
    """Delta-encode a NoteEvent list into one MIDI track (reuses basic_pitch's encoder)."""
    from setloom.transcription import basic_pitch as bp

    tuples: list[tuple[int, int, mido.Message]] = []
    for event in events:
        tuples.append(
            (event.start_tick, bp._RANK_NOTE_ON,
             mido.Message("note_on", channel=channel, note=event.note, velocity=event.velocity, time=0))
        )
        tuples.append(
            (event.start_tick + event.duration_ticks, bp._RANK_NOTE_OFF,
             mido.Message("note_off", channel=channel, note=event.note, velocity=0, time=0))
        )
    return bp._emit_track(tuples, bpm, include_tempo=include_tempo)


def _write_events_midi(events: list[NoteEvent], path: Path, bpm: float, *, channel: int) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    midi = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    midi.tracks.append(_note_event_track(events, bpm, channel=channel, include_tempo=True))
    midi.save(str(path))
    return path


# --- dispatchers -----------------------------------------------------------


def transcribe_poly(
    stem: str, wav: Path, out_dir: Path, track: str, grid: Grid, *,
    model_root: Path = DEFAULT_BP_MODEL_ROOT, emit_events: bool = False, model=None,
) -> StemTranscription:
    """Polyphonic transcription via Basic Pitch; absolute time at ``grid.bpm`` with bends.

    ``model`` is an optional pre-loaded ``BasicPitchModel`` reused across stems so the
    MLX model loads once per pass rather than once per stem.
    """
    from setloom.transcription import basic_pitch as bp

    midi_path = out_dir / f"{track}.{stem}.mid"
    events_path = out_dir / f"{track}.{stem}.events.json" if emit_events else None
    request = bp.TranscriptionRequest(
        audio=str(wav),
        out_midi=str(midi_path),
        out_events=str(events_path) if events_path else None,
        model_root=model_root,
        midi_tempo=grid.bpm,
        include_pitch_bends=True,
    )
    result = bp.transcribe_audio(request, model=model)
    notes = list(result.notes)
    return StemTranscription(
        stem, ROUTE_POLY, midi_path, result.events_path, notes,
        is_drum=False, stats={"note_count": len(notes)},
    )


def _device() -> str:
    import torch

    return "mps" if torch.backends.mps.is_available() else "cpu"


def _prep_melodic(y, sr: int, stem: str):
    """High-pass the synth stem (it duplicates the bassline) and clamp.

    Clamping to [-1, 1] is load-bearing: filtfilt overshoot trips torchfcpe's mel
    extractor on MPS (probe finding, 2026-06-10).
    """
    import numpy as np
    import scipy.signal as ss

    if stem == "synth":
        sos = ss.butter(4, HP_CUTOFF_HZ, "hp", fs=sr, output="sos")
        y = ss.sosfiltfilt(sos, y)
    peak = float(np.max(np.abs(y)))
    if peak > 1.0:
        y = y / peak
    return np.ascontiguousarray(y, dtype=np.float32)


_FCPE = None


def _f0_track(y, sr: int):
    """Frame-rate f0 in Hz (0 where unvoiced) via torchfcpe."""
    import warnings

    import torch
    from torchfcpe import spawn_bundled_infer_model

    global _FCPE
    device = _device()
    if _FCPE is None:
        _FCPE = spawn_bundled_infer_model(device=device)
    audio = torch.from_numpy(y).unsqueeze(0).unsqueeze(-1).to(device)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f0 = _FCPE.infer(audio, sr=sr, decoder_mode="local_argmax", threshold=0.006)
    return f0.squeeze().cpu().numpy()


def _f0_steps(f0, duration: float, grid: Grid):
    """Median-voiced f0 per 16th step -> MIDI pitch array (-1 = rest)."""
    import numpy as np

    times = np.linspace(0.0, duration, len(f0), endpoint=False)
    step = grid.bar_dur / 16.0
    n_steps = grid.n_bars * 16
    step_pitch = np.full(n_steps, -1, dtype=int)
    for s in range(n_steps):
        t_start = grid.t0 + s * step
        sel = (times >= t_start) & (times < t_start + step)
        if not sel.any():
            continue
        voiced = f0[sel] > 0
        if voiced.mean() < FCPE_VOICED_MIN:
            continue
        hz = float(np.median(f0[sel][voiced]))
        if hz > 0:
            step_pitch[s] = int(round(69 + 12 * np.log2(hz / 440.0)))
    return step_pitch


def transcribe_mono(
    stem: str, wav: Path, out_dir: Path, track: str, grid: Grid, *, emit_events: bool = False,
) -> StemTranscription:
    """Monophonic transcription via FCPE; grid-quantized 16th steps at ``grid.bpm``."""
    import librosa

    from setloom.anatomy import analysis as an

    y, _ = librosa.load(str(wav), sr=SR, mono=True)
    y = _prep_melodic(y, SR, stem)
    f0 = _f0_track(y, SR)
    step_pitch = _f0_steps(f0, len(y) / SR, grid)
    notes = an.segment_notes(step_pitch)

    midi_path = out_dir / f"{track}.{stem}.mid"
    write_bass_midi(notes, midi_path, grid.bpm)
    events = _steps_to_note_events(notes)
    events_path = None
    if emit_events:
        events_path = _write_event_json(events, out_dir / f"{track}.{stem}.events.json")
    return StemTranscription(
        stem, ROUTE_MONO, midi_path, events_path, events,
        is_drum=False, stats=an.note_stats(notes, grid.n_bars * 16),
    )


def _onset_velocity(onset_env, frame: int) -> int:
    import numpy as np

    if not len(onset_env):
        return 100
    peak = float(onset_env.max()) or 1.0
    strength = float(onset_env[min(frame, len(onset_env) - 1)]) / peak
    return int(np.clip(round(40 + strength * 80), 1, 127))


def transcribe_drum(
    stem: str, wav: Path, out_dir: Path, track: str, grid: Grid, *, emit_events: bool = False,
) -> StemTranscription:
    """Onset detection mapped to one GM note; absolute time at ``grid.bpm`` on channel 9."""
    import librosa

    from setloom.transcription import basic_pitch as bp

    y, _ = librosa.load(str(wav), sr=SR, mono=True)
    onset_env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=SR, hop_length=HOP, backtrack=True)
    times = librosa.frames_to_time(frames, sr=SR, hop_length=HOP)
    note = DRUM_GM_NOTE.get(stem, DEFAULT_DRUM_NOTE)

    events = [
        NoteEvent(
            DRUM_CHANNEL, note, _onset_velocity(onset_env, int(frame)),
            bp._seconds_to_tick(float(t), grid.bpm), SIXTEENTH_TICKS,
        )
        for t, frame in zip(times, frames)
    ]
    midi_path = _write_events_midi(events, out_dir / f"{track}.{stem}.mid", grid.bpm, channel=DRUM_CHANNEL)
    events_path = None
    if emit_events:
        events_path = _write_event_json(events, out_dir / f"{track}.{stem}.events.json")
    return StemTranscription(
        stem, ROUTE_DRUM, midi_path, events_path, events,
        is_drum=True, stats={"onset_count": len(events), "gm_note": note},
    )


# --- combined multi-track MIDI --------------------------------------------


def assemble_multitrack(results: list[StemTranscription], out_path: Path, bpm: float) -> Path:
    """One type-1 MIDI, one named track per stem. Pitched stems rotate non-drum
    channels; drum stems are forced to channel 9. ``set_tempo`` on the first track."""
    from setloom.transcription import basic_pitch as bp

    midi = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    include_tempo = True
    channel_idx = 0
    for result in results:
        if result.is_drum:
            channel = DRUM_CHANNEL
        else:
            channel = bp._PITCH_BEND_CHANNELS[channel_idx % len(bp._PITCH_BEND_CHANNELS)]
            channel_idx += 1

        if result.route == ROUTE_POLY:
            tuples: list[tuple[int, int, mido.Message]] = []
            for note in bp._drop_overlapping_pitch_bends(list(result.notes)):
                tuples.extend(bp._note_messages(note, channel, bpm))
            track = bp._emit_track(tuples, bpm, include_tempo=include_tempo)
        else:
            track = _note_event_track(result.notes, bpm, channel=channel, include_tempo=include_tempo)

        track.insert(0, mido.MetaMessage("track_name", name=result.stem, time=0))
        midi.tracks.append(track)
        include_tempo = False

    if not midi.tracks:
        midi.tracks.append(bp._emit_track([], bpm, include_tempo=True))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    midi.save(str(out_path))
    return out_path


# --- pass entry point ------------------------------------------------------


def _kept_stems(layer_dir: Path) -> list[str]:
    """Kept stem names with a WAV on disk, from the manifest if present else by glob."""
    import yaml

    layer_dir = Path(layer_dir)
    manifest = layer_dir / "manifest.yml"
    if manifest.is_file():
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        kept = [e["layer"] for e in data.get("stems", []) if e.get("kept")]
        return [s for s in kept if (layer_dir / f"{s}.wav").is_file()]
    return sorted(p.stem for p in layer_dir.glob("*.wav"))


def transcribe_pass(
    audio_path: Path,
    track: str,
    layer_dir: Path,
    grid: Grid,
    out_dir: Path,
    *,
    cli_overrides: dict[str, str] | None = None,
    emit_events: bool = False,
    bp_model_root: Path = DEFAULT_BP_MODEL_ROOT,
) -> list[str]:
    """Route + transcribe each kept stem; write per-stem + combined MIDI + dossier.

    Reuse cached outputs only while stem file metadata, routing, timing, backend,
    model content, and requested output formats match.
    """
    import yaml

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dossier = out_dir / f"{track}.transcribe.yml"
    combined = out_dir / f"{track}.combined.mid"
    layer_dir = Path(layer_dir)
    kept = _kept_stems(layer_dir)
    if not kept:
        return ["transcribe:no-stems"]

    sidecar = load_transcribe_sidecar(audio_path)
    routes = resolve_routes(kept, sidecar, cli_overrides)

    stem_files = {}
    for stem in kept:
        wav = layer_dir / f"{stem}.wav"
        stat = wav.stat()
        stem_files[stem] = [str(wav.resolve()), stat.st_size, stat.st_mtime_ns]
    cache_inputs = {
        "version": 2,
        "stems": stem_files,
        "routes": routes,
        "sidecar": sidecar,
        "cli_overrides": cli_overrides or {},
        "grid": [grid.bpm, grid.t0, grid.n_bars],
        "bp_model_root": str(Path(bp_model_root).resolve()),
        "bp_backend": BP_CACHE_BACKEND,
        "bp_assets": {
            name: hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            for name in ("config.json", "model.safetensors", "manifest.json")
            for path in (Path(bp_model_root) / name,)
        } if ROUTE_POLY in routes.values() else None,
        "emit_events": emit_events,
    }
    outputs = [combined]
    for stem, route in routes.items():
        if route != ROUTE_SKIP:
            outputs.append(out_dir / f"{track}.{stem}.mid")
            if emit_events:
                outputs.append(out_dir / f"{track}.{stem}.events.json")
    if dossier.is_file():
        try:
            cached = yaml.safe_load(dossier.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            cached = None
        if (isinstance(cached, dict) and cached.get("cache_inputs") == cache_inputs
                and all(path.is_file() for path in outputs)):
            return ["transcribe:cached"]

    # Load the Basic Pitch MLX model once and reuse it across every poly stem.
    bp_model = None
    if any(routes[s] == ROUTE_POLY for s in kept):
        from setloom.transcription import basic_pitch as bp

        bp_model = bp.BasicPitchModel(bp.default_model_path(bp_model_root))

    results: list[StemTranscription] = []
    for stem in kept:
        route = routes[stem]
        if route == ROUTE_SKIP:
            continue
        wav = layer_dir / f"{stem}.wav"
        if route == ROUTE_POLY:
            results.append(transcribe_poly(stem, wav, out_dir, track, grid,
                                           model_root=bp_model_root, emit_events=emit_events,
                                           model=bp_model))
        elif route == ROUTE_MONO:
            results.append(transcribe_mono(stem, wav, out_dir, track, grid, emit_events=emit_events))
        else:  # ROUTE_DRUM
            results.append(transcribe_drum(stem, wav, out_dir, track, grid, emit_events=emit_events))

    assemble_multitrack(results, combined, grid.bpm)
    _write_dossier(dossier, track, grid, results, sidecar or {}, cli_overrides or {}, cache_inputs)
    return ["transcribe:analyzed"]


def _write_dossier(
    path: Path, track: str, grid: Grid, results: list[StemTranscription],
    sidecar: dict[str, str], cli_overrides: dict[str, str], cache_inputs: dict,
) -> None:
    def source(stem: str) -> str:
        if stem in cli_overrides:
            return "cli"
        if stem in sidecar:
            return "sidecar"
        return "default"

    stems = [
        {
            "stem": r.stem,
            "route": r.route,
            "source": source(r.stem),
            "midi": r.midi_path.name,
            "events": r.events_path.name if r.events_path else None,
            "is_drum": r.is_drum,
            "stats": r.stats,
        }
        for r in results
    ]
    _write_yaml_if_changed(
        path,
        {
            "track": track,
            "note": "per-stem transcription; poly=Basic Pitch, mono=FCPE, drum=onset->GM note",
            "bpm": grid.bpm,
            "combined_midi": f"{track}.combined.mid",
            "stems": stems,
            "cache_inputs": cache_inputs,
        },
    )
