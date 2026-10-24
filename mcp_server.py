#!/usr/bin/env python3
"""
ClaudeGravity MCP Server & Command Optimizer
Zero-dependency JSON-RPC 2.0 stdio Model Context Protocol (MCP) server for Claude Code, Antigravity, and AI assistants.
Analyzes tasks, selects optimal model pairings (Architekt, Prüfstatiker, Bauleiter),
minimizes token costs by up to 70% (or 100% in Phase 3 via local models), and outputs/executes the optimal claudegravity command.

Usage:
  - As MCP Server (stdio): python3 mcp_server.py
  - As CLI Optimizer:      python3 mcp_server.py --optimize "Task description" [--priority best-code|lowest-cost|local-free|balanced]
"""

# Damit ein zu altes Python (z. B. /usr/bin/python3 3.9 auf macOS) eine klare Meldung statt eines SyntaxErrors liefert
from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Cross-Platform Console-Encoding (Windows CMD/PowerShell UTF-8 Fix)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MCP_PROTOCOL_VERSION = "2024-11-05"
# Neueste zuerst; der Server antwortet mit der Version des Clients, wenn er sie kennt
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", MCP_PROTOCOL_VERSION)
SERVER_NAME = "claudegravity-mcp"
SERVER_VERSION = "1.4.0"
PROJECT_ENV = "CLAUDEGRAVITY_PROJECT"
HOST_ENV = "CLAUDEGRAVITY_HOST"
# clientInfo.name aus initialize → Backend-Schlüssel des Loops (Teilstring, klein geschrieben, erster Treffer gilt)
HOST_CLIENT_BACKENDS = (
    ("codex", "codex"),
    ("antigravity", "agy"),
    ("agy", "agy"),
    ("gemini", "gemini"),
    ("claude", "claude"),
    ("copilot", "copilot"),
)
HOST_LABELS = {"codex": "Codex", "agy": "Antigravity", "gemini": "Gemini CLI", "claude": "Claude", "copilot": "GitHub Copilot"}
# Lokale Server, bei denen priority "auto" zur Strategie hybrid wird
LOCAL_SERVER_KEYS = ("ollama", "lmstudio", "endpoint")
# Client, der den Server gestartet hat (aus initialize)
HOST_CLIENT: dict = {}
SERVER_INSTRUCTIONS = (
    "ClaudeGravity lässt Plan, Review und Bau von getrennten Anbietern erledigen. Ablauf: claudegravity_optimize zeigt die "
    "Rollenbelegung (der aufrufende Client wird Architekt, ein lokales Ollama prüft und baut), claudegravity_run mit background=true startet den Lauf, claudegravity_status zeigt den Fortschritt, "
    "claudegravity_stop bricht ab. project_path immer als absoluten Pfad angeben, weil Desktop-Apps den Server nicht im "
    "Projektordner starten. yolo nur auf ausdrücklichen Wunsch setzen."
)

DEFAULT_MODEL = "CLI-Default"
AUTO_OLLAMA_MODEL = "automatisch (installierte Ollama-Modelle)"
MODEL_AWARE_CLIS = ("claude", "agy", "gemini")
CLOUD_PLANNER_ORDER = ("codex", "claude", "agy", "gemini")
LOCAL_BACKEND_ORDER = ("ollama", "lmstudio", "endpoint", "ollama-cli")
OLLAMA_KEYS = ("ollama", "ollama-cli")
ROLE_PARAMS = ("architekt", "architekt_model", "pruefstatiker", "pruefstatiker_model", "bauer", "bauer_model", "abnahme", "abnahme_model")


def extra_path_dirs(home: Path | None = None) -> list[Path]:
    """Übliche Installationsorte von claude, codex, gemini, ollama & Co., die Desktop-Apps nicht im PATH haben."""
    home = home or Path.home()
    if sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        dirs = [appdata / "npm", local / "Programs" / "Ollama", home / ".local" / "bin", local / "ClaudeGravity" / "bin"]
    else:
        dirs = [
            Path("/opt/homebrew/bin"),
            Path("/usr/local/bin"),
            home / ".local" / "bin",
            home / ".npm-global" / "bin",
            home / ".bun" / "bin",
            home / ".volta" / "bin",
            home / ".cargo" / "bin",
            home / "bin",
            # CLIs, die Desktop-Apps mitbringen (nur, wenn vorhanden)
            Path("/Applications/Codex.app/Contents/Resources"),
            Path("/Applications/Antigravity.app/Contents/Resources/app/bin"),
            home / ".antigravity" / "antigravity" / "bin",
            Path("/Applications/Ollama.app/Contents/Resources"),
        ]
        # nvm: alle installierten Node-Versionen, neueste zuerst
        nvm = home / ".nvm" / "versions" / "node"
        if nvm.is_dir():
            dirs += sorted((p / "bin" for p in nvm.iterdir()), key=lambda p: p.parent.name, reverse=True)
    return dirs


def extend_search_path(env: dict | None = None, home: Path | None = None) -> list[str]:
    """Ergänzt PATH um vorhandene Ordner aus extra_path_dirs(); liefert die neu hinzugefügten Ordner."""
    env = os.environ if env is None else env
    current = [p for p in env.get("PATH", "").split(os.pathsep) if p]
    known = {os.path.normcase(os.path.normpath(p)) for p in current}
    added = []
    for directory in extra_path_dirs(home):
        key = os.path.normcase(os.path.normpath(str(directory)))
        if key not in known and directory.is_dir():
            added.append(str(directory))
            known.add(key)
    if added:
        env["PATH"] = os.pathsep.join(current + added)
    return added


def resolve_project_dir(raw: str | None) -> tuple[Path | None, str | None]:
    """Projektordner aus project_path, sonst CLAUDEGRAVITY_PROJECT, sonst cwd. Liefert (Pfad, None) oder (None, Fehlertext).

    Desktop-Apps starten den Server meist in `/` oder im Home-Ordner; ein relativer Pfad wäre dort fast immer falsch.
    """
    raw = (raw or "").strip()
    if raw in ("", ".", "./"):
        raw = os.environ.get(PROJECT_ENV, "").strip() or raw or "."
    path = Path(os.path.expandvars(os.path.expanduser(raw)))
    if not path.is_absolute():
        cwd = Path.cwd()
        if cwd == Path(cwd.anchor) or cwd == Path.home():
            return None, (
                f"Fehler: project_path `{raw}` ist relativ, der MCP-Server läuft aber in `{cwd}` (typisch für Desktop-Apps). "
                f"Bitte einen absoluten Pfad angeben oder {PROJECT_ENV} in der MCP-Konfiguration setzen."
            )
        path = cwd / path
    path = path.resolve()
    if not path.is_dir():
        return None, f"Fehler: Projektpfad '{path}' existiert nicht."
    return path, None


