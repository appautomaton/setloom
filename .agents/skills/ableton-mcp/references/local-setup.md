# Setloom Ableton MCP local setup

Source of truth as of this workspace setup:

- Setloom root: this checkout
- Local MCP source: `local/mcp/ableton-mcp/`
- Local launcher: `local/mcp/run-ableton-mcp.sh`
- Codex project config: `.codex/config.toml`
- Ableton Remote Script hook: `~/Music/Ableton/User Library/Remote Scripts/AbletonMCP/__init__.py`
- Remote Script symlink target: `<Setloom root>/local/mcp/ableton-mcp/AbletonMCP_Remote_Script/__init__.py`
- Default Remote Script socket: host `0.0.0.0`, port `9877`
- Default MCP bridge target: host `localhost`, port `9877`

## Codex config

`.codex/config.toml` holds the project-scoped `[mcp_servers.ableton]` entry and is
the only place that records a machine path: its `command` is the absolute path of
this checkout's `local/mcp/run-ableton-mcp.sh`. Update that one line when the
checkout moves; the launcher derives every other path from its own location.

No Ableton app path is required in Setloom config. The MCP bridge connects to an already-running Ableton Remote Script.

## Launcher behavior

`local/mcp/run-ableton-mcp.sh`:

- changes directory to the Setloom root
- sets `UV_CACHE_DIR="$ROOT/tmp/uv-cache"`
- sets `ABLETON_MCP_DISABLE_TELEMETRY=true` by default
- sets `PYTHONPATH="$ROOT/local/mcp/ableton-mcp"`
- runs `uv run --no-sync python -m MCP_Server.server`

Install the `ableton-mcp` dependency group explicitly in the repo environment
before starting the bridge. The launcher and health check do not sync packages.
The Setloom root `pyproject.toml` owns that dependency group. Do not create a nested virtualenv under `local/mcp/ableton-mcp`.

## Lifecycle

- Ableton Live must be running; the MCP bridge does not launch it.
- Ableton loads the Remote Script only while Ableton is running.
- Codex starts the Python MCP bridge when the Setloom Codex session starts.
- Codex stops the Python MCP bridge when the session exits.
- This setup should not produce duplicate Ableton app bundles or background Ableton instances.

## Required Ableton UI setting

In Ableton Preferences → Link/Tempo/MIDI:

- Control Surface: `AbletonMCP`
- Input: `None`
- Output: `None`

If the Control Surface was just installed or changed, restart Ableton or rescan/reselect the control surface.
