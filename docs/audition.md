<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# Local HTML auditions

`setloom.audition` builds a directly openable `index.html` from prepared audio.
The page contains its CSS, classic JavaScript controller, and display data;
audio remains in child files. Listening needs no Python process, npm project,
network connection, or local server. Keep the artifact folder together.

## Entry and authoring files

Deliver an absolute link to the path returned by `build_page`: the song's root
`index.html`. This is the assembled listening page, with styles, playback and
display data already included.

Keep track-owned authoring files distinct from that entry:

| File | Role |
| --- | --- |
| `index.html` | Generated listening entry; open this file. |
| `audition/index.html.in` | Editable layout with assembly slots; read during building. |
| `audition/build_page.py`, `app.js`, `style.css` | Song-owned adapter, behavior and styling. |

Use the `.html.in` suffix for new track templates. Opening an unassembled template
does not load the player or its data. When replacing an already shared template
URL, retain a small redirect page with a manual link to the root entry; keep that
compatibility page separate from the template passed to `build_page`.

Before delivery, run the song's page builder and share its returned entry path.
Check resource assembly and playback logic separately from actual browser use;
if browser verification is unavailable, state that limit. Rebuilding HTML alone
does not require a new audio render or a server.

## A minimal page

Use the repository's existing Python environment during authoring:

```python
from pathlib import Path
from setloom.audition import AudioOption, Session, build_page

root = Path("tmp/my-song")
session = Session(
    title="My Song",
    options=(
        AudioOption("current", "Current performance", "render/current.m4a"),
        AudioOption("previous", "Previous performance", "render/previous.m4a"),
    ),
    default="current",
)
page = build_page(root, session)
```

The files must already exist. The builder checks the audio streams and durations
with the existing `ffprobe`, then writes `root/index.html`. It does not render,
copy, normalize, or change audio. A one-option session works without an original
recording, MIDI, tempo, score, or comparison version.

Each option is a prepared listening view. It may represent a full mix, a solo,
a combination, a removal diagnostic, or a matched-level preview. IDs and paths
are explicit; the shared code has no instrument or edition naming rules. Different
options can reference the same file, which is probed once per build.

## Time and level

Positions are session seconds. `AudioOption.offset` declares the session time
at the beginning of an excerpt. Switching preserves position inside the new
option's available range; otherwise it clamps to that range. An excerpt starting
at 89 seconds therefore uses `offset=89`. This is an explicit time correspondence,
not inferred beat alignment or structural time-warping.

`AudioOption.gain` is a playback attenuation in `(0, 1]`, defaulting to 1. It is
not a loudness target. Prepared level-matched files already contain their preview
gain and normally use 1. Do not apply that gain twice. Use prepared audio for
gain increases; native media volume is limited to 1.

Choose comparison levels for the musical question. A removal diagnostic should
preserve contributions at their mix level. A timbre or master-processing comparison
may need matched loudness. Actual release level is another valid listening view.
The controller does not choose among these policies.

## Preserve a song's presentation

A custom template has exactly three assembly slots:

```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{{TITLE}}</title><!-- AUDITION_STYLE --></head>
<body>
  <h1>{{TITLE}}</h1>
  <!-- AUDITION_AUDIO -->
  <p id="status" role="status"></p>
  <!-- AUDITION_PLAYER -->
</body>
</html>
```

Read the layout from `audition/index.html.in` and pass `template`, `styles`, and
`script` strings to `build_page`. Optional
`presentation` data is embedded unchanged: the song owns its display projection,
part meanings, passages, visual choices, and feedback. It need not change the
production's canonical source schema to suit the player.

The audio slot supplies a native player with the default file. It remains usable
if enhanced controls cannot initialize. A custom script can attach the shared
transport:

```javascript
const payload = SetloomAudition.read();
const transport = new SetloomAudition.Transport(
  payload.session, document.getElementById('audition-audio')
);
transport.subscribe(state => {
  document.getElementById('status').textContent = state.error ||
    `${state.loading ? 'Loading' : state.playing ? 'Playing' : 'Paused'} · ${state.label}`;
});
```