def host_backend(client_name: str | None = None) -> str | None:
    """Backend-Schlüssel des aufrufenden Clients: CLAUDEGRAVITY_HOST, sonst clientInfo.name aus initialize."""
    forced = os.environ.get(HOST_ENV, "").strip().lower()
    if forced:
        return None if forced in ("aus", "off", "none") else forced
    name = (client_name if client_name is not None else HOST_CLIENT.get("name", "")).lower()
    return next((key for part, key in HOST_CLIENT_BACKENDS if part in name), None)


def is_endpoint_reachable(url: str, timeout: float = 0.3) -> bool:
    """Kurzer GET-Test; auch 401/403/404/405 zählen als erreichbar, weil dort ein Server antwortet."""
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "ClaudeGravity-MCP/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in [200, 401, 403, 404, 405]
    except Exception:
        return False


def ollama_base_url() -> str:
    """Adresse des Ollama-Servers aus OLLAMA_HOST (wie bei der Ollama-CLI), sonst localhost:11434."""
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if not host:
        return "http://localhost:11434"
    if "://" not in host:
        host = "http://" + host
    parts = urllib.parse.urlsplit(host)
    name = parts.hostname or "localhost"
    if name in ("0.0.0.0", "::"):
        name = "localhost"
    if ":" in name:
        name = f"[{name}]"
    return f"{parts.scheme}://{name}:{parts.port or 11434}"


def detect_installed_agents() -> dict[str, str]:
    """Installierte CLIs und erreichbare Endpunkte mit Anzeigenamen, wie loop.py sie erkennt."""
    agents = {}
    if shutil.which("claude"):
        agents["claude"] = "Claude Code"
    if shutil.which("agy"):
        agents["agy"] = "Google Antigravity (agy)"
    if shutil.which("gemini"):
        agents["gemini"] = "Gemini CLI"
    if shutil.which("codex"):
        agents["codex"] = "Codex CLI"
    if shutil.which("copilot") or shutil.which("gh"):
        agents["copilot"] = "GitHub Copilot CLI"
    if shutil.which("ollama"):
        agents["ollama-cli"] = "Ollama CLI"

    ollama_url = ollama_base_url()
    if is_endpoint_reachable(ollama_url, timeout=0.3 if "localhost" in ollama_url else 1.5):
        agents["ollama"] = f"Ollama ({'Lokal' if 'localhost' in ollama_url else 'Netzwerk'}: {ollama_url})"
    if is_endpoint_reachable("http://localhost:1234"):
        agents["lmstudio"] = "LM Studio (Lokal: http://localhost:1234)"

    env_endpoint = os.environ.get("CLAUDEGRAVITY_ENDPOINT") or os.environ.get("OPENAI_BASE_URL") or os.environ.get("AI_ENDPOINT")
    if env_endpoint:
        label = "Benutzerdefinierter KI-Server"
        agents["endpoint"] = f"{label} ({env_endpoint})"

    return agents


def analyze_task_complexity(task: str) -> dict:
    """Grobe Einschätzung der Aufgabe aus Schlüsselwörtern (Refactor, Sicherheit, Architektur, Tests, kleiner Fix)."""
    t_lower = task.lower()
    is_refactor = any(w in t_lower for w in ["refactor", "refaktoriere", "umbau", "restrukturier", "clean up", "aufräumen"])
    is_security = any(w in t_lower for w in ["secur", "sicher", "auth", "token", "login", "vulnerability", "lücke", "passw"])
    is_architectural = any(w in t_lower for w in ["architekt", "migration", "redesign", "framework", "datenbank", "schema", "api design"])
    is_testing = any(w in t_lower for w in ["test", "unit", "pytest", "spec", "coverage", "abdeckung"])
    is_small_fix = any(w in t_lower for w in ["fix", "bug", "fehler", "korrigier", "typo", "klein", "patch"]) and not (
        is_refactor or is_architectural
    )

    complexity = "hoch" if (is_architectural or is_refactor or is_security) else ("niedrig" if is_small_fix else "mittel")

    return {
        "complexity": complexity,
        "is_refactor": is_refactor,
        "is_security": is_security,
        "is_architectural": is_architectural,
        "is_testing": is_testing,
        "is_small_fix": is_small_fix,
    }


def format_shell_command(argv: list[str], shell: str = "bash") -> str:
    """Formatiert einen Befehl zum Kopieren ins Terminal, korrekt gequotet für bash, cmd oder powershell."""
    if shell == "cmd":
        return subprocess.list2cmdline(argv)
    if shell == "powershell":
        return " ".join([argv[0]] + ["'" + a.replace("'", "''") + "'" for a in argv[1:]])
    return shlex.join(argv)


def loop_launch_argv(loop_args: list[str]) -> list[str]:
    """Startbefehl für loop.py ohne Shell: Aufgabentext wird nie von einer Shell interpretiert."""
    return [sys.executable, str(Path(__file__).resolve().parent / "loop.py")] + loop_args


def background_log_path(project_dir: Path) -> Path:
    """Log für Hintergrundläufe. Liegt als Datei in sessions/, damit .dual-loop nur diesen Unterordner hat."""
    sessions = project_dir / ".dual-loop" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    return sessions / f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_background.log"


# Im Hintergrund gestartete Läufe dieses Server-Prozesses, damit beendete Läufe nicht als Zombie "laufend" wirken
BACKGROUND_PROCS: dict[int, subprocess.Popen] = {}


def background_info_path(log_path: Path) -> Path:
    """JSON neben dem Hintergrund-Log mit PID, Startzeit und Befehl."""
    return log_path.with_name(log_path.name[: -len(".log")] + ".json")


def latest_background_run(project_dir: Path) -> dict | None:
    """Angaben zum letzten Hintergrundlauf im Projekt (aus der JSON neben dem Log) oder None."""
    sessions = project_dir / ".dual-loop" / "sessions"
    if not sessions.is_dir():
        return None
    for path in sorted(sessions.glob("*_background.json"), key=lambda p: p.name, reverse=True):
        try:
            info = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(info, dict) and isinstance(info.get("pid"), int):
            return info
    return None


def process_state(pid: int) -> tuple[bool, int | None]:
    """(läuft noch, Exit-Code oder None). Den Exit-Code kennt nur der Server-Prozess, der den Lauf gestartet hat."""
    proc = BACKGROUND_PROCS.get(pid)
    if proc is not None:
        code = proc.poll()
        return code is None, code
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False, None
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False, None
            return code.value == 259, None  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False, None
    except PermissionError:
        return True, None
    except OSError:
        return False, None
    return True, None


