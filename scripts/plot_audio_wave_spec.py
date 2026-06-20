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
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import soundfile as sf
from scipy import signal

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
DIFF_CMAP = LinearSegmentedColormap.from_list("setloom_diff", ["#2c5cff", "#101820", "#ffb84d"])
DEFAULT_WIDTH_PX = 2400
DEFAULT_HEIGHT_BY_ROWS = {1: 920, 2: 1600, 3: 2200, 4: 3000}
TITLE_SIZE = 24
PANEL_TITLE_SIZE = 20
LABEL_SIZE = 19
TICK_SIZE = 17
LEGEND_SIZE = 15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio")
    parser.add_argument("--out")
    parser.add_argument("--compare", help="second audio file for A/B visual comparison")
    parser.add_argument("--compare-label-a", default="A")
    parser.add_argument("--compare-label-b", default="B")
    parser.add_argument(
        "--compare-layout",
        choices=["overlay", "stack", "side", "diff"],
        default="overlay",
        help="comparison layout; heatmap overlay is disallowed for spectrograms; use side, stack, or diff",
    )
    parser.add_argument("--bpm", type=float, default=123.0)
    parser.add_argument("--channel", type=int, default=0, help="real file channel index used when --signal channel")
    parser.add_argument(
        "--signal",
        choices=["channel", "left", "right", "mid", "side", "mono"],
        default="channel",
        help="analysis signal for waveform/spectrogram/spectrum; mid/side/mono are derived from L/R",
    )
    parser.add_argument("--start", type=float, default=0.0, help="window start in seconds")
    parser.add_argument("--end", type=float, help="window end in seconds")
    parser.add_argument("--bar-start", type=float, help="window start in bars; overrides --start")
    parser.add_argument("--bar-end", type=float, help="window end in bars; overrides --end")
    parser.add_argument(
        "--view",
        choices=["both", "wave", "spectrogram", "spectrum", "stereo", "all"],
        default="both",
        help="plot type",
    )
    parser.add_argument("--grid", choices=["off", "beats", "bars"], default="bars")
    parser.add_argument("--max-freq", type=float, default=12000.0)
    parser.add_argument("--dpi", type=int, default=160)
    parser.add_argument("--width-px", type=int, default=DEFAULT_WIDTH_PX, help="target output width in pixels")
    parser.add_argument("--height-px", type=int, help="target output height in pixels; defaults by view")
    return parser.parse_args()


def window_seconds(args: argparse.Namespace, duration_s: float) -> tuple[float, float]:
    bar_s = 4.0 * 60.0 / args.bpm
    start = args.start
    end = duration_s if args.end is None else args.end
    if args.bar_start is not None:
        start = args.bar_start * bar_s
    if args.bar_end is not None:
        end = args.bar_end * bar_s
    start = max(0.0, min(float(start), duration_s))
    end = max(start + 1.0 / 44100.0, min(float(end), duration_s))
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


def add_time_grid(ax: plt.Axes, start_s: float, end_s: float, bpm: float, mode: str) -> None:
    if mode == "off":
        return
    beat_s = 60.0 / bpm
    step = beat_s if mode == "beats" else beat_s * 4.0
    first = np.ceil(start_s / step) * step
    for t in np.arange(first, end_s + step * 0.5, step):
        ax.axvline(t, color=GRID, lw=0.45 if mode == "beats" else 0.75, alpha=0.24 if mode == "beats" else 0.42)


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
    gs = fig.add_gridspec(rows, 1, hspace=0.34, top=top, bottom=0.08, left=0.085, right=0.992)
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
    gs = fig.add_gridspec(rows, cols, hspace=0.30, wspace=0.15, top=top, bottom=0.09, left=0.085, right=0.992)
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


