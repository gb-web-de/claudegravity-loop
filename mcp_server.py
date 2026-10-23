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

import argparse
import json
import os
import platform
import re
import shlex
import shutil
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
SERVER_NAME = "claudegravity-mcp"
SERVER_VERSION = "1.2.0"

DEFAULT_MODEL = "CLI-Default"
AUTO_OLLAMA_MODEL = "automatisch (installierte Ollama-Modelle)"
MODEL_AWARE_CLIS = ("claude", "agy", "gemini")
CLOUD_PLANNER_ORDER = ("codex", "claude", "agy", "gemini")
LOCAL_BACKEND_ORDER = ("ollama", "lmstudio", "endpoint", "ollama-cli")
OLLAMA_KEYS = ("ollama", "ollama-cli")
ROLE_PARAMS = ("architekt", "architekt_model", "pruefstatiker", "pruefstatiker_model",
               "bauer", "bauer_model", "abnahme", "abnahme_model")


def is_endpoint_reachable(url: str, timeout: float = 0.3) -> bool:
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

    env_endpoint = (
        os.environ.get("CLAUDEGRAVITY_ENDPOINT") or
        os.environ.get("OPENAI_BASE_URL") or
        os.environ.get("AI_ENDPOINT")
    )
    if env_endpoint:
        label = "Benutzerdefinierter KI-Server"
        agents["endpoint"] = f"{label} ({env_endpoint})"

    return agents


def analyze_task_complexity(task: str) -> dict:
    t_lower = task.lower()
    is_refactor = any(w in t_lower for w in ["refactor", "refaktoriere", "umbau", "restrukturier", "clean up", "aufräumen"])
    is_security = any(w in t_lower for w in ["secur", "sicher", "auth", "token", "login", "vulnerability", "lücke", "passw"])
    is_architectural = any(w in t_lower for w in ["architekt", "migration", "redesign", "framework", "datenbank", "schema", "api design"])
    is_testing = any(w in t_lower for w in ["test", "unit", "pytest", "spec", "coverage", "abdeckung"])
    is_small_fix = any(w in t_lower for w in ["fix", "bug", "fehler", "korrigier", "typo", "klein", "patch"]) and not (is_refactor or is_architectural)

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