def stop_background_run(project_dir: Path) -> tuple[bool, str]:
    """Beendet den letzten Hintergrundlauf des Projekts samt Kindprozessen. Nur PIDs aus der eigenen Lauf-Datei."""
    info = latest_background_run(project_dir)
    if info is None:
        return False, f"Kein Hintergrundlauf in `{project_dir}` gefunden."
    pid = info["pid"]
    running, _ = process_state(pid)
    if not running:
        return False, f"Der letzte Hintergrundlauf (PID {pid}) läuft nicht mehr."
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
        else:
            # Eigene Prozessgruppe (start_new_session): SIGTERM erreicht auch die CLIs; der Loop speichert dabei seinen Stand
            os.killpg(pid, signal.SIGTERM)
    except OSError as exc:
        return False, f"Konnte PID {pid} nicht beenden: {exc}"
    return True, f"🛑 Hintergrundlauf (PID {pid}) beendet. Fortsetzen mit `claudegravity -c` im Projekt `{project_dir}`."


def tail_lines(path: Path, count: int) -> list[str]:
    """Letzte `count` Zeilen einer Textdatei; leere Liste, wenn sie fehlt oder unlesbar ist."""
    if count <= 0 or not path.is_file():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-count:]
    except OSError:
        return []


def format_session_status(project_dir: Path, log_lines: int = 15) -> str:
    """Stand der letzten Session aus state.json, .done und den Logs, als Markdown."""
    sessions = project_dir / ".dual-loop" / "sessions"
    entries = sorted(sessions.iterdir(), key=lambda p: p.name) if sessions.is_dir() else []
    session = next((p for p in reversed(entries) if p.is_dir()), None)
    background = next((p for p in reversed(entries) if p.is_file() and p.name.endswith("_background.log")), None)
    if session is None and background is None:
        return f"Keine Session in `{project_dir}` gefunden. Start mit `claudegravity_run`."
    lines = [f"### ClaudeGravity Status: `{project_dir}`", ""]
    if session is not None:
        state: dict = {}
        for name in ("state.json", "state.json.bak"):
            try:
                state = json.loads((session / name).read_text(encoding="utf-8"))
                break
            except (OSError, ValueError):
                continue
        state = state if isinstance(state, dict) else {}
        done = (session / ".done").exists()
        metrics = state.get("metrics") or {}
        step = state.get("last_iteration")
        if state.get("stages"):
            step = f"{step} (Etappe {int(state.get('stage_index', 0)) + 1}/{len(state['stages'])})"
        lines += [
            f"* **Session:** `{session.name}`",
            f"* **Aufgabe:** {state.get('task', '?')}",
            f"* **Phase:** {state.get('phase', '?')}" + (" · Fertigmeldung liegt vor" if done else ""),
            f"* **Bau-Runde:** {step if step is not None else '–'}",
            f"* **Tokens:** {metrics.get('total_tokens', 0):,}".replace(",", ".")
            + (f" · gemeldete Kosten {metrics['cost_usd']:.2f} USD" if metrics.get("cost_usd") else ""),
            f"* **Zuletzt aktualisiert:** {state.get('updated_at', '?')}",
        ]
        if state.get("abort_reason"):
            lines.append(f"* **Abbruchgrund:** {state['abort_reason']}")
        log_tail = tail_lines(session / "LOG.md", log_lines)
        if log_tail:
            lines += ["", "**LOG.md (Ende):**", "```", *log_tail, "```"]
    run = latest_background_run(project_dir)
    if run is not None:
        running, code = process_state(run["pid"])
        if running:
            state_text = "läuft noch"
        elif code is None:
            state_text = "beendet"
        else:
            state_text = f"beendet (Exit-Code {code})"
        lines += ["", f"**Hintergrundlauf:** PID {run['pid']} · {state_text} · gestartet {run.get('started_at', '?')}"]
    if background is not None:
        bg_tail = tail_lines(background, log_lines)
        lines += ["", f"**Hintergrund-Log:** `{background}`"]
        if bg_tail:
            lines += ["```", *bg_tail, "```"]
    return "\n".join(lines)