def spectrogram_db(x: np.ndarray, sr: int, max_freq: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    freqs, times, spec = signal.spectrogram(
        x,
        fs=sr,
        window="hann",
        nperseg=2048,
        noverlap=1536,
        mode="magnitude",
    )
    keep = (freqs >= 20) & (freqs <= max_freq)
    return freqs[keep], times, 20 * np.log10(spec[keep] + 1e-8)


def draw_spectrogram(
    ax: plt.Axes,
    freqs: np.ndarray,
    times: np.ndarray,
    spec_db: np.ndarray,
    start_s: float,
    vmin: float,
    vmax: float,
    cmap: str = CMAP,
) -> None:
    ax._setloom_axis_kind = "time"
    ax.imshow(
        spec_db,
        aspect="auto",
        origin="lower",
        extent=[times[0] + start_s, times[-1] + start_s, freqs[0], freqs[-1]],
        vmin=vmin,
        vmax=vmax,
        cmap=cmap,
    )
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=5))
    ax.yaxis.set_minor_locator(ticker.NullLocator())
    ax.set_ylabel("Hz")


def plot_spectrogram(ax: plt.Axes, x: np.ndarray, sr: int, start_s: float, max_freq: float) -> None:
    freqs, times, spec_db = spectrogram_db(x, sr, max_freq)
    lo, hi = np.quantile(spec_db, [0.05, 0.997])
    draw_spectrogram(ax, freqs, times, spec_db, start_s, lo, hi)


def spectrum_db(x: np.ndarray, sr: int, max_freq: float) -> tuple[np.ndarray, np.ndarray]:
    if len(x) < 2:
        return np.asarray([]), np.asarray([])
    window = np.hanning(len(x)).astype(np.float32)
    mag = np.abs(np.fft.rfft(x * window))
    freqs = np.fft.rfftfreq(len(x), d=1.0 / sr)
    keep = (freqs >= 20) & (freqs <= max_freq)
    return freqs[keep], 20 * np.log10(mag[keep] + 1e-8)


def format_frequency_axis(ax: plt.Axes) -> None:
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(ticker.LogLocator(base=10.0, numticks=5))
    ax.xaxis.set_minor_locator(ticker.NullLocator())
    ax.set_ylabel("dB")
    ax.set_xlabel("Hz")


def plot_spectrum(ax: plt.Axes, x: np.ndarray, sr: int, max_freq: float) -> None:
    ax._setloom_axis_kind = "frequency"
    freqs, db = spectrum_db(x, sr, max_freq)
    if len(freqs) == 0:
        return
    ax.plot(freqs, db, color=LINE, lw=0.9)
    format_frequency_axis(ax)


def set_panel_title(ax: plt.Axes, index: int, text: str) -> None:
    ax.set_title(f"[{index}] {text}", loc="left", fontsize=PANEL_TITLE_SIZE, color=FG, pad=10)


def set_figure_title(fig: plt.Figure, title: str) -> None:
    fig.suptitle(title, x=0.085, y=0.985, ha="left", fontsize=TITLE_SIZE, color=FG)


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
        l = left[i : i + frame]
        r = right[i : i + frame]
        if len(l) < 2:
            continue
        denom = np.sqrt(np.sum(l * l) * np.sum(r * r)) + 1e-9
        c = float(np.sum(l * r) / denom)
        mid = (l + r) * 0.5
        side = (l - r) * 0.5
        w = 20.0 * np.log10((np.sqrt(np.mean(side * side)) + 1e-9) / (np.sqrt(np.mean(mid * mid)) + 1e-9))
        times.append(start_s + (i + len(l) * 0.5) / sr)
        corr.append(np.clip(c, -1.0, 1.0))
        width_db.append(np.clip(w, -60.0, 12.0))
    return np.asarray(times), np.asarray(corr), np.asarray(width_db)


def save(fig: plt.Figure, out: Path, dpi: int) -> None:
    fig.savefig(out, dpi=dpi, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.035)
    plt.close(fig)
    print(out)


