<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Contributing

Setloom is for people who want to make club music without the studio getting in
the way: independent developers, producers, and the technically curious. If that
is you, welcome. Code, documentation, and good questions are all appreciated.

## What we value

A few principles shape everything here, and they are worth knowing before you
start.

- **The human is the taste owner.** Tools and agents propose; a person listens
  and decides. Keep the listening gate intact: never let a script or a model
  become the final word on whether music is good.
- **Reproducible over opaque.** Prefer source you can re-run to artifacts you
  cannot. Specs, MIDI, render code, and notes travel with the work; large or
  copyrighted binaries do not.
- **Open and keyboard-first.** Favor open-source, scriptable tools over manual
  clicking. Python is the control plane.
- **References are study, not law.** Treat reference tracks as review vocabulary
  and abstract moves to learn from, never as templates or genre rules.

## Getting oriented

Start with [docs/README.md](docs/README.md), then open only the doc the task
needs. [AGENTS.md](AGENTS.md) holds the operating rules for coding agents and is
worth reading even if you work by hand. Run everything through the repo-local
`uv` environment:

```bash
uv run --group dev pytest          # behavior tests (add --group transcription or anatomy for ML paths)
uv run --group dev ruff check src  # lint
```

## What makes a good contribution

- Clear, high-signal English in docs and prompts.
- Behavior covered by a test, or a note on why it cannot be.
- No proprietary samples, unlicensed sample packs, model weights, or copyrighted
  audio, anywhere in the tree.
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