def optimize_claudegravity_command(
    task: str,
    priority: str = "auto",
    project_path: str = ".",
    endpoint: str | None = None,
    ask_mode: bool = False,
    yolo: bool = False,
    max_iterations: int = 10,
    proof: str | None = None,
    roles: dict | None = None,
    stages: str = "auto",
    approve_plan: bool = False,
    merge: bool = False,
) -> dict:
    """Berechnet Rollen und Befehl. `roles` überschreibt einzelne Rollen, z. B. {"architekt": "codex", "bauer_model": "qwen3-coder:30b"}."""
    agents = detect_installed_agents()
    roles = {k: v for k, v in (roles or {}).items() if v}
    comp = analyze_task_complexity(task)
    p_norm = priority.lower().strip()
    if p_norm in ["best-code", "quality", "best", "code"]:
        p_norm = "best-code"
    elif p_norm in ["lowest-cost", "eco", "economy", "cost", "lowest"]:
        p_norm = "lowest-cost"
    elif p_norm in ["local-free", "free", "local"]:
        p_norm = "local-free"
    elif p_norm in ["hybrid", "mixed"]:
        p_norm = "hybrid"
    elif p_norm in ["auto", ""]:
        # Cloud plant, lokales Modell prüft und baut, sobald Ollama, LM Studio oder ein Endpunkt erreichbar ist
        p_norm = "hybrid" if endpoint or any(k in agents for k in LOCAL_SERVER_KEYS) else "balanced"
        priority = "auto"
    else:
        p_norm = "balanced"

    has_claude = "claude" in agents
    has_agy = "agy" in agents
    has_gemini = "gemini" in agents

    if has_claude and (has_agy or has_gemini):
        planner_cli = "claude"
        reviewer_cli = "agy" if has_agy else "gemini"
    elif has_agy and has_claude:
        planner_cli = "claude"
        reviewer_cli = "agy"
    elif has_claude:
        planner_cli = "claude"
        reviewer_cli = "claude"
    elif has_agy:
        planner_cli = "agy"
        reviewer_cli = "agy"
    else:
        avail = list(agents.keys())
        planner_cli = avail[0] if avail else "claude"
        reviewer_cli = avail[1] if len(avail) > 1 else planner_cli

    if p_norm == "best-code":
        strategy_flag = "best-code"
        planner_model = "sonnet" if planner_cli == "claude" else "gemini-4-argon"
        planner_effort = "high"
        reviewer_model = "gemini-4-argon" if reviewer_cli in ["agy", "gemini"] else "sonnet"
        reviewer_effort = "high"
        builder_cli = planner_cli
        builder_model = planner_model
        builder_effort = "high"
        cost_benefit = (
            "💎 Maximale Codequalität & Sicherheit: Alle Phasen (Architekt, Prüfstatiker, Bauleiter) "
            "nutzen Frontier-Modelle mit intensivem Thinking-Effort. Höchste Fehlertoleranz und "
            "gründlichste Testabdeckung."
        )
    elif p_norm == "lowest-cost":
        strategy_flag = "eco"
        planner_model = "sonnet" if planner_cli == "claude" else "gemini-4-argon"
        planner_effort = "medium"
        reviewer_model = "gemini-4-argon" if reviewer_cli in ["agy", "gemini"] else "sonnet"
        reviewer_effort = "medium"
        builder_cli = planner_cli
        builder_model = "haiku" if builder_cli == "claude" else "gemini-3.8-flash"
        builder_effort = "low"
        cost_benefit = (
            "💰 Maximale Kosten- & Tokenersparnis (bis zu 70% Ersparnis!):\n"
            "   • Phase 1 (Planung) & Phase 2 (Review) verbrauchen nur ~10-15% aller Tokens -> Spitzenmodell sichert fehlerfreie Architektur.\n"
            f"   • Phase 3 (Bau-Loop) verbraucht ~85-90% aller Tokens -> Schnelles Spar-Modell ({builder_model}) setzt den genehmigten Plan kostengünstig um."
        )
    elif p_norm == "hybrid":
        strategy_flag = "hybrid"
        planner_cli = next((k for k in CLOUD_PLANNER_ORDER if k in agents), planner_cli)
        local = next((k for k in LOCAL_BACKEND_ORDER if k in agents), None)
        reviewer_cli = local or reviewer_cli
        builder_cli = local or planner_cli
        planner_model = DEFAULT_MODEL
        planner_effort = "high"
        reviewer_model = AUTO_OLLAMA_MODEL if local in OLLAMA_KEYS else DEFAULT_MODEL
        reviewer_effort = None
        builder_model = AUTO_OLLAMA_MODEL if local in OLLAMA_KEYS else DEFAULT_MODEL
        builder_effort = None
        cost_benefit = (
            "🧩 Hybrid: Die Cloud-CLI plant und nimmt ab (wenige Tokens), ein lokales Modell prüft den Plan und baut "
            "ihn in kleinen Etappen für 0 €. Der Loop prüft jede Etappe mit dem Prüfbefehl."
            + ("" if local else "\n   ⚠️ Kein lokales Modell erkannt (Ollama, LM Studio, Endpunkt): Hybrid fällt auf die Cloud-CLI zurück.")
        )
    elif p_norm == "local-free":
        strategy_flag = "local-free"
        planner_model = "sonnet" if planner_cli == "claude" else "gemini-4-argon"
        planner_effort = "high"
        reviewer_model = "gemini-4-argon" if reviewer_cli in ["agy", "gemini"] else "sonnet"
        reviewer_effort = "high"

        if endpoint:
            builder_cli = f"Endpoint ({endpoint})"
            builder_model = "qwen2.5-coder:32b"
        elif "endpoint" in agents:
            builder_cli = agents["endpoint"]
            builder_model = "qwen2.5-coder:32b"
        elif "ollama" in agents:
            builder_cli = "ollama"
            builder_model = AUTO_OLLAMA_MODEL
        elif "lmstudio" in agents:
            builder_cli = "LM Studio (Lokal)"
            builder_model = "default"
        else:
            builder_cli = planner_cli
            builder_model = "qwen2.5-coder:latest"

        builder_effort = "low"
        cost_benefit = (
            "💎 100% kostenlose Bau-Iterationen (0 € API-Kosten in Phase 3!):\n"
            "   • Phase 1 & 2 nutzen exzellente Cloud-Architektur (Claude/Gemini).\n"
            f"   • Phase 3 (Bau-Loop) wird komplett an das lokale / private KI-Modell ({builder_cli}) übergeben."
        )
    else:  # balanced
        strategy_flag = "balanced"
        planner_model = "sonnet (Standard)" if planner_cli == "claude" else "gemini-4-argon (Standard)"
        planner_effort = "high" if planner_cli == "agy" else None
        reviewer_model = "gemini-4-argon (Standard)" if reviewer_cli in ["agy", "gemini"] else "sonnet (Standard)"
        reviewer_effort = "high" if reviewer_cli == "agy" else None
        builder_cli = planner_cli
        builder_model = planner_model
        builder_effort = None
        cost_benefit = (
            "⚖️ Ausgewogene Standard-Konfiguration: Hohe Denk-Präzision in der Planung bei verlässlicher Ausführungsgeschwindigkeit."
        )

    # Modellnamen gelten nur für Claude und Gemini; andere CLIs nutzen ihr eigenes Standardmodell
    if planner_cli not in MODEL_AWARE_CLIS and planner_model != AUTO_OLLAMA_MODEL:
        planner_model = DEFAULT_MODEL
    if reviewer_cli not in MODEL_AWARE_CLIS and reviewer_model != AUTO_OLLAMA_MODEL:
        reviewer_model = DEFAULT_MODEL
    if p_norm in ("best-code", "lowest-cost", "balanced") and builder_cli not in MODEL_AWARE_CLIS:
        builder_model = DEFAULT_MODEL

    # Der Client, aus dem der Server aufgerufen wird, führt den Loop als Architekt, wenn seine CLI installiert ist.
    # Ausdrückliche Rollen gehen vor; der Prüfstatiker bleibt ein anderer Anbieter.
    host = host_backend()
    host_leads = bool(host and host in agents and "architekt" not in roles)
    if host_leads:
        if host != planner_cli:
            if builder_cli == planner_cli and "bauer" not in roles:
                roles["bauer"] = host
            roles["architekt"] = host
        if reviewer_cli == host and "pruefstatiker" not in roles:
            alternative = next((k for k in LOCAL_BACKEND_ORDER + CLOUD_PLANNER_ORDER if k in agents and k != host), None)
            if alternative:
                roles["pruefstatiker"] = alternative

    # Ausdrückliche Rollen aus dem Aufruf haben Vorrang
    planner_cli = roles.get("architekt", planner_cli)
    reviewer_cli = roles.get("pruefstatiker", reviewer_cli)
    if "bauer" in roles:
        builder_cli = roles["bauer"]
    for key in ("architekt", "pruefstatiker", "bauer"):
        if key in roles and f"{key}_model" not in roles:
            roles_model = AUTO_OLLAMA_MODEL if roles[key] in OLLAMA_KEYS else DEFAULT_MODEL
            if key == "architekt":
                planner_model = roles_model
            elif key == "pruefstatiker":
                reviewer_model = roles_model
            else:
                builder_model = roles_model
    planner_model = roles.get("architekt_model", planner_model)
    reviewer_model = roles.get("pruefstatiker_model", reviewer_model)
    builder_model = roles.get("bauer_model", builder_model)
    inspector_cli = roles.get("abnahme")

    cmd_args = [task]
    if strategy_flag != "balanced":
        cmd_args += ["--strategy", strategy_flag]
    if endpoint:
        cmd_args += ["--endpoint", endpoint]
    for flag, key in (
        ("--architekt", "architekt"),
        ("--architekt-model", "architekt_model"),
        ("--pruefstatiker", "pruefstatiker"),
        ("--pruefstatiker-model", "pruefstatiker_model"),
        ("--bauer", "bauer"),
        ("--bauer-model", "bauer_model"),
        ("--abnahme", "abnahme"),
        ("--abnahme-model", "abnahme_model"),
    ):
        if key in roles:
            cmd_args += [flag, str(roles[key])]
    if p_norm in ("lowest-cost", "local-free") and "bauer_model" not in roles and builder_model not in (AUTO_OLLAMA_MODEL, DEFAULT_MODEL):
        cmd_args += ["--bauer-model", builder_model]
    if ask_mode or comp["is_architectural"]:
        cmd_args.append("-i")
    if yolo:
        cmd_args.append("--yolo")
    if max_iterations != 10:
        cmd_args += ["-m", str(max_iterations)]
    if proof:
        cmd_args += ["--proof", proof]
    if stages and stages != "auto":
        cmd_args += ["--etappen", stages]
    if approve_plan:
        cmd_args.append("--plan-auto")
    if merge:
        cmd_args.append("--merge")
    if project_path not in [".", "./", ""]:
        cmd_args += ["-p", project_path]

    command_str = format_shell_command(["claudegravity"] + cmd_args)

    return {
        "task": task,
        "priority": p_norm,
        "priority_auto": priority == "auto",
        "host": {"backend": host, "client": HOST_CLIENT.get("name"), "leads": host_leads},
        "complexity_analysis": comp,
        "strategy": strategy_flag,
        "roles": {
            "architekt": {
                "role": "🏗️ Architekt (Phase 1: Planung & Entwurf)",
                "cli": planner_cli,
                "model": planner_model,
                "effort": planner_effort or "Standard",
                "token_share": "~10-15% der Gesamt-Tokens",
            },
            "pruefstatiker": {
                "role": "🧐 Prüfstatiker (Phase 2: Prüfung & Review)",
                "cli": reviewer_cli,
                "model": reviewer_model,
                "effort": reviewer_effort or "Standard",
                "token_share": "~5-10% der Gesamt-Tokens",
            },
            "bauleiter": {
                "role": "🔨 Bauleiter (Phase 3: Bau & Umsetzung)",
                "cli": builder_cli,
                "model": builder_model,
                "effort": builder_effort or "Standard",
                "token_share": "~80-90% der Gesamt-Tokens (Hauptverbrauch!)",
            },
            "abnahme": {
                "role": "🔎 Abnahme (Phase 4: Prüfung des fertigen Codes)",
                "cli": inspector_cli
                or (planner_cli if p_norm == "hybrid" else "automatisch (Prüfstatiker oder Architekt, nie der Bauleiter)"),
                "model": roles.get("abnahme_model", DEFAULT_MODEL),
                "effort": "Standard",
                "token_share": "gering (nur der Diff)",
            },
        },
        "stages": stages or "auto",
        "cost_benefit_analysis": cost_benefit,
        "recommended_command": command_str,
        "loop_args": cmd_args,
        "installed_agents": agents,
    }


