# SPDX-License-Identifier: AGPL-3.0-only
"""Hermetic tests for the per-stem transcription pass.

No model weights, no network, no torch/CoreML: pure routing/override/assembler logic
plus a pass run with the three transcribers monkeypatched. Importing basic_pitch for
``TranscribedNote`` is safe (CoreML loads only inside ``BasicPitchModel``).
"""

from pathlib import Path

import mido
import numpy as np
import pytest
import soundfile as sf
import yaml
from pydantic import ValidationError

from setloom.anatomy import transcribe as tx
from setloom.anatomy.pipeline import Grid
from setloom.anatomy.transcribe import ROUTE_DRUM, ROUTE_MONO, ROUTE_POLY, StemTranscription
from setloom.midi import NoteEvent
from setloom.transcription.basic_pitch import TranscribedNote

GRID = Grid(120.0, 0.0, 4)


# --- routing & overrides ---------------------------------------------------


def test_default_route_table() -> None:
    assert tx.default_route("kick") == ROUTE_DRUM
    assert tx.default_route("snare") == ROUTE_DRUM
    assert tx.default_route("hh") == ROUTE_DRUM
    assert tx.default_route("bass") == ROUTE_MONO
    assert tx.default_route("double-bass") == ROUTE_MONO
    assert tx.default_route("vocal") == ROUTE_MONO
    assert tx.default_route("back-vocal") == ROUTE_MONO
    for s in ("synth", "keys", "piano", "digital-piano", "marimba", "guitar"):
        assert tx.default_route(s) == ROUTE_POLY
    assert tx.default_route("totally-unknown") == ROUTE_POLY  # safe fallback


def test_parse_transcriber_flag() -> None:
    assert tx.parse_transcriber_flag("bass=poly,marimba=poly,percussion=drum") == {
        "bass": "poly", "marimba": "poly", "percussion": "drum"
    }
    assert tx.parse_transcriber_flag(" bass = mono ,") == {"bass": "mono"}  # spaces + trailing comma
    for bad in ("bass", "bass=", "=poly", "bass=banana"):
        with pytest.raises(ValueError):
            tx.parse_transcriber_flag(bad)


def test_resolve_routes_precedence() -> None:
    kept = ["bass", "synth", "kick"]
    assert tx.resolve_routes(kept) == {"bass": "mono", "synth": "poly", "kick": "drum"}
    assert tx.resolve_routes(kept, sidecar={"bass": "poly"})["bass"] == "poly"
    # CLI wins over sidecar
    assert tx.resolve_routes(kept, sidecar={"bass": "poly"}, cli_overrides={"bass": "mono"})["bass"] == "mono"
    assert tx.resolve_routes(kept, cli_overrides={"synth": "skip"})["synth"] == "skip"
    with pytest.raises(ValueError):
        tx.resolve_routes(kept, cli_overrides={"bass": "banana"})


def test_resolve_routes_warns_on_not_kept() -> None:
    kept = ["bass", "synth"]
    with pytest.warns(UserWarning):
        routes = tx.resolve_routes(kept, cli_overrides={"guitar": "poly"})
    assert "guitar" not in routes


def test_load_transcribe_sidecar(tmp_path) -> None:
    audio = tmp_path / "Gaia.mp3"
    audio.touch()
    assert tx.load_transcribe_sidecar(audio) == {}  # absent -> {}
    side = tmp_path / "Gaia.transcribe.yml"
    side.write_text("transcribe:\n  bass: poly\n  marimba: poly\n", encoding="utf-8")
    assert tx.load_transcribe_sidecar(audio) == {"bass": "poly", "marimba": "poly"}
    side.write_text("transcribe:\n  bass: poly\nbogus: 1\n", encoding="utf-8")  # extra=forbid
    with pytest.raises(ValidationError):
        tx.load_transcribe_sidecar(audio)
    side.write_text("transcribe:\n  bass: banana\n", encoding="utf-8")  # bad route
    with pytest.raises(ValidationError):
        tx.load_transcribe_sidecar(audio)


# --- conversions -----------------------------------------------------------


def test_steps_to_note_events() -> None:
    events = tx._steps_to_note_events([(0, 16, 57)])
    assert len(events) == 1
    e = events[0]
    assert (e.note, e.velocity, e.start_tick, e.duration_ticks) == (57, 96, 0, 16 * 120 - 10)


