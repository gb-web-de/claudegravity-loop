#!/bin/sh
# Startet den ClaudeGravity-MCP-Server aus der Claude-Desktop-Erweiterung (.mcpb) unter macOS und Linux.
# Desktop-Apps sehen oft nur /usr/bin:/bin; unter macOS ist /usr/bin/python3 meist 3.9. Deshalb sucht dieses
# Skript ein Python ab 3.10: zuerst CLAUDEGRAVITY_PYTHON (Einstellung der Erweiterung), dann übliche Orte,
# zuletzt `uv run`, das bei Bedarf ein passendes Python lädt. Aufruf: launch.sh <pfad/zu/mcp_server.py>

ok() {
  [ -n "$1" ] && [ -x "$1" ] && "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

case "$CLAUDEGRAVITY_PYTHON" in
  ""|*'${'*) ;;
  *)
    if ok "$CLAUDEGRAVITY_PYTHON"; then exec "$CLAUDEGRAVITY_PYTHON" "$@"; fi
    echo "[!] CLAUDEGRAVITY_PYTHON=$CLAUDEGRAVITY_PYTHON ist kein Python ab 3.10, suche weiter." >&2
    ;;
esac

for dir in /opt/homebrew/bin /usr/local/bin "$HOME/.local/bin" "$HOME/.pyenv/shims" /usr/bin /bin; do
  for name in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if ok "$dir/$name"; then exec "$dir/$name" "$@"; fi
  done
done
for name in python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
  found=$(command -v "$name" 2>/dev/null)
  if ok "$found"; then exec "$found" "$@"; fi
done
for uv in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
  if [ -x "$uv" ]; then exec "$uv" run --no-project --python ">=3.10" "$@"; fi
done

echo "[!] ClaudeGravity braucht Python 3.10 oder neuer und hat keins gefunden." >&2
echo "    Python installieren (z. B. brew install python) oder in den Einstellungen der Erweiterung den Pfad angeben." >&2
exit 1
