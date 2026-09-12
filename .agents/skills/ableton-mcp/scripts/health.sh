#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
cd "$ROOT"

DO_IMPORT=0
DO_PORT=0
for arg in "$@"; do
  case "$arg" in
    --import) DO_IMPORT=1 ;;
    --port) DO_PORT=1 ;;
    -h|--help)
      cat <<'USAGE'
Usage: .agents/skills/ableton-mcp/scripts/health.sh [--import] [--port]

Static checks are always run. --import verifies Python import through uv.
--port checks whether localhost:9877 is open; failure is normal when Ableton is not running or the Remote Script is not loaded.
USAGE
      exit 0
      ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

pass=0
fail=0
warn=0

ok() { printf 'OK   %s\n' "$*"; pass=$((pass+1)); }
bad() { printf 'FAIL %s\n' "$*"; fail=$((fail+1)); }
note() { printf 'WARN %s\n' "$*"; warn=$((warn+1)); }

check_path() {
  local path="$1"
  if [ -e "$path" ]; then ok "$path exists"; else bad "$path missing"; fi
}

check_path ".codex/config.toml"
check_path "local/mcp/ableton-mcp/MCP_Server/server.py"
check_path "local/mcp/ableton-mcp/AbletonMCP_Remote_Script/__init__.py"
check_path "local/mcp/run-ableton-mcp.sh"
check_path "pyproject.toml"
check_path "uv.lock"

grep -q '\[mcp_servers\.ableton\]' .codex/config.toml && ok "Codex MCP entry exists" || bad "Codex MCP entry missing"
grep -q '^ableton-mcp[[:space:]]*=' pyproject.toml && ok "uv dependency group exists" || bad "uv dependency group missing or changed"
[ -x local/mcp/run-ableton-mcp.sh ] && ok "launcher is executable" || bad "launcher is not executable"

REMOTE="$HOME/Music/Ableton/User Library/Remote Scripts/AbletonMCP/__init__.py"
EXPECTED="$ROOT/local/mcp/ableton-mcp/AbletonMCP_Remote_Script/__init__.py"
if [ -L "$REMOTE" ]; then
  target="$(readlink "$REMOTE")"
  if [ "$target" = "$EXPECTED" ]; then ok "Remote Script symlink points to Setloom local source"; else bad "Remote Script symlink points to $target"; fi
elif [ -e "$REMOTE" ]; then
  note "Remote Script exists but is not a symlink: $REMOTE"
else
  bad "Remote Script hook missing: $REMOTE"
fi

if [ "$DO_IMPORT" -eq 1 ]; then
  if command -v uv >/dev/null 2>&1; then
    if PYTHONPATH="$ROOT/local/mcp/ableton-mcp" UV_CACHE_DIR="$ROOT/tmp/uv-cache" uv run --no-sync python - <<'PY'
import MCP_Server.server as s
print(f"import-ok {s.ABLETON_HOST}:{s.ABLETON_PORT}")
PY
    then ok "Python MCP server imports"; else bad "Python MCP server import failed"; fi
  else
    bad "uv not found"
  fi
fi

if [ "$DO_PORT" -eq 1 ]; then
  if nc -z localhost 9877 >/dev/null 2>&1; then ok "localhost:9877 is open"; else note "localhost:9877 is closed"; fi
fi

printf '\nsummary: %d ok, %d warn, %d fail\n' "$pass" "$warn" "$fail"
[ "$fail" -eq 0 ]