def test_onset_velocity() -> None:
    env = np.array([0.0, 1.0, 0.5])
    assert tx._onset_velocity(env, 1) == 120  # full strength -> 40 + 80
    assert tx._onset_velocity(env, 2) == 80   # half strength -> 40 + 40
    assert tx._onset_velocity(np.array([]), 0) == 100  # no envelope -> default


# --- drum dispatch (librosa monkeypatched) --------------------------------


def test_transcribe_drum(tmp_path, monkeypatch) -> None:
    import librosa

    monkeypatch.setattr(librosa, "load", lambda *a, **k: (np.zeros(22050, np.float32), 22050))
    monkeypatch.setattr(librosa.onset, "onset_strength", lambda **k: np.array([0.0, 1.0, 0.5, 0.0]))
    monkeypatch.setattr(librosa.onset, "onset_detect", lambda **k: np.array([1, 2]))
    monkeypatch.setattr(librosa, "frames_to_time", lambda frames, **k: np.array([0.5, 1.0]))

    st = tx.transcribe_drum("kick", tmp_path / "kick.wav", tmp_path, "T", GRID)
    assert st.is_drum and st.route == ROUTE_DRUM
    assert [e.note for e in st.notes] == [36, 36]      # GM kick
    assert all(e.channel == 9 for e in st.notes)        # drum channel
    assert st.notes[0].start_tick == 480                # 0.5s @120bpm = 480 ticks
    assert st.midi_path.is_file()
    assert st.stats == {"onset_count": 2, "gm_note": 36}


# --- multi-track assembler -------------------------------------------------


def test_assemble_multitrack_channels(tmp_path) -> None:
    poly1 = StemTranscription("synth", ROUTE_POLY, tmp_path / "s.mid", None,
                              [TranscribedNote(0.0, 0.5, 60, 100, 0.9)], is_drum=False)
    poly2 = StemTranscription("keys", ROUTE_POLY, tmp_path / "k.mid", None,
                              [TranscribedNote(0.0, 0.5, 64, 100, 0.9)], is_drum=False)
    drum = StemTranscription("kick", ROUTE_DRUM, tmp_path / "d.mid", None,
                             [NoteEvent(9, 36, 100, 0, 120), NoteEvent(9, 36, 100, 240, 120)], is_drum=True)
    out = tmp_path / "combined.mid"
    tx.assemble_multitrack([poly1, poly2, drum], out, 120.0)

    mid = mido.MidiFile(str(out))
    assert len(mid.tracks) == 3
    names = [next((m.name for m in t if m.type == "track_name"), None) for t in mid.tracks]
    assert names == ["synth", "keys", "kick"]

    def first_channel(track):
        return next(m.channel for m in track if m.type == "note_on")

    assert first_channel(mid.tracks[2]) == 9             # drum forced to ch 9
    assert first_channel(mid.tracks[0]) != 9 and first_channel(mid.tracks[1]) != 9
    assert first_channel(mid.tracks[0]) != first_channel(mid.tracks[1])  # rotating, distinct
    tempo_counts = [sum(1 for m in t if m.type == "set_tempo") for t in mid.tracks]
    assert tempo_counts == [1, 0, 0]                     # tempo on first track only


def test_assemble_poly_pitch_bends(tmp_path) -> None:
    # non-overlapping notes keep their bends -> pitchwheel present
    n1 = TranscribedNote(0.0, 0.25, 60, 100, 0.9, pitch_bends=(0, 1, 2))
    n2 = TranscribedNote(0.5, 0.75, 62, 100, 0.9, pitch_bends=(0, -1))
    keep = StemTranscription("synth", ROUTE_POLY, tmp_path / "a.mid", None, [n1, n2], is_drum=False)
    out = tmp_path / "keep.mid"
    tx.assemble_multitrack([keep], out, 120.0)
    assert any(m.type == "pitchwheel" for m in mido.MidiFile(str(out)).tracks[0])

    # time-overlapping notes drop their bends (single channel can't carry both)
    o1 = TranscribedNote(0.0, 0.5, 60, 100, 0.9, pitch_bends=(0, 1))
    o2 = TranscribedNote(0.25, 0.75, 62, 100, 0.9, pitch_bends=(0, 1))
    drop = StemTranscription("synth", ROUTE_POLY, tmp_path / "b.mid", None, [o1, o2], is_drum=False)
    out2 = tmp_path / "drop.mid"
    tx.assemble_multitrack([drop], out2, 120.0)
    assert not any(m.type == "pitchwheel" for m in mido.MidiFile(str(out2)).tracks[0])


