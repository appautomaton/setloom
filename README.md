<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Setloom

Music production has a gatekeeper: the interface. The piano roll, the plug-in
maze, the mixing-desk vocabulary: decades of craft stacked between you and the
idea already playing in your head. Setloom removes the gatekeeper.

You bring taste. The agent brings labor. It writes each track's source, renders
the audition, and inspects the result; you listen and say what's wrong. You
never open a DAW, never operate a plug-in, never learn what a sidechain is
unless you want to. The only skills required are the ones you already have:
hearing a track, and knowing whether it moves you.

Setloom, by AppAutomaton, is an open-source, keyboard-first harness for
producing club tracks and DJ sets. It is built around one division of labor:
**the human is the taste owner; the agent does everything else.** It is honest
about where that frontier sits today.

## How it works

Three roles, one loop.

- **You, the taste owner.** You listen and give direction in plain language:
  *the bass is too busy before the break; make the arp darker.* You make every
  musical decision. Nothing is final until you say so.
- **The agent, the producer.** It turns your direction into concrete source
  changes: writes the track's own code, renders a fresh audition, plays it back,
  and reports the tradeoffs. It proposes; it never decides for you.
- **The harness, the studio.** A small, unopinionated toolkit that scaffolds
  tracks, renders, inspects audio, and keeps the work reproducible. It owns
  technical hygiene only. It composes nothing.

The listening gate is no-click: the agent prepares and plays the audio, and you
only listen and type.

## What you can do

- Scaffold a new track (spec, runnable assembler, and listening notes) from a
  single command.
- Render track harnesses from editable source files.
- Export and inspect MIDI.
- Inspect audio from the command line: waveform, spectrum, spectrogram, stereo
  field, and A/B comparisons.
- Recover note candidates from reference audio (macOS).
- Drive SuperCollider and Logic Pro as local production surfaces when a track
  calls for them.

## Quick start

Setloom runs through one repo-local `uv` environment. No side virtualenvs.

```bash
# Scaffold a track. assemble.py starts as a skeleton the agent fills with the composition.
uv run setloom new T06 --title midnight-signal --bpm 124 --key "F# minor"
uv run --no-sync python music/tracks/T06/assemble.py

# Audition and inspect the render
uv run setloom play local/candidates/T06/seed-0/demo.wav
uv run setloom inspect local/candidates/T06/seed-0/demo.wav --view all --out tmp/inspect.png

# Study a reference: recover its notes (macOS) and dissect its anatomy
uv run --group transcription setloom transcribe reference.wav --out tmp/notes.mid --events tmp/notes.json
uv run setloom anatomize local/corpus/audio --layers
```

Transcription is macOS-only; the local Basic Pitch asset is
`models/basic-pitch/icassp_2022/nmp.mlpackage`.

Per-track code imports the primitives directly. `setloom.midi`, `setloom.audio`,
and `setloom.conductor` carry the MIDI, DSP-hygiene, and music-theory math that
each track's `assemble.py` builds on:

```python
from setloom.midi import DRUM_CHANNEL, NoteEvent, TICKS_PER_BAR

# a four-on-the-floor kick across one bar
kick = [
    NoteEvent(DRUM_CHANNEL, 36, 110, beat * (TICKS_PER_BAR // 4), 120)
    for beat in range(4)
]
```

## The loop

```text
producer thesis
  → per-track source edit
  → render audition
  → play / inspect waveform + spectrum
  → human listening note
  → revise or promote
```

Use project-local `./tmp/` for disposable work. Durable candidates live under
`local/candidates/`, release assets under `local/releases/`, and production
source under `music/`.

## Where it stands today

Setloom is not a one-click melodic-techno generator, and it does not pretend to
be. Composition is not solved.

What works today is the loop above: an agent that converts human feedback into
concrete source changes quickly, researches when it helps, renders and inspects
reproducibly, and keeps the workspace clean enough that the next pass continues
without forensics. The leverage is disciplined iteration, not automation that
replaces judgment. That honesty is the foundation everything else is built on.

## How the harness thinks

The harness owns **technical hygiene only**: mono-safe low end, clip prevention,
a loudness target, mixable edges. Everything that makes a track *that* track
(groove, kick pattern, bass profile, energy arc, timbre) lives in the track's
own spec and source, under the taste owner's direction.

So the code stays unopinionated. It ships primitives and opt-in diagnostics; it
assembles nothing on its own. Machine reports and plots are navigation aids,
never the verdict. The verdict is always a person listening.

## Local audio tools

- **SuperCollider** drives scriptable synth lanes. The Lux in Umbra harness
  routes `scsynth` through source files such as `source/pluck-synth.json`, with
  the SynthDef topology in `harness/pluck.py`.
- **Logic Pro**, when installed, is a local reference surface for timbre checks
  and audition targets, never the Setloom output path. Full tool policy lives in
  [docs/tooling.md](docs/tooling.md).

## Repository map

```text
AGENTS.md                  Operating instructions for coding agents.
docs/                      Short project, workflow, and tooling notes.
music/tracks/              Per-track specs, source, and listening notes.
music/T5-lux-in-umbra/     Full production harness for "Lux in Umbra."
src/setloom/               CLI plus MIDI, audio, theory, inspection,
                           scaffold, schema, and anatomy primitives.
scripts/                   Opt-in local genAI experiments.
tests/                     Behavior tests for the reusable toolkit.
local/                     Gitignored corpus, candidates, and releases.
models/                    Gitignored model weights.
tmp/                       Gitignored scratch space.
```

## What a release carries

Setloom values editable source over opaque bounces. A release is its recipe, not
just its render:

```text
spec + source/MIDI + stems + render code + listening notes
```

Audio, proprietary samples, model weights, and disposable renders stay out of
version control unless a specific release process says otherwise. Anything
durable is regenerable from its spec, seed, and recipe.

## License & trademarks

- **Code, prompts, schemas, and harness logic:** AGPL-3.0-only.
- **Documentation:** CC BY-SA 4.0 unless marked otherwise.
- **Your music:** outputs belong to you, subject to the third-party samples,
  models, and inputs you bring.
- **Third-party:** the audio-to-MIDI decoder is derived from Spotify's Basic
  Pitch (Apache-2.0); see [NOTICE](LICENSES/NOTICE).

`Setloom` and `AppAutomaton` are project names; see [TRADEMARKS.md](LICENSES/TRADEMARKS.md).
Canonical license texts live in [LICENSE](LICENSE) and [LICENSES/](LICENSES/).
