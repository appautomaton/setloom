# Source grounding

This Setloom skill is grounded in the local files and reference clones below. Re-check them before making claims.

## Runtime source

- Local MCP server source: `local/mcp/ableton-mcp/`
- Provenance file: `local/mcp/ableton-mcp/SOURCE.txt`
- MCP entrypoint: `local/mcp/ableton-mcp/MCP_Server/server.py`
- Ableton Remote Script: `local/mcp/ableton-mcp/AbletonMCP_Remote_Script/__init__.py`
- Telemetry local config: `local/mcp/ableton-mcp/MCP_Server/config.py` with telemetry disabled by default

## Reference clones

Reference clones live under `tmp/skill-mcp-ref/` and are scratch/reference material, not the active runtime unless copied into `local/mcp/`.

Known reference snapshots from setup:

- `tmp/skill-mcp-ref/ableton-mcp`: ahujasid/ableton-mcp, commit `5e9ffbd`, MIT, provides the MCP server and Ableton Remote Script used for the local runtime copy.
- `tmp/skill-mcp-ref/ableton-lom-skill`: Ableton LOM reference skill, commit `7c7d189`, useful when extending Remote Script code against Live's Python API.
- `tmp/skill-mcp-ref/ableton-skills`: producer workflow reference skills, commit `c46ef14`, useful for music-production guidance but not an MCP backend.
- `tmp/skill-mcp-ref/producer-pal`: Producer Pal reference, commit `21effbd`, useful as an alternative REST/Max-for-Live design reference. It is not the installed Setloom backend.

## Truth hierarchy

1. Current live MCP tools exposed to Codex.
2. Current Setloom files under `local/mcp/`, `.codex/config.toml`, `pyproject.toml`, and `uv.lock`.
3. Current Ableton UI state and MCP command responses.
4. Reference clones under `tmp/skill-mcp-ref/`.
5. Prior conversation memory.

If these disagree, inspect and report the disagreement rather than smoothing it over.
