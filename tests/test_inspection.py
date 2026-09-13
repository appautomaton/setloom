# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import setloom.inspection as inspection
from setloom.audio import write_audio
from setloom.cli import main


def test_cli_inspect_writes_wave_plot(tmp_path) -> None:
    sr = 44_100
    t = np.arange(sr // 20, dtype=np.float32) / sr
    tone = 0.1 * np.sin(2 * np.pi * 440 * t)
    wav_path = tmp_path / "tone.wav"
    out_path = tmp_path / "tone-wave.png"

    write_audio(wav_path, np.column_stack([tone, tone]), sample_rate=sr)

    rc = main([
        "inspect",
        str(wav_path),
        "--view",
        "wave",
        "--out",
        str(out_path),
        "--end",
        "0.05",
    ])

    assert rc == 0
    assert out_path.is_file()
    assert out_path.stat().st_size > 0


@pytest.mark.parametrize("view,compare", [("wave", False), ("wave", True),
                                        ("rhythm", False), ("rhythm", True)])
def test_default_inspection_output_preserves_reference_directory(tmp_path, monkeypatch, view, compare):
    monkeypatch.chdir(tmp_path)
    source_dir = tmp_path / "local/corpus/audio"
    source_dir.mkdir(parents=True)
    source = source_dir / "reference.wav"
    sf.write(source, np.zeros((2048, 2)), 8000)
    output = inspection.render_audio_inspection(
        source, view=view, compare=source if compare else None,
    )
    assert output.is_relative_to(Path("tmp/inspection"))
    assert output.is_file()
    assert list(source_dir.iterdir()) == [source]


@pytest.mark.parametrize("length", [4096, 8192, 16384])
def test_bin_centered_tone_level_is_independent_of_window_length(length) -> None:
    sr = 8192
    tone = 0.1 * np.sin(2 * np.pi * 512 * np.arange(length) / sr)
    freqs, db = inspection.spectrum_db(tone, sr, 2000)
    assert freqs[np.argmax(db)] == 512
    assert np.max(db) == pytest.approx(-20.0, abs=1e-5)
    freqs, times, db = inspection.spectrogram_db(tone, sr, 2000)
    assert times[0] == 1024 / sr  # frame center, not the frame's left edge
    assert freqs[np.argmax(db[:, 0])] == 512
    assert db.max() == pytest.approx(-20.0, abs=1e-5)


def test_comparison_reads_only_selected_frames(tmp_path, monkeypatch) -> None:
    sr = 8000
    paths = [tmp_path / "a.wav", tmp_path / "b.wav"]
    for path in paths:
        sf.write(path, np.zeros((2 * sr, 2)), sr)
    original = sf.read
    reads = []

    def record_read(path, **kwargs):
        reads.append((kwargs["start"], kwargs["stop"]))
        return original(path, **kwargs)

    monkeypatch.setattr(inspection.sf, "read", record_read)
    inspection.render_audio_inspection(
        paths[0], compare=paths[1], view="wave", start=0.5, end=0.75,
        out=tmp_path / "nested" / "wave.png",
    )
    assert reads == [(4000, 6000), (4000, 6000)]
    assert (tmp_path / "nested" / "wave.png").is_file()


@pytest.mark.parametrize("layout", [None, "stack", "diff"])
def test_short_spectrogram_supports_pitch_labels_and_silence(tmp_path, layout) -> None:
    sr = 44100
    path = tmp_path / "silence.wav"
    sf.write(path, np.zeros((sr // 100, 2)), sr)
    args = [
        "inspect", str(path), "--view", "spectrogram", "--pitch-labels",
        "--fft-size", "8192", "--hop-size", "256", "--min-freq", "100",
        "--max-freq", "4000", "--out", str(tmp_path / "short.png"),
    ]
    if layout is not None:
        args += ["--compare", str(path), "--compare-layout", layout]
    assert main(args) == 0
    assert (tmp_path / "short.png").is_file()


def test_spectrogram_mesh_uses_frame_and_frequency_centers() -> None:
    inspection.load_plotting_backend()
    fig, (wave_ax, ax) = inspection.make_figure(2, 1200, 1400, 100)
    try:
        inspection.draw_spectrogram(
            ax, np.array([400.0, 440.0, 480.0]), np.array([0.05, 0.10]),
            np.zeros((3, 2)), 10.0, -40, 0, pitch_labels=True,
        )
        coords = ax.collections[0].get_coordinates()
        np.testing.assert_allclose(coords[0, :, 0], [10.025, 10.075, 10.125])
        np.testing.assert_allclose(coords[:, 0, 1], [380, 420, 460, 500])
        labels = dict(zip(ax.get_yticks(), [tick.get_text() for tick in ax.get_yticklabels()]))
        assert labels[440.0] == "A4"
        for panel in (wave_ax, ax):
            panel.set_xlim(10, 11)
        fig.canvas.draw()
        assert wave_ax.transData.transform((10.5, 0))[0] == pytest.approx(
            ax.transData.transform((10.5, 440))[0]
        )
    finally:
        inspection.plt.close(fig)


@pytest.mark.parametrize("start,end", [(1, 0.5), (2, 3), (0, float("nan"))])
def test_invalid_windows_fail_before_loading_pcm(tmp_path, monkeypatch, start, end) -> None:
    path = tmp_path / "silence.wav"
    sf.write(path, np.zeros(8000), 8000)

    def unexpected_read(*args, **kwargs):
        pytest.fail("invalid window should not load PCM")

    monkeypatch.setattr(inspection.sf, "read", unexpected_read)
    with pytest.raises(SystemExit, match="window"):
        inspection.render_audio_inspection(path, start=start, end=end)


def test_grid_origin_applies_to_bar_windows_and_drawn_subdivisions():
    args = inspection.parse_args([
        "input.wav", "--bpm", "150", "--grid-origin", "0.234",
        "--bar-start", "1", "--bar-end", "2",
    ])
    assert inspection.window_seconds(args, 10) == pytest.approx((1.834, 3.434))
    inspection.load_plotting_backend()
    fig, (ax,) = inspection.make_figure(1, 1200, 700, 100)
    try:
        inspection.add_time_grid(ax, 0.2, 0.55, 150, "subdivisions", 0.234, 4)
        positions = [line.get_xdata()[0] for line in ax.lines]
        assert positions == pytest.approx([0.234, 0.334, 0.434, 0.534])
        ax.clear()
        inspection.add_time_grid(ax, 0, 1, None, "bars")
        assert not ax.lines  # No invented tempo when bpm is unspecified.
    finally:
        inspection.plt.close(fig)


def test_bar_window_requires_tempo_and_input_cannot_be_overwritten(tmp_path):
    path = tmp_path / "audio.wav"
    sf.write(path, np.zeros(8000), 8000)
    before = path.read_bytes()
    with pytest.raises(SystemExit, match="explicit --bpm"):
        main(["inspect", str(path), "--bar-end", "1"])
    with pytest.raises(SystemExit, match="input paths"):
        main(["inspect", str(path), "--out", str(path)])
    assert path.read_bytes() == before
