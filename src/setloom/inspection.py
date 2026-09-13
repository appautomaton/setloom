# SPDX-License-Identifier: AGPL-3.0-only
"""Generate high-contrast audio inspection plots.

Most Setloom renders are stereo files with two real channels: left and right.
Single-lane views such as waveform, spectrogram, and spectrum inspect one
analysis signal derived from those channels:

- channel: one real channel selected by --channel; this preserves old behavior.
- left/right: explicit real stereo channels.
- mid: (left + right) / 2, useful for centered kick/bass/body inspection.
- side: (left - right) / 2, useful for width/space inspection.
- mono: arithmetic average across all file channels, useful for fold-down checks.

These analysis signals are not extra channels stored in the WAV file.

Spectrogram comparison deliberately does not support heatmap overlay: two
overlaid heatmaps create ambiguous colors. Use side/stack for aligned reading
or diff for direct contrast. In diff mode, orange means B has more energy and
blue means A has more energy.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Literal

import numpy as np
import soundfile as sf
from scipy import signal

from setloom.rhythm import FrequencyBand, analyze_rhythm, grid_positions

BG = "#05070a"
PANEL = "#0b0f14"
FG = "#e8eee8"
MUTED = "#9fb0aa"
GRID = "#b8872f"
WAVE = "#b174ff"
WAVE_R = "#41d6c3"
LINE = "#ffd36b"
DIFF = "#ff6b8a"
CMAP = "inferno"
plt: Any = None
ticker: Any = None
DIFF_CMAP: Any = None
DEFAULT_WIDTH_PX = 2400
DEFAULT_HEIGHT_BY_ROWS = {1: 920, 2: 1600, 3: 2200, 4: 3000}
TITLE_SIZE = 24
PANEL_TITLE_SIZE = 20
LABEL_SIZE = 19
TICK_SIZE = 17
LEGEND_SIZE = 15

CompareLayout = Literal["overlay", "stack", "side", "diff"]
GridMode = Literal["off", "beats", "bars", "subdivisions"]
InspectionSignal = Literal["channel", "left", "right", "mid", "side", "mono"]
InspectionView = Literal["both", "wave", "spectrogram", "spectrum", "stereo", "all", "rhythm"]


@dataclass(frozen=True)
class AudioInspectionRequest:
    """Self-contained request for rendering one Setloom audio inspection plot."""

    audio: str | Path
    out: str | Path | None = None
    compare: str | Path | None = None
    compare_label_a: str = "A"
    compare_label_b: str = "B"
    compare_layout: CompareLayout = "overlay"
    bpm: float | None = None
    channel: int = 0
    signal: InspectionSignal = "channel"
    start: float = 0.0
    end: float | None = None
    bar_start: float | None = None
    bar_end: float | None = None
    view: InspectionView = "both"
    grid: GridMode = "bars"
    grid_origin: float = 0.0
    subdivisions: int = 4
    band: tuple[FrequencyBand, ...] | None = None
    envelope_ms: float = 8.0
    envelope_hop_ms: float = 2.0
    peak_distance_ms: float = 30.0
    report: str | Path | None = None
    min_freq: float = 20.0
    max_freq: float = 12000.0
    fft_size: int = 2048
    hop_size: int = 512
    pitch_labels: bool = False
    dpi: int = 160
    width_px: int = DEFAULT_WIDTH_PX
    height_px: int | None = None

    def to_namespace(self) -> argparse.Namespace:
        values = {field.name: getattr(self, field.name) for field in fields(self)}
        return argparse.Namespace(**values)


def load_plotting_backend() -> None:
    global DIFF_CMAP, plt, ticker
    if plt is not None:
        return
    cache_root = Path("tmp") / "matplotlib"
    xdg_cache = Path("tmp") / "xdg-cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    xdg_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_root.resolve()))
    os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache.resolve()))

    import matplotlib

    matplotlib.use("Agg")

    import matplotlib.pyplot as mpl_pyplot
    import matplotlib.ticker as mpl_ticker
    from matplotlib.colors import LinearSegmentedColormap

    plt = mpl_pyplot
    ticker = mpl_ticker
    DIFF_CMAP = LinearSegmentedColormap.from_list(
        "setloom_diff", ["#2c5cff", "#101820", "#ffb84d"]
    )


def parse_band(value: str) -> FrequencyBand:
    try:
        name, low, high = value.split(":")
        return FrequencyBand(name, float(low), float(high))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("band must be NAME:LOW_HZ:HIGH_HZ") from exc


def configure_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("audio")
    parser.add_argument("--out", help="output image path (default: tmp/inspection/)")
    parser.add_argument("--compare", help="second audio file for A/B visual comparison")
    parser.add_argument("--compare-label-a", default="A")
    parser.add_argument("--compare-label-b", default="B")
    parser.add_argument(
        "--compare-layout",
        choices=["overlay", "stack", "side", "diff"],
        default="overlay",
        help="comparison layout; heatmap overlay is disallowed for spectrograms; use side, stack, or diff",
    )
    parser.add_argument("--bpm", type=float, help="known tempo for grid/bar coordinates; no tempo is assumed")
    parser.add_argument("--channel", type=int, default=0, help="real file channel index used when --signal channel")
    parser.add_argument(
        "--signal",
        choices=["channel", "left", "right", "mid", "side", "mono"],
        default="channel",
        help="analysis signal for waveform/spectrogram/spectrum; mid/side/mono are derived from L/R",
    )
    parser.add_argument("--start", type=float, default=0.0, help="window start in seconds")
    parser.add_argument("--end", type=float, help="window end in seconds")
    parser.add_argument("--bar-start", type=float, help="window start in zero-based 4/4 bars from grid-origin; requires bpm, overrides start")
    parser.add_argument("--bar-end", type=float, help="window end in zero-based 4/4 bars from grid-origin; requires bpm, overrides end")
    parser.add_argument(
        "--view",
        choices=["both", "wave", "spectrogram", "spectrum", "stereo", "all", "rhythm"],
        default="both",
        help="plot type",
    )
    parser.add_argument("--grid", choices=["off", "beats", "bars", "subdivisions"], default="bars")
    parser.add_argument("--grid-origin", type=float, default=0.0, help="absolute seconds of beat zero (default 0); does not move the audio")
    parser.add_argument("--subdivisions", type=int, default=4, help="divisions per quarter-note beat for subdivision grid/rhythm samples (default 4)")
    parser.add_argument("--band", action="append", type=parse_band, help="rhythm band NAME:LOW_HZ:HIGH_HZ; repeat to replace default observation bands")
    parser.add_argument("--envelope-ms", type=float, default=8.0, help="rhythm RMS window in ms (default 8)")
    parser.add_argument("--envelope-hop-ms", type=float, default=2.0, help="rhythm envelope sampling step in ms (default 2)")
    parser.add_argument("--peak-distance-ms", type=float, default=30.0, help="minimum spacing of rhythm envelope maxima in ms (default 30); not note decoding")
    parser.add_argument("--report", help="optional rhythm evidence JSON, including source timing and analysis settings")
    parser.add_argument("--min-freq", type=float, default=20.0)
    parser.add_argument("--max-freq", type=float, default=12000.0)
    parser.add_argument("--fft-size", type=int, default=2048, help="spectrogram window in samples; longer windows resolve pitch more finely but smear attacks")
    parser.add_argument("--hop-size", type=int, default=512, help="spectrogram step in samples; a smaller step does not improve the window's time resolution")
    parser.add_argument("--pitch-labels", action="store_true", help="label spectrogram frequencies as equal-tempered notes (A4=440 Hz); harmonics are not necessarily played notes")
    parser.add_argument("--dpi", type=int, default=160)
    parser.add_argument("--width-px", type=int, default=DEFAULT_WIDTH_PX, help="target output width in pixels")
    parser.add_argument("--height-px", type=int, help="target output height in pixels; defaults by view")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = configure_parser(argparse.ArgumentParser(description=__doc__))
    return parser.parse_args(argv)


def window_seconds(args: argparse.Namespace, duration_s: float) -> tuple[float, float]:
    if args.bpm is not None and (not np.isfinite(args.bpm) or args.bpm <= 0):
        raise SystemExit("--bpm must be finite and positive")
    if not np.isfinite(args.grid_origin):
        raise SystemExit("--grid-origin must be finite")
    if not isinstance(args.subdivisions, int) or args.subdivisions < 1:
        raise SystemExit("--subdivisions must be a positive integer")
    if (args.bar_start is not None or args.bar_end is not None) and args.bpm is None:
        raise SystemExit("bar windows require an explicit --bpm")
    start = args.start
    end = duration_s if args.end is None else args.end
    if args.bar_start is not None:
        start = args.grid_origin + args.bar_start * 4.0 * 60.0 / args.bpm
    if args.bar_end is not None:
        end = args.grid_origin + args.bar_end * 4.0 * 60.0 / args.bpm
    if not np.isfinite(start) or not np.isfinite(end):
        raise SystemExit("window bounds must be finite")
    start = max(0.0, min(float(start), duration_s))
    end = max(0.0, min(float(end), duration_s))
    if end <= start:
        raise SystemExit("selected window is empty; end must be after start")
    return start, end


def slice_audio(y: np.ndarray, sr: int, start_s: float, end_s: float) -> np.ndarray:
    i0 = int(round(start_s * sr))
    i1 = int(round(end_s * sr))
    return y[i0:i1]


def apply_style(ax: plt.Axes) -> None:
    ax.set_facecolor(PANEL)
    for spine in ax.spines.values():
        spine.set_color("#2b353a")
        spine.set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=TICK_SIZE, width=1.0, length=5)
    ax.xaxis.label.set_color(FG)
    ax.yaxis.label.set_color(FG)
    ax.title.set_color(FG)
    ax.xaxis.label.set_size(LABEL_SIZE)
    ax.yaxis.label.set_size(LABEL_SIZE)


def add_time_grid(
    ax: plt.Axes, start_s: float, end_s: float, bpm: float | None, mode: str,
    origin: float = 0, subdivisions: int = 4,
) -> None:
    if mode == "off" or bpm is None:
        return
    _, positions = grid_positions(
        start_s, end_s, bpm / 4 if mode == "bars" else bpm, origin=origin,
        subdivisions=subdivisions if mode == "subdivisions" else 1,
    )
    for t in positions:
        ax.axvline(t, color=GRID, lw=0.75 if mode == "bars" else 0.45,
                   alpha=0.42 if mode == "bars" else 0.24)


def make_figure(rows: int, width_px: int, height_px: int | None, dpi: int) -> tuple[plt.Figure, list[plt.Axes]]:
    width_px = max(1200, int(width_px))
    resolved_height_px = max(700, int(height_px or DEFAULT_HEIGHT_BY_ROWS[rows]))
    fig = plt.figure(
        figsize=(width_px / dpi, resolved_height_px / dpi),
        dpi=dpi,
        facecolor=BG,
        constrained_layout=False,
    )
    top = {1: 0.78, 2: 0.86, 3: 0.88, 4: 0.91}[rows]
    gs = fig.add_gridspec(rows, 1, hspace=0.34, top=top, bottom=0.08, left=0.085, right=0.92)
    axes = [fig.add_subplot(gs[i]) for i in range(rows)]
    for ax in axes:
        apply_style(ax)
    return fig, axes


def make_grid(
    rows: int,
    cols: int,
    width_px: int,
    height_px: int | None,
    dpi: int,
) -> tuple[plt.Figure, list[plt.Axes]]:
    width_px = max(1200, int(width_px))
    resolved_height_px = max(700, int(height_px or DEFAULT_HEIGHT_BY_ROWS.get(rows, 1320)))
    fig = plt.figure(
        figsize=(width_px / dpi, resolved_height_px / dpi),
        dpi=dpi,
        facecolor=BG,
        constrained_layout=False,
    )
    top = 0.78 if rows == 1 else 0.89
    gs = fig.add_gridspec(rows, cols, hspace=0.30, wspace=0.32, top=top, bottom=0.09, left=0.085, right=0.92)
    axes = [fig.add_subplot(gs[r, c]) for r in range(rows) for c in range(cols)]
    for ax in axes:
        apply_style(ax)
    return fig, axes


def plot_wave(ax: plt.Axes, x: np.ndarray, sr: int, start_s: float, channel_label: str, color: str = WAVE) -> None:
    ax._setloom_axis_kind = "time"
    t = start_s + np.arange(len(x)) / sr
    ax.plot(t, x, color=color, lw=0.42)
    ax.set_ylim(-1.0, 1.0)
    ax.set_ylabel(channel_label)


def spectrogram_db(
    x: np.ndarray, sr: int, max_freq: float, *, min_freq: float = 20.0,
    fft_size: int = 2048, hop_size: int = 512,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One-sided, window-normalized bin amplitude in dBFS (not PSD or LUFS)."""
    if fft_size < 4 or not 1 <= hop_size <= fft_size:
        raise ValueError("require fft-size >= 4 and 1 <= hop-size <= fft-size")
    nperseg = min(fft_size, len(x))
    if nperseg < 4:
        raise ValueError("spectrogram needs at least four audio samples")
    freqs, times, spec = signal.spectrogram(
        x,
        fs=sr,
        window="hann",
        nperseg=nperseg,
        noverlap=nperseg - min(hop_size, nperseg),
        detrend=False,
        scaling="spectrum",
        mode="magnitude",
    )
    spec *= 2.0
    spec[0] *= 0.5
    if nperseg % 2 == 0:
        spec[-1] *= 0.5
    keep = (freqs >= min_freq) & (freqs <= max_freq)
    if np.count_nonzero(keep) < 2:
        raise ValueError("frequency range needs at least two FFT bins; widen it or increase fft-size")
    return freqs[keep], times, 20 * np.log10(np.maximum(spec[keep], 1e-8))


