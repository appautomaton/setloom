# SPDX-License-Identifier: AGPL-3.0-only

import numpy as np

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
