<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# T04 Vocal Brief: "Ad Auroram"

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

Voice gate verdict (taste owner): "i like take 3 lol feels like 'in the name of
love' Bebe Rexha vibe lol but 2 is good to!" — review-vocabulary read: emotive,
anthemic female vocal with melodic lift; spec sets melodic_emotion 8. Reference
artists are vocabulary only, never imitation targets.

Locked facts from take 3 (measured, not chosen): 123 bpm, **D minor** (the
model drifted from the A-minor meta; the vocal wins, the spec follows), vocal
active bars 1-17, 20-21, 24-25, 28-35, 39-43 of ~61; demucs vocal stem at
`anatomy/_stems/latin-vocal-take3/vocals.wav`.

After the voice gate: transcribe the vocal melody to MIDI, derive the lead
motif from its contour, and build the two-cycle club arrangement per
`spec.yml` — verse in break_2 (the main break), hook chops in break_1/drop_1,
hook return at peak.