def draw_spectrogram(
    ax: plt.Axes,
    freqs: np.ndarray,
    times: np.ndarray,
    spec_db: np.ndarray,
    start_s: float,
    vmin: float,
    vmax: float,
    cmap: str = CMAP,
    *,
    pitch_labels: bool = False,
    time_step_s: float | None = None,
    difference: bool = False,
) -> None:
    ax._setloom_axis_kind = "time"
    # Explicit bin edges preserve frequency and frame-center geometry even for
    # one-frame closeups. imshow's endpoint extent shifts the first/last bins.
    dt = times[1] - times[0] if len(times) > 1 else time_step_s
    if dt is None or dt <= 0:
        raise ValueError("one-frame spectrogram needs a positive time step")
    df = freqs[1] - freqs[0]
    time_edges = np.r_[times - dt / 2, times[-1] + dt / 2] + start_s
    freq_edges = np.r_[freqs - df / 2, freqs[-1] + df / 2]
    mesh = ax.pcolormesh(
        time_edges,
        freq_edges,
        spec_db,
        shading="flat",
        vmin=vmin,
        vmax=vmax,
        cmap=cmap,
        rasterized=True,
    )
    ax.set_yscale("log")
    ax.set_ylim(max(freq_edges[0], 1e-6), freq_edges[-1])
    if pitch_labels:
        lo, hi = 69 + 12 * np.log2(np.array([freqs[0], freqs[-1]]) / 440.0)
        step = 1 if hi - lo <= 16 else 3 if hi - lo <= 48 else 12
        pitches = np.arange(int(np.ceil(lo / step)) * step, int(np.floor(hi)) + 1, step)
        names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
        ax.set_yticks(440 * 2.0 ** ((pitches - 69) / 12))
        ax.set_yticklabels([f"{names[p % 12]}{p // 12 - 1}" for p in pitches])
    else:
        ax.yaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=5))
    ax.yaxis.set_minor_locator(ticker.NullLocator())
    ax.set_ylabel("pitch reference (A4=440 Hz)" if pitch_labels else "Hz")
    # Keep time axes aligned with waveform panels; a regular colorbar steals
    # width only from the spectrogram and visually misaligns simultaneous events.
    color_axis = ax.inset_axes([1.012, 0, 0.02, 1])
    bar = ax.figure.colorbar(mesh, cax=color_axis)
    bar.set_label("difference (dB)" if difference else "bin amplitude (dBFS)", color=FG)
    bar.ax.tick_params(colors=MUTED)


