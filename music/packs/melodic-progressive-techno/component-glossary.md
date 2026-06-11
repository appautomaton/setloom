<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Component Glossary: Melodic Techno Layers

Shared language for listening notes and reviews. The taste owner names what they hear with these terms; agents map them to dossier metrics (`dossier-guide.md`) and review words (`taste-lexicon.md`).

One prerequisite term: **timbre** is the character of a sound — what makes two instruments playing the same pitch at the same loudness still sound different. In synthesis, timbre comes from waveform, filter, envelope, and effects. Patch libraries (including Logic Pro's, used as a local reference surface only) are organized by timbre category: pads, plucks, leads, basses.

**Stem today** shows where each component lands in the current demucs 4-stem separation. **Owner** is the harness layer responsible per `AGENTS.md`: deterministic rules, GenAI, or mix engineering.

## Layer 1 — Foundation (rhythm and low end)

| Component | Role | Stem today | Owner |
| --- | --- | --- | --- |
| Kick | Four-on-the-floor pulse, ~50–100 Hz. Breakdowns are defined by removing it; lone accent kicks inside a break are a corpus signature (`anatomy-findings.md`) | drums | deterministic |
| Bass | Low melodic voice, ~40–120 Hz. In this lane usually a rolling pedal bass: repeated 16th-notes on the root, 0.75–0.93 step occupancy per corpus | bass | deterministic |
| Percussion | Hi-hats (closed/open), claps, rides, shakers. Off-beat placement creates the bounce between kicks | drums | deterministic |

## Layer 2 — Harmonic and melodic (the emotional core)

| Component | Role | Stem today | Owner |
| --- | --- | --- | --- |
| Pad | Sustained, slowly evolving chords; soft attack, wide stereo. The atmospheric bed — perceived warmth or melancholy mostly lives here | other | GenAI |
| Lead | The main melodic voice; the motif you remember. Often plucky or lightly distorted | other | GenAI |
| Arp | Chord notes played one at a time in a repeating pattern; sequencer-driven hypnotic motion | other | GenAI |
| Pluck | Short percussive melodic notes, fast decay; melodic and rhythmic at once, often with heavy delay | other | GenAI |
| Stab | Short rhythmic chord hit; punctuation in the groove | other | GenAI |
| Drone | One sustained unchanging tone; tension floor under breakdowns | other | GenAI |

## Layer 3 — Texture and motion (transitions and space)

| Component | Role | Stem today | Owner |
| --- | --- | --- | --- |
| Atmosphere | Noise beds, field recordings, textures; makes the track feel like a place | other | GenAI + engineering |
| Riser / uplifter | Sweep climbing in pitch or loudness over 4–16 bars; announces the drop | other | engineering |
| Impact / downlifter | Boom or falling sweep at a phrase boundary; lands the arrival | other | engineering |
| White-noise sweep | Filtered noise washing up or down; the standard transition tool | other | engineering |
| Vocals | In this lane: chopped phrases, heavily reverbed, more texture than song. Corpus is bimodal: near-absent (0.01–0.14 share) vs featured collab (0.34–0.54) | vocals | GenAI (ACE-Step a-cappella lane, Recipe 1b) — T04 uses a generated voice as THE lead, placed per a bar budget at the low end of the corpus range (0.10 share) |

## The "other" bucket

Everything in layers 2–3 collapses into one demucs stem for energy accounting. Since the layer lens shipped (`setloom anatomize --layers`, change 2026-06-10-anatomy-layer-lens), the lump is also dissected per track into named layers — synth, keys, kick, snare, hh, toms and more — with per-layer dossiers and melodic MIDI. The lens layers are overlapping extractions (not a partition), so demucs keeps the accounting job; see `dossier-guide.md` for how to read both.

## Using this in listening notes

Name the component, the section, and the direction: "pad too thin in the main break", "lead needs more bite at the drop", "riser overstays into bar 97". Sentences in that shape map directly onto taste-lexicon rows and generator knobs.
