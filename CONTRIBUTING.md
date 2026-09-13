<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Contributing

Setloom is for people who want to make club music without the studio getting in
the way: independent developers, producers, and the technically curious. If that
is you, welcome. Code, documentation, and good questions are all appreciated.

## What we value

A few principles shape everything here, and they are worth knowing before you
start.

- **Agents own production quality; humans judge the result.** Bring musical
  taste and creative judgment. A rejected result needs substantive revision;
  scripts and measurements do not override the listener's verdict.
- **Reproducible over opaque.** Prefer source you can re-run to artifacts you
  cannot. Specs, MIDI, render code, and notes travel with the work; large or
  copyrighted binaries do not.
- **Tools serve understood operations.** Favor open, scriptable tools for
  repeatable work and use authorized UI control where needed. Musical analysis,
  voice grouping and sound design still require patient hands-on work.
- **Follow the musical brief.** Study the actual recording or performance.
  Faithful reconstruction, reinterpretation and composition need different
  decisions; previous-track recipes and reports do not settle them.

## Getting oriented

Start with [docs/README.md](docs/README.md), then open only the doc the task
needs. [AGENTS.md](AGENTS.md) holds the operating rules for coding agents and is
worth reading even if you work by hand. Run everything through the repo-local
`uv` environment:

```bash
uv run --group dev --group anatomy --group transcription pytest  # full behavior suite on Apple Silicon
uv run --group dev ruff check src  # lint
```

## What makes a good contribution

- Clear, high-signal English in docs and prompts.
- Behavior covered by a test, or a note on why it cannot be.
- Keep audio, proprietary samples and model weights out of Git. New working
  material belongs in `tmp/`; retained assets follow [working stages](docs/workflow.md#working-stages).
- Changes scoped to what you set out to do, with the workspace left clean for the
  next person.

## Sign your work

Setloom uses the Developer Certificate of Origin. Add a sign-off line to each
commit:

```text
Signed-off-by: Your Name <you@example.com>
```

`git commit -s` adds it for you. The sign-off means you have the right to submit
your contribution under the project licenses (see [LICENSES/](LICENSES/)).

Thank you for helping Setloom stay open, honest, and a pleasure to work in.