| Operation | Behavior |
| --- | --- |
| `select(id)` | Select an available option; preserve position and playback intent. Unknown IDs fail without substituting the mix. |
| `play()`, `pause()`, `toggle()` | Control the selected audio. Initialization and paused selection never start playback. |
| `seek(seconds)` | Seek in session seconds, including while metadata is loading. |
| `setLoop({start, end})`, `setLoop(null)` | Set or remove a loop inside the selected resource's available range. |
| `setVolume(value)` | Set listener volume in `[0, 1]`, separate from the declared option gain. Native volume changes update the same state; mute is preserved across selections. |
| `now()`, `state()` | Read the current session position or transport state. |
| `subscribe(listener)` | Observe state; returns an unsubscribe function. |
| `destroy()` | Stop playback and clean pending waits, listeners, and animation work. Page closure invokes it automatically; back-forward cache suspension pauses and retains the controller. |

The controller isolates media elements across selections and cancels metadata
waits. Late play promises cannot take ownership of a newer option or cancel a newer
play request. Native controls and custom controls update the same state, including
`volume` and `muted`. Inspection should use its own selection;
choosing notes to view does not require calling `select()`.

Custom version/part controls must expose the actual available options. Disable
a missing counterpart and explain it; do not silently play something else. The
controller reports availability through its `options` map. Musical grouping and
counterpart relationships remain in the song's adapter.

## Files, exports, and rebuilding

Required paths must be relative descendants of the declared root. Parent paths,
absolute paths, missing files, and symlinks escaping the root are rejected before
the existing page is replaced. Spaces and Unicode in audio filenames are encoded
for URLs. Optional outbound research links may appear. The builder checks HTML
`src` and `href` references, rejects external script elements and browser modules,
and prohibits `<base>` elements that would change resource resolution.

Track-supplied CSS and JavaScript are trusted authoring inputs, not sandboxed code.
They must keep the direct-file contract: no runtime data fetching, remote fonts,
CSS imports, or service dependencies. Static HTML validation does not inspect every
URL that custom code could construct. The default presentation initializes in its
own scope so an appended custom script can use its own variable names.

Small MIDI and JSON downloads can be embedded with `exports=("source/part.mid",)`.
Duplicate paths are embedded once. In custom scripts, call
`SetloomAudition.bindDownloads(payload.exports)` to serve matching `a[download]`
links through browser blobs, without fetching local files. Include only useful
exports; a large full source JSON need not be embedded merely because it exists.

The embedded payload includes `controller_version`, `session`, `presentation`,
and `exports`. Generated pages are snapshots: rebuild a current page deliberately
to adopt changes; do not update a reviewed historical page by linking it to a
mutable runtime script elsewhere. The shared browser assets ship inside the
Python package and are inlined during building.

Keep each adapter beside its song as `<song>/audition/build_page.py`. After a
presentation change, rerun that adapter to rebuild the HTML alone:

```sh
uv run --no-sync python tmp/my-song/audition/build_page.py
```

## Ownership and limits

Shared code owns resource resolution, transport, selection, page assembly and
technical validation. The song owns musical grouping, comparable options, the
listening question, visual identity and scoped feedback. Score graphics and
artistic presentation stay song-owned until several songs demonstrate the same
requirement.

- Availability is independent of approval. A rejected artifact may remain
  available for diagnosis, and an approved one may have moved. Building a page
  never resets a listening verdict.
- An option need not correspond to one MIDI track or instrument. Record its
  meaning and membership when supplied; do not infer them from register,
  filename or a separator label.
- A comparison across project roots needs an explicitly planned bundle of the
  selected assets. Do not widen the root to the repository or duplicate the corpus.
- Compute waveform summaries and display projections at build time. Playback
  does not depend on Web Audio decoding or browser-side signal processing.
- Native media seeking and looping can introduce a short pause. The transport
  does not promise sample-accurate switching or seamless musical loops.

## Verification

`tests/test_audition.py` checks real local audio resources, root containment,
safe JSON embedding, filename handling, exports, relocation, and custom assembly.
`tests/audition_transport.mjs` exercises metadata cancellation, stale play promises,
pause/seek during loading, offsets, gain, loop/end behavior, retry, and native
controls. Existing Node is only an offline test runner; no npm project is created.

These are technical checks; they establish neither actual browser playback nor
listening approval. Exercise the generated `file://` page in a real browser when
tooling permits: opening, seeking, switching, looping, downloads and page closure.
When the browser tool restricts `file://`, report that limit. Do not start a
server or switch browser surfaces to work around it.