def host_lines(host: dict) -> list[str]:
    """Zeile zum aufrufenden Client für die Empfehlung (leer, wenn keiner erkannt wurde)."""
    backend = host.get("backend")
    if not backend:
        return []
    label = HOST_LABELS.get(backend, backend)
    if host.get("leads"):
        return [f"* **Aufgerufen aus:** {label} – führt den Loop als Architekt (`{backend}`)"]
    return [f"* **Aufgerufen aus:** {label} – CLI `{backend}` nicht im PATH, daher nicht als Rolle eingesetzt"]


def format_optimization_markdown(opt: dict) -> str:
    """Empfehlung von claudegravity_optimize als Markdown mit Rollen und Startbefehlen für Bash, CMD und PowerShell."""
    r = opt["roles"]
    cmd_base = opt["recommended_command"]
    cmd_cmd = format_shell_command(["claudegravity.bat"] + opt["loop_args"], "cmd")
    cmd_ps = format_shell_command([".\\claudegravity.ps1"] + opt["loop_args"], "powershell")

    lines = [
        "### 🎯 ClaudeGravity Optimierungs-Empfehlung",
        f"* **Aufgabe:** {opt['task']}",
        f"* **Gewählte Priorität:** `{opt['priority']}`"
        + (" (automatisch)" if opt.get("priority_auto") else "")
        + f" (Erkannte Komplexität: {opt['complexity_analysis']['complexity']})",
        *host_lines(opt.get("host") or {}),
        "",
        "#### 👥 Rollen- und Modellbelegung:",
        f"1. **{r['architekt']['role']}**",
        f"   • CLI/Endpoint: `{r['architekt']['cli']}` | Modell: `{r['architekt']['model']}` | Effort: `{r['architekt']['effort']}`",
        f"   • Token-Anteil: {r['architekt']['token_share']}",
        f"2. **{r['pruefstatiker']['role']}**",
        f"   • CLI/Endpoint: `{r['pruefstatiker']['cli']}` | Modell: `{r['pruefstatiker']['model']}` | Effort: `{r['pruefstatiker']['effort']}`",
        f"   • Token-Anteil: {r['pruefstatiker']['token_share']}",
        f"3. **{r['bauleiter']['role']}**",
        f"   • CLI/Endpoint: `{r['bauleiter']['cli']}` | Modell: `{r['bauleiter']['model']}` | Effort: `{r['bauleiter']['effort']}`",
        f"   • Token-Anteil: {r['bauleiter']['token_share']}",
        f"4. **{r['abnahme']['role']}**",
        f"   • CLI/Endpoint: `{r['abnahme']['cli']}` | Modell: `{r['abnahme']['model']}`",
        f"* **Etappen-Modus:** `{opt.get('stages', 'auto')}` (auto: an, wenn der Bauleiter ein lokales Modell oder ein Endpunkt ist)",
        "",
        "#### 💡 Wirtschaftlichkeits- & Qualitäts-Analyse:",
        opt["cost_benefit_analysis"],
        "",
        "#### 🚀 Empfohlener Befehl für dein System:",
        "*Linux / macOS (Bash / Zsh):*",
        "```bash",
        cmd_base,
        "```",
        "*Windows (CMD / Eingabeaufforderung):*",
        "```cmd",
        cmd_cmd,
        "```",
        "*Windows (PowerShell):*",
        "```powershell",
        cmd_ps,
        "```",
    ]
    return "\n".join(lines)


# ==========================================
# MCP Protocol Handlers (JSON-RPC 2.0 stdio)
# ==========================================

