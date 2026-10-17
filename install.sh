#!/usr/bin/env sh
# ====================================================================
# ClaudeGravity Installer (Linux / macOS)
# Trägt den MCP-Server in alle gefundenen Clients ein und legt die
# globalen Befehle claudegravity, claudegravity-loop, claudegravity-mcp an.
#   ./install.sh               installieren / aktualisieren
#   ./install.sh --uninstall   entfernen
#   ./install.sh --status      Status anzeigen
# ====================================================================
DIR="$(cd "$(dirname "$0")" && pwd)"
for PY in python3 python; do
    if command -v "$PY" >/dev/null 2>&1 && "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        exec "$PY" "$DIR/install.py" "$@"
    fi
done
echo "[!] FEHLER: Python 3.10+ wurde nicht gefunden." >&2
exit 1
