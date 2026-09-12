# Current Ableton MCP tool map

Ground this list in `local/mcp/ableton-mcp/MCP_Server/server.py`. If the live MCP tool list or server source differs, prefer the current source.

## Connection

The MCP server uses `ABLETON_HOST` and `ABLETON_PORT`, defaulting to `localhost:9877`. The Remote Script listens on port `9877` inside Ableton.

## Read tools

- `get_session_info(user_prompt="")`: returns overall Live Set/session state.
- `get_track_info(track_index, user_prompt="")`: returns details for one track.
- `get_clip_notes(track_index, clip_index, from_pitch=0, pitch_span=128, from_time=0.0, time_span=-1.0, user_prompt="")`: returns MIDI notes from a Session clip as JSON dictionaries. Use `time_span=-1` to read through the clip end.
- `get_browser_tree(category_type="all", user_prompt="")`: returns browser category/folder tree. Category examples in code: `all`, `instruments`, `sounds`, `drums`, `audio_effects`, `midi_effects`.
- `get_browser_items_at_path(path, user_prompt="")`: returns browser items under a category/folder path.
- `get_arrangement_clips(track_index, user_prompt="")`: returns Arrangement clips for one track.

## Mutating tools

- `create_midi_track(index=-1, user_prompt="")`: creates a MIDI track; `-1` means append.
- `create_audio_track(index=-1, user_prompt="")`: creates an audio track; `-1` means append.
- `set_track_name(track_index, name, user_prompt="")`: renames a track.
- `create_clip(track_index, clip_index, length=4.0, user_prompt="")`: creates a MIDI clip in Session View.
- `create_audio_clip(track_index, clip_index, path, user_prompt="")`: imports an audio file into an audio track clip slot. The server doc says Live 12.0.5+ is required for the underlying API.
- `add_notes_to_clip(track_index, clip_index, notes, user_prompt="")`: adds MIDI notes. Note dictionaries use `pitch`, `start_time`, `duration`, `velocity`, and `mute`.
- `set_clip_name(track_index, clip_index, name, user_prompt="")`: renames a clip.
- `set_tempo(tempo, user_prompt="")`: sets Live Set tempo.
- `load_instrument_or_effect(track_index, uri, user_prompt="")`: loads a browser item by URI onto a track.
- `load_drum_kit(track_index, rack_uri, kit_path, user_prompt="")`: loads a drum rack URI, searches a kit path, and loads the first loadable kit found.
- `fire_clip(track_index, clip_index, user_prompt="")`: starts a Session clip.
- `stop_clip(track_index, clip_index, user_prompt="")`: stops a Session clip.
- `start_playback(user_prompt="")`: starts playback.
- `stop_playback(user_prompt="")`: stops playback.
- `set_arrangement_time(time, user_prompt="")`: moves the Arrangement playhead in beats.
- `duplicate_to_arrangement(track_index, clip_index, destination_time, user_prompt="")`: copies a Session clip into Arrangement View at a beat position.
- `switch_to_arrangement_view(user_prompt="")`: switches Ableton UI to Arrangement View.

## Common patterns

### MIDI clip

1. `get_session_info`
2. `create_midi_track`
3. `set_track_name`
4. `create_clip`
5. `add_notes_to_clip`
6. `set_clip_name`

### Browser loading

1. `get_browser_tree(category_type="instruments")` or another category
2. `get_browser_items_at_path(path="...")`
3. Use a returned loadable item's URI with `load_instrument_or_effect`

### Arrangement promotion

1. Build or identify a Session clip.
2. `duplicate_to_arrangement(track_index, clip_index, destination_time)`
3. `get_arrangement_clips(track_index)`
4. `switch_to_arrangement_view()`
