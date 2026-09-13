# SPDX-License-Identifier: AGPL-3.0-only
"""Audio fidelity, random access and filesystem allocation at the shared writer."""

import os

import numpy as np
import pytest
import soundfile as sf

from setloom.audio import write_audio


@pytest.mark.parametrize("subtype", ["FLOAT", "PCM_24", "PCM_16"])
def test_sparse_wav_preserves_encoding_and_seek_boundaries(tmp_path, subtype):
    audio = np.zeros((300003, 2), dtype=np.float32)
    audio[90000:91000] = [0.1234567, -0.4321098]
    # No threshold may remove weak values or change floating headroom/signed zero.
    audio[95000] = [1.25, -1.5]
    audio[96000] = [1e-30, -1e-40]
    audio[97000] = [-0.0, 0.0]
    expected = tmp_path / "native.wav"
    actual = tmp_path / "nested" / "shared.wav"
    sf.write(expected, audio, 44100, subtype=subtype)
    write_audio(actual, audio, subtype=subtype)
    info = sf.info(actual)
    assert (info.frames, info.channels, info.samplerate, info.subtype) == (
        len(audio),
        2,
        44100,
        subtype,
    )
    for start in [0, 89990, 95000, 96000, 97000, 299995]:
        a, _ = sf.read(expected, start=start, frames=100, dtype="float32", always_2d=True)
        b, _ = sf.read(actual, start=start, frames=100, dtype="float32", always_2d=True)
        np.testing.assert_array_equal(a.view(np.uint32), b.view(np.uint32))
    # Compare every encoded sample, independent of optional header timestamps.
    a, _ = sf.read(expected, dtype="float32", always_2d=True)
    b, _ = sf.read(actual, dtype="float32", always_2d=True)
    np.testing.assert_array_equal(a.view(np.uint32), b.view(np.uint32))


@pytest.mark.parametrize("frames", [0, 1, 17003, 300003])
@pytest.mark.parametrize("subtype", ["FLOAT", "PCM_24"])
def test_silent_and_empty_mono_wav_preserve_length(tmp_path, frames, subtype):
    path = tmp_path / "mono.wav"
    write_audio(path, np.zeros(frames, np.float32), sample_rate=8000, subtype=subtype)
    audio, sr = sf.read(path, dtype="float32")
    assert sr == 8000 and audio.shape == (frames,)
    assert not np.any(audio.view(np.uint32))


def test_overwriting_existing_audio_removes_old_tail(tmp_path):
    path = tmp_path / "replace.wav"
    sf.write(path, np.ones((400003, 2), np.float32), 44100, subtype="FLOAT")
    write_audio(path, np.zeros((300003, 2), np.float32), subtype="FLOAT")
    audio, _ = sf.read(path, dtype="float32", always_2d=True)
    assert audio.shape == (300003, 2)
    assert not np.any(audio.view(np.uint32))


def test_dense_audio_keeps_native_writer_and_precision_default(tmp_path, monkeypatch):
    import setloom.audio as module

    def unexpected_sparse_path(*args):
        raise AssertionError("Dense audio should retain the native writer")

    monkeypatch.setattr(module, "_SparseWavIO", unexpected_sparse_path)
    audio = np.full((100000, 2), 1e-6, np.float32)
    path = tmp_path / "dense.wav"
    write_audio(path, audio)
    assert sf.info(path).subtype == "PCM_24"


def test_existing_non_wav_output_remains_supported(tmp_path):
    path = tmp_path / "delivery.flac"
    write_audio(path, np.zeros((17003, 2), np.float32))
    info = sf.info(path)
    assert (info.format, info.subtype, info.frames) == ("FLAC", "PCM_24", 17003)


def test_large_silent_regions_reduce_disk_allocation_when_supported(tmp_path):
    # Some filesystems allocate small gaps eagerly. Probe a long gap first;
    # content/seek tests above remain unconditional on every filesystem.
    probe = tmp_path / "filesystem-probe"
    with probe.open("wb") as file:
        file.write(b"a")
        file.seek(64 * 1024 * 1024)
        file.write(b"b")
        file.flush()
        os.fsync(file.fileno())
    stat = probe.stat()
    if not hasattr(stat, "st_blocks") or stat.st_blocks * 512 > stat.st_size // 2:
        pytest.skip("filesystem does not expose useful sparse allocation")
    audio = np.zeros((9000000, 2), np.float32)
    audio[4200000:4300000] = 0.1
    path = tmp_path / "sparse.wav"
    write_audio(path, audio, subtype="FLOAT")
    stat = path.stat()
    assert stat.st_blocks * 512 < stat.st_size // 4
    assert sf.info(path).frames == len(audio)
