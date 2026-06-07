<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Mix Architecture Blueprint (Codex GPT-5.5, 2026-06-07)

Provenance: deep consultation in the standing Codex session (1.02M tokens read,
16 commands, read-only) after listening take-7. Prompted with the taste owner's
verbatim critique ("homeless person wearing as many clothes as possible";
"maturity = variety within one spectrum"; "there is mathematics behind it").
Status: **the engineering constitution for Setloom's sound system** — patch and
mix changes should comply or explicitly justify divergence. Confidence tags are
Codex's own; this is model-knowledge pending the listening gate.

Headline diagnosis: *"The core mistake is not 'too few layers'; it is too many
equal-status layers with unrelated roles."* It also caught that the designed SC
percussion SynthDefs existed but were never wired into the render (GM bed still
running) — guaranteed collage. [high]

## A. Percussion architecture

**Clap verdict:** a bright handclap on every 2 & 4 reads tech-house/trance/EDM,
not the Innellea/Colyn/8Kays lane — the taste owner's suspicion is correct.
If used at all: dark, short, wet, −18 to −24 dB vs kick, phrase accents only. [high]

| Element | Role | Sections | Rule |
|---|---|---|---|
| Kick | anchor | groove/drop/peak/outro | 4-on-floor, mono, strongest transient |
| Closed hat | pulse grid | groove offbeats; restrained 16th bed in drop/peak | HPF >6k, vel 44–78, never flat |
| Open hat | offbeat sizzle | drop/peak only | offbeat 8ths, vel 45–58, decay 180–300ms |
| Shaker | texture bed | groove/drop/peak | HPF >4.2k, −18…−22 dB vs kick |
| Rim/dark clap | optional shadow backbeat | peak (or select drop phrases) | −18…−24 dB, NOT every bar |
| Ride | peak shimmer | final 16–32 peak bars | very low, HPF >5k; never with loud openhat+shaker |
| Perc ticks | syncopation | groove/drop/peak | 1–3 non-beat hits/bar, 2/4/8-bar call-response |
| Fills | transition punctuation | final bar pre-section | no timer fills |

Voice caps (excl. bass): groove 3–4 · break 0–1 · drop 4–5 · peak 5 max. [high]
Mature rhythm = velocity language, phrase mutes, rests before transitions,
call-response, density change every 8/16 bars — inside a SMALL roster. [high]

## B. Spectral allocation (mono below 120 Hz; no stereo reverb <250 Hz)

| Element | Owned band | Fences (HPF/LPF) |
|---|---|---|
| Kick body | 38–70 Hz | 25–30 / 120 |
| Kick click | 1.5–5 kHz | 1.2k / 7k |
| Sub bass | 60–110 Hz | 32–35 / 160–220 |
| Bass harmonics | 110–320 Hz | — / 280–350 |
| Tom/impact | 80–180 Hz | 45 / 600 (transitions only) |
| Pad body | 180–900 Hz | 150–180 / 3.5–4.5k |
| Chords | 250–1.8k | 180–220 / 3.5–4k |
| Lead | 600–4.2k | 300–400 / 4.2–5.2k |
| Arp | 900–5.5k | 500–700 / 5–6k |
| Clap/rim | 900–3.5k | 700–900 / 3.8–4.5k |
| Hats/shaker/ride | 5.5–12k | 4.5–6k / 12–14k |
| Reverb/delay returns | 300–5.5k | 250–350 / 5–6k |

"Do not solve lead/arp/chord conflicts with EQ alone — if two parts both want
1–5 kHz, one becomes background or rests." [high]

## C. Gain hierarchy (kick = 0 dB reference; linear = 10^(dB/20))

| Role | dB vs kick | Linear |
|---|---|---|
| Kick | 0 | 1.00 |
| Bass | −3 | 0.71 |
| Lead (foreground) | −8 | 0.40 |
| Break pad | −9 | 0.35 |
| Chords (break) | −10 | 0.32 |
| Chord stabs (drop/peak) | −16 | 0.16 |
| Arp | −14 | 0.20 |
| FX riser | −18…−6 ramp | 0.13–0.50 |
| Shaker/top bed | −18…−22 | 0.13–0.08 |
| Ride | −22 | 0.08 |
| Clap/rim shadow | −18…−24 | 0.13–0.06 |
| GM bed | ≤ −24 or **zero** | ≤0.06 |

Demo loudness targets: integrated ≈ −11 LUFS, drop short-term ≈ −9, true peak
≤ −1 dBTP, crest 7–9 dB. Master chain (sox): premaster `gain -n -6` →
`highpass 28` → soft-knee compand (6:-70,…,-4,-3) → `gain -n -1`. Render stems
24-bit, not int16. [high]

> **Taste-owner amendment (2026-06-07, take-8):** use the GENRE default, not
> the conservative demo target — techno/tech house masters run ~−8..−6 LUFS,
> significantly louder than vocal music. Master chain gained +9 dB makeup and
> a brickwall-ish limiter; achieved drop/peak RMS ≈ −10.8 dBFS (full-file
> −12.5), true peak −1 dB. Further pushes trade audible squash — ears decide.

## D. Coherence rules ("one instrument designed by one person")

- Shared oscillator family: sine lows, saw/pulse harmonics, filtered noise percussion.
- Shared saturation: gentle tanh on kick/bass/tom only (drive 1.2–1.8).
- Melodic LPF ≤ 5.5k; high-shelf −3…−6 dB above 6.5k everywhere.
- Shared LFO grid: 0.025 / 0.035 / 0.07 / 0.11 / 0.13 Hz.
- Shared chorus family: 11–23 ms delays, 2–5 ms modulation.
- One dark room: fake a shared send by summing melodic stems → HPF 280 / LPF
  5200 → one reverb → mix back at ≈ −18 dB.
- Foreground limit: lead OR full arp, never both. Pad and chords: one body, one detail.
- Brightness ownership: hats/air own >6 kHz; melodic parts do not fight them.

## E. Top 5 changes, ranked (status)

1. Wire the SC percussion kit, kill the GM bed → **done 2026-06-07**
2. Kill the every-bar 2&4 clap; shadow accents only → **done** (peak-only, every 4th bar)
3. Adopt the gain hierarchy; lower competing melodic layers → **done** (MIX_GAINS = table C)
4. Deterministic master bus (headroom + compression + normalize) → **done** (sox chain)
5. Coherence as hard generator rules (one top bed, one shimmer, one foreground,
   one room) → **partially**: levels/patches comply; generator-level role
   enforcement and the shared send bus remain open.
