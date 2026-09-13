<!-- SPDX-License-Identifier: CC-BY-SA-4.0 -->

# DAW control

Choose a controllable path for the musical operation actually needed. Keep
musical timing in MIDI and host automation; network messages and simulated
keystrokes are not a musical clock. Use authorized accessibility or visual
control when it serves the task.

## Ableton Live

The local MCP bridge uses Live's Remote Script API. Its source is
`local/mcp/ableton-mcp/`; use the project Ableton MCP skill for setup and the
current schema. Reuse the existing bridge and coordinate writers to the Set.

The local check on 2026-09-11 with Live 12.4.2 verified session/track/clip/browser
queries, MIDI clip creation and note readback, instrument loading by returned
browser URI, and copying a Session clip into Arrangement. The current bridge's
Arrangement insertion path does not prescribe a Session-first musical workflow.

At that check, the bridge lacked device-parameter editing, mixer/send editing,
automation writing, general note replacement and audio export. Live exposes
[automatable parameters](https://docs.cycling74.com/apiref/lom/deviceparameter/);
a bridge gap is not a Live limitation. Choose among available authorized
controls, another suitable rendering path, and extending the bridge. If extending
it, update both bridge and Remote Script and verify the operation on disposable
material before applying it to production.

Operational distinctions from the local check:

- A browser summary can be empty while `get_browser_items_at_path("instruments")`
  returns loadable devices. Inspect the relevant branch before concluding absence.
- Mutation acknowledgements may omit an index or report stale state. Query the
  resulting objects before dependent edits; names alone do not identify them.
- Read parameter bounds and displayed units. Internal values are not necessarily
  Hz, dB or MIDI-controller values.
- Concurrent writers can invalidate track and clip indexes.
- An application command may leave a modal save dialog unresolved. Verify visible
  completion; global keystrokes can reach the wrong app while the user is working.

## Logic Pro

The same-date check of Logic 12.3.1 found standard application/document/window
AppleScript support and named accessibility controls, but no track, note, region
or plug-in parameter classes in its scripting dictionary. This does not establish
a full production API.

Available approaches include importing authored MIDI,
[Scripter](https://support.apple.com/guide/logicpro/use-scripter-lgce728c68f6/mac)
for MIDI processing inside an instrument channel, and configured
[controller/OSC mappings](https://support.apple.com/en-ca/guide/logicpro/ctlsf67f4bdc/12.2/mac/15.6).
Scripter's parameter API concerns its own script. No Setloom OSC connection was
established in that check.

Retain a native project and mappings when using Logic-specific instruments.
Use verified UI controls for operations without a suitable script interface,
and inspect the exported audio. Alchemy and Retro Synth were not exposed as
external Audio Units by the local `auval -a` check; do not assume an external
Python host can load Logic's internal instruments.

Keep Logic audio input set to None and microphone permission off, as the user
required. Inspection and offline production do not authorize playback.

## Unverified bridge leads

Prior source research identified [wstierhout/ableton-live-mcp](https://github.com/wstierhout/ableton-live-mcp)
and [MongLong0214/logic-pro-mcp](https://github.com/MongLong0214/logic-pro-mcp) as
possible extensions to evaluate. Neither is the locally verified bridge described
above; the Logic approach still uses native UI operations.