def plot_spectrogram(
    ax: plt.Axes, x: np.ndarray, sr: int, start_s: float, max_freq: float,
    *, min_freq: float = 20.0, fft_size: int = 2048, hop_size: int = 512,
    pitch_labels: bool = False,
) -> None:
    freqs, times, spec_db = spectrogram_db(
        x, sr, max_freq, min_freq=min_freq, fft_size=fft_size, hop_size=hop_size,
    )
    lo, hi = np.quantile(spec_db, [0.05, 0.997])
    draw_spectrogram(
        ax, freqs, times, spec_db, start_s, lo, max(hi, lo + 1.0),
        pitch_labels=pitch_labels, time_step_s=min(hop_size, len(x)) / sr,
    )


def spectrum_db(
    x: np.ndarray, sr: int, max_freq: float, *, min_freq: float = 20.0,
) -> tuple[np.ndarray, np.ndarray]:
    if len(x) < 2:
        return np.asarray([]), np.asarray([])
    window = signal.windows.hann(len(x), sym=False)
    mag = 2.0 * np.abs(np.fft.rfft(x * window)) / window.sum()
    mag[0] *= 0.5
    if len(x) % 2 == 0:
        mag[-1] *= 0.5
    freqs = np.fft.rfftfreq(len(x), d=1.0 / sr)
    keep = (freqs >= min_freq) & (freqs <= max_freq)
    return freqs[keep], 20 * np.log10(np.maximum(mag[keep], 1e-8))


