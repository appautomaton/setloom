# Runtime and upstream sources

Establish available operations from the exposed MCP tools, current Live responses
and installed implementation in `local/mcp/ableton-mcp/`.

- Server: `MCP_Server/server.py`
- Remote Script: `AbletonMCP_Remote_Script/__init__.py`
- Installation provenance: `SOURCE.txt`
- Local telemetry settings: `MCP_Server/config.py`

Paths above are relative to the installed implementation. Inspect local changes
before assuming upstream behavior applies.

For implementation research:

- [Ableton MCP](https://github.com/ahujasid/ableton-mcp): upstream bridge.
- [Live Object Model reference](https://github.com/mikecfisher/ableton-lom-skill): Live API research.
- [Producer Pal](https://github.com/adamjmurray/producer-pal): alternative integration, not the installed backend.

Upstream capabilities do not establish what the local bridge exposes.