ROLE_SCHEMA = {
    "architekt": {"type": "string", "description": "CLI für den Architekten (claude, agy, gemini, codex, ollama, lmstudio, endpoint)."},
    "architekt_model": {"type": "string", "description": "Modell für den Architekten (z. B. qwen3:30b bei Ollama)."},
    "pruefstatiker": {
        "type": "string",
        "description": "CLI für den Prüfstatiker, nie derselbe Anbieter mit demselben Modell wie der Architekt.",
    },
    "pruefstatiker_model": {"type": "string", "description": "Modell für den Prüfstatiker (z. B. gpt-oss:20b bei Ollama)."},
    "bauer": {"type": "string", "description": "CLI für den Bauleiter (z. B. ollama)."},
    "bauer_model": {
        "type": "string",
        "description": "Modell für den Bauleiter (z. B. qwen3-coder:30b). Ohne Angabe wählt der Loop bei Ollama aus den installierten Modellen.",
    },
    "abnahme": {"type": "string", "description": "CLI für die Abnahme des fertigen Codes, nie der Bauleiter (z. B. codex)."},
    "abnahme_model": {"type": "string", "description": "Modell für die Abnahme."},
    "stages": {
        "type": "string",
        "enum": ["auto", "an", "aus"],
        "default": "auto",
        "description": "Etappen-Modus: Plan in Etappen, Bauleiter setzt sie einzeln um (auto: an bei lokalen Bauleitern).",
    },
    "approve_plan": {
        "type": "boolean",
        "default": False,
        "description": "Plan ohne Rückfrage freigeben, sobald der Prüfstatiker APPROVED meldet (--plan-auto). Im Hintergrund immer an.",
    },
    "merge": {
        "type": "boolean",
        "default": False,
        "description": "Session-Branch nach erfolgreicher Abnahme in den Ausgangs-Branch mergen (--merge).",
    },
}


def role_arguments(arguments: dict) -> dict:
    """Nur die gesetzten Rollen-Parameter aus den Tool-Argumenten."""
    return {k: arguments.get(k) for k in ROLE_PARAMS if arguments.get(k)}


MCP_TOOLS = [
    {
        "name": "claudegravity_optimize",
        "title": "ClaudeGravity: Rollen und Befehl empfehlen",
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
        "description": (
            "Analysiert eine Programmieraufgabe und ermittelt die optimale Kombination aus Modellen, "
            "Reasoning-Effort und Rollen (Architekt, Prüfstatiker, Bauleiter) für ClaudeGravity Loop basierend auf dem Ziel "
            "(bester Code vs. geringste Kosten vs. 0€ lokale Modelle). Liefert den exakten, plattformunabhängigen Shell-Befehl."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Beschreibung der Programmieraufgabe, des Refactorings oder des neuen Features."},
                "priority": {
                    "type": "string",
                    "enum": ["auto", "best-code", "lowest-cost", "local-free", "hybrid", "balanced"],
                    "default": "auto",
                    "description": "auto (hybrid, sobald Ollama, LM Studio oder ein Endpunkt erreichbar ist, sonst balanced), best-code (Frontier-Modelle), lowest-cost (bis zu 70% Ersparnis), local-free (0€ Bauleiter via Ollama, LM Studio oder Server im Heimnetz), hybrid (der aufrufende Client bzw. eine Cloud-CLI plant und nimmt ab, Ollama prüft und baut in Etappen), balanced (ausgewogen).",
                },
                "endpoint": {
                    "type": "string",
                    "description": "Optionaler KI-Endpunkt (z.B. http://localhost:11434/v1 oder http://192.168.1.50:11434/v1).",
                },
                "project_path": {"type": "string", "default": ".", "description": "Pfad zum Ziel-Projektverzeichnis (Standard: .)."},
                "ask_mode": {
                    "type": "boolean",
                    "default": False,
                    "description": "Ob der interaktive Fragen-Modus (-i / --ask) für menschliche Klärung aktiviert werden soll.",
                },
                "yolo": {
                    "type": "boolean",
                    "default": False,
                    "description": "Ob volle Schreib- und Toolrechte ohne manuelle Nachfrage erteilt werden sollen (--yolo).",
                },
                "proof": {
                    "type": "string",
                    "description": "Optionaler Prüfbefehl (--proof), den der Loop nach jeder Bau-Runde selbst ausführt.",
                },
                "max_iterations": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximale Anzahl autonomer Runden in Phase 3 (Standard: 10).",
                },
                **ROLE_SCHEMA,
            },
            "required": ["task"],
        },
    },
    {
        "name": "claudegravity_run",
        "title": "ClaudeGravity: Loop starten",
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
        "description": (
            "Startet den ClaudeGravity Loop mit optimierten Parametern direkt auf dem System. Mit background=true läuft er "
            "als eigener Prozess weiter (für Desktop-Apps ohne Terminal); Fortschritt mit claudegravity_status, Abbruch mit "
            "claudegravity_stop. Ohne background kommt nur der Befehl zum Starten im Terminal zurück."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Die auszuführende Aufgabe."},
                "priority": {
                    "type": "string",
                    "enum": ["auto", "best-code", "lowest-cost", "local-free", "hybrid", "balanced"],
                    "default": "auto",
                    "description": "Wie bei claudegravity_optimize; auto nimmt hybrid, wenn ein lokales Modell erreichbar ist.",
                },
                "endpoint": {"type": "string", "description": "Optionaler KI-Endpunkt."},
                "project_path": {
                    "type": "string",
                    "default": ".",
                    "description": "Absoluter Pfad zum Projekt. Ohne Angabe CLAUDEGRAVITY_PROJECT bzw. das Arbeitsverzeichnis des Servers.",
                },
                "yolo": {
                    "type": "boolean",
                    "default": False,
                    "description": "Volle Schreib- und Toolrechte für den Bauleiter ohne Nachfrage (--yolo). Nur auf ausdrücklichen Wunsch setzen; Architekt und Prüfstatiker bleiben immer lesend.",
                },
                "proof": {
                    "type": "string",
                    "description": "Prüfbefehl, den der Loop nach jeder Bau-Runde selbst ausführt, z.B. 'python -m unittest discover -s tests'.",
                },
                "ask_mode": {"type": "boolean", "default": False, "description": "Fragen-Modus (-i); entfällt im Hintergrund."},
                "max_iterations": {"type": "integer", "default": 10},
                "background": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "Im Hintergrund starten. Setzt --plan-auto (gebaut wird nur ein vom Prüfstatiker genehmigter Plan) "
                        "und lässt -i weg, weil niemand Rückfragen beantworten kann."
                    ),
                },
                **ROLE_SCHEMA,
            },
            "required": ["task"],
        },
    },
    {
        "name": "claudegravity_status",
        "title": "ClaudeGravity: Stand des Laufs",
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
        "description": (
            "Zeigt den Stand der letzten Loop-Session eines Projekts: Aufgabe, Phase, Runde/Etappe, Tokens, "
            "Abbruchgrund, ob die Fertigmeldung vorliegt, ob ein Hintergrundlauf noch läuft, und die letzten Zeilen von LOG.md "
            "und des Hintergrund-Logs. "
            "Gedacht zum Nachsehen nach claudegravity_run mit background."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "default": ".", "description": "Absoluter Pfad zum Ziel-Projekt."},
                "log_lines": {"type": "integer", "default": 15, "description": "Wie viele Zeilen vom Ende der Logs (0 = keine)."},
            },
        },
    },
    {
        "name": "claudegravity_stop",
        "title": "ClaudeGravity: Hintergrundlauf abbrechen",
        "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False},
        "description": (
            "Bricht den letzten mit claudegravity_run (background) gestarteten Lauf eines Projekts ab, samt der gestarteten CLIs. "
            "Der Stand bleibt in der Session erhalten und lässt sich mit `claudegravity -c` fortsetzen."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"project_path": {"type": "string", "default": ".", "description": "Absoluter Pfad zum Ziel-Projekt."}},
        },
    },
    {
        "name": "claudegravity_info",
        "title": "ClaudeGravity: Systemprüfung",
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
        "description": "Prüft die installierten AI-CLIs (Claude, Antigravity, Gemini, Codex, Copilot, Ollama, LM Studio, eigene Endpunkte) und gibt Empfehlungen.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def text_result(text: str, is_error: bool = False) -> dict:
    """Tool-Ergebnis im MCP-Format mit einem Textblock."""
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def manual_start_command(project_dir: Path, loop_args: list[str]) -> tuple[str, str]:
    """(Sprache, Befehl) zum Start im Terminal dieses Systems; nutzt dasselbe Python wie der Server."""
    argv = loop_launch_argv(loop_args)
    if sys.platform == "win32":
        quoted = " ".join("'" + a.replace("'", "''") + "'" for a in argv)
        return "powershell", f"Set-Location -LiteralPath '{str(project_dir).replace(chr(39), chr(39) * 2)}'; & {quoted}"
    return "bash", f"cd {shlex.quote(str(project_dir))} && {shlex.join(argv)}"


def start_background_run(project_dir: Path, loop_args: list[str]) -> tuple[subprocess.Popen, Path]:
    """Startet loop.py losgelöst vom MCP-Server: eigene Sitzung bzw. Prozessgruppe, kein stdin, unter Windows ohne Fenster."""
    log_path = background_log_path(project_dir)
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200) | getattr(
            subprocess, "CREATE_NO_WINDOW", 0x08000000
        )
    else:
        kwargs["start_new_session"] = True
    with open(log_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            loop_launch_argv(loop_args),
            cwd=str(project_dir),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
            **kwargs,
        )
    BACKGROUND_PROCS[proc.pid] = proc
    info = {
        "pid": proc.pid,
        "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "log": str(log_path),
        "loop_args": loop_args,
    }
    background_info_path(log_path).write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return proc, log_path


