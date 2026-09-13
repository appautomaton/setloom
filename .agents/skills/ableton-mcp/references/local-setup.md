# Setloom Ableton MCP local setup

Source of truth as of this workspace setup:

- Setloom root: `/Users/ac/dev/media/setloom`
- Local MCP source: `local/mcp/ableton-mcp/`
- Local launcher: `local/mcp/run-ableton-mcp.sh`
- Codex project config: `.codex/config.toml`
- Ableton Remote Script hook: `~/Music/Ableton/User Library/Remote Scripts/AbletonMCP/__init__.py`
- Remote Script symlink target: `/Users/ac/dev/media/setloom/local/mcp/ableton-mcp/AbletonMCP_Remote_Script/__init__.py`
- Default Remote Script socket: host `0.0.0.0`, port `9877`
- Default MCP bridge target: host `localhost`, port `9877`

## Codex config

The project-scoped MCP entry is:

```toml
[mcp_servers.ableton]
enabled = true
required = false
command = "/Users/ac/dev/media/setloom/local/mcp/run-ableton-mcp.sh"
args = []
startup_timeout_sec = 60
tool_timeout_sec = 60
default_tools_approval_mode = "prompt"
```

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