def format_frequency_axis(ax: plt.Axes) -> None:
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=5))
    ax.xaxis.set_minor_locator(ticker.NullLocator())
    ax.set_ylabel("bin amplitude (dBFS)")
    ax.set_xlabel("Hz")


def plot_spectrum(ax: plt.Axes, x: np.ndarray, sr: int, max_freq: float, *, min_freq: float = 20.0) -> None:
    ax._setloom_axis_kind = "frequency"
    freqs, db = spectrum_db(x, sr, max_freq, min_freq=min_freq)
    if len(freqs) == 0:
        return
    ax.plot(freqs, db, color=LINE, lw=0.9)
    format_frequency_axis(ax)


def set_panel_title(ax: plt.Axes, index: int, text: str) -> None:
    ax.set_title(f"[{index}] {text}", loc="left", fontsize=PANEL_TITLE_SIZE, color=FG, pad=10)


def set_figure_title(fig: plt.Figure, title: str) -> None:
    name, separator, detail = title.partition(" | ")
    lines = [name, detail] if separator else [name]
    available_points = fig.get_figwidth() * 72 * 0.85
    font_size = min(TITLE_SIZE, available_points / (0.54 * max(map(len, lines))))
    fig.suptitle("\n".join(lines), x=0.085, y=0.985, ha="left", fontsize=font_size, color=FG)


def stereo_metrics(y: np.ndarray, sr: int, start_s: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    left = y[:, 0]
    right = y[:, min(1, y.shape[1] - 1)]
    frame = 4096
    hop = 1024
    if len(y) < frame:
        frame = max(16, len(y))
        hop = frame
    times = []
    corr = []
    width_db = []
    for i in range(0, max(1, len(y) - frame + 1), hop):
        left_frame = left[i : i + frame]
        right_frame = right[i : i + frame]
        if len(left_frame) < 2:
            continue
        denom = (
            np.sqrt(np.sum(left_frame * left_frame) * np.sum(right_frame * right_frame)) + 1e-9
        )
        c = float(np.sum(left_frame * right_frame) / denom)
        mid = (left_frame + right_frame) * 0.5
        side = (left_frame - right_frame) * 0.5
        w = 20.0 * np.log10(
            (np.sqrt(np.mean(side * side)) + 1e-9)
            / (np.sqrt(np.mean(mid * mid)) + 1e-9)
        )
        times.append(start_s + (i + len(left_frame) * 0.5) / sr)
        corr.append(np.clip(c, -1.0, 1.0))
        width_db.append(np.clip(w, -60.0, 12.0))
    return np.asarray(times), np.asarray(corr), np.asarray(width_db)


def save(fig: plt.Figure, out: Path, dpi: int, *, announce: bool) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.035)
    plt.close(fig)
    if announce:
        print(out)
    return out


def title_for(path: Path, start_s: float, end_s: float, args: argparse.Namespace) -> str:
    signal_label = "stereo L/R + corr + side/mid" if args.view == "stereo" else signal_title(args.signal, args.channel)
    if args.bar_start is not None or args.bar_end is not None:
        bar_s = 4.0 * 60.0 / args.bpm
        bar_start = (start_s - args.grid_origin) / bar_s
        bar_end = (end_s - args.grid_origin) / bar_s
        return f"{path.name} | bars {bar_start:.1f}-{bar_end:.1f} | {args.view} | {signal_label}"
    return f"{path.name} | {start_s:.2f}-{end_s:.2f}s | {args.view} | {signal_label}"


def format_time_axis(ax: plt.Axes, start_s: float, end_s: float) -> None:
    duration = end_s - start_s
    nbins = 7 if duration > 90 else 6
    ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=nbins))


def read_audio(path: Path, *, start_s: float = 0.0, end_s: float | None = None) -> tuple[np.ndarray, int]:
    """Read only the requested frames, with no full-track allocation for a closeup."""
    sr = sf.info(path).samplerate
    return sf.read(
        path, start=round(start_s * sr), stop=None if end_s is None else round(end_s * sr),
        dtype="float32", always_2d=True,
    )


def inspection_output_path(audio: Path, kind: str, explicit: str | Path | None) -> Path:
    """Keep generated inspection images out of the source recording's directory."""
    return Path(explicit) if explicit else Path("tmp/inspection") / f"{audio.stem}.{kind}.png"


def channel_data(y: np.ndarray, channel: int) -> np.ndarray:
    ch = min(max(channel, 0), y.shape[1] - 1)
    return y[:, ch]


def analysis_signal(y: np.ndarray, mode: str, channel: int) -> tuple[np.ndarray, str]:
    left = y[:, 0]
    right = y[:, min(1, y.shape[1] - 1)]
    if mode == "channel":
        ch = min(max(channel, 0), y.shape[1] - 1)
        return y[:, ch], f"ch {ch}"
    if mode == "left":
        return left, "left"
    if mode == "right":
        return right, "right"
    if mode == "mid":
        return (left + right) * 0.5, "mid"
    if mode == "side":
        return (left - right) * 0.5, "side"
    return np.mean(y, axis=1), "mono"