def optimize_claudegravity_command(
    task: str,
    priority: str = "balanced",
    project_path: str = ".",
    endpoint: str | None = None,
    ask_mode: bool = False,
    yolo: bool = False,
    max_iterations: int = 10,
    proof: str | None = None,
    roles: dict | None = None,
    stages: str = "auto",
    approve_plan: bool = False,
    merge: bool = False
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
        planner_model = "claude-3-7-sonnet" if planner_cli == "claude" else "gemini-2.5-pro"
        planner_effort = "high"
        reviewer_model = "gemini-2.5-pro" if reviewer_cli in ["agy", "gemini"] else "claude-3-7-sonnet"
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
        planner_model = "claude-3-7-sonnet" if planner_cli == "claude" else "gemini-2.5-pro"
        planner_effort = "medium"
        reviewer_model = "gemini-2.5-pro" if reviewer_cli in ["agy", "gemini"] else "claude-3-7-sonnet"
        reviewer_effort = "medium"
        builder_cli = planner_cli
        builder_model = "claude-3-5-haiku" if builder_cli == "claude" else "gemini-2.5-flash"
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
        planner_model = "claude-3-7-sonnet" if planner_cli == "claude" else "gemini-2.5-pro"
        planner_effort = "high"
        reviewer_model = "gemini-2.5-pro" if reviewer_cli in ["agy", "gemini"] else "claude-3-7-sonnet"
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
        planner_model = "claude-sonnet (Standard)" if planner_cli == "claude" else "gemini-2.5-pro (Standard)"
        planner_effort = "high" if planner_cli == "agy" else None
        reviewer_model = "gemini-2.5-pro (Standard)" if reviewer_cli in ["agy", "gemini"] else "claude-sonnet (Standard)"
        reviewer_effort = "high" if reviewer_cli == "agy" else None
        builder_cli = planner_cli
        builder_model = planner_model
        builder_effort = None
        cost_benefit = (
            "⚖️ Ausgewogene Standard-Konfiguration: Hohe Denk-Präzision in der Planung bei "
            "verlässlicher Ausführungsgeschwindigkeit."
        )

    # Modellnamen gelten nur für Claude und Gemini; andere CLIs nutzen ihr eigenes Standardmodell
    if planner_cli not in MODEL_AWARE_CLIS and planner_model != AUTO_OLLAMA_MODEL:
        planner_model = DEFAULT_MODEL
    if reviewer_cli not in MODEL_AWARE_CLIS and reviewer_model != AUTO_OLLAMA_MODEL:
        reviewer_model = DEFAULT_MODEL
    if p_norm in ("best-code", "lowest-cost", "balanced") and builder_cli not in MODEL_AWARE_CLIS:
        builder_model = DEFAULT_MODEL

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
    for flag, key in (("--architekt", "architekt"), ("--architekt-model", "architekt_model"),
                      ("--pruefstatiker", "pruefstatiker"), ("--pruefstatiker-model", "pruefstatiker_model"),
                      ("--bauer", "bauer"), ("--bauer-model", "bauer_model"),
                      ("--abnahme", "abnahme"), ("--abnahme-model", "abnahme_model")):
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
        "complexity_analysis": comp,
        "strategy": strategy_flag,
        "roles": {
            "architekt": {
                "role": "🏗️ Architekt (Phase 1: Planung & Entwurf)",
                "cli": planner_cli,
                "model": planner_model,
                "effort": planner_effort or "Standard",
                "token_share": "~10-15% der Gesamt-Tokens"
            },
            "pruefstatiker": {
                "role": "🧐 Prüfstatiker (Phase 2: Prüfung & Review)",
                "cli": reviewer_cli,
                "model": reviewer_model,
                "effort": reviewer_effort or "Standard",
                "token_share": "~5-10% der Gesamt-Tokens"
            },
            "bauleiter": {
                "role": "🔨 Bauleiter (Phase 3: Bau & Umsetzung)",
                "cli": builder_cli,
                "model": builder_model,
                "effort": builder_effort or "Standard",
                "token_share": "~80-90% der Gesamt-Tokens (Hauptverbrauch!)"
            },
            "abnahme": {
                "role": "🔎 Abnahme (Phase 4: Prüfung des fertigen Codes)",
                "cli": inspector_cli or (planner_cli if p_norm == "hybrid" else "automatisch (Prüfstatiker oder Architekt, nie der Bauleiter)"),
                "model": roles.get("abnahme_model", DEFAULT_MODEL),
                "effort": "Standard",
                "token_share": "gering (nur der Diff)"
            }
        },
        "stages": stages or "auto",
        "cost_benefit_analysis": cost_benefit,
        "recommended_command": command_str,
        "loop_args": cmd_args,
        "installed_agents": agents
    }


