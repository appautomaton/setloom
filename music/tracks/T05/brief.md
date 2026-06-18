# T05 Brief — bad-romance-megatron-mashup

## What this is

A 123 BPM techno edit mashing two external MIDI sources onto one phrase grid, with a Steinway piano chord bed replacing the music-box ostinato lane.

## Sources

| material | source | role |
|---|---|---|
| moving bass (F/G/A/C) | Bad Romance (Lady Gaga) MIDI ti=01 | low-end spine, re-timed to 123 BPM |
| C-minor 8th-note ostinato | Lopyt "Megatron" MIDI ti=00 pluck | motif lead, re-arranged by section |
| Steinway piano chords | Logic Pro library `Steinway Piano 2` sample | chord bed (replaces music-box ostinato) |
| kick / hats / perc / fills / pad / fx / chords | harness generators from T05 spec | scaffolding + break kick-gating |

## Harness use vs bypass

**Used the harness for:** spec validation, scaffolding MIDI generation (drums, chords, fills, pad, fx), section routing, break kick-gating (`drums.py` auto-mutes kick in `break` sections), conductor harmony (Am-F-C-G, degrees 0,5,2,6).

**Bypassed the harness for (with reason):**
- **bass lane** — `BassGenerator` is hardcoded to a tonic pedal + b7 neighbor. Bad Romance's bass is a *moving line* (F→G→A→C, 9 distinct pitches F1-G2). Fed re-arranged Bad Romance bass as NoteEvents through a custom saw-pressure numpy synth.
- **lead lane (motif pluck)** — no `LeadGroovePlan` exists in schema; `LeadGenerator` writes built-in gestures. Fed re-arranged Lopyt ostinato as NoteEvents through a custom FM 7:3 bell synth.
- **music-box lane → piano** — original Lopyt music-box ostinato (single-note, high octave) sounded cheap as FM bell. Replaced with Steinway piano chord bed (root+third+fifth per bar, from conductor harmony).
- **scaffolding patches.scd + mix bus** — harness SuperCollider patches (`vibe_hat` 9kHz digital ticks, `vibe_clap` 2&4 tech-house, `vibe_shaker` 16th preset bed) read as cheap MIDI. Replaced all voices with custom numpy synthesis (saw-derived kick/bass, FM 7:3 bell motif, dark saw chords/pad, noise-swell fx).
- **harness shaker + clap_ride** — muted entirely (cheap percussion tell).

## Re-arrangement map (123 BPM, 144 bars)

| bars | section | kick | bass | motif pluck | piano chords |
|---|---|---|---|---|---|
| 0-7 | intro | sparse | — | — | — |
| 8-23 | groove_a | 4-on-floor | enters (BR line) | pluck enters | — |
| 24-39 | groove_b | 4-on-floor | continues | pluck + mbox→piano | piano enters |
| 40-55 | break | **OUT** (harness) | downbeat-root held | stabs (even bars) | piano sustains |
| 56-87 | drop_1 | 4-on-floor + hat bed | full BR line | pluck full | piano chords |
| 88-103 | groove_c | 4-on-floor | half-time | pluck half-time | piano chords |
| 104-135 | peak | 4-on-floor + open hats | full BR line | pluck **+12** | piano chords |
| 136-143 | outro | 4-on-floor | fade 4 bars | pluck fade | — |

## Synthesis voices

- **kick**: saw-derived thump (wrapped-phase saw → lowpass, click transient)
- **bass**: 3x additive saw stack + bandpass body + sidechain gap (saw-pressure character)
- **motif pluck**: FM 7:3 bell (carrier:modulator = 7:3, mod index 2.2×velocity, -12c detune, LFO crossfade dark/bright at 1/4 note)
- **piano chords**: Steinway sampled piano (Logic Pro library), strongest velocity layer per note, pitch-shifted to match conductor chord tones
- **chords**: 2x additive saw → lowpass (dark stab/sustain)
- **pad**: 3x additive saw → lowpass (dark conductor bed)
- **fx**: noise-swell riser (band-swept) + sub-drop impact
- **perc**: dark rim (700-2200Hz shadow) + pitched tom (saw drop)

## Iteration history

| version | change | verdict |
|---|---|---|
| v1 | harness SC patches + mix bus | rejected — cheap percussion (hat/clap/shaker) |
| v2 | custom numpy synth, no harness patches | "轰头 + 清澈" but motif pluck too "冲" |
| v3 | FM 7:3 bell + reverb + dark LPF | "高级音色" but 嘈杂/糊 — 80/90s MIDI taste |
| v4 | FM bell simplified, no reverb | clear but MIDI taste (static saw) + mbox cheap |
| v5 | v3 FM bell restored, only reverb+lowmid removed | **motif + drums good** |
| v6 | mbox → Steinway piano chord bed | **"味道有了"** ✓ |

## Listening gate

Status: **keep** (pending human confirmation of full mix)

Mix: `/tmp/setloom-bad-romance-analysis/t05/auditions-v6/00-full-mix.wav`
- 282s, -9.9 LUFS, peak 0.871, no clipping
- Stem previews: `/tmp/setloom-bad-romance-analysis/t05/stem-previews-v5/` (v5 stems) + `render-v6/stem-piano-chords.wav`
