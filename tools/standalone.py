"""Einstieg des eigenständigen Programms (Release-Download, bringt sein eigenes Python mit).

Ein Programm für alles, gebaut mit `tools/build_standalone.py`:

  claudegravity <aufgabe> …   Loop (wie loop.py), auch als Befehl claudegravity-loop
  claudegravity mcp …         MCP-Server (wie mcp_server.py), auch als Befehl claudegravity-mcp
  claudegravity install …     sich selbst installieren: Befehle anlegen, MCP-Server und Skill eintragen (wie install.py)
"""

import os
import sys
from pathlib import Path

SUBCOMMANDS = ("mcp", "install")


def route(argv: list[str]) -> tuple[str, list[str]]:
    """Ziel (loop, mcp oder install) und die restlichen Argumente; der Programmname claudegravity-mcp startet den Server."""
    name = Path(argv[0]).stem.lower() if argv else ""
    rest = list(argv[1:])
    if name.endswith("-mcp"):
        return "mcp", rest
    if rest and rest[0] in SUBCOMMANDS:
        return rest[0], rest[1:]
    return "loop", rest


def main() -> int:
    """Programmaufruf verteilen."""
    # Startet das Programm sich selbst (Hintergrundlauf des MCP-Servers, Kandidaten), soll der neue Prozess
    # eigenständig entpacken und nicht den Ordner dieses Prozesses mitbenutzen, der mit ihm verschwindet.
    os.environ["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    target, rest = route(sys.argv)
    prog = Path(sys.argv[0]).name if sys.argv else "claudegravity"
    if target == "mcp":
        import mcp_server

        sys.argv = [prog] + rest
        mcp_server.main()
        return 0
    if target == "install":
        import install

        sys.argv = [f"{prog} install"] + rest
        return install.main()
    from claudegravity.cli import run_cli

    sys.argv = [prog] + rest
    run_cli()
    return 0


if __name__ == "__main__":
    sys.exit(main())
