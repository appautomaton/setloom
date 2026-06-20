# SPDX-License-Identifier: AGPL-3.0-only
"""Top-level render orchestration."""

from __future__ import annotations

import soundfile as sf

from .bass import render_remapped_bass
from .bed import render_bed_with_bass
from .context import MIX_PLAN, OUT, SR
from .dsp import cap, fade, highpass, stats
from .piano import render_piano
from .pluck import render_pluck
from .texture import render_space, render_support


def write_report(lines: list[str]) -> None:
    (OUT / "render-report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    piano = render_piano()
    support = render_support()
    pluck = render_pluck()
    space = render_space(piano, pluck)
    bass, bass_events = render_remapped_bass(MIX_PLAN)
    bed, kick_core, bass_phase = render_bed_with_bass(bass)

    top_cfg = MIX_PLAN["top_mix"]
    final_cfg = MIX_PLAN["final_mix"]
    top = (
        highpass(piano, top_cfg["piano_hpf_hz"]) * top_cfg["piano_gain"]
        + highpass(pluck, top_cfg["pluck_hpf_hz"]) * top_cfg["pluck_gain"]
        + highpass(support, top_cfg["support_hpf_hz"]) * top_cfg["support_gain"]
        + space * top_cfg["space_gain"]
    )
    mix = cap((bed * final_cfg["bed_gain"]) + top, peak=final_cfg["peak"])

    sf.write(OUT / "full-mix.wav", fade(mix), SR)
    sf.write(OUT / "bed.wav", fade(bed), SR)
    sf.write(OUT / "stem-kick.wav", fade(kick_core), SR)
    sf.write(OUT / "stem-bass.wav", fade(bass_phase), SR)
    sf.write(OUT / "stem-top.wav", fade(cap(top, peak=top_cfg["top_peak"])), SR)

    pitch_pairs: dict[str, int] = {}
    for event in bass_events:
        key = f"{event['source_note']}->{event['note']}"
        pitch_pairs[key] = pitch_pairs.get(key, 0) + 1
    pitch_summary = " ".join(f"{k}:{v}" for k, v in sorted(pitch_pairs.items(), key=lambda item: (-item[1], item[0]))[:16])

    report = [
        "# T5 Lux in Umbra",
        "",
        "Outputs:",
        "- render/full-mix.wav",
        "- render/bed.wav",
        "- render/stem-piano.wav",
        "- render/stem-pluck.wav",
        "- render/stem-support.wav",
        "- render/stem-space.wav",
        "- render/stem-bass.wav",
        "- render/stem-kick.wav",
        "- render/stem-top.wav",
        "- source/remapped-bass-events.json",
        "",
        "Bass remap:",
        "- source-bass-rhythm start_tick, duration_ticks, and velocity preserved.",
        "- Pitch source: source/remapped-bass-events.json.",
        "- Score source: source/score.json.",
        "- Pluck patch source: source/pluck-synth.json.",
        "- Mix plan source: source/mix-plan.json.",
        f"- remapped_events={len(bass_events)}",
        f"- top pitch maps: {pitch_summary}",
        "",
        stats("main_mix", mix),
        stats("bed", bed),
        stats("top", top),
        stats("piano", piano),
        stats("pluck", pluck),
        stats("support", support),
        stats("space", space),
        stats("bass_phase", bass_phase),
        stats("kick_phase", kick_core),
    ]
    write_report(report)
    return 0