def signal_title(mode: str, channel: int) -> str:
    if mode == "channel":
        return f"signal ch {channel}"
    return f"signal {mode}"


def finalize_time_axes(
    fig: plt.Figure, start_s: float, end_s: float, bpm: float | None, grid: str,
    origin: float = 0, subdivisions: int = 4,
) -> None:
    for ax in fig.axes:
        if getattr(ax, "_setloom_axis_kind", None) == "time":
            add_time_grid(ax, start_s, end_s, bpm, grid, origin, subdivisions)
            ax.set_xlim(start_s, end_s)
            format_time_axis(ax, start_s, end_s)


def compare_title(path_a: Path, path_b: Path, start_s: float, end_s: float, args: argparse.Namespace) -> str:
    if args.bar_start is not None or args.bar_end is not None:
        bar_s = 4.0 * 60.0 / args.bpm
        window = f"bars {(start_s - args.grid_origin) / bar_s:.1f}-{(end_s - args.grid_origin) / bar_s:.1f}"
    else:
        window = f"{start_s:.2f}-{end_s:.2f}s"
    layout = args.compare_layout
    if args.compare_layout == "diff":
        layout = f"diff ({args.compare_label_b} - {args.compare_label_a})"
    return f"{path_a.name} vs {path_b.name} | {window} | {args.view} {layout} | {signal_title(args.signal, args.channel)}"


def set_common_ylim(axes: list[plt.Axes]) -> None:
    lows = []
    highs = []
    for ax in axes:
        low, high = ax.get_ylim()
        lows.append(low)
        highs.append(high)
    if lows and highs:
        low = min(lows)
        high = max(highs)
        for ax in axes:
            ax.set_ylim(low, high)


