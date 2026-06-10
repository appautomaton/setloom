<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# T02 Release Record: Anima Ex Machina

Committed safety copy of the release record. The package itself (master WAV,
320k preview MP3, cover art, raw reports) is local-only under `releases/T02/`
and never committed.

- Track: Anima Ex Machina
- Artist: App Automaton
- Format: melodic techno / progressive techno demo master
- Status: upload package frozen for SoundCloud, 2026-06
- Final source: completed `pass4c-fast-entry-fable` candidate

## Package inventory (local `releases/T02/soundcloud-upload/`)

- `App Automaton - Anima Ex Machina (SoundCloud Master).wav`
- `App Automaton - Anima Ex Machina (SoundCloud Preview 320k).mp3`
- `App Automaton - Anima Ex Machina cover.png`
- `qa-report.txt`, `comparison-report.txt`, `upload-notes.md`

## QA summary

- Duration 250.74 s, 44100 Hz.
- Master: peak -1.05 dBFS, true-peak estimate -1.02 dBTP, LUFS -8.11, stereo correlation 0.937.
- Source: peak -1.00 dBFS, LUFS -8.42.
- Segment loudness (LUFS): intro/groove bars 8-16 at -6.92; break/build 16-32 at -12.87; drop 32-48 at -7.04; second breath 56-72 at -8.21; peak reprise 72-104 at -6.61; outro 112-128 at -15.13.
- Fast-entry check: audible lead bed inside the first 4 seconds; lead bed plus bass answer by bars 4-8 (no kick-only intro).

## Production lineage

Implemented in the selected candidate: second breath around bars 60-71, peak
reprise around bars 72-104, cleaner top-groove layering, near/far percussion
choreography, and reduced boundary FX repetition. The pass4b completion raised
the bars 72-104 lead reprise and added breath/counterline material around bars
64-72. The pass4c completion fixed the overlong kick-only intro with an audible
same-family lead bed by bar 2 and a bass answer by bar 4. Deferred to a future
pass: deeper stereo-width redesign and a fully conductor-native rewrite.

Production note: this release used user-owned Logic Pro sample-library assets
routed through Setloom's Python/file-based orchestration; proprietary source
samples are never committed.
