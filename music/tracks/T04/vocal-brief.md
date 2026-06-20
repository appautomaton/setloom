<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# T04 Vocal Brief: "Nova Flamma"

Track name chosen at the naming gate (2026-06-10): **Nova Flamma** ("a new
flame", verse line 2). The sung hook remains "ad auroram" — title and hook
are deliberately different phrases.

Vocal-first design (2026-06-10). The sung lead is designed and locked before
any arrangement; groove, bass, and structure get built around it afterward.
The taste owner delegated stanza, voice, and length decisions to the agent.

## Lyric (original, rhymed trochaic Latin)

| Latin | English |
| --- | --- |
| Umbra cadit, nox recedit | The shadow falls, the night recedes |
| Nova flamma cor incendit | A new flame sets the heart alight |
| Inter astra somniamus | Among the stars we dream |
| Ad auroram navigamus | We sail toward the dawn |

- Form: 8 syllables per line, stress-based trochaic (strong syllable per beat
  at 4/4), rhyme AABB (-edit/-endit, -amus/-amus). Original text; quotes nothing.
- Hook chop: "ad auroram" — open vowels, built for sparse chopped accents.
- Arc: lines 1-2 belong to the breakdown, lines 3-4 lift into the drop.
- Vocal budget: one 8-bar stanza pass (~16 s at 123 bpm), sung in the break,
  hook returns at the drop; total vocal share stays inside the grammar's
  ≤ 0.15 lane. Repetition is the arrangement's job, not the lyric's.

## Vocal placement budget (132-bar / 4:18 streaming edit, 2026-06-10)

Taste-owner rule: the voice visits the track, never carries it ("we are NOT
making a pop song"). Budget: 0.15 × 132 = 19 vocal-active bars, all cut from
the one locked take. Intro ghost and outro echo are optional garnish only if
the total stays under budget.

| Placement | Bars | Material |
| --- | --- | --- |
| break_1 tease | 2 | chopped "ad auroram" accents, dry |
| drop_1 accents | 3 | sparse hook chops inside the groove |
| break_2 verse | 8 | the full stanza, once, intimate |
| peak hook return | 6 | whole hook, widest treatment |
| **total** | **19** | **0.14 share — inside the lane** |

## Reusable generation prompt (the sound-world constant)

Variation comes from seeds only; this caption is the controlled knob. If a
systematic trait is wrong, change one clause once and re-log here.

```
hypnotic melodic techno, dark and cinematic, ethereal female vocal singing a
short Latin verse, vocal only in the breakdown and the drop, instrumental
elsewhere, steady four-on-the-floor kick, rolling sixteenth-note bass pedal
locked to the root, dark evolving analog pads, sparse glassy arpeggio motif,
long atmospheric breakdown where the verse is sung, climactic drop where the
vocal hook returns, controlled low end, mixable club arrangement
```

Metas: bpm 123, keyscale A minor, vocal_language `la`, duration 120 (sketch),
thinking on (composition mode; takes are one-offs by design — keep the WAV).

## Vocal-lane caption (Recipe 1b, derived 2026-06-10)

Taste-owner directive: take 3's prompt is the asset — reuse it, but regenerate
voice-only at lyric length ("the generated audio is 2 minutes like 30s voice
for real"); melody differences across regens are accepted. Derivation: the
sound-world clauses kept, the band clauses swapped for a cappella. Lyrics are
`lyrics.la.txt` with the `[inst]` blocks stripped (verse + chorus only).

```
hypnotic melodic techno, dark and cinematic, ethereal female vocal singing a
short Latin verse, a cappella, voice only, no drums, no bass, no instruments,
intimate verse, anthemic vocal hook return, mixable club vocal lead
```

Metas: bpm 123, keyscale d minor (locked from take 3), vocal_language `la`,
duration 30 (beat math: 8-bar verse + 4-bar hook + tail at 123 bpm ≈ 28 s;
the first rolls at 50 s sang wall-to-wall — the model fills the canvas),
thinking on.

## Voice rationale

Ethereal female lead: corpus-anchored (the 8Kays & Delhia De France track in
the measured corpus is this exact formula) and spectrally complementary to
dark pads + rolling low end.

## Take log

| Take | Seed | Verdict |
| --- | --- | --- |
| latin-vocal-take1 | 4101 | reject — vocals smeared across the whole take, no structure |
| latin-vocal-take2 | 4102 | backup ("2 is good too") — strongest vocal presence, but front-loaded structure |
| latin-vocal-take3 | 4103 | **keep** — voice gate winner, 2026-06-10 |
| latin-vocal-xl4b-take1 | 4103 | tier A/B only (4B LM + XL DiT): drifted D major, off-brief; current tier stays default, big tier staged for atmosphere work |
| latin-vocal-clean-take1 | 4201 | technical flag — 50 s, no confident melodic line above 200 Hz (low drone, not a female vocal); pre-gate analysis, not a taste verdict |
| latin-vocal-clean-take2 | 4202 | awaiting gate — 50 s (oversized canvas: lyric stretched wall-to-wall), busiest melody D4-G4, ~5 notes/bar |
| latin-vocal-clean-take3 | 4203 | awaiting gate — 50 s (oversized canvas), sparse anthemic F4/A4, ~3 notes/bar |
| latin-vocal-clean-take4 | 4204 | passed over at gate (take 6 chosen) — 30 s, melody D4-A4, arrived pre-cut into 15.7 s verse + 11.7 s hook |
| latin-vocal-clean-take5 | 4205 | passed over at gate (take 6 chosen) — 30 s, melody D4-F4 |
| latin-vocal-clean-take6 | 4206 | **keep** — voice gate winner 2026-06-10 ("good style", melody approved); melody D4-G5, 99% D minor. Raw take leaked instruments despite the a-cappella caption (53-stem lens measured synth -19, bass -19, kick -27, drums -28 dBFS under the voice). Fix in `latin-vocal-clean-take6-tailfix.wav` (34.5 s): RoFormer lead-vocal + vocal layers only (sub-180 Hz now 0.0%, transients 0.2%), canvas-edge cutoff dissolved by fading the dry voice into an unfaded reverb send. Ear-check passed on the ending 2026-06-10 — **this file is the locked T04 voice lead**; it stays dry, spatial treatment is per-placement at mix time |

Stem acceptance (taste owner, 2026-06-10): take-3 demucs isolation approved —
"normal distortion, fixable with 混音 (mix effects) at mixdown." No xl-base
re-extraction needed unless the final mix gate says otherwise.

Voice gate verdict (taste owner): "i like take 3 lol feels like 'in the name of
love' Bebe Rexha vibe lol but 2 is good to!" — review-vocabulary read: emotive,
anthemic female vocal with melodic lift; spec sets melodic_emotion 8. Reference
artists are vocabulary only, never imitation targets.

Locked facts from take 3 (measured, not chosen): 123 bpm, **D minor** (the
model drifted from the A-minor meta; the vocal wins, the spec follows), vocal
active bars 1-17, 20-21, 24-25, 28-35, 39-43 of ~61; demucs vocal stem at
`local/corpus/stems/latin-vocal-take3/vocals.wav`.

After the voice gate: transcribe the vocal melody to MIDI, derive the lead
motif from its contour, and build the two-cycle club arrangement per
`spec.yml` — verse in break_2 (the main break), hook chops in break_1/drop_1,
hook return at peak.

## Arrangement build record (2026-06-10, full-autonomy session)

The track is assembled by `assemble.py` beside this brief — placements,
treatments, gains, and the master chain are all data in that file; re-running
it reproduces `local/candidates/T04/mix/nova-flamma-final.wav` byte-for-byte
from the engine stems, the two Magenta pads, and the locked voice.

Placements as built (vs the budget above): break_1 tease at bar 28 (P1,
wet-only reverb ghost, voice-to-bed −6.3 dB), drop_1 chops at bars 40/48/56
(P3 fragment, echo, chords+arp duck −2.5 dB opens the window), break_2 verse
at bars 76/79/83 (P1→P2→P3, intimate reverb, +6.1 to +8.7 dB), peak hook at
bars 96/98 and 104/106 (P4→P5 with the dissolve tail closing each pass,
dotted-eighth echo + wide reverb, +3.1 to +5.3 dB). Vocal share measured by
the arrangement audit: 0.10 (budget was 0.14; in the corpus near-absent band).

Voice-to-bed ratios are corpus-anchored: Human Nature's separated stems put
featured breakdown vocals at up to +8.5 dB, full-section vocals at +3 to +6,
ghosts at −5 to −10. Every placement sits inside its band.

Pads: Magenta RT 2, steered by embedding the engine's own chords+pad audio
(D minor by construction) blended with a text prompt — text-only prompting
landed in the wrong key (C#-centered) and is recorded as a dead end.
`t04-pad-main` (D-centered, Dm11 colors) carries grooves/drops/peak;
`t04-pad-break` (airier) carries both breaks; both high-passed at 160 Hz,
crossfade-looped per section. Intro/outro carry only the engine pad so the
edges stay mixable.

Master: glue compressor + 4x-oversampled limiter (chain in `assemble.py`),
−8.9 LUFS integrated (corpus window −9..−8), LRA 11.1, true peak −0.9 dBFS.
Streaming-edit deviations are deliberate: duration is 4.36 min, main break is
late at 0.55, and bass occupancy is lower because break_2 leaves room for the
voice.

Known quirk, deliberate exclusion: scrender still renders its internal lead
bus (`stem-lead*.wav`) even with the lead lane removed from the spec; the
assembly ignores those stems — the voice is THE lead.

## Reimagined production pass (2026-06-11)

The 2026-06-10 arrangement is now a legacy baseline, not the active T04
production recipe. The active build is:

- `music/tracks/T04/spec.yml`: current T04 track spec and track-specific groove
  plan.
- `music/tracks/T04/production.yml`: executable song production design —
  section intent, lane hierarchy, spatial widths, vocal placements, ducking,
  genai atmosphere spans, master target, and listening clips.
- `music/tracks/T04/assemble.py`: manifest renderer, not the arrangement
  itself.

Retained fact: `local/candidates/genai/latin-vocal-clean-take6-tailfix.wav`
remains the locked female voice source. Retired facts: the old smoke-test
T04 stems/report and any T02-derived bed are not production truth. Current
MIDI/stems must be regenerated from the T04 spec before audition.

Active v2 outputs:

- full master: `local/candidates/T04/mix/nova-flamma-reimagined-v2-master.wav`
- no-voice twin: `local/candidates/T04/mix/nova-flamma-reimagined-v2-novoice.wav`
- listening clips: `local/candidates/T04/auditions/reimagined-break1-tease.wav`,
  `reimagined-drop1-body.wav`, `reimagined-mainbreak-fullverse.wav`,
  `reimagined-peak-hook.wav`

Technical checks are supporting evidence only. Current musical truth for T04
lives in the spec, production config, source code, locked vocal file, and human
listening notes.