def render_compare(
    args: argparse.Namespace,
    path_a: Path,
    path_b: Path,
    y_a: np.ndarray,
    y_b: np.ndarray,
    sr: int,
    start_s: float,
    end_s: float,
    *,
    announce: bool,
) -> Path:
    if args.view not in {"wave", "spectrum", "spectrogram"}:
        raise SystemExit("--compare supports --view wave, spectrum, or spectrogram")
    if args.view == "spectrogram" and args.compare_layout == "overlay":
        raise SystemExit("spectrogram overlay is not useful; use --compare-layout stack, side, or diff")

    x_a, signal_label = analysis_signal(y_a, args.signal, args.channel)
    x_b, _ = analysis_signal(y_b, args.signal, args.channel)
    n = min(len(x_a), len(x_b))
    x_a = x_a[:n]
    x_b = x_b[:n]
    out = inspection_output_path(path_a, f"{args.view}-{args.compare_layout}", args.out)
    title = compare_title(path_a, path_b, start_s, end_s, args)

    if args.view == "wave":
        if args.compare_layout == "side":
            fig, axes = make_grid(1, 2, args.width_px, args.height_px or 980, args.dpi)
            set_figure_title(fig, title)
            plot_wave(axes[0], x_a, sr, start_s, f"{args.compare_label_a} {signal_label}", WAVE)
            plot_wave(axes[1], x_b, sr, start_s, f"{args.compare_label_b} {signal_label}", WAVE_R)
            set_panel_title(axes[0], 1, f"Waveform - {args.compare_label_a} {signal_label}")
            set_panel_title(axes[1], 2, f"Waveform - {args.compare_label_b} {signal_label}")
        elif args.compare_layout == "stack":
            fig, axes = make_figure(2, args.width_px, args.height_px, args.dpi)
            set_figure_title(fig, title)
            plot_wave(axes[0], x_a, sr, start_s, f"{args.compare_label_a} {signal_label}", WAVE)
            plot_wave(axes[1], x_b, sr, start_s, f"{args.compare_label_b} {signal_label}", WAVE_R)
            axes[1].set_xlabel("seconds")
            set_panel_title(axes[0], 1, f"Waveform - {args.compare_label_a} {signal_label}")
            set_panel_title(axes[1], 2, f"Waveform - {args.compare_label_b} {signal_label}")
        elif args.compare_layout == "diff":
            fig, axes = make_figure(1, args.width_px, args.height_px, args.dpi)
            set_figure_title(fig, title)
            diff = x_b - x_a
            plot_wave(axes[0], diff, sr, start_s, f"{args.compare_label_b} - {args.compare_label_a}", DIFF)
            peak = max(float(np.max(np.abs(diff))), 1e-6)
            axes[0].set_ylim(-peak * 1.08, peak * 1.08)
            axes[0].set_xlabel("seconds")
            set_panel_title(axes[0], 1, f"Waveform diff - {args.compare_label_b} minus {args.compare_label_a}")
        else:
            fig, axes = make_figure(1, args.width_px, args.height_px, args.dpi)
            set_figure_title(fig, title)
            plot_wave(axes[0], x_a, sr, start_s, signal_label, WAVE)
            t = start_s + np.arange(len(x_b)) / sr
            axes[0].plot(t, x_b, color=WAVE_R, lw=0.42, alpha=0.72, label=args.compare_label_b)
            axes[0].lines[0].set_label(args.compare_label_a)
            axes[0].legend(facecolor=PANEL, edgecolor="#2b353a", labelcolor=FG, fontsize=LEGEND_SIZE, loc="upper right")
            axes[0].set_xlabel("seconds")
            set_panel_title(axes[0], 1, f"Waveform overlay - {signal_label}")
        finalize_time_axes(fig, start_s, end_s, args.bpm, args.grid,
                           args.grid_origin, args.subdivisions)
        return save(fig, out, args.dpi, announce=announce)

    if args.view == "spectrum":
        freqs_a, db_a = spectrum_db(x_a, sr, args.max_freq, min_freq=args.min_freq)
        freqs_b, db_b = spectrum_db(x_b, sr, args.max_freq, min_freq=args.min_freq)
        n = min(len(freqs_a), len(freqs_b), len(db_a), len(db_b))
        freqs = freqs_a[:n]
        db_a = db_a[:n]
        db_b = db_b[:n]
        if args.compare_layout == "side":
            fig, axes = make_grid(1, 2, args.width_px, args.height_px or 980, args.dpi)
            set_figure_title(fig, title)
            axes[0].plot(freqs, db_a, color=WAVE, lw=0.9)
            axes[1].plot(freqs, db_b, color=WAVE_R, lw=0.9)
            for ax in axes:
                ax._setloom_axis_kind = "frequency"
                format_frequency_axis(ax)
            set_panel_title(axes[0], 1, f"Spectrum - {args.compare_label_a} {signal_label}")
            set_panel_title(axes[1], 2, f"Spectrum - {args.compare_label_b} {signal_label}")
            set_common_ylim(axes)
        elif args.compare_layout == "stack":
            fig, axes = make_figure(2, args.width_px, args.height_px, args.dpi)
            set_figure_title(fig, title)
            axes[0].plot(freqs, db_a, color=WAVE, lw=0.9)
            axes[1].plot(freqs, db_b, color=WAVE_R, lw=0.9)
            for ax in axes:
                ax._setloom_axis_kind = "frequency"
                format_frequency_axis(ax)
            axes[0].set_xlabel("")
            set_panel_title(axes[0], 1, f"Spectrum - {args.compare_label_a} {signal_label}")
            set_panel_title(axes[1], 2, f"Spectrum - {args.compare_label_b} {signal_label}")
            set_common_ylim(axes)
        elif args.compare_layout == "diff":
            fig, axes = make_figure(1, args.width_px, args.height_px, args.dpi)
            set_figure_title(fig, title)
            axes[0].plot(freqs, db_b - db_a, color=DIFF, lw=0.9)
            axes[0].axhline(0.0, color=GRID, lw=0.8, alpha=0.55)
            axes[0]._setloom_axis_kind = "frequency"
            axes[0].set_xlabel("Hz")
            format_frequency_axis(axes[0])
            axes[0].set_ylabel(f"{args.compare_label_b} - {args.compare_label_a} dB")
            set_panel_title(axes[0], 1, f"Spectrum diff - {args.compare_label_b} minus {args.compare_label_a}")
        else:
            fig, axes = make_figure(1, args.width_px, args.height_px, args.dpi)
            set_figure_title(fig, title)
            axes[0].plot(freqs, db_a, color=WAVE, lw=0.9, label=args.compare_label_a)
            axes[0].plot(freqs, db_b, color=WAVE_R, lw=0.9, alpha=0.8, label=args.compare_label_b)
            axes[0]._setloom_axis_kind = "frequency"
            format_frequency_axis(axes[0])
            axes[0].legend(facecolor=PANEL, edgecolor="#2b353a", labelcolor=FG, fontsize=LEGEND_SIZE, loc="upper right")
            set_panel_title(axes[0], 1, f"Spectrum overlay - {signal_label}")
        return save(fig, out, args.dpi, announce=announce)

    spec_options = dict(min_freq=args.min_freq, fft_size=args.fft_size, hop_size=args.hop_size)
    draw_options = dict(pitch_labels=args.pitch_labels, time_step_s=min(args.hop_size, n) / sr)
    freqs_a, times_a, spec_a = spectrogram_db(x_a, sr, args.max_freq, **spec_options)
    freqs_b, times_b, spec_b = spectrogram_db(x_b, sr, args.max_freq, **spec_options)
    rows = min(spec_a.shape[0], spec_b.shape[0])
    cols = min(spec_a.shape[1], spec_b.shape[1])
    freqs = freqs_a[:rows]
    times = times_a[:cols]
    spec_a = spec_a[:rows, :cols]
    spec_b = spec_b[:rows, :cols]
    lo, hi = np.quantile(np.concatenate([spec_a.ravel(), spec_b.ravel()]), [0.05, 0.997])
    hi = max(hi, lo + 1.0)
    if args.compare_layout == "side":
        fig, axes = make_grid(1, 2, args.width_px, args.height_px or 980, args.dpi)
        set_figure_title(fig, title)
        draw_spectrogram(axes[0], freqs, times, spec_a, start_s, lo, hi, **draw_options)
        draw_spectrogram(axes[1], freqs, times, spec_b, start_s, lo, hi, **draw_options)
        set_panel_title(axes[0], 1, f"Spectrogram - {args.compare_label_a} {signal_label}")
        set_panel_title(axes[1], 2, f"Spectrogram - {args.compare_label_b} {signal_label}")
    elif args.compare_layout == "stack":
        fig, axes = make_figure(2, args.width_px, args.height_px, args.dpi)
        set_figure_title(fig, title)
        draw_spectrogram(axes[0], freqs, times, spec_a, start_s, lo, hi, **draw_options)
        draw_spectrogram(axes[1], freqs, times, spec_b, start_s, lo, hi, **draw_options)
        axes[1].set_xlabel("seconds")
        set_panel_title(axes[0], 1, f"Spectrogram - {args.compare_label_a} {signal_label}")
        set_panel_title(axes[1], 2, f"Spectrogram - {args.compare_label_b} {signal_label}")
    else:
        fig, axes = make_figure(1, args.width_px, args.height_px, args.dpi)
        set_figure_title(fig, title)
        spec_diff = spec_b - spec_a
        lim = max(float(np.quantile(np.abs(spec_diff), 0.995)), 1e-6)
        draw_spectrogram(axes[0], freqs, times, spec_diff, start_s, -lim, lim, DIFF_CMAP, difference=True, **draw_options)
        set_panel_title(axes[0], 1, f"Spectrogram diff - {args.compare_label_b} minus {args.compare_label_a}")
        axes[0].set_xlabel("seconds")
    finalize_time_axes(fig, start_s, end_s, args.bpm, args.grid,
                       args.grid_origin, args.subdivisions)
    return save(fig, out, args.dpi, announce=announce)


