<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Cross-Model Review: Codex (GPT-5.5), 2026-06-07

Provenance: produced by OpenAI Codex CLI (GPT-5.5) in a read-only run over this
repository (session 019ea271-279b-7cc3-8ea4-e3b1b9e19261, 51 commands, no file
writes). **No live web search was used** — sections A and C are the model's
training-period domain knowledge and are treated as `model-knowledge` evidence:
they raise assumption quality but do not become corpus facts without
corroboration or a listening verdict.

## Triage status (coordinator, 2026-06-07)

| Finding | Status |
|---|---|
| section_model 288-bar overshoot | Convergent with validator finding; fixed via `section_model_presets` (grammar v2) |
| Home double-count (marino-canal + adriatique) | Verified true; deduped in corpus + findings stats |
| Arodes Beyond artist-page citation | Web-verified 2026-06-07: page lists "Beyond - Extended Mix" 124 BPM — corroboration stands |
| Euphoria year/label era | Web-verified 2026-06-07: released 2024-11-01 on [PIAS] Électronique — model knowledge confirmed |
| Jan Blomqvist original/remix conflation | Plausible; flagged in corpus unknowns, routed to worksheet |
| Grammar additions (groove/harmony/tension blocks, vocab, rules) | Folded into style.yml as `model-knowledge` assumptions (grammar v2) |
| Generator P1 critiques | Implemented in generator v2 (same change) |

---

## A. Style grammar review (knowledge-based)

1. `style.yml` captures the lane directionally, but it is still metadata-shaped, not yet music-shaped.

- `bpm_range: [120, 125]` is right for the starting lane and safer than `[122,126]`; 123 BPM is a good center. Expansion profiles should allow soft overrides down to 118 and up to 128 for vocal/organic or peak-time variants. [confidence: high]
- `key_mode_bias: minor` is correct, but too coarse. This lane often uses minor tonality, modal ambiguity, suspended chords, pedal tones, and occasional bright major-center records, especially on the progressive/melodic-house side. [confidence: high]
- `section_model` is the biggest structural problem: `32+32+32+64+32+64+32 = 288 bars`, which is about 9.2–9.6 minutes at 120–125 BPM. That conflicts with the pack's 5.5–8.5 minute target and 9-minute rejection rule. [confidence: high]
- `style_vector_defaults`: `darkness: 8`, `melodic_emotion: 7`, `groove_hypnosis: 8`, and `cinematic_tension: 7` fit the Afterlife-adjacent center. `arrangement_patience: 9` is high unless this is explicitly an extended-mix profile. `vocal_presence: 1` and `organic_texture: 2` understate the expansion anchors. `peak_time_pressure: 6` is conservative for the Massano/modern peak-time side. [confidence: high]
- `review_vocabulary` is useful but generic. It needs lane-specific terms: weak pump, overfilled low mids, too preset-arp, break loses the floor, no phrase payoff, too bright/cheesy, not hypnotic enough. [confidence: high]
- `rejection_rules` cover the core gate, but `low-end-conflict` is only partly enforceable by MIDI onset separation. This lane needs rules for sidechain-shaped space, bass note length, top-loop density, melodic layer count, and break/drop floor continuity. [confidence: high]

2. Missing grammar dimensions:

- Bass articulation: offbeat eighth pulse, rolling sixteenth sub, syncopated pedal, root/fifth pickups, and per-section contour. [confidence: high]
- Sidechain pump as rhythm, not just a mix fix: attack/recovery shape, kick-duck depth, and bass release time. [confidence: high]
- Percussion character: offbeat open hat, 16th shaker/top-loop bed, restrained claps, metallic ticks, noise/impact accents. [confidence: high]
- Breakdown construction: kickless emotional break, kick-under-break, motif reveal, pad swell, false drop, and re-entry timing. [confidence: high]
- Tension devices: filter-open automation, risers, reverse reverb, snare/hat rolls, arp density ramps, delay throws. [confidence: high]
- Sound palette descriptors: mono sub, rounded/reese bass, wide dark pads, plucked metallic arps, granular/vocal texture, cinematic impacts. [confidence: high]
- Groove swing/shuffle and velocity contour: usually subtle, but top loops should not feel perfectly flat. [confidence: medium]
- Subprofiles: deep progressive, dark hypnotic, peak-time pressure, organic/vocal crossover. One scalar vector cannot cover all anchors cleanly. [confidence: high]

3. Proposed `style.yml` additions/changes (YAML drafts as delivered; folded into grammar v2 with model-knowledge tags):