def optimize_from_arguments(arguments: dict, project_path: str) -> dict:
    """optimize_claudegravity_command() mit den Tool-Argumenten eines MCP-Aufrufs."""
    try:
        max_iterations = int(arguments.get("max_iterations", 10))
    except (TypeError, ValueError):
        max_iterations = 10
    return optimize_claudegravity_command(
        task=arguments.get("task", ""),
        priority=arguments.get("priority") or "auto",
        project_path=project_path,
        endpoint=arguments.get("endpoint"),
        ask_mode=bool(arguments.get("ask_mode", False)),
        yolo=bool(arguments.get("yolo", False)),
        max_iterations=max_iterations,
        proof=arguments.get("proof"),
        roles=role_arguments(arguments),
        stages=arguments.get("stages", "auto"),
        approve_plan=bool(arguments.get("approve_plan", False) or arguments.get("background", False)),
        merge=bool(arguments.get("merge", False)),
    )


def handle_tool_call(name: str, arguments: dict) -> dict:
    """Einen MCP-Tool-Aufruf ausführen und das Ergebnis im MCP-Format liefern."""
    arguments = arguments if isinstance(arguments, dict) else {}
    if name in ("claudegravity_optimize", "claudegravity_run") and not str(arguments.get("task", "")).strip():
        return text_result("Fehler: Parameter `task` fehlt.", True)

    if name == "claudegravity_optimize":
        opt = optimize_from_arguments(arguments, arguments.get("project_path", "."))
        return text_result(format_optimization_markdown(opt))

    if name == "claudegravity_run":
        p_dir, error = resolve_project_dir(arguments.get("project_path"))
        if error:
            return text_result(error, True)
        # Absoluter Pfad, damit `-p` und das Arbeitsverzeichnis des Laufs nicht doppelt aufgelöst werden
        opt = optimize_from_arguments(arguments, str(p_dir))
        if not arguments.get("background", False):
            lang, command = manual_start_command(p_dir, opt["loop_args"])
            return text_result(
                "📋 Bereit zum Starten. Bitte führe folgenden Befehl im Terminal aus "
                f"(oder rufe das Tool mit `background: true` auf):\n\n```{lang}\n{command}\n```"
            )
        # Im Hintergrund kann niemand Rückfragen beantworten
        loop_args = [a for a in opt["loop_args"] if a not in ("-i", "--ask")]
        running = latest_background_run(p_dir)
        if running is not None and process_state(running["pid"])[0]:
            return text_result(
                f"Im Projekt `{p_dir}` läuft schon ein Hintergrundlauf (PID {running['pid']}). "
                "Stand mit `claudegravity_status`, Abbruch mit `claudegravity_stop`.",
                True,
            )
        try:
            proc, log_path = start_background_run(p_dir, loop_args)
        except OSError as exc:
            return text_result(f"Fehler beim Start: {exc}", True)
        return text_result(
            f"🚀 ClaudeGravity Loop im Hintergrund gestartet (PID {proc.pid})!\n"
            f"Befehl: `{format_shell_command(['claudegravity'] + loop_args)}`\nProjekt: `{p_dir}`\n"
            f"Ausgabe: `{log_path}`\nStand abfragen: Tool `claudegravity_status` mit project_path `{p_dir}`, "
            "abbrechen mit `claudegravity_stop`."
        )

    if name == "claudegravity_status":
        p_dir, error = resolve_project_dir(arguments.get("project_path"))
        if error:
            return text_result(error, True)
        try:
            log_lines = int(arguments.get("log_lines", 15))
        except (TypeError, ValueError):
            log_lines = 15
        return text_result(format_session_status(p_dir, log_lines))

    if name == "claudegravity_stop":
        p_dir, error = resolve_project_dir(arguments.get("project_path"))
        if error:
            return text_result(error, True)
        stopped, message = stop_background_run(p_dir)
        return text_result(message, not stopped)

    if name == "claudegravity_info":
        return text_result(format_info())

    return text_result(f"Unbekanntes Tool: {name}", True)