def title_for(path: Path, start_s: float, end_s: float, args: argparse.Namespace) -> str:
    signal_label = "stereo L/R + corr + side/mid" if args.view == "stereo" else signal_title(args.signal, args.channel)
    if args.bar_start is not None or args.bar_end is not None:
        bar_s = 4.0 * 60.0 / args.bpm
        bar_start = start_s / bar_s
        bar_end = end_s / bar_s
        return f"{path.name} | bars {bar_start:.1f}-{bar_end:.1f} | {args.view} | {signal_label}"
    return f"{path.name} | {start_s:.2f}-{end_s:.2f}s | {args.view} | {signal_label}"


def format_time_axis(ax: plt.Axes, start_s: float, end_s: float) -> None:
    duration = end_s - start_s
    nbins = 7 if duration > 90 else 6
    ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=nbins))


def read_audio(path: Path) -> tuple[np.ndarray, int]:
    return sf.read(path, dtype="float32", always_2d=True)


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


def finalize_time_axes(fig: plt.Figure, start_s: float, end_s: float, bpm: float, grid: str) -> None:
    for ax in fig.axes:
        if getattr(ax, "_setloom_axis_kind", None) == "time":
            add_time_grid(ax, start_s, end_s, bpm, grid)
            ax.set_xlim(start_s, end_s)
            format_time_axis(ax, start_s, end_s)


def compare_title(path_a: Path, path_b: Path, start_s: float, end_s: float, args: argparse.Namespace) -> str:
    if args.bar_start is not None or args.bar_end is not None:
        bar_s = 4.0 * 60.0 / args.bpm
        window = f"bars {start_s / bar_s:.1f}-{end_s / bar_s:.1f}"
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
) -> int:
    if args.view not in {"wave", "spectrum", "spectrogram"}:
        raise SystemExit("--compare supports --view wave, spectrum, or spectrogram")
    if args.view == "spectrogram" and args.compare_layout == "overlay":
        raise SystemExit("spectrogram overlay is not useful; use --compare-layout stack, side, or diff")

    x_a, signal_label = analysis_signal(y_a, args.signal, args.channel)
    x_b, _ = analysis_signal(y_b, args.signal, args.channel)
    n = min(len(x_a), len(x_b))
    x_a = x_a[:n]
    x_b = x_b[:n]
    out = Path(args.out) if args.out else path_a.with_suffix(f".{args.view}-{args.compare_layout}.png")
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
        finalize_time_axes(fig, start_s, end_s, args.bpm, args.grid)
        save(fig, out, args.dpi)
        return 0

    if args.view == "spectrum":
        freqs_a, db_a = spectrum_db(x_a, sr, args.max_freq)
        freqs_b, db_b = spectrum_db(x_b, sr, args.max_freq)
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
        save(fig, out, args.dpi)
        return 0

    freqs_a, times_a, spec_a = spectrogram_db(x_a, sr, args.max_freq)
    freqs_b, times_b, spec_b = spectrogram_db(x_b, sr, args.max_freq)
    rows = min(spec_a.shape[0], spec_b.shape[0])
    cols = min(spec_a.shape[1], spec_b.shape[1])
    freqs = freqs_a[:rows]
    times = times_a[:cols]
    spec_a = spec_a[:rows, :cols]
    spec_b = spec_b[:rows, :cols]
    lo, hi = np.quantile(np.concatenate([spec_a.ravel(), spec_b.ravel()]), [0.05, 0.997])
    if args.compare_layout == "side":
        fig, axes = make_grid(1, 2, args.width_px, args.height_px or 980, args.dpi)
        set_figure_title(fig, title)
        draw_spectrogram(axes[0], freqs, times, spec_a, start_s, lo, hi)
        draw_spectrogram(axes[1], freqs, times, spec_b, start_s, lo, hi)
        set_panel_title(axes[0], 1, f"Spectrogram - {args.compare_label_a} {signal_label}")
        set_panel_title(axes[1], 2, f"Spectrogram - {args.compare_label_b} {signal_label}")
    elif args.compare_layout == "stack":
        fig, axes = make_figure(2, args.width_px, args.height_px, args.dpi)
        set_figure_title(fig, title)
        draw_spectrogram(axes[0], freqs, times, spec_a, start_s, lo, hi)
        draw_spectrogram(axes[1], freqs, times, spec_b, start_s, lo, hi)
        axes[1].set_xlabel("seconds")
        set_panel_title(axes[0], 1, f"Spectrogram - {args.compare_label_a} {signal_label}")
        set_panel_title(axes[1], 2, f"Spectrogram - {args.compare_label_b} {signal_label}")
    else:
        fig, axes = make_figure(1, args.width_px, args.height_px, args.dpi)
        set_figure_title(fig, title)
        spec_diff = spec_b - spec_a
        lim = float(np.quantile(np.abs(spec_diff), 0.995))
        draw_spectrogram(axes[0], freqs, times, spec_diff, start_s, -lim, lim, DIFF_CMAP)
        set_panel_title(axes[0], 1, f"Spectrogram diff - {args.compare_label_b} minus {args.compare_label_a}")
        axes[0].set_xlabel("seconds")
    finalize_time_axes(fig, start_s, end_s, args.bpm, args.grid)
    save(fig, out, args.dpi)
    return 0