- `generation_defaults`: `default_bpm: 123`, `bpm_soft_outliers: [118, 128]`, `key_mode_weights` (minor 0.67 / major 0.25 / ambiguous_or_suspended 0.08), `section_model_presets` — `club_default_224` (32/32/16/48/16/48/32) and `extended_peak_256` (32/32/32/64/32/32/32). Basis: 224–256 bars stays in the 7.2–8.5 minute club-edit zone at 120–125 BPM while preserving 16/32-bar phrasing. [confidence: high]
- `groove`: bass_articulation_weights (rolling_16th_sub 0.45 / offbeat_eighth_pulse 0.35 / syncopated_pedal 0.20), sidechain (required, duck_on_kick_beats, recovery_shape medium_slow), percussion (offbeat_open_hat optional, closed_hat_16th_bed section_dependent, random_percussion phrase_patterned_only, swing_amount [0.00, 0.06]). Basis: the lane's drive comes from controlled bass/pump/top-loop interaction. [confidence: high]
- `harmony_and_melody`: harmonic_rhythm_bars [4, 8, 16]; chord_colors (minor_triad, sus2, sus4, add9, no_third_power_stack); lead_density (break sparse_to_medium, drop sparse, peak medium_with_repetition); motif_policy (repeat_then_vary, max_competing_melodic_layers 2). Basis: melodic-techno hooks work through repetition, restraint, modal color, gradual variation. [confidence: high]
- `arrangement_tension`: breakdown_devices (filtered_pad_swell, motif_reveal, kick_drop_or_kick_under, noise_riser, false_drop); drop_entry_devices (bass_return, arp_density_lift, cymbal_or_noise_impact); automation_lanes_required (filter_cutoff, reverb_send, delay_feedback, arp_density). Basis: breakdown/drop identity in this lane is mostly automation, density, and tension management. [confidence: high]
- `review_vocabulary` additions: weak_pump, overfilled_low_mids, too_preset_arp, break_loses_floor, no_phrase_payoff. [confidence: high]
- `rejection_rules` additions: melodic-layer-overload (max two foreground melodic layers in drop/peak), weak-pump (bass note length/onset pattern leaves no kick-duck space), unphrased-fills (fills without section or phrase-transition purpose); all `basis: assumption`. [confidence: high]

## B. Corpus sanity check

(No live web verification in this pass; flags beyond the already-noted 'Look At You' match and three key conflicts.)

- `Home` is double-counted: `marino-canal.yml` and `adriatique.yml` include the same Adriatique/Marino Canal/Delhia de France record. Aggregate BPM/key/duration stats should dedupe it. [confidence: high]
- `jan-blomqvist.yml` likely conflates original/remix metadata for `The Space In Between`: the profile source names the Ben Böhmer extended remix, while the track title is recorded as the base original. Treat the 2018/120 BPM value as remix-specific unless verified. [confidence: medium]
- `arodes.yml` marks `Beyond (Extended Mix)` BPM as corroborated, but one source is an artist-level SongBPM page rather than a track-specific source. Downgrade unless the exact track value is visible. [confidence: high] *(Coordinator: visible — verified, stands.)*
- `arodes.yml` uses only 2026 collaborations: weak as a style anchor; older signature material needs a deeper pass. [confidence: medium]
- `miss-monique.yml` `Hacienda Na Xamena 2025-12-05`: venue/date combination worth checking for listing-date ambiguity. [confidence: medium]
- `innellea.yml` `Euphoria` year unknown: domain expectation is the 2024 Belonging/[PIAS] era. [confidence: medium] *(Coordinator: confirmed 2024-11-01.)*

## C. Generator musicality critique

- **Drums**: four-on-the-floor is characteristic; offbeat-only hats are neutral/basic; independent 5% random percussion is an anti-pattern (no phrase logic). P1: 2/4/8-bar percussion patterns, 16th shaker/hat beds with velocity contour, section-aware density. P2: open hats, rides, crashes/noise impacts at phrase entries. P3: subtle top-loop microtiming. [confidence: high]
- **Bass**: root offbeat eighths are characteristic for part of the lane but too narrow for the Afterlife/melodic-techno center. P1: articulation profiles (rolling 16ths, offbeat pulse, syncopated pedal) selected by `bass_aggression` and `peak_time_pressure`; shorten notes / encode sidechain gaps so the bass breathes around the kick. P2: rare fifth/octave pickups near phrase turns. [confidence: high]
- **Chords**: whole-bar tonic triads acceptable in breaks, static and cluttered in drops/peaks. P1: 4/8/16-bar progressions, suspended/add9/no-third colors, voice-led inversions; pads in breaks, filtered stabs or reduced density in drops. P2: thin chords when arp and lead are active. [confidence: high]
- **Arp**: continuous 16th ascending triad arp sounds preset-like as a default. P1: phrase-gate with rests, accents, density ramps, automation hooks; rhythmic cells (3-3-2, dotted pulses, octave pedals). P2: mute or simplify under lead motifs. [confidence: high]
- **Lead**: sparse motif placement directionally right; one-bar motifs at the start of every 8-bar block too mechanical. P1: 2-bar motif family with repeat-then-vary over 16 bars; placement around breakdown reveal, pre-drop tension, peak response. P2: contour targets and resolution notes. [confidence: high]
- **Fills**: snare/tom runs every 16th bar is the clearest anti-pattern (generic EDM/rock-derived). P1: section-transition-aware only; silence, filtered noise, reverse reverb, hat/snare rolls, restrained impacts. P2: reserve toms for rare peak moments. P3: fill family by energy/tension profile. [confidence: high]
- `generate.py` aligns with Setloom's posture (deterministic variants + listening gate). Reports should add musical diagnostics beyond note counts: bass articulation profile, melodic layer count, section density, fill locations, unresolved listening questions. [confidence: high]
