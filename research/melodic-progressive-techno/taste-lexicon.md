<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Taste Lexicon: Review Words → Measurements → Knobs

One row per `review_vocabulary` term in `style.yml`. **Sounds like** stays open until the taste owner fills it from listening sessions; that column is the human half of the contract. **Measures as** names the dossier metric (see `dossier-guide.md`) when one exists today. **Knob** is where a revision request lands in the generator.

| Term | Measures as (today) | Knob to turn |
| --- | --- | --- |
| `too_busy` | `drums.high_perc_onsets_per_bar_groove` and `other.onset_rate_per_bar` above corpus norms | percussion densities (`parts/drums.py`, `shaker.py`, `clap_ride.py`); `max_competing_melodic_layers` |
| `too_flat` | low variance across `energy_curve_16bar` sections | conductor energy curve contrast *(conductor change, deferred)* |
| `too_edm` | not yet measured (no riser/drop-signal detector) | `parts/fx.py` riser/impact frequency; fills restraint |
| `too_static` | `harmonic_changes_per_16bars` ≈ 2 plus unvarying chord list | harmonic mode selection; lead variation rate (`parts/lead.py` gestures) |
| `not_club_functional` | executable gates: `club-length`, `unmixable-edges`; low `kick_coverage` | duration profile; intro/outro bars in section model |
| `low_end_conflict` | not yet measured (kick/bass overlap needs per-stem timing compare) | bass sidechain gap (`parts/bass.py`); kick/bass register split |
| `weak_pump` | partially: `bass.step_occupancy` ≈ 1.0 with no kick-beat gaps | bass note gaps before beats; sidechain recovery shape |
| `overfilled_low_mids` | not yet measured (needs 120–400 Hz per-stem energy) | pad/chords register and voicing |
| `too_preset_arp` | not yet measured (arp phrase-motion metric) | arp contour selection (`parts/arp.py`) |
| `break_loses_floor` | main-break span vs corpus 8–43 bars; break start vs 0.42–0.48 | section-model break lengths |
| `no_phrase_payoff` | section boundaries off 16/32-bar multiples | conductor phrase clock and boundary snapping |
| `palette_incoherence` | not measurable from dossiers; ears only | scrender layer palette coherence rules |
| `tech_minimal_collapse` | not yet measured (lead density/variation metric) | lead gesture development (`parts/lead.py`, `counterline.py`) |
| `independent_backgrounds` | future: inter-stem energy-envelope correlation | conductor shared space plan |
| `drum_monotony` | partially: per-phrase variance of high-perc density | fills purpose rules; section-dependent percussion roles |

## Sounds like — listening column

Fill during audition sessions, one short quote per term, citing track and bars (e.g. `too_busy: "T01 v2 bars 65–80, hats fight the arp"`). Keep entries here so the future listening-notes consumer can pair your words with these metrics.

*(all entries open as of 2026-06-10)*
