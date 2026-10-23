#!/usr/bin/env python3
"""
ClaudeGravity Installer
Registriert den ClaudeGravity MCP-Server (mcp_server.py) in allen gefundenen MCP-Clients
und macht die Befehle `claudegravity`, `claudegravity-loop` und `claudegravity-mcp`
global aus jedem Ordner aufrufbar. Nur Python-Standardbibliothek, idempotent.

Usage:
  python3 install.py              # installieren / aktualisieren
  python3 install.py --uninstall  # alles wieder entfernen
  python3 install.py --status     # anzeigen, was eingetragen ist
  python3 install.py --dry-run    # nur anzeigen, nichts verändern
  python3 install.py --only claude,gemini --no-path
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SERVER_NAME = "claudegravity"
REPO_DIR = Path(__file__).resolve().parent
LOOP_SCRIPT = REPO_DIR / "loop.py"
MCP_SCRIPT = REPO_DIR / "mcp_server.py"
IS_WINDOWS = sys.platform == "win32"
HOME = Path.home()

# Globale Befehle -> Zielskript
COMMANDS = {
    "claudegravity": LOOP_SCRIPT,
    "claudegravity-loop": LOOP_SCRIPT,
    "claudegravity-mcp": MCP_SCRIPT,
}

MARK_BEGIN = "# >>> claudegravity >>>"
MARK_END = "# <<< claudegravity <<<"

DRY_RUN = False
# Standardprojekt für Desktop-Apps (--project): landet als CLAUDEGRAVITY_PROJECT in der Server-Umgebung
PROJECT_DIR: Path | None = None


def say(symbol: str, msg: str) -> None:
    print(f"  {symbol} {msg}")


def verb(done: str, would: str) -> str:
    return would if DRY_RUN else done


def python_command() -> str:
    """Absoluter Python-Pfad: MCP-Clients starten Server ohne Shell-PATH."""
    return str(Path(sys.executable).absolute())


def server_env() -> dict:
    """Umgebung für den MCP-Server: UTF-8 und optional das Standardprojekt."""
    env = {"PYTHONIOENCODING": "utf-8"}
    if PROJECT_DIR is not None:
        env["CLAUDEGRAVITY_PROJECT"] = str(PROJECT_DIR)
    return env


def server_entry(extra: dict | None = None) -> dict:
    entry = {
        "command": python_command(),
        "args": [str(MCP_SCRIPT)],
        "env": server_env(),
    }
    if extra:
        entry.update(extra)
    return entry


def app_data_dir() -> Path:
    if IS_WINDOWS:
        return Path(os.environ.get("APPDATA", HOME / "AppData" / "Roaming"))
    if sys.platform == "darwin":
        return HOME / "Library" / "Application Support"
    return Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))


# --------------------------------------------------------------------
# JSON-basierte MCP-Konfigurationen
# --------------------------------------------------------------------


def read_json(path: Path) -> dict | None:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8").strip()
        return json.loads(text) if text else {}
    except (json.JSONDecodeError, OSError) as e:
        say("!", f"{path} konnte nicht gelesen werden ({e}) – übersprungen.")
        return None


def write_json(path: Path, data: dict) -> None:
    if DRY_RUN:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(path.name + ".claudegravity.bak")
        if not backup.exists():
            shutil.copy2(path, backup)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def json_client(path: Path, key: str = "mcpServers", extra: dict | None = None):
    def install() -> bool:
        data = read_json(path)
        if data is None:
            return False
        servers = data.setdefault(key, {})
        new = server_entry(extra)
        if servers.get(SERVER_NAME) == new:
            say("=", f"bereits aktuell: {path}")
            return True
        servers[SERVER_NAME] = new
        write_json(path, data)
        say("+", f"{verb('eingetragen', 'würde eintragen')}: {path}")
        return True

    def uninstall() -> bool:
        data = read_json(path)
        if not data or SERVER_NAME not in data.get(key, {}):
            return True
        del data[key][SERVER_NAME]
        write_json(path, data)
        say("-", f"{verb('entfernt', 'würde entfernen')}: {path}")
        return True

    def status() -> bool:
        data = read_json(path) or {}
        return SERVER_NAME in data.get(key, {})

    return install, uninstall, status


# --------------------------------------------------------------------
# Codex CLI (~/.codex/config.toml) – Block zwischen Markern
# --------------------------------------------------------------------


def strip_marked_block(text: str) -> str:
    start = text.find(MARK_BEGIN)
    end = text.find(MARK_END)
    if start == -1 or end == -1:
        return text
    end += len(MARK_END)
    return (text[:start].rstrip("\n") + "\n" + text[end:].lstrip("\n")).lstrip("\n")


def codex_client():
    path = HOME / ".codex" / "config.toml"

    def block() -> str:
        # JSON-Strings sind gültige TOML-Basic-Strings (Backslashes unter Windows!)
        return "\n".join(
            [
                MARK_BEGIN,
                f"[mcp_servers.{SERVER_NAME}]",
                f"command = {json.dumps(python_command())}",
                f"args = [{json.dumps(str(MCP_SCRIPT))}]",
                "env = { " + ", ".join(f"{json.dumps(k)} = {json.dumps(v)}" for k, v in server_env().items()) + " }",
                MARK_END,
                "",
            ]
        )

    def install() -> bool:
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        if block() in old:
            say("=", f"bereits aktuell: {path}")
            return True
        base = strip_marked_block(old)
        if f"[mcp_servers.{SERVER_NAME}]" in base:
            say("!", f"{path} enthält schon einen eigenen [mcp_servers.{SERVER_NAME}]-Eintrag – nicht verändert.")
            return False
        new = (base.rstrip("\n") + "\n\n" if base.strip() else "") + block()
        if not DRY_RUN:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new, encoding="utf-8")
        say("+", f"{verb('eingetragen', 'würde eintragen')}: {path}")
        return True

    def uninstall() -> bool:
        if not path.exists():
            return True
        old = path.read_text(encoding="utf-8")
        if MARK_BEGIN not in old:
            return True
        if not DRY_RUN:
            path.write_text(strip_marked_block(old), encoding="utf-8")
        say("-", f"{verb('entfernt', 'würde entfernen')}: {path}")
        return True

    def status() -> bool:
        return path.exists() and MARK_BEGIN in path.read_text(encoding="utf-8")

    return install, uninstall, status


# --------------------------------------------------------------------
# Claude Code (über die offizielle CLI, Scope "user" = alle Projekte)
# --------------------------------------------------------------------


def run_cli(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def claude_code_client():
    exe = shutil.which("claude") or "claude"

    def status() -> bool:
        try:
            return run_cli([exe, "mcp", "get", SERVER_NAME]).returncode == 0
        except OSError:
            return False

    def uninstall() -> bool:
        if not status():
            return True
        if not DRY_RUN:
            run_cli([exe, "mcp", "remove", SERVER_NAME, "--scope", "user"])
        say("-", f"{verb('entfernt aus', 'würde entfernen aus')} Claude Code (Scope: user)")
        return True

    def install() -> bool:
        if DRY_RUN:
            say("+", "würde in Claude Code eintragen (claude mcp add --scope user)")
            return True
        if status():
            run_cli([exe, "mcp", "remove", SERVER_NAME, "--scope", "user"])
        env_args = [arg for k, v in server_env().items() for arg in ("-e", f"{k}={v}")]
        res = run_cli([exe, "mcp", "add", "--scope", "user", SERVER_NAME, *env_args, "--", python_command(), str(MCP_SCRIPT)])
        if res.returncode != 0:
            say("!", f"claude mcp add fehlgeschlagen: {(res.stderr or res.stdout).strip()}")
            return False
        say("+", "eingetragen in Claude Code (Scope: user)")
        return True

    return install, uninstall, status


# --------------------------------------------------------------------
# Client-Registry: (Name, erkannt?, Factory)
# --------------------------------------------------------------------


def clients() -> dict[str, tuple[str, bool, tuple]]:
    gemini_dir = HOME / ".gemini"
    agy_dir = gemini_dir / "antigravity"
    claude_desktop = app_data_dir() / "Claude"
    vscode_user = app_data_dir() / "Code" / "User"
    return {
        "claude": ("Claude Code", bool(shutil.which("claude")), claude_code_client()),
        "claude-desktop": ("Claude Desktop", claude_desktop.is_dir(), json_client(claude_desktop / "claude_desktop_config.json")),
        "gemini": ("Gemini CLI", bool(shutil.which("gemini")) or gemini_dir.is_dir(), json_client(gemini_dir / "settings.json")),
        "antigravity": ("Google Antigravity", bool(shutil.which("agy")) or agy_dir.is_dir(), json_client(agy_dir / "mcp_config.json")),
        "codex": ("OpenAI Codex CLI", bool(shutil.which("codex")) or (HOME / ".codex").is_dir(), codex_client()),
        "copilot": (
            "GitHub Copilot CLI",
            bool(shutil.which("copilot")) or (HOME / ".copilot").is_dir(),
            json_client(HOME / ".copilot" / "mcp-config.json", extra={"type": "local", "tools": ["*"]}),
        ),
        "cursor": ("Cursor", bool(shutil.which("cursor")) or (HOME / ".cursor").is_dir(), json_client(HOME / ".cursor" / "mcp.json")),
        "windsurf": (
            "Windsurf",
            (HOME / ".codeium" / "windsurf").is_dir(),
            json_client(HOME / ".codeium" / "windsurf" / "mcp_config.json"),
        ),
        "vscode": (
            "VS Code (Copilot Chat)",
            vscode_user.is_dir(),
            json_client(vscode_user / "mcp.json", key="servers", extra={"type": "stdio"}),
        ),
    }


# --------------------------------------------------------------------
# Globale Befehle
# --------------------------------------------------------------------


def bin_dir_default() -> Path:
    if IS_WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA", HOME / "AppData" / "Local")) / "ClaudeGravity" / "bin"
    return HOME / ".local" / "bin"


def path_contains(directory: Path) -> bool:
    norm = lambda p: os.path.normcase(os.path.normpath(p))
    return any(norm(p) == norm(str(directory)) for p in os.environ.get("PATH", "").split(os.pathsep) if p)


def shell_rc_files() -> list[Path]:
    rcs = [HOME / ".bashrc", HOME / ".zshrc"]
    if sys.platform == "darwin":
        rcs.append(HOME / ".bash_profile")
    existing = [rc for rc in rcs if rc.exists()]
    if existing:
        return existing
    shell = os.path.basename(os.environ.get("SHELL", ""))
    return [HOME / (".zshrc" if shell == "zsh" else ".bashrc")]


def unix_path_block(bin_dir: Path) -> str:
    return f'{MARK_BEGIN}\nexport PATH="{bin_dir}:$PATH"\n{MARK_END}\n'


def install_commands_unix(bin_dir: Path, touch_path: bool) -> None:
    if not DRY_RUN:
        bin_dir.mkdir(parents=True, exist_ok=True)
    for script in set(COMMANDS.values()):
        if not DRY_RUN:
            script.chmod(script.stat().st_mode | 0o111)
    for name, target in COMMANDS.items():
        link = bin_dir / name
        if link.is_symlink() and link.resolve() == target:
            say("=", f"{name} -> {target}")
            continue
        if link.exists() and not link.is_symlink():
            say("!", f"{link} existiert bereits und ist kein Symlink – nicht überschrieben.")
            continue
        if not DRY_RUN:
            if link.is_symlink():
                link.unlink()
            link.symlink_to(target)
        say("+", f"{name} -> {target}")

    if not touch_path or path_contains(bin_dir):
        return
    for rc in shell_rc_files():
        text = rc.read_text(encoding="utf-8") if rc.exists() else ""
        if MARK_BEGIN in text:
            continue
        if not DRY_RUN:
            with rc.open("a", encoding="utf-8") as f:
                f.write(("\n" if text and not text.endswith("\n") else "") + "\n" + unix_path_block(bin_dir))
        say("+", f"PATH-Eintrag {verb('ergänzt', 'würde ergänzt')} in {rc} (neues Terminal öffnen oder `source {rc}`)")


def uninstall_commands_unix(bin_dir: Path) -> None:
    for name, target in COMMANDS.items():
        link = bin_dir / name
        if link.is_symlink() and link.resolve() == target:
            if not DRY_RUN:
                link.unlink()
            say("-", f"{link}")
    for rc in [HOME / ".bashrc", HOME / ".zshrc", HOME / ".bash_profile"]:
        if rc.exists() and MARK_BEGIN in rc.read_text(encoding="utf-8"):
            if not DRY_RUN:
                rc.write_text(strip_marked_block(rc.read_text(encoding="utf-8")), encoding="utf-8")
            say("-", f"PATH-Eintrag {verb('entfernt', 'würde entfernt')} aus {rc}")


WIN_LAUNCHERS = {
    "claudegravity": "claudegravity.bat",
    "claudegravity-loop": "claudegravity.bat",
    "claudegravity-mcp": "claudegravity-mcp.bat",
}


def win_user_path(new_value: str | None = None) -> str:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            value, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            value = ""
        if new_value is not None:
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_value)
            try:
                import ctypes

                # WM_SETTINGCHANGE an alle Fenster, damit neue Terminals den PATH sehen
                ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 0x2, 5000, None)
            except Exception:
                pass
        return value


def install_commands_windows(bin_dir: Path, touch_path: bool) -> None:
    if not DRY_RUN:
        bin_dir.mkdir(parents=True, exist_ok=True)
    for name, launcher in WIN_LAUNCHERS.items():
        shim = bin_dir / f"{name}.cmd"
        content = f'@echo off\r\ncall "{REPO_DIR / launcher}" %*\r\nexit /b %ERRORLEVEL%\r\n'
        if shim.exists() and shim.read_text(encoding="utf-8", errors="replace") == content:
            say("=", f"{shim}")
            continue
        if not DRY_RUN:
            shim.write_text(content, encoding="utf-8", newline="")
        say("+", f"{shim}")

    if not touch_path:
        return
    current = win_user_path()
    entries = [p for p in current.split(";") if p]
    if any(os.path.normcase(p.rstrip("\\")) == os.path.normcase(str(bin_dir)) for p in entries):
        say("=", f"{bin_dir} ist bereits im Benutzer-PATH")
        return
    if not DRY_RUN:
        win_user_path(";".join(entries + [str(bin_dir)]))
    say("+", f"{bin_dir} {verb('zum Benutzer-PATH hinzugefügt', 'würde zum Benutzer-PATH hinzugefügt')} (neues Terminal öffnen)")


def uninstall_commands_windows(bin_dir: Path) -> None:
    for name in WIN_LAUNCHERS:
        shim = bin_dir / f"{name}.cmd"
        if shim.exists():
            if not DRY_RUN:
                shim.unlink()
            say("-", f"{shim}")
    if bin_dir.is_dir() and not any(bin_dir.iterdir()) and not DRY_RUN:
        bin_dir.rmdir()
    current = win_user_path()
    entries = [p for p in current.split(";") if p]
    kept = [p for p in entries if os.path.normcase(p.rstrip("\\")) != os.path.normcase(str(bin_dir))]
    if kept != entries:
        if not DRY_RUN:
            win_user_path(";".join(kept))
        say("-", f"{bin_dir} {verb('aus dem Benutzer-PATH entfernt', 'würde aus dem Benutzer-PATH entfernt')}")


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------


def main() -> int:
    global DRY_RUN, PROJECT_DIR
    parser = argparse.ArgumentParser(description="ClaudeGravity Installer: MCP-Server in alle Clients eintragen & globale Befehle anlegen")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--uninstall", action="store_true", help="MCP-Einträge und globale Befehle wieder entfernen")
    mode.add_argument("--status", action="store_true", help="Anzeigen, wo ClaudeGravity eingetragen ist")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts verändern")
    parser.add_argument("--only", default=None, help="Nur diese Clients (kommagetrennt), z. B. claude,gemini,codex")
    parser.add_argument("--all-clients", action="store_true", help="Auch nicht erkannte Clients konfigurieren")
    parser.add_argument("--no-mcp", action="store_true", help="MCP-Clients nicht anfassen")
    parser.add_argument("--no-commands", action="store_true", help="Keine globalen Befehle anlegen")
    parser.add_argument("--no-path", action="store_true", help="PATH nicht verändern")
    parser.add_argument("--project", default=None, help="Standardprojekt für Desktop-Apps (CLAUDEGRAVITY_PROJECT), wenn project_path fehlt")
    parser.add_argument("--bin-dir", default=None, help=f"Zielordner für Befehle (Standard: {bin_dir_default()})")
    args = parser.parse_args()
    DRY_RUN = args.dry_run
    if args.project:
        PROJECT_DIR = Path(args.project).expanduser().resolve()
        if not PROJECT_DIR.is_dir():
            print(f"[!] --project {PROJECT_DIR} existiert nicht.")
            return 1

    if sys.version_info < (3, 10):
        print("[!] ClaudeGravity benötigt Python 3.10+.")
        return 1

    registry = clients()
    selected = list(registry)
    if args.only:
        selected = [c.strip() for c in args.only.split(",") if c.strip()]
        unknown = [c for c in selected if c not in registry]
        if unknown:
            print(f"[!] Unbekannte Clients: {', '.join(unknown)}. Verfügbar: {', '.join(registry)}")
            return 1
    bin_dir = Path(args.bin_dir).expanduser().resolve() if args.bin_dir else bin_dir_default()

    print(f"ClaudeGravity Installer ({platform.system()}) – Repo: {REPO_DIR}")
    if DRY_RUN:
        print("  (Trockenlauf: es wird nichts verändert)")

    if args.status:
        print("\nMCP-Clients:")
        for key in selected:
            label, detected, (_, _, status) = registry[key]
            mark = "✓ eingetragen" if status() else ("○ nicht eingetragen" if detected else "· nicht gefunden")
            print(f"  {mark:22} {label} [{key}]")
        print("\nGlobale Befehle:")
        for name in COMMANDS:
            found = shutil.which(name)
            print(f"  {'✓' if found else '○'} {name}{'  -> ' + found if found else ''}")
        return 0

    failures = 0
    if not args.no_mcp:
        print("\nMCP-Server:" if not args.uninstall else "\nMCP-Server entfernen:")
        for key in selected:
            label, detected, (install, uninstall, status) = registry[key]
            if args.uninstall:
                if not status():
                    continue
                print(f" {label}")
                failures += not uninstall()
            elif detected or args.all_clients or args.only:
                print(f" {label}")
                failures += not install()
            else:
                say("·", f"{label} nicht gefunden – übersprungen")

    if not args.no_commands:
        print("\nGlobale Befehle:" if not args.uninstall else "\nGlobale Befehle entfernen:")
        if IS_WINDOWS:
            (uninstall_commands_windows(bin_dir) if args.uninstall else install_commands_windows(bin_dir, not args.no_path))
        else:
            (uninstall_commands_unix(bin_dir) if args.uninstall else install_commands_unix(bin_dir, not args.no_path))

    print()
    if DRY_RUN:
        print("Trockenlauf beendet – es wurde nichts verändert.")
    elif args.uninstall:
        print("Fertig. ClaudeGravity wurde entfernt (Backups *.claudegravity.bak bleiben erhalten).")
    else:
        print("Fertig. Neues Terminal öffnen und testen mit:  claudegravity --info")
        print("MCP-Clients ggf. neu starten, damit der Server 'claudegravity' geladen wird.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
