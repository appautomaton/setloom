<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Style Grammar

Style grammar turns taste references into constraints that agents and generators can use.

Setloom does not ask agents to copy artists. It extracts musical dimensions from references and uses those dimensions to guide generation, tuning, and review.

Executable style packs live under `music/packs/`. This document explains the first grammar; it is not the source of truth for automation.

Today the generators and the rejection gate consume only part of the pack: `generation_defaults.bpm_range`, `generation_defaults.duration_profiles`, and `rejection_rules`. The remaining sections carry review vocabulary and target constraints that are not yet machine-enforced.

Style packs are not per-song arrangement plans. Reference-derived metrics such
as bass occupancy, phrase grid, and low-end safety constrain candidates, but a
track's `spec.yml` owns its specific groove/generator choices. When a track
needs a distinct drum or bass identity, encode that as a track-level groove
plan instead of stretching one style-pack cell across every song.

## Starting Style Pack

```text
melodic-progressive-techno
```

The starting lane is dark, melodic, progressive, and club-functional.

## Reference Anchors

| Anchor | Grammar Signal |
| --- | --- |
| Innellea | Cinematic tension, dramatic synth movement, darker emotional peaks. |
| Colyn | Elegant melodic lift, wide atmosphere, clean progressive flow. |
| 8Kays | Dark drive, hypnotic groove, controlled aggression. |
| Marino Canal | Deep progressive structure, smooth tension curves. |
| ENAI | Punchier modern melodic techno energy. |
| Jono Stephenson | Emotional melodic hooks, polished club arrangement. |
| Miss Monique | Long-form set flow, accessible melodic progression. |

Expansion anchors:

| Anchor | Grammar Signal |
| --- | --- |
| WhoMadeWho | Organic and vocal-forward electronic emotion. |
| Arodes | Warm melodic house flow and restrained dancefloor drive. |
| Massano | Peak-time melodic techno pressure and direct impact. |
| Jan Blomqvist | Vocal-led electronic songcraft and live-set crossover. |
| Adriatique | Sophisticated melodic/deep structure and controlled atmosphere. |

## Style Vector

Example:

```yaml
style_vector:
  darkness: 8
  melodic_emotion: 7
  groove_hypnosis: 8
  cinematic_tension: 7
  bass_aggression: 6
  arrangement_patience: 9
  hook_density: 5
  vocal_presence: 1
  organic_texture: 2
  peak_time_pressure: 6
```

## Generation Defaults

Starting defaults:

- BPM: 122 to 126.
- Meter: 4/4.
- Phrase grid: 8-bar local movement, with larger payoffs on 16/32-bar boundaries.
- Kick: four-on-the-floor, stable, controlled, not generative-chaotic.
- Bass: mono-aware, rhythmically locked, sidechain-friendly, split into kick, sub, rumble, and mid-bass roles.
- Melody: motif-based, sparse enough to survive club repetition, but never reduced to a short mechanical loop when there is no vocal.
- Breaks: emotional, but not so long that the set loses motion.
- Arrangement: intro and outro must be DJ-mixable.

## Reference-Derived Production Rules

The first melodic/progressive techno grammar now treats production as an ensemble system, not a pile of isolated tracks.

Reference anatomy and listening gates showed these hard rules:

- Low-end removal and restoration are the main dramatic device.
- Breaks should collapse or thin the low end while widening upper atmosphere.
- Drops should restore centered, mono-compatible low end while keeping upper material controlled-wide.
- Peak sections should open presence and air without sacrificing low-end safety.
- Layers must rotate roles. They should not all become maximal at the same time.
- Reverb and delay should usually live on shared, ducked space returns, not as static global wash.
- Drum production needs role separation: near kick/body, top groove, offbeat/open hat, shaker motion, far/room accents, fills, impacts.
- If the track has no vocal, the lead must act as the emotional foreground. A two-bar classical or MIDI-like motif is not enough; it needs phrase-level development, call-response, counterline, and repeat variation.

## Conductor-First Writing

Melodic/progressive techno generation should be driven by a shared conductor, not independent part loops. The conductor owns:

- `PhraseClock`: 8-bar local grid plus 16/32-bar payoff boundaries.
- `HarmonicTimeline`: chord degree, color, and harmonic rhythm by bar.
- `EnergyCurve`: section and phrase-level lift.
- `SpacePlan`: which section owns foreground, motion, bed, and shared ambience.

Part generators should read this shared state. Chords, lead, counterline, arp, drums, FX, and tonal bass support should not each invent their own phrase logic. The sub/rumble lane is the exception: it must stay pedal-safe and mono-stable while higher bass or tonal support carries harmonic movement. A candidate with impressive sound design but no shared conductor tends to collapse into tech-minimal: strong groove, weak melodic identity.

Track-specific groove plans are the bridge between corpus grammar and actual
composition. They may customize bass cells, percussion phrase patterns, and
section-level variation while preserving kick/bass separation and sidechain
space. A generator should reject unsafe timing, not erase a track's identity by
falling back to the same global loop.

## Review Vocabulary

Use these terms consistently:

- Too busy: too many events compete for attention.
- Too flat: energy does not lift across sections.
- Too EDM: drop or hook feels over-signaled, obvious, or festival-pop.
- Too static: loop works but does not evolve.
- Not club-functional: the track is hard to mix, weak on low end, or lacks phrase clarity.
- Low-end conflict: kick and bass compete in timing, tuning, length, or spectral space.
- Tech-minimal collapse: groove and low end work, but melodic identity is too short, static, or underdeveloped for melodic techno.
- Independent backgrounds: atmosphere, classical material, and FX feel like separate loops rather than one arrangement system.
- Drum monotony: drums are loud or heavy, but lack near/far depth, phrase accents, top-groove evolution, or transition-purpose fills.