def render_rhythm(
    args: argparse.Namespace, paths: list[Path], start_s: float, end_s: float,
    *, announce: bool,
) -> Path:
    if args.signal != "channel" or args.channel != 0:
        raise SystemExit("rhythm measures mean channel power; --signal/--channel do not apply")
    if len(paths) > 1 and args.compare_layout not in ("overlay", "stack"):
        raise SystemExit("rhythm comparison supports --compare-layout overlay or stack")
    out = inspection_output_path(paths[0], "rhythm", args.out)
    if args.report and Path(args.report).resolve() in {out.resolve(), *(p.resolve() for p in paths)}:
        raise SystemExit("--report must differ from the plot and input paths")
    try:
        reports = [analyze_rhythm(
            path, start=start_s, end=end_s, bpm=args.bpm, grid_origin=args.grid_origin,
            subdivisions=args.subdivisions, bands=args.band, envelope_ms=args.envelope_ms,
            hop_ms=args.envelope_hop_ms, peak_distance_ms=args.peak_distance_ms,
        ) for path in paths]
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    labels = [f"{label}: {path.name}" for label, path in zip(
        (args.compare_label_a, args.compare_label_b), paths,
    )]
    band_count = len(reports[0]["bands"])
    stacked = len(paths) > 1 and args.compare_layout == "stack"
    rows = band_count * (len(paths) if stacked else 1)
    fig, axes = make_grid(rows, 1, args.width_px, args.height_px or 500 + 440 * rows, args.dpi)
    set_figure_title(fig, (
        f"Rhythm evidence | {start_s:.3f}-{end_s:.3f}s | {args.envelope_ms:g} ms RMS\n"
        "Mean channel power; dots = envelope maxima, not note onsets; no gain normalization"
    ))
    for i, band in enumerate(reports[0]["bands"]):
        values = []
        band_axes = []
        for j, report in enumerate(reports):
            ax = axes[i * len(paths) + j] if stacked else axes[i]
            band_axes.append(ax)
            color = (WAVE, WAVE_R)[j]
            data = report["bands"][i]
            env = data["envelope"]
            values.extend(env["rms_dbfs"])
            ax.plot(env["seconds"], env["rms_dbfs"], color=color, lw=0.9, label=labels[j])
            ax.scatter([p["peak_seconds"] for p in data["landmarks"]],
                       [p["rms_dbfs"] for p in data["landmarks"]], color=color, s=12)
            ax._setloom_axis_kind = "time"
            ax.set_ylabel("RMS dBFS")
            ax.set_title(f"{band['name']} | {band['low_hz']:g}-{band['high_hz']:g} Hz",
                         fontsize=PANEL_TITLE_SIZE, loc="left", color=FG, pad=10)
        ceiling = max(-80, max(values, default=-200) + 3)
        for ax in set(band_axes):
            ax.set_ylim(ceiling - 100, ceiling)
            ax.legend(facecolor=PANEL, edgecolor="#2b353a", labelcolor=FG,
                      fontsize=LEGEND_SIZE, loc="lower right")
    axes[-1].set_xlabel("absolute file seconds")
    finalize_time_axes(fig, start_s, end_s, args.bpm, args.grid,
                       args.grid_origin, args.subdivisions)
    result = save(fig, out, args.dpi, announce=announce)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps({
            "schema_version": 1, "kind": "rhythm-comparison",
            "sources": [{"label": label, "evidence": report}
                        for label, report in zip(labels, reports)],
        }, indent=2, allow_nan=False) + "\n")
        if announce:
            print(report_path)
    return result


