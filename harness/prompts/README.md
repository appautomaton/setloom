<!-- SPDX-License-Identifier: AGPL-3.0-only -->

# Harness Prompts

This directory contains starter prompts for Setloom agents.

Prompt files are part of the harness and are licensed under AGPL-3.0-only.

## Status

These files are role contracts, not wired agents. No automated dispatch invokes
them yet: the current pipeline is the deterministic `setloom` CLI plus a human
listening gate, and any agent following these contracts is launched manually.
Treat them as the target shape for future orchestration work.

## Prompt Rules

- Write in clear English.
- Prefer structured outputs over prose.
- Separate automated checks from human listening judgment.
- Never claim a track is final without a listening gate.
- Do not imitate artists. Extract style grammar.
- Preserve editable artifacts: MIDI, stems, specs, reports, and notes.