def format_optimization_markdown(opt: dict) -> str:
    r = opt["roles"]
    cmd_base = opt["recommended_command"]
    cmd_cmd = format_shell_command(["claudegravity.bat"] + opt["loop_args"], "cmd")
    cmd_ps = format_shell_command([".\\claudegravity.ps1"] + opt["loop_args"], "powershell")

    lines = [
        "### 🎯 ClaudeGravity Optimierungs-Empfehlung",
        f"* **Aufgabe:** {opt['task']}",
        f"* **Gewählte Priorität:** `{opt['priority']}` (Erkannte Komplexität: {opt['complexity_analysis']['complexity']})",
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
    "pruefstatiker": {"type": "string", "description": "CLI für den Prüfstatiker, nie derselbe Anbieter mit demselben Modell wie der Architekt."},
    "pruefstatiker_model": {"type": "string", "description": "Modell für den Prüfstatiker (z. B. gpt-oss:20b bei Ollama)."},
    "bauer": {"type": "string", "description": "CLI für den Bauleiter (z. B. ollama)."},
    "bauer_model": {"type": "string", "description": "Modell für den Bauleiter (z. B. qwen3-coder:30b). Ohne Angabe wählt der Loop bei Ollama aus den installierten Modellen."},
    "abnahme": {"type": "string", "description": "CLI für die Abnahme des fertigen Codes, nie der Bauleiter (z. B. codex)."},
    "abnahme_model": {"type": "string", "description": "Modell für die Abnahme."},
    "stages": {"type": "string", "enum": ["auto", "an", "aus"], "default": "auto", "description": "Etappen-Modus: Plan in Etappen, Bauleiter setzt sie einzeln um (auto: an bei lokalen Bauleitern)."},
    "approve_plan": {"type": "boolean", "default": False, "description": "Plan ohne Rückfrage freigeben, sobald der Prüfstatiker APPROVED meldet (--plan-auto). Im Hintergrund immer an."},
    "merge": {"type": "boolean", "default": False, "description": "Session-Branch nach erfolgreicher Abnahme in den Ausgangs-Branch mergen (--merge)."},
}


def role_arguments(arguments: dict) -> dict:
    return {k: arguments.get(k) for k in ROLE_PARAMS if arguments.get(k)}