def render_from_args(args: argparse.Namespace, *, announce: bool = False) -> Path:
    load_plotting_backend()
    path = Path(args.audio)
    info = sf.info(path)
    sr = info.samplerate
    compare_path = Path(args.compare) if args.compare else None
    paths = [path, compare_path] if compare_path is not None else [path]
    if args.out and Path(args.out).resolve() in {p.resolve() for p in paths}:
        raise SystemExit("--out must differ from the input paths")
    if args.view != "rhythm" and (args.report or args.band):
        raise SystemExit("--report and --band require --view rhythm")
    duration_s = info.frames / sr
    if compare_path is not None:
        compare_info = sf.info(compare_path)
        compare_sr = compare_info.samplerate
        if compare_sr != sr:
            raise SystemExit(f"sample-rate mismatch: {sr} vs {compare_sr}")
        duration_s = min(duration_s, compare_info.frames / sr)
    if not (np.isfinite(args.min_freq) and np.isfinite(args.max_freq)
            and 0 < args.min_freq < min(args.max_freq, sr / 2)):
        raise SystemExit("require 0 < min-freq < max-freq, with min-freq below Nyquist")
    if args.fft_size < 4 or not 1 <= args.hop_size <= args.fft_size:
        raise SystemExit("require fft-size >= 4 and 1 <= hop-size <= fft-size")
    start_s, end_s = window_seconds(args, duration_s)
    start_s, end_s = round(start_s * sr) / sr, round(end_s * sr) / sr
    if args.view == "rhythm":
        return render_rhythm(args, paths, start_s, end_s, announce=announce)
    y, _ = read_audio(path, start_s=start_s, end_s=end_s)
    y_compare = None
    if compare_path is not None:
        y_compare, _ = read_audio(compare_path, start_s=start_s, end_s=end_s)
    if len(y) == 0:
        raise SystemExit("selected window is empty")
    if y_compare is not None and len(y_compare) == 0:
        raise SystemExit("selected comparison window is empty")

    if compare_path is not None and y_compare is not None:
        return render_compare(
            args,
            path,
            compare_path,
            y,
            y_compare,
            sr,
            start_s,
            end_s,
            announce=announce,
        )

    x, signal_label = analysis_signal(y, args.signal, args.channel)
    out = inspection_output_path(path, args.view, args.out)
    title = title_for(path, start_s, end_s, args)
    spec_options = dict(
        min_freq=args.min_freq, fft_size=args.fft_size, hop_size=args.hop_size,
        pitch_labels=args.pitch_labels,
    )

    if args.view == "wave":
        fig, axes = make_figure(1, args.width_px, args.height_px, args.dpi)
        set_figure_title(fig, title)
        plot_wave(axes[0], x, sr, start_s, signal_label)
        set_panel_title(axes[0], 1, f"Waveform - {signal_label}")
        axes[0].set_xlabel("seconds")
    elif args.view == "spectrogram":
        fig, axes = make_figure(1, args.width_px, args.height_px, args.dpi)
        set_figure_title(fig, title)
        plot_spectrogram(axes[0], x, sr, start_s, args.max_freq, **spec_options)
        set_panel_title(axes[0], 1, f"Spectrogram - {signal_label}")
        axes[0].set_xlabel("seconds")
    elif args.view == "spectrum":
        fig, axes = make_figure(1, args.width_px, args.height_px, args.dpi)
        set_figure_title(fig, title)
        plot_spectrum(axes[0], x, sr, args.max_freq, min_freq=args.min_freq)
        set_panel_title(axes[0], 1, f"Spectrum - {signal_label}")
    elif args.view == "stereo":
        fig, axes = make_figure(3, args.width_px, args.height_px, args.dpi)
        set_figure_title(fig, title)
        plot_wave(axes[0], y[:, 0], sr, start_s, "L", WAVE)
        plot_wave(axes[0], y[:, min(1, y.shape[1] - 1)], sr, start_s, "L/R", WAVE_R)
        set_panel_title(axes[0], 1, "Left and right waveforms")
        times, corr, width_db = stereo_metrics(y, sr, start_s)
        axes[1].plot(times, corr, color=LINE, lw=0.9)
        axes[1]._setloom_axis_kind = "time"
        axes[1].set_ylim(-1.05, 1.05)
        axes[1].set_ylabel("corr")
        set_panel_title(axes[1], 2, "Stereo correlation")
        axes[2].plot(times, width_db, color=WAVE_R, lw=0.9)
        axes[2]._setloom_axis_kind = "time"
        axes[2].set_ylim(-60, 12)
        axes[2].set_ylabel("side/mid dB")
        axes[2].set_xlabel("seconds")
        set_panel_title(axes[2], 3, "Stereo width - side/mid dB")
    else:
        rows = 4 if args.view == "all" else 2
        fig, axes = make_figure(rows, args.width_px, args.height_px, args.dpi)
        set_figure_title(fig, title)
        plot_wave(axes[0], x, sr, start_s, signal_label)
        plot_spectrogram(axes[1], x, sr, start_s, args.max_freq, **spec_options)
        set_panel_title(axes[0], 1, f"Waveform - {signal_label}")
        set_panel_title(axes[1], 2, f"Spectrogram - {signal_label}")
        if args.view == "all":
            plot_spectrum(axes[2], x, sr, args.max_freq, min_freq=args.min_freq)
            set_panel_title(axes[2], 3, f"Spectrum - {signal_label}")
            times, corr, width_db = stereo_metrics(y, sr, start_s)
            axes[3].plot(times, corr, color=LINE, lw=0.85, label="corr")
            axes[3].plot(times, width_db / 60.0, color=WAVE_R, lw=0.85, label="side/mid dB / 60")
            axes[3]._setloom_axis_kind = "time"
            axes[3].set_ylim(-1.05, 1.05)
            axes[3].legend(facecolor=PANEL, edgecolor="#2b353a", labelcolor=FG, fontsize=LEGEND_SIZE, loc="upper right")
            axes[3].set_ylabel("stereo")
            axes[3].set_xlabel("seconds")
            set_panel_title(axes[3], 4, "Stereo metrics - corr and side/mid")
        else:
            axes[1].set_xlabel("seconds")

    finalize_time_axes(fig, start_s, end_s, args.bpm, args.grid,
                       args.grid_origin, args.subdivisions)
    return save(fig, out, args.dpi, announce=announce)


def render_audio_inspection(
    audio: str | Path | AudioInspectionRequest,
    **overrides: Any,
) -> Path:
    """Render an audio inspection plot and return the written PNG path.

    Pass either an ``AudioInspectionRequest`` or the audio path plus keyword
    options matching the request fields, for example:

    ``render_audio_inspection("mix.wav", view="all", out="tmp/mix-inspect.png")``.
    """
    if isinstance(audio, AudioInspectionRequest):
        if overrides:
            raise TypeError("overrides are not accepted when passing AudioInspectionRequest")
        request = audio
    else:
        request = AudioInspectionRequest(audio=audio, **overrides)
    return render_from_args(request.to_namespace(), announce=False)


def run(args: argparse.Namespace) -> int:
    render_from_args(args, announce=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