# --- pass integration (dispatchers monkeypatched) -------------------------


def _build_layer_dir(tmp_path, stems=("synth", "bass", "kick")):
    layer_dir = tmp_path / "stems" / "T"
    layer_dir.mkdir(parents=True)
    for stem in stems:
        sf.write(layer_dir / f"{stem}.wav", np.zeros((100, 2), np.float32), 44100)
    manifest = {"stems": [{"layer": s, "kept": True} for s in stems] + [{"layer": "oboe", "kept": False}]}
    (layer_dir / "manifest.yml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return layer_dir


def _patch_dispatchers(monkeypatch):
    from setloom.transcription import basic_pitch as bp

    # Routing/cache tests must not load local CoreML weights or require that group.
    monkeypatch.setattr(bp, "BasicPitchModel", lambda *_a, **_k: object())

    def fake(route, is_drum, notes):
        def _f(stem, wav, out_dir, track, grid, **kwargs):
            path = out_dir / f"{track}.{stem}.mid"
            path.write_bytes(b"")
            return StemTranscription(stem, route, path, None, list(notes), is_drum=is_drum, stats={})
        return _f

    monkeypatch.setattr(tx, "transcribe_poly", fake("poly", False, [TranscribedNote(0.0, 0.5, 60, 100, 0.9)]))
    monkeypatch.setattr(tx, "transcribe_mono", fake("mono", False, [NoteEvent(0, 40, 96, 0, 110)]))
    monkeypatch.setattr(tx, "transcribe_drum", fake("drum", True, [NoteEvent(9, 36, 100, 0, 120)]))


def test_transcribe_pass_writes_and_caches(tmp_path, monkeypatch) -> None:
    layer_dir = _build_layer_dir(tmp_path)
    out_dir = tmp_path / "dossiers"
    out_dir.mkdir()
    audio = tmp_path / "T.mp3"
    audio.touch()
    _patch_dispatchers(monkeypatch)

    status = tx.transcribe_pass(audio, "T", layer_dir, GRID, out_dir)
    assert status == ["transcribe:analyzed"]
    assert (out_dir / "T.combined.mid").is_file()
    for stem in ("synth", "bass", "kick"):
        assert (out_dir / f"T.{stem}.mid").is_file()
    dossier = yaml.safe_load((out_dir / "T.transcribe.yml").read_text(encoding="utf-8"))
    routes = {s["stem"]: s["route"] for s in dossier["stems"]}
    assert routes == {"synth": "poly", "bass": "mono", "kick": "drum"}

    # second run is cached, no rewrite
    before = (out_dir / "T.combined.mid").stat().st_mtime
    assert tx.transcribe_pass(audio, "T", layer_dir, GRID, out_dir) == ["transcribe:cached"]
    assert (out_dir / "T.combined.mid").stat().st_mtime == before


def test_transcribe_pass_sidecar_and_cli_precedence(tmp_path, monkeypatch) -> None:
    layer_dir = _build_layer_dir(tmp_path)
    out_dir = tmp_path / "dossiers"
    out_dir.mkdir()
    audio = tmp_path / "T.mp3"
    audio.touch()
    (tmp_path / "T.transcribe.yml").write_text("transcribe:\n  bass: poly\n", encoding="utf-8")
    _patch_dispatchers(monkeypatch)

    # sidecar alone: bass -> poly
    tx.transcribe_pass(audio, "T", layer_dir, GRID, out_dir)
    dossier = yaml.safe_load((out_dir / "T.transcribe.yml").read_text(encoding="utf-8"))
    bass = next(s for s in dossier["stems"] if s["stem"] == "bass")
    assert bass["route"] == "poly" and bass["source"] == "sidecar"

    # Changing the route must take effect without manually deleting cached files.
    tx.transcribe_pass(audio, "T", layer_dir, GRID, out_dir, cli_overrides={"bass": "mono"})
    dossier = yaml.safe_load((out_dir / "T.transcribe.yml").read_text(encoding="utf-8"))
    bass = next(s for s in dossier["stems"] if s["stem"] == "bass")
    assert bass["route"] == "mono" and bass["source"] == "cli"


@pytest.mark.parametrize("change", ["stem", "missing_midi", "events", "grid", "model_root"])
def test_transcribe_cache_rebuilds_changed_or_incomplete_outputs(tmp_path, monkeypatch, change) -> None:
    layer_dir = _build_layer_dir(tmp_path)
    out_dir = tmp_path / "dossiers"
    audio = tmp_path / "T.mp3"
    audio.touch()
    _patch_dispatchers(monkeypatch)
    tx.transcribe_pass(audio, "T", layer_dir, GRID, out_dir)

    grid, options = GRID, {}
    if change == "stem":
        (layer_dir / "bass.wav").write_bytes(b"changed source")
    elif change == "missing_midi":
        (out_dir / "T.bass.mid").unlink()
    elif change == "events":
        options["emit_events"] = True
    elif change == "grid":
        grid = Grid(bpm=128.0, t0=0.1, n_bars=2)
    else:
        options["bp_model_root"] = tmp_path / "another-model"

    assert tx.transcribe_pass(audio, "T", layer_dir, grid, out_dir, **options) == [
        "transcribe:analyzed"
    ]
    assert (out_dir / "T.bass.mid").is_file()


def test_transcribe_pass_skip_route(tmp_path, monkeypatch) -> None:
    layer_dir = _build_layer_dir(tmp_path)
    out_dir = tmp_path / "dossiers"
    out_dir.mkdir()
    audio = tmp_path / "T.mp3"
    audio.touch()
    _patch_dispatchers(monkeypatch)

    tx.transcribe_pass(audio, "T", layer_dir, GRID, out_dir, cli_overrides={"synth": "skip"})
    dossier = yaml.safe_load((out_dir / "T.transcribe.yml").read_text(encoding="utf-8"))
    assert "synth" not in [s["stem"] for s in dossier["stems"]]


# --- mono FCPE helpers (moved here from the layer lens) --------------------


def _sine(freq, dur, sr, amp=0.3):
    t = np.arange(int(dur * sr)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_prep_melodic_strips_bassline_and_clamps() -> None:
    sr = 22050
    y = _sine(60, 2.0, sr, amp=0.9) + _sine(880, 2.0, sr, amp=0.9)  # sums past 1.0
    out = tx._prep_melodic(y, sr, "synth")
    assert np.max(np.abs(out)) <= 1.0
    spec = np.abs(np.fft.rfft(out)) ** 2
    freqs = np.fft.rfftfreq(len(out), 1 / sr)
    assert spec[freqs < 100].sum() / spec.sum() < 0.05          # synth bassline stripped
    keys = tx._prep_melodic(_sine(60, 1.0, sr), sr, "keys")     # non-synth: only normalized
    spec_k = np.abs(np.fft.rfft(keys)) ** 2
    assert spec_k[np.fft.rfftfreq(len(keys), 1 / sr) < 100].sum() / spec_k.sum() > 0.9


def test_f0_steps_quantizes_to_grid() -> None:
    from setloom.anatomy.analysis import segment_notes

    grid = Grid(bpm=120.0, t0=0.0, n_bars=1)  # 2 s bar, 16 steps of 0.125 s
    f0 = np.full(200, 220.0)  # constant A3 over 2 s
    steps = tx._f0_steps(f0, 2.0, grid)
    assert (steps == 57).all()
    assert segment_notes(steps) == [(0, 16, 57)]


def test_poly_loads_basic_pitch_model_once(tmp_path, monkeypatch) -> None:
    from setloom.transcription import basic_pitch as bp
    from setloom.transcription.basic_pitch import TranscriptionResult

    layer_dir = _build_layer_dir(tmp_path, stems=("synth", "keys", "kick"))
    out_dir = tmp_path / "dossiers"
    out_dir.mkdir()
    audio = tmp_path / "T.mp3"
    audio.touch()

    loads = {"n": 0}

    class _FakeModel:
        def __init__(self, *a, **k):
            loads["n"] += 1

    seen = []

    def fake_transcribe(request, *, model=None):
        seen.append(model)
        Path(request.out_midi).write_bytes(b"")
        return TranscriptionResult(midi_path=Path(request.out_midi), events_path=None, notes=())

    monkeypatch.setattr(bp, "BasicPitchModel", _FakeModel)
    monkeypatch.setattr(bp, "default_model_path", lambda root: tmp_path / "model")
    monkeypatch.setattr(bp, "transcribe_audio", fake_transcribe)

    # synth + keys are poly; skip the drum stem so only the poly path runs
    tx.transcribe_pass(audio, "T", layer_dir, GRID, out_dir, cli_overrides={"kick": "skip"})
    assert loads["n"] == 1                          # CoreML model loaded exactly once
    assert len(seen) == 2 and all(m is not None for m in seen)
    assert len({id(m) for m in seen}) == 1          # the same instance reused