def main() -> int:
    args = parse_args()
    path = Path(args.audio)
    y, sr = read_audio(path)
    compare_path = Path(args.compare) if args.compare else None
    y_compare = None
    if compare_path is not None:
        y_compare, compare_sr = read_audio(compare_path)
        if compare_sr != sr:
            raise SystemExit(f"sample-rate mismatch: {sr} vs {compare_sr}")
    duration_s = len(y) / sr if y_compare is None else min(len(y), len(y_compare)) / sr
    start_s, end_s = window_seconds(args, duration_s)
    y = slice_audio(y, sr, start_s, end_s)
    if y_compare is not None:
        y_compare = slice_audio(y_compare, sr, start_s, end_s)
    if len(y) == 0:
        raise SystemExit("selected window is empty")
    if y_compare is not None and len(y_compare) == 0:
        raise SystemExit("selected comparison window is empty")

    if compare_path is not None and y_compare is not None:
        return render_compare(args, path, compare_path, y, y_compare, sr, start_s, end_s)

    x, signal_label = analysis_signal(y, args.signal, args.channel)
    out = Path(args.out) if args.out else path.with_suffix(f".{args.view}.png")
    title = title_for(path, start_s, end_s, args)

    if args.view == "wave":
        fig, axes = make_figure(1, args.width_px, args.height_px, args.dpi)
        set_figure_title(fig, title)
        plot_wave(axes[0], x, sr, start_s, signal_label)
        set_panel_title(axes[0], 1, f"Waveform - {signal_label}")
        axes[0].set_xlabel("seconds")
    elif args.view == "spectrogram":
        fig, axes = make_figure(1, args.width_px, args.height_px, args.dpi)
        set_figure_title(fig, title)
        plot_spectrogram(axes[0], x, sr, start_s, args.max_freq)
        set_panel_title(axes[0], 1, f"Spectrogram - {signal_label}")
        axes[0].set_xlabel("seconds")
    elif args.view == "spectrum":
        fig, axes = make_figure(1, args.width_px, args.height_px, args.dpi)
        set_figure_title(fig, title)
        plot_spectrum(axes[0], x, sr, args.max_freq)
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
        plot_spectrogram(axes[1], x, sr, start_s, args.max_freq)
        set_panel_title(axes[0], 1, f"Waveform - {signal_label}")
        set_panel_title(axes[1], 2, f"Spectrogram - {signal_label}")
        if args.view == "all":
            plot_spectrum(axes[2], x, sr, args.max_freq)
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

    for ax in fig.axes:
        if getattr(ax, "_setloom_axis_kind", None) == "time":
            add_time_grid(ax, start_s, end_s, args.bpm, args.grid)
            ax.set_xlim(start_s, end_s)
            format_time_axis(ax, start_s, end_s)
    save(fig, out, args.dpi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
