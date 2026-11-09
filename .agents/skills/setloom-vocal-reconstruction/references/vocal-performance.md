<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Vocal performance

## Interpret a phrase

Inspect the original phrase, its entrance and released ending, with relevant
estimates as supporting evidence. Establish which components move independently:
lead, response, double, harmony or effect return. A separator's back-vocal label
does not identify another singer; harmonic peaks do not establish more notes.

Follow the fundamental through ornaments, register changes and weak passages.
The strongest partial may change while the sung pitch continues. Check octave
alternatives against harmonic motion and exposed passages. Preserve meaningful
slides, vibrato, re-attacks and breath gaps; do not quantize away an ornament or
connect unrelated syllables merely to smooth a tracker.

For intelligible words, establish language and review uncertain text against the
recording before phonetic alignment. Speech recognition supplies candidates, not
verified lyrics, phonemes or musical timing. Preserve uncertainty where it could
change pronunciation; do not replace unknown syllables with invented words.

## Choose an editable representation

| Vocal behavior | Representation |
| --- | --- |
| A distinct pitched attack or intentional repeated note | Note event with timing and expression. |
| Sliding, vibrato or inflection within a syllable | Continuous pitch control where voiced; retain unvoiced intervals separately. |
| Changing vowel colour, effort or spectral tilt | Resonance and excitation controls; their motion may continue at one pitch. |
| Consonant, aspiration or breath | Timed articulation and suitable voiced or unvoiced excitation. |
| A continuing response, harmony or double | Independently controlled voice when source behavior supports it. |
| A delayed repeat or spatial tail | Effect response and its decay, without inventing fresh sung notes. |

These are representational choices, not required tracks. Pitch, articulation and
resonance can share one instrument while retaining different control clocks.
Distinguish phoneme boundaries from note boundaries: one vowel can span several
notes, and several syllables can share one pitch.

## Choose a voice model

Harmonic synthesis with stochastic excitation can recover pitched contour,
vowel colour and breath from measured behavior. Coordinate partial phases for a
shared voiced excitation rather than independently restarting every fragment.
Changing harmonic magnitudes can approximate formant motion; broad noise alone
cannot reproduce the identity and timing of consonants.

Source-filter synthesis, an independent voice sampler or a singing model may
supply useful articulation when its actual controls support the brief. Choose
among available renderers by their response to pitch, phoneme duration,
transitions and expression; an attractive isolated vowel does not prove
that the renderer can perform the phrase. No particular model or partial count
is a default requirement.

For independent resynthesis, the renderer must perform the recovered events and
controls without replaying the original waveform or source phase. Retain editable
inputs sufficient to repeat that performance.

Use the recording to inform dynamics and timbre without treating separated
amplitudes as original faders. Check the combined path through note gates,
velocity, envelopes and effects: plausible controls can suppress the same event
twice. Preserve voiced continuity without forcing breath, diction and spatial
decay through the same note-off envelope.

## Diagnose the performed difference

| Difference | Investigate before choosing a correction |
| --- | --- |
| Stepped, chopped or doubled phrasing | Pitch fragments, syllable continuity, shared estimates and overlapping releases. |
| Hollow, washed-out or synthetic tone | Source attenuation, partial relationships, excitation, resonance motion and stereo interaction; compare the original as well as the estimate. |
| Recognizable melody but unclear words | Transcript, phonetic content, consonant excitation and syllable-to-note alignment. More harmonics cannot supply missing articulation. |
| A reply sounds like an extra lead | Independent contour versus delay or leakage, plus its original prominence and timing. |
| Ending sounds cut off or becomes another note | Direct vocal release, breath and effect return ownership. |

Verify the correction in the complete phrase and its transition at comparable
playback level. Preserve the supported performance while changing the failed
explanation. Record whether the result recovers contour, articulation or timbre;
do not treat improvement in one as proof that all three are complete.
