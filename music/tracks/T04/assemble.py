# SPDX-License-Identifier: AGPL-3.0-only
"""T04 'Nova Flamma' assembly recipe: stems + genai pads + voice lead -> full mix.

Reproducible render: engine stems from seed-4103/variant-01, two Magenta pad
beds (audio-steered, chroma-gated), and the locked voice lead placed per the
vocal brief budget (19 vocal-active bars). The voice asset stays dry on disk;
every placement gets its own spatial treatment here, at mix time.

Run from the repo root:

    uv run --no-sync python music/tracks/T04/assemble.py

Inputs (gitignored, regenerable from spec/seed/recipe):
    local/candidates/T04/seed-4103/variant-01/stem-*.wav   (scrender)
    local/candidates/genai/t04-pad-{main,break}.wav         (Magenta RT 2)
    local/candidates/genai/latin-vocal-clean-take6-tailfix.wav (locked lead)

Output:
    local/candidates/T04/mix/nova-flamma-v1.wav      (mix, peak-normalized)
    local/candidates/T04/mix/nova-flamma-final.wav   (club master)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

ROOT = Path(__file__).resolve().parents[3]
V = ROOT / "local/candidates/T04/seed-4103/variant-01"
GENAI = ROOT / "local/candidates/genai"
VOICE = GENAI / "latin-vocal-clean-take6-tailfix.wav"
OUT_DIR = ROOT / "local/candidates/T04/mix"
PIECES = ROOT / "local/candidates/T04/voice/pieces"

SR = 44100
BPM = 123.0
BAR_S = 4 * 60 / BPM  # 1.9512s
TOTAL_BARS = 132

# scrender's internal lead bus is deliberately excluded: the voice is THE lead.
STEM_GAINS = {
    "kick": 1.00,
    "bass": 0.50,
    "perc": 3.00,
    "chords": 1.30,
    "arp": 0.70,
    "pad": 0.45,  # engine pad: conductor-harmony glue, all sections
    "fx": 1.00,
}

# Genai pad spans: (start_bar, end_bar, asset, gain). Intro/outro carry only
# the engine pad so the edges stay mixable.
PAD_SPANS = [
    (8, 24, "t04-pad-main", 0.35),   # groove_a
    (24, 32, "t04-pad-break", 0.60), # break_1
    (32, 72, "t04-pad-main", 0.45),  # drop_1 + groove_b
    (72, 88, "t04-pad-break", 0.60), # break_2 (verse bed)
    (88, 120, "t04-pad-main", 0.45), # peak
]
PAD_HPF_HZ = 160.0  # low-end safety: sub belongs to kick/bass only
PAD_XFADE_BARS = 2
PAD_EDGE_FADE_BARS = 1.0

# Voice pieces: name -> (trim_start, trim_len, sox treatment chain).
# Onsets from RMS phrase analysis; 0.15s pre-roll keeps the consonant attack.
# Treatments reuse the chains proven on this voice at the tail-fix gate.
BODY_EQ = ["equalizer", "280", "1q", "+3", "equalizer", "4000", "1q", "+1.5"]
PIECE_DEFS = {
    "tease":  (4.52, 4.60, ["highpass", "300", "lowpass", "5000", "pad", "0", "3",
                            "reverb", "-w", "85", "70", "100", "gain", "-9"]),
    "verse1": (4.52, 4.60, [*BODY_EQ, "pad", "0", "2", "reverb", "30", "40", "100", "10", "gain", "-1.5"]),
    "verse2": (11.00, 6.62, [*BODY_EQ, "pad", "0", "2", "reverb", "30", "40", "100", "10", "gain", "-1.5"]),
    "verse3": (18.73, 3.70, [*BODY_EQ, "pad", "0", "2", "reverb", "30", "40", "100", "10", "gain", "-1.5"]),
    "chop":   (18.73, 1.10, ["highpass", "350", "pad", "0", "3",
                             "echo", "0.7", "0.6", "366", "0.5", "732", "0.3", "gain", "-3"]),
    "hook1":  (23.19, 3.26, [*BODY_EQ, "pad", "0", "3",
                             "echo", "0.8", "0.5", "366", "0.35", "732", "0.18",
                             "reverb", "55", "40", "100", "20"]),
    "hook2":  (27.13, 7.37, [*BODY_EQ, "pad", "0", "3",
                             "echo", "0.8", "0.5", "366", "0.35", "732", "0.18",
                             "reverb", "55", "40", "100", "20"]),
}

# Placements: (piece, bar, gain). Budget per vocal-brief: break_1 tease 2 /
# drop_1 accents 3 / break_2 verse 8 / peak hook 6 vocal-active bars.
PLACEMENTS = [
    ("tease", 28.0, 1.20),
    ("chop", 40.0, 3.20),
    ("chop", 48.0, 3.20),
    ("chop", 56.0, 3.20),
    ("verse1", 76.0, 0.70),
    ("verse2", 79.0, 0.70),
    ("verse3", 83.0, 0.70),
    ("hook1", 96.0, 2.20),
    ("hook2", 98.0, 2.20),
    ("hook1", 104.0, 2.20),
    ("hook2", 106.0, 2.20),
]
VOICE_PRE_ROLL_S = 0.15  # sung onset lands on the bar tick

# Mix automation: every vocal placement opens a window — the harmonic lanes
# ride down while kick/bass keep the groove. Depth/length per piece kind.
DUCK_LANES = ("chords", "arp", "pad")
DUCK_BY_PIECE = {  # piece -> (depth dB, window bars)
    "chop": (-2.5, 1.5),
    "verse1": (-3.5, 2.4), "verse2": (-3.5, 3.4), "verse3": (-3.5, 2.0),
    "hook1": (-3.5, 1.7), "hook2": (-3.5, 4.0),
}


def bar_to_sample(bar: float) -> int:
    return int(round(bar * BAR_S * SR))


def load_stereo(path: Path) -> np.ndarray:
    y, sr = sf.read(path, always_2d=True)
    assert sr == SR, f"{path}: {sr} != {SR}"
    if y.shape[1] == 1:
        y = np.repeat(y, 2, axis=1)
    return y.astype(np.float64)


def highpass(y: np.ndarray, hz: float) -> np.ndarray:
    sos = butter(4, hz, btype="highpass", fs=SR, output="sos")
    return sosfiltfilt(sos, y, axis=0)


def crossfade_loop(src: np.ndarray, length: int, offset: int) -> np.ndarray:
    """Tile ``src`` to ``length`` samples with equal-power crossfades."""
    xf = bar_to_sample(PAD_XFADE_BARS)
    src = np.roll(src, -offset, axis=0)
    hop = len(src) - xf
    out = np.zeros((length + len(src), 2))
    t = np.linspace(0, np.pi / 2, xf)[:, None]
    fade_in, fade_out = np.sin(t), np.cos(t)
    pos = 0
    while pos < length:
        piece = src.copy()
        if pos > 0:
            piece[:xf] *= fade_in  # incoming head fades in over the outgoing tail
        piece[-xf:] *= fade_out
        out[pos : pos + len(piece)] += piece
        pos += hop
    return out[:length]


def edge_fades(y: np.ndarray, fade_bars: float) -> np.ndarray:
    n = bar_to_sample(fade_bars)
    env = np.ones(len(y))
    env[:n] = np.linspace(0, 1, n)
    env[-n:] = np.linspace(1, 0, n)
    return y * env[:, None]


def cut_voice_pieces() -> None:
    PIECES.mkdir(parents=True, exist_ok=True)
    for name, (start, length, chain) in PIECE_DEFS.items():
        out = PIECES / f"{name}.wav"
        cmd = ["sox", str(VOICE), str(out), "trim", f"{start}", f"{length}",
               "fade", "t", "0.03", "0", "0.06", *chain]
        subprocess.run(cmd, check=True, capture_output=True, text=True)


def duck_envelope(length: int) -> np.ndarray:
    """Gain envelope dipping under each vocal placement window."""
    env = np.ones(length)
    edge = bar_to_sample(0.5)
    for piece, bar, _gain in PLACEMENTS:
        if piece not in DUCK_BY_PIECE:
            continue
        depth_db, bars = DUCK_BY_PIECE[piece]
        dip = 10 ** (depth_db / 20)
        s0 = bar_to_sample(bar) - int(VOICE_PRE_ROLL_S * SR)
        s1 = s0 + bar_to_sample(bars)
        env[s0:s1] = np.minimum(env[s0:s1], dip)
        env[s0 - edge : s0] = np.minimum(env[s0 - edge : s0], np.linspace(1, dip, edge))
        env[s1 : s1 + edge] = np.minimum(env[s1 : s1 + edge], np.linspace(dip, 1, edge))
    return env


def main() -> int:
    total = bar_to_sample(TOTAL_BARS)
    cut_voice_pieces()

    stems = {name: load_stereo(V / f"stem-{name}.wav") for name in STEM_GAINS}
    length = max(total, *(len(y) for y in stems.values()))
    duck = duck_envelope(length)
    mix = np.zeros((length, 2))
    for name, gain in STEM_GAINS.items():
        y = stems[name]
        lane = y * gain
        if name in DUCK_LANES:
            lane *= duck[: len(lane), None]
        mix[: len(lane)] += lane

    pads = {name: load_stereo(GENAI / f"{name}.wav") for name in
            {span[2] for span in PAD_SPANS}}
    for i, (b0, b1, asset, gain) in enumerate(PAD_SPANS):
        s0, s1 = bar_to_sample(b0), bar_to_sample(b1)
        bed = crossfade_loop(pads[asset], s1 - s0, offset=i * 7 * SR % len(pads[asset]))
        bed = highpass(bed, PAD_HPF_HZ)
        bed = edge_fades(bed, PAD_EDGE_FADE_BARS)
        bed *= duck[s0:s1, None]
        mix[s0:s1] += bed * gain

    for piece, bar, gain in PLACEMENTS:
        y = load_stereo(PIECES / f"{piece}.wav")
        start = bar_to_sample(bar) - int(VOICE_PRE_ROLL_S * SR)
        end = min(start + len(y), length)
        mix[start:end] += y[: end - start] * gain

    peak = np.abs(mix).max()
    mix *= 10 ** (-1.0 / 20) / peak  # normalize to -1 dBFS true peak (approx)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "nova-flamma-v1.wav"
    sf.write(out, mix, SR, subtype="PCM_24")
    print(f"peak pre-norm {20 * np.log10(peak):.1f} dBFS -> wrote {out}")
    master(out)
    return 0


# Club master: glue compression, then a 4x-oversampled limiter. Drive is kept
# moderate on purpose: the corpus-loud version (level_in 15.5dB, -8.9 LUFS)
# flattened section contrast to 1 dB and buried the voice — taste-owner
# rejected. Contrast preserved beats loudness matched.
# alimiter's auto-`level` must stay disabled or it re-normalizes to 0 dBFS.
MASTER_CHAIN = (
    "acompressor=threshold=-18dB:ratio=2:attack=20:release=250:makeup=4dB,"
    "aresample=176400,"
    "alimiter=level_in=8dB:limit=0.871:attack=5:release=100:level=disabled,"
    "aresample=44100"
)


def master(mix_path: Path) -> None:
    out = mix_path.parent / "nova-flamma-final.wav"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mix_path),
         "-af", MASTER_CHAIN, "-c:a", "pcm_s24le", str(out)],
        check=True,
    )
    print(f"mastered -> {out}")


if __name__ == "__main__":
    raise SystemExit(main())