MCP_TOOLS = [
    {
        "name": "claudegravity_optimize",
        "description": (
            "Analysiert eine Programmieraufgabe und ermittelt die optimale Kombination aus Modellen, "
            "Reasoning-Effort und Rollen (Architekt, Prüfstatiker, Bauleiter) für ClaudeGravity Loop basierend auf dem Ziel "
            "(bester Code vs. geringste Kosten vs. 0€ lokale Modelle). Liefert den exakten, plattformunabhängigen Shell-Befehl."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Beschreibung der Programmieraufgabe, des Refactorings oder des neuen Features."
                },
                "priority": {
                    "type": "string",
                    "enum": ["best-code", "lowest-cost", "local-free", "hybrid", "balanced"],
                    "default": "balanced",
                    "description": "best-code (Frontier-Modelle), lowest-cost (bis zu 70% Ersparnis), local-free (0€ Bauleiter via Ollama, LM Studio oder Server im Heimnetz), hybrid (Cloud-CLI wie Codex plant und nimmt ab, Ollama prüft und baut in Etappen), balanced (ausgewogen)."
                },
                "endpoint": {
                    "type": "string",
                    "description": "Optionaler KI-Endpunkt (z.B. http://localhost:11434/v1 oder http://192.168.1.50:11434/v1)."
                },
                "project_path": {
                    "type": "string",
                    "default": ".",
                    "description": "Pfad zum Ziel-Projektverzeichnis (Standard: .)."
                },
                "ask_mode": {
                    "type": "boolean",
                    "default": False,
                    "description": "Ob der interaktive Fragen-Modus (-i / --ask) für menschliche Klärung aktiviert werden soll."
                },
                "yolo": {
                    "type": "boolean",
                    "default": False,
                    "description": "Ob volle Schreib- und Toolrechte ohne manuelle Nachfrage erteilt werden sollen (--yolo)."
                },
                "proof": {
                    "type": "string",
                    "description": "Optionaler Prüfbefehl (--proof), den der Loop nach jeder Bau-Runde selbst ausführt."
                },
                "max_iterations": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximale Anzahl autonomer Runden in Phase 3 (Standard: 10)."
                },
                **ROLE_SCHEMA
            },
            "required": ["task"]
        }
    },
    {
        "name": "claudegravity_run",
        "description": "Startet den ClaudeGravity Loop mit optimierten Parametern direkt auf dem System.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Die auszuführende Aufgabe."
                },
                "priority": {
                    "type": "string",
                    "enum": ["best-code", "lowest-cost", "local-free", "hybrid", "balanced"],
                    "default": "balanced"
                },
                "endpoint": {
                    "type": "string",
                    "description": "Optionaler KI-Endpunkt."
                },
                "project_path": {
                    "type": "string",
                    "default": "."
                },
                "yolo": {
                    "type": "boolean",
                    "default": False,
                    "description": "Volle Schreib- und Toolrechte für den Bauleiter ohne Nachfrage (--yolo). Nur auf ausdrücklichen Wunsch setzen; Architekt und Prüfstatiker bleiben immer lesend."
                },
                "proof": {
                    "type": "string",
                    "description": "Prüfbefehl, den der Loop nach jeder Bau-Runde selbst ausführt, z.B. 'python -m unittest discover -s tests'."
                },
                "ask_mode": {
                    "type": "boolean",
                    "default": False
                },
                "max_iterations": {
                    "type": "integer",
                    "default": 10
                },
                "background": {
                    "type": "boolean",
                    "default": False,
                    "description": "Im Hintergrund starten. Setzt --plan-auto: gebaut wird nur ein vom Prüfstatiker genehmigter Plan."
                },
                **ROLE_SCHEMA
            },
            "required": ["task"]
        }
    },
    {
        "name": "claudegravity_info",
        "description": "Prüft die installierten AI-CLIs (Claude, Antigravity, Gemini, Codex, Copilot, Ollama, LM Studio, eigene Endpunkte) und gibt Empfehlungen.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


def handle_tool_call(name: str, arguments: dict) -> dict:
    if name == "claudegravity_optimize":
        task = arguments.get("task", "")
        priority = arguments.get("priority", "balanced")
        project_path = arguments.get("project_path", ".")
        endpoint = arguments.get("endpoint")
        ask_mode = arguments.get("ask_mode", False)
        yolo = arguments.get("yolo", False)
        max_iterations = arguments.get("max_iterations", 10)

        opt = optimize_claudegravity_command(
            task=task,
            priority=priority,
            project_path=project_path,
            endpoint=endpoint,
            ask_mode=ask_mode,
            yolo=yolo,
            max_iterations=max_iterations,
            proof=arguments.get("proof"),
            roles=role_arguments(arguments),
            stages=arguments.get("stages", "auto"),
            approve_plan=arguments.get("approve_plan", False) or arguments.get("background", False),
            merge=arguments.get("merge", False)
        )
        md_text = format_optimization_markdown(opt)
        return {
            "content": [
                {"type": "text", "text": md_text}
            ],
            "isError": False
        }

    elif name == "claudegravity_run":
        task = arguments.get("task", "")
        priority = arguments.get("priority", "balanced")
        project_path = arguments.get("project_path", ".")
        endpoint = arguments.get("endpoint")
        ask_mode = arguments.get("ask_mode", False)
        yolo = arguments.get("yolo", False)
        max_iterations = arguments.get("max_iterations", 10)
        background = arguments.get("background", False)

        opt = optimize_claudegravity_command(
            task=task,
            priority=priority,
            project_path=project_path,
            endpoint=endpoint,
            ask_mode=ask_mode,
            yolo=yolo,
            max_iterations=max_iterations,
            proof=arguments.get("proof"),
            roles=role_arguments(arguments),
            stages=arguments.get("stages", "auto"),
            approve_plan=arguments.get("approve_plan", False) or arguments.get("background", False),
            merge=arguments.get("merge", False)
        )
        cmd_str = opt["recommended_command"]

        p_dir = Path(project_path).resolve()
        if not p_dir.exists():
            return {
                "content": [{"type": "text", "text": f"Fehler: Projektpfad '{p_dir}' existiert nicht."}],
                "isError": True
            }

        if background:
            proc = subprocess.Popen(
                loop_launch_argv(opt["loop_args"]),
                cwd=str(p_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"🚀 ClaudeGravity Loop im Hintergrund gestartet (PID {proc.pid})!\nBefehl: `{cmd_str}`\nProjekt: `{p_dir}`"
                    }
                ],
                "isError": False
            }
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"📋 Bereit zum Starten. Bitte führe folgenden Befehl im Terminal aus:\n\n```bash\ncd {shlex.quote(str(p_dir))} && {cmd_str}\n```"
                    }
                ],
                "isError": False
            }

    elif name == "claudegravity_info":
        agents = detect_installed_agents()
        os_name = f"{platform.system()} {platform.release()}"
        lines = [
            f"### 🖥️ Betriebssystem: {os_name} (Python {platform.python_version()})",
            "### 🔍 Erkannte KI-Systeme & Endpoints auf diesem System:",
            ""
        ]
        for k, a in agents.items():
            lines.append(f"* **{a}** (`{k}`)")
        if not agents:
            lines.append("⚠️ Keine unterstützten AI-CLIs oder lokalen Server gefunden.")
        lines.append("")
        lines.append("💡 **Empfohlene Strategien:**")
        lines.append("1. **best-code:** Maximale Codequalität mit Claude Sonnet 3.7 & Gemini 2.5 Pro.")
        lines.append("2. **eco:** Bis zu 70% Ersparnis (Architekt=Sonnet, Bauleiter=Haiku oder Flash).")
        lines.append("3. **local-free:** 0 € Kosten im Bau-Loop! Cloud-Architekt plant, lokaler Server (Ollama, LM Studio oder ein Rechner im Heimnetz) baut autonom.")
        return {
            "content": [{"type": "text", "text": "\n".join(lines)}],
            "isError": False
        }

    else:
        return {
            "content": [{"type": "text", "text": f"Unbekanntes Tool: {name}"}],
            "isError": True
        }


