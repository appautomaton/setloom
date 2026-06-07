<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Tooling

Setloom is open-source first and keyboard-first. Proprietary DAWs may be useful for optional inspection or export, but they are not core dependencies.

## Core Tooling Direction

| Layer | Preferred Tools | Purpose |
| --- | --- | --- |
| MIDI generation | Python, Mido, pretty_midi, music21 | Generate editable drums, bass, chords, arps, motifs, and fills. |
| Pattern systems | TidalCycles, Strudel | Explore club-functional rhythm and phrase patterns. |
| Synthesis | SuperCollider, Csound, ChucK, Sonic Pi | Render procedural instruments and textures. |
| DSP | Faust, LV2 plugins, SoX, FFmpeg | Build and apply effects, meters, exports, and checks. |
| DAW fallback | Ardour through scripts, Lua, or OSC | Optional arrangement and inspection path when needed. |

## GenAI Boundary

Use GenAI for melody, motifs, harmonic direction, atmosphere, and variation.

Do not rely on GenAI audio as the primary source for kick, bass, groove, or low-end timing. Those parts need deterministic control.

