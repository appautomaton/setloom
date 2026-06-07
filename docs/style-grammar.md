<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Style Grammar

Style grammar turns taste references into constraints that agents and generators can use.

Setloom does not ask agents to copy artists. It extracts musical dimensions from references and uses those dimensions to guide generation, tuning, and review.

Executable style packs live under `style-packs/`. This document explains the first grammar; it is not the source of truth for automation.

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
- Phrase length: 16 or 32 bars.
- Kick: four-on-the-floor, stable, controlled, not generative-chaotic.
- Bass: mono-aware, rhythmically locked, sidechain-friendly.
- Melody: motif-based, sparse enough to survive club repetition.
- Breaks: emotional, but not so long that the set loses motion.
- Arrangement: intro and outro must be DJ-mixable.

## Review Vocabulary

Use these terms consistently:

- Too busy: too many events compete for attention.
- Too flat: energy does not lift across sections.
- Too EDM: drop or hook feels over-signaled, obvious, or festival-pop.
- Too static: loop works but does not evolve.
- Not club-functional: the track is hard to mix, weak on low end, or lacks phrase clarity.
- Low-end conflict: kick and bass compete in timing, tuning, length, or spectral space.