def run_mcp_stdio_server():
    """Liest JSON-RPC 2.0 Nachrichten von stdin und antwortet auf stdout."""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line_str = line.strip()
            if not line_str:
                continue

            req = json.loads(line_str)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "initialize":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": SERVER_NAME,
                            "version": SERVER_VERSION
                        }
                    }
                }
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()

            elif method == "notifications/initialized":
                continue

            elif method == "ping":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {}
                }
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()

            elif method == "tools/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": MCP_TOOLS
                    }
                }
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()

            elif method == "tools/call":
                t_name = params.get("name", "")
                t_args = params.get("arguments", {})
                tool_res = handle_tool_call(t_name, t_args)
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": tool_res
                }
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()

            else:
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Methode '{method}' wird nicht unterstützt."
                    }
                }
                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()

        except json.JSONDecodeError as err:
            err_res = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse-Fehler: {err}"
                }
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()
        except (KeyboardInterrupt, BrokenPipeError):
            break
        except Exception as exc:
            err_res = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Interner Fehler: {exc}"
                }
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="ClaudeGravity MCP Server & Command Optimizer")
    parser.add_argument("task_pos", nargs="?", default=None, help="Aufgabe (für direkten CLI-Aufruf)")
    parser.add_argument("--optimize", "-o", dest="optimize_task", default=None, help="Aufgabe analysieren und optimalen Befehl ausgeben")
    parser.add_argument("--priority", default="balanced", choices=["best-code", "quality", "eco", "lowest-cost", "cost", "local-free", "free", "local", "hybrid", "mixed", "balanced"], help="Priorität: best-code, lowest-cost, local-free, hybrid, balanced")
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
        res = handle_tool_call("claudegravity_info", {})
        print(res["content"][0]["text"])
        return

    if cli_task:
        opt = optimize_claudegravity_command(
            task=cli_task,
            priority=args.priority,
            project_path=args.project,
            endpoint=args.endpoint,
            ask_mode=args.ask,
            yolo=args.yolo,
            max_iterations=args.max_iterations
        )
        print("\n" + format_optimization_markdown(opt) + "\n")
        return

    run_mcp_stdio_server()


if __name__ == "__main__":
    main()
