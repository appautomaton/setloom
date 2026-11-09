---
name: setloom-vocal-reconstruction
description: Reconstruct a recorded vocal performance as editable phrasing, articulation and sound. Use for singing, chants or spoken vocals with mismatched contour, diction, tone or phrase behavior; not lyrics-only transcription.
---

<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Setloom Vocal Reconstruction

Recover how the voice performs a phrase, then choose a sound model that can
realize it. Melody, intelligible words and vocal character are distinct goals;
let the brief determine which must be preserved.

The primary agent owns source interpretation, vocal design and fidelity review.
Do not delegate these judgments. Inspect original and rebuilt passages directly
using available auditory and time-frequency evidence; playback does not establish
hearing.

- Interpret phrase continuity, pitch motion, syllable articulation and breath
  together. A detector fragment, harmonic or released tail need not be a new
  note or another singer.
- Separate independently moving vocal lines when supported. Reconcile overlapping
  estimates and effects before adding voices; use the original mix to judge
  prominence and space.
- Match representation to behavior: notes for discrete pitch events, continuous
  controls for inflection and tone, articulation for words, effects for returns.
  MIDI alone does not describe a complete vocal performance.
- Choose the renderer for the gesture. When pitch is supported but the voice
  still fails, investigate excitation, resonance, articulation and routing before
  adding notes or compensating layers.
- Judge phrase identity and timing in ensemble, using solos to locate differences.
  Vowel resemblance does not establish intelligible lyrics or the singer's exact
  timbre; spectral agreement does not establish listening success.

Read only what the question needs:

- [Vocal representation and sound](references/vocal-performance.md): phrase
  inference, renderer choices and vocal mismatch diagnosis.
- [Shared source evidence](../../../docs/reconstruction.md#representation-and-provenance):
  ambiguous ownership and reconstruction provenance.
- [Words and language](../../../docs/tooling.md#vocal-words-and-phrasing):
  when lyrics or syllable timing require speech recognition.

Keep interpretation, controls and renderer settings with the track. Distinguish
reference playback or retained audio from a newly generated performance.
