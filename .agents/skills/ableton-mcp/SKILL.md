---
name: ableton-mcp
description: Control or troubleshoot Ableton Live through Setloom's local MCP bridge and Remote Script. Use for actual Set, track, clip, note, browser, transport, and bridge operations.
---

# Ableton MCP for Setloom

## Grounding rule

Treat the Setloom checkout and the live MCP tool schema as the source of truth. Do not rely on memory for installed paths, tool names, or capabilities.

- For setup/lifecycle questions, read `references/local-setup.md`.
- For available Ableton operations, read `references/tool-map.md` or inspect `local/mcp/ableton-mcp/MCP_Server/server.py`.
- For provenance or comparison to reference projects, read `references/source-grounding.md`.
- For a quick static check, run `scripts/health.sh` from this skill directory.

Do not claim Producer Pal, `ableton-mcp-extended`, or any other backend is installed unless the current repo proves it.

## Operating model

The Setloom setup has three pieces:

1. **Codex MCP bridge**: Codex starts `local/mcp/run-ableton-mcp.sh` from `.codex/config.toml` when a Codex session starts in Setloom.
2. **Ableton Remote Script**: Ableton loads `AbletonMCP` from the user's Ableton User Library and listens on TCP port `9877`.
3. **Ableton Live**: Live must be running with the Remote Script configured. The MCP bridge itself does not launch Live or create app copies.

The bridge exits with the Codex session. Avoid starting another Ableton MCP bridge from Claude, Cursor, `uvx`, or a second Codex session at the same time.

## Session workflow

1. Inspect whether Ableton is running when live control is requested.
2. If connection fails, verify Ableton Preferences → Link/Tempo/MIDI has Control Surface `AbletonMCP` with Input/Output `None`.
3. Start by reading current state with `get_session_info`; read individual tracks with `get_track_info` before editing.
4. Use track and clip indexes from the returned session state, not from visual guesses.
5. State-mutating tools immediately change the open Live Set; use the authorized scope and current state to choose the edit.
6. If a task needs browser items, call `get_browser_tree` then `get_browser_items_at_path`; load only URIs returned by the MCP/browser.
7. The current bridge inserts Arrangement MIDI by copying a Session clip with `duplicate_to_arrangement`. Use an existing suitable clip or create the needed one; this bridge limitation does not prescribe a Session-first composition workflow.

## Safe troubleshooting

Use `scripts/health.sh` for static setup checks. Add flags only when useful:

```bash
.agents/skills/ableton-mcp/scripts/health.sh
.agents/skills/ableton-mcp/scripts/health.sh --import
.agents/skills/ableton-mcp/scripts/health.sh --port
```

Interpret failures narrowly:

- MCP missing in `codex mcp list`: check `.codex/config.toml` from the Setloom root.
- Import failure: check `pyproject.toml` dependency group `ableton-mcp`, `uv.lock`, and `local/mcp/ableton-mcp/MCP_Server/config.py`.
- Port `9877` closed: Ableton is not running, the Remote Script is not selected, or Ableton has not finished loading.
- Tools exist but calls fail: inspect the returned error first; do not patch the server before proving whether this is setup, Live state, or missing capability.

## Extending the MCP server

When a capability is missing, choose among available authorized controls and
extending the bridge according to the production need and expected reuse.
If extension is the chosen solution:

1. Inspect `local/mcp/ableton-mcp/MCP_Server/server.py` and `local/mcp/ableton-mcp/AbletonMCP_Remote_Script/__init__.py`.
2. Add or edit both sides: an MCP tool in `server.py` and a command handler in the Remote Script.
3. For Ableton state changes, route work onto Live's main thread using the Remote Script's existing queued/scheduled pattern.
4. Keep command payloads JSON-serializable and return structured data where possible.
5. Validate by importing the MCP server; restart Codex for bridge changes and restart/reselect the Control Surface for Remote Script changes.
6. Record what changed and the local source path used.

Do not replace this local setup with global `uvx` installs or app-bundle changes unless the user explicitly asks.