def format_info() -> str:
    """Systemprüfung: Betriebssystem, Python, Startumgebung des Servers, erkannte CLIs und Endpunkte."""
    agents = detect_installed_agents()
    lines = [
        f"### 🖥️ Betriebssystem: {platform.system()} {platform.release()} (Python {platform.python_version()})",
        f"* **Python des Servers:** `{sys.executable}`",
        f"* **Skript:** `{Path(__file__).resolve()}`",
        f"* **Arbeitsverzeichnis:** `{Path.cwd()}`",
        f"* **{PROJECT_ENV}:** `{os.environ.get(PROJECT_ENV) or '–'}`",
        f"* **Aufrufender Client:** {HOST_CLIENT.get('name') or '–'}" + (f" → Architekt `{host_backend()}`" if host_backend() else ""),
        f"* **PATH ergänzt um:** {', '.join(f'`{d}`' for d in ADDED_PATH_DIRS) or '–'}",
        "",
        "### 🔍 Erkannte KI-Systeme & Endpoints auf diesem System:",
        "",
    ]
    for k, a in agents.items():
        lines.append(f"* **{a}** (`{k}`)")
    if not agents:
        lines.append("⚠️ Keine unterstützten AI-CLIs oder lokalen Server gefunden. Bei Desktop-Apps fehlt oft der Shell-PATH: ")
        lines.append("   Ordner der CLIs in der MCP-Konfiguration unter `env` → `PATH` eintragen.")
    lines += [
        "",
        "💡 **Empfohlene Strategien:**",
        "1. **best-code:** Maximale Codequalität mit Claude Sonnet 3.7 & Gemini 2.5 Pro.",
        "2. **eco:** Bis zu 70% Ersparnis (Architekt=Sonnet, Bauleiter=Haiku oder Flash).",
        "3. **local-free:** 0 € Kosten im Bau-Loop! Cloud-Architekt plant, lokaler Server (Ollama, LM Studio oder ein Rechner im Heimnetz) baut autonom.",
    ]
    return "\n".join(lines)


# Ordner, die extend_search_path() beim Start ergänzt hat (für claudegravity_info)
ADDED_PATH_DIRS: list[str] = []


def negotiate_protocol_version(requested) -> str:
    """Version des Clients, wenn bekannt, sonst die neueste unterstützte."""
    return requested if requested in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]


def handle_message(req) -> dict | None:
    """Eine JSON-RPC-Nachricht verarbeiten. Liefert die Antwort oder None bei Notifications (ohne `id`)."""
    if not isinstance(req, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Ungültige Anfrage."}}
    is_notification = "id" not in req
    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}
    if is_notification:
        # notifications/initialized, notifications/cancelled usw. bekommen nie eine Antwort
        return None
    try:
        if method == "initialize":
            client = params.get("clientInfo") or {}
            HOST_CLIENT.clear()
            HOST_CLIENT.update({k: str(client.get(k, "")) for k in ("name", "version") if client.get(k)})
            result = {
                "protocolVersion": negotiate_protocol_version(params.get("protocolVersion")),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "title": "ClaudeGravity Loop", "version": SERVER_VERSION},
                "instructions": SERVER_INSTRUCTIONS,
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": MCP_TOOLS}
        elif method == "tools/call":
            result = handle_tool_call(params.get("name", ""), params.get("arguments") or {})
        elif method in ("resources/list", "prompts/list", "resources/templates/list"):
            # Manche Clients fragen das immer ab; leere Listen statt Fehlermeldung im Client-Log
            key = {"resources/list": "resources", "prompts/list": "prompts"}.get(method, "resourceTemplates")
            result = {key: []}
        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Methode '{method}' wird nicht unterstützt."}}
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": f"Interner Fehler: {exc}"}}
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def run_mcp_stdio_server():
    """Liest JSON-RPC 2.0 Nachrichten von stdin und antwortet auf stdout.

    Während der Server läuft, zeigt sys.stdout auf stderr: Ein versehentliches print() landet so im Client-Log,
    statt das Protokoll zu zerstören.
    """
    out = sys.stdout
    sys.stdout = sys.stderr
    reader = getattr(sys.stdin, "buffer", None)

    def send(message: dict) -> None:
        out.write(json.dumps(message) + "\n")
        out.flush()

    print(f"{SERVER_NAME} {SERVER_VERSION} bereit (Python {platform.python_version()}, cwd {Path.cwd()})", file=sys.stderr)
    try:
        while True:
            raw = reader.readline() if reader is not None else sys.stdin.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
            line = line.strip().lstrip("﻿")
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as err:
                send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse-Fehler: {err}"}})
                continue
            res = handle_message(req)
            if res is not None:
                send(res)
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    finally:
        sys.stdout = out


def main():
    """MCP-Server über stdio starten oder, mit Aufgabe bzw. --optimize, eine Empfehlung direkt ausgeben."""
    if sys.version_info < (3, 10):
        print(f"[!] ClaudeGravity benötigt Python 3.10+ (gestartet mit {sys.executable}, {platform.python_version()}).", file=sys.stderr)
        print("    In der MCP-Konfiguration den absoluten Pfad zu einem neueren Python als `command` eintragen.", file=sys.stderr)
        sys.exit(1)
    ADDED_PATH_DIRS[:] = extend_search_path()

    parser = argparse.ArgumentParser(description="ClaudeGravity MCP Server & Command Optimizer")
    parser.add_argument("task_pos", nargs="?", default=None, help="Aufgabe (für direkten CLI-Aufruf)")
    parser.add_argument("--optimize", "-o", dest="optimize_task", default=None, help="Aufgabe analysieren und optimalen Befehl ausgeben")
    parser.add_argument(
        "--priority",
        default="auto",
        choices=[
            "auto",
            "best-code",
            "quality",
            "eco",
            "lowest-cost",
            "cost",
            "local-free",
            "free",
            "local",
            "hybrid",
            "mixed",
            "balanced",
        ],
        help="Priorität: auto (hybrid, wenn ein lokales Modell erreichbar ist), best-code, lowest-cost, local-free, hybrid, balanced",
    )
    parser.add_argument("--endpoint", default=None, help="KI-Endpunkt (z.B. http://localhost:11434/v1 oder http://192.168.1.50:11434/v1)")
    parser.add_argument("-p", "--project", default=".", help="Zielprojekt-Pfad")
    parser.add_argument("-i", "--ask", action="store_true", help="Fragen-Modus (-i)")
    parser.add_argument("--yolo", action="store_true", help="YOLO-Modus (--yolo)")
    parser.add_argument("-m", "--max-iterations", type=int, default=10, help="Max Iterationen")
    parser.add_argument("--info", action="store_true", help="Installierte AI-CLIs und Endpunkte prüfen")
    parser.add_argument("--mcp", action="store_true", help="Als MCP-Server (stdio JSON-RPC) starten")

    args = parser.parse_args()

    cli_task = args.optimize_task or args.task_pos

    if args.info:
        print(format_info())
        return

    if cli_task:
        opt = optimize_claudegravity_command(
            task=cli_task,
            priority=args.priority,
            project_path=args.project,
            endpoint=args.endpoint,
            ask_mode=args.ask,
            yolo=args.yolo,
            max_iterations=args.max_iterations,
        )
        print("\n" + format_optimization_markdown(opt) + "\n")
        return

    run_mcp_stdio_server()


if __name__ == "__main__":
    main()
