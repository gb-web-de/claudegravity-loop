#!/usr/bin/env python3
"""
ClaudeGravity Loop - Cross-Model Adversarial & Autonomous Execution Loop
Auto-detects available CLIs (Claude Code, Google Antigravity agy, Gemini CLI, Codex).
Supports:
- Universal YOLO permission propagation across all phases (Planning, Review, Build)
- Automatic detection and recovery if a model attempts file writes during planning
- Resume after crashes/interrupts (--resume / -c)
- Interactive Plan Approval & Change Routing (UI options on top, CLI options at bottom)
- Versioned plan archives, audit logs, and permission handling (--yolo)
"""

import argparse
import datetime
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

STOP_REQUESTED = False

PLANNING_DIRECTIVE = (
    "\n\nSTRIKTE VORGABE FÜR DIE PLANUNG:\n"
    "- Du befindest dich in der REINEN PLANUNGSPHASE.\n"
    "- Erstelle, modifiziere oder lösche KEINE Dateien auf der Festplatte (weder in docs/ noch im Code).\n"
    "- Gib den vollständigen, detaillierten Plan DIREKT als Markdown-Text auf stdout aus.\n"
    "- Beginne sofort mit dem Markdown-Inhalt des Plans (ohne Tool-Aufrufe zum Dateischreiben).\n"
)


def sigint_handler(signum, frame):
    global STOP_REQUESTED
    print("\n[!] Abbruch empfangen. Beende aktuelle Iteration sauber...")
    STOP_REQUESTED = True


signal.signal(signal.SIGINT, sigint_handler)
signal.signal(signal.SIGTERM, sigint_handler)


class RateLimitError(Exception):
    def __init__(self, binary: str, message: str, reset_time: str | None = None, reset_seconds: int | None = None):
        super().__init__(f"{binary} Limit erreicht: {message}")
        self.binary = binary
        self.message = message
        self.reset_time = reset_time
        self.reset_seconds = reset_seconds


RATE_LIMIT_PATTERNS = [
    r"hit your session limit",
    r"rate limit",
    r"rate_limit",
    r"quota exceeded",
    r"resource_exhausted",
    r"too many requests",
    r"usage limit",
    r"hit your limit",
    r"credit balance is too low",
    r"capacity",
    r"overloaded",
]

TIME_PATTERNS = [
    r"resets?\s+(?:in\s+|at\s+)?([0-9]+\s*(?:hours?|hrs?|minutes?|mins?|seconds?|secs?|h|m|s))\b",
    r"resets?\s+(?:in\s+|at\s+)?([0-9]+(?::[0-9]+)?\s*(?:am|pm)?(?:\s*\([^\)]+\))?)\b",
    r"try again in\s+([0-9]+\s*(?:hours?|hrs?|minutes?|mins?|seconds?|secs?|h|m|s))\b",
]


def is_rate_limit(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in RATE_LIMIT_PATTERNS)


def extract_reset_time(text: str) -> str | None:
    for p in TIME_PATTERNS:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def parse_reset_seconds(time_str: str | None) -> int | None:
    if not time_str:
        return None
    s = time_str.strip().lower()

    dur_m = re.match(r'^([0-9]+(?:\.[0-9]+)?)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)$', s)
    if dur_m:
        val = float(dur_m.group(1))
        unit = dur_m.group(2)
        if unit.startswith('h'):
            return int(val * 3600)
        elif unit.startswith('m'):
            return int(val * 60)
        elif unit.startswith('s'):
            return int(val)

    now = datetime.datetime.now()
    s_clean = re.sub(r'\(.*?\)', '', s).strip()
    for fmt in ['%I:%M%p', '%I%p', '%H:%M', '%H:%M:%S']:
        try:
            t = datetime.datetime.strptime(s_clean, fmt).time()
            target = datetime.datetime.combine(now.date(), t)
            diff = int((target - now).total_seconds())
            if -3600 <= diff <= 0:
                return 15
            elif diff < -3600:
                target += datetime.timedelta(days=1)
                diff = int((target - now).total_seconds())
            if diff > 0:
                return diff
        except ValueError:
            continue
    return None


def wait_countdown(seconds: int, reset_str: str = "") -> bool:
    print(f"\n⏳ Starte Countdown ({seconds}s bis {reset_str or 'Reset'}). Drücke [Strg+C] zum Abbrechen...")
    try:
        for remaining in range(seconds, 0, -1):
            if STOP_REQUESTED:
                return False
            mins, secs = divmod(remaining, 60)
            hours, mins = divmod(mins, 60)
            time_display = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours else f"{mins:02d}:{secs:02d}"
            sys.stdout.write(f"\r⏳ Warte noch: {time_display} ... ")
            sys.stdout.flush()
            time.sleep(1)
        print("\n⏰ Wartezeit abgelaufen! Setze Ausführung fort...")
        return True
    except KeyboardInterrupt:
        print("\n[!] Warten durch Nutzer abgebrochen.")
        return False


def extract_flag_value(flags: list[str] | None, flag_name: str) -> str | None:
    """Extrahiert den Wert eines Flags wie --model <name> oder --effort=<val> aus einer Flag-Liste."""
    if not flags:
        return None
    for i, f in enumerate(flags):
        if f == flag_name and i + 1 < len(flags):
            return flags[i + 1]
        elif f.startswith(f"{flag_name}="):
            return f.split("=", 1)[1]
    return None


class SessionMetrics:
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.cost_usd = 0.0
        self.by_agent: dict[str, dict] = {}

    def add(
        self,
        agent_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
        role: str | None = None,
        model: str | None = None,
        effort: str | None = None
    ):
        if total_tokens == 0:
            total_tokens = input_tokens + output_tokens
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += total_tokens
        self.cost_usd += cost_usd

        tracker_key = f"{role} [{agent_name}]" if role else agent_name
        if tracker_key not in self.by_agent:
            self.by_agent[tracker_key] = {
                "agent_name": agent_name,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "role": role or "",
                "model": model or "",
                "effort": effort or "",
            }

        entry = self.by_agent[tracker_key]
        entry["input_tokens"] += input_tokens
        entry["output_tokens"] += output_tokens
        entry["total_tokens"] += total_tokens
        entry["cost_usd"] += cost_usd
        if role:
            entry["role"] = role
        if model:
            entry["model"] = model
        if effort:
            entry["effort"] = effort

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd, 4),
            "by_agent": self.by_agent
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "SessionMetrics":
        m = cls()
        if not data:
            return m
        m.input_tokens = data.get("input_tokens", 0)
        m.output_tokens = data.get("output_tokens", 0)
        m.total_tokens = data.get("total_tokens", 0)
        m.cost_usd = data.get("cost_usd", 0.0)
        m.by_agent = data.get("by_agent", {})
        return m


def format_metrics_report(metrics: SessionMetrics) -> str:
    lines = [
        "",
        "---",
        "### 📊 Ressourcen-Verbrauch & Kosten (ClaudeGravity Audit)",
        f"* **Gesamt-Tokens:** {metrics.total_tokens:,} Tokens",
        f"  * **Input-Tokens:** {metrics.input_tokens:,}",
        f"  * **Output-Tokens:** {metrics.output_tokens:,}",
        f"* **Entstandene Kosten (geschätzt):** ~${metrics.cost_usd:.4f} USD",
        "* **Aufschlüsselung nach Rolle, Agent, Modell & Effort:**"
    ]
    if metrics.by_agent:
        for tracker_key, usage in metrics.by_agent.items():
            role_str = usage.get("role")
            agent_str = usage.get("agent_name", tracker_key)
            title = f"{role_str} ({agent_str})" if role_str else agent_str
            lines.append(f"  * **{title}**")
            if usage.get("model"):
                lines.append(f"    * **Modell:** `{usage['model']}`")
            if usage.get("effort"):
                lines.append(f"    * **Reasoning-Effort:** `{usage['effort']}`")
            cost_str = f"~${usage['cost_usd']:.4f} USD" if usage.get("cost_usd", 0.0) > 0 else "Abo-Inklusivkontingent"
            lines.append(f"    * **Verbrauch:** {usage['total_tokens']:,} Tokens (Input: {usage['input_tokens']:,}, Output: {usage['output_tokens']:,})")
            lines.append(f"    * **Kosten:** {cost_str}")
    else:
        lines.append("  * Keine detaillierte Modell-Aufschlüsselung verfügbar.")
    lines.append(f"* **Audit-Zeitstempel:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    return "\n".join(lines)


def append_metrics_to_done(session_dir: Path, project_path: Path, metrics: SessionMetrics):
    """Schreibt den Token- und Kostenbericht in die .done-Datei des Session-Ordners."""
    session_done = session_dir / ".done"
    root_done = project_path / ".done"

    if root_done.exists() and not session_done.exists():
        try:
            shutil.move(str(root_done), str(session_done))
        except Exception:
            pass

    if not session_done.exists():
        session_done.write_text("# Aufgabe abgeschlossen\n", encoding="utf-8")

    content = session_done.read_text(encoding="utf-8")
    if "ClaudeGravity Audit" not in content:
        report = format_metrics_report(metrics)
        with open(session_done, "a", encoding="utf-8") as f:
            f.write(report)
        print(f"📊 Ressourcen-Audit erfolgreich in {session_done.relative_to(project_path)} eingetragen.")


class AgentCLI:
    def __init__(
        self,
        name: str,
        binary: str,
        run_fn,
        metrics_tracker: SessionMetrics | None = None,
        role: str = "Architekt",
        model: str | None = None,
        effort: str | None = None
    ):
        self.name = name
        self.binary = binary
        self.run_fn = run_fn
        self.metrics_tracker = metrics_tracker
        self.role = role
        self.model = model
        self.effort = effort

    def run(self, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> str:
        text, metrics = self.run_fn(self.binary, prompt, cwd, extra_flags)
        if metrics:
            used_model = metrics.get("model") or extract_flag_value(extra_flags, "--model") or self.model
            used_effort = metrics.get("effort") or extract_flag_value(extra_flags, "--effort") or self.effort
            if used_model:
                self.model = used_model
            if used_effort:
                self.effort = used_effort
            if self.metrics_tracker:
                self.metrics_tracker.add(
                    agent_name=self.name,
                    input_tokens=metrics.get("input_tokens", 0),
                    output_tokens=metrics.get("output_tokens", 0),
                    total_tokens=metrics.get("total_tokens", 0),
                    cost_usd=metrics.get("cost_usd", 0.0),
                    role=self.role,
                    model=used_model,
                    effort=used_effort
                )
        return text


def create_agent(
    binary: str,
    agents: dict[str, AgentCLI],
    role: str = "Architekt",
    model: str | None = None,
    effort: str | None = None,
    metrics_tracker: SessionMetrics | None = None
) -> AgentCLI:
    base = agents.get(binary)
    if not base:
        raise ValueError(f"Agent-CLI '{binary}' ist nicht verfügbar.")
    return AgentCLI(
        name=base.name,
        binary=base.binary,
        run_fn=base.run_fn,
        metrics_tracker=metrics_tracker,
        role=role,
        model=model,
        effort=effort
    )


def _exec_cli(binary: str, args: list[str], cwd: Path | None = None) -> str:
    cmd = [binary] + args
    res = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if res.returncode != 0:
        err_msg = res.stderr.strip() or res.stdout.strip() or f"Fehlercode {res.returncode}"
        if is_rate_limit(err_msg):
            r_time = extract_reset_time(err_msg)
            r_secs = parse_reset_seconds(r_time) if r_time else None
            raise RateLimitError(binary, err_msg, r_time, r_secs)
        raise RuntimeError(f"{binary} Fehler (Code {res.returncode}): {err_msg}")
    return res.stdout.strip()


def _exec_claude(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> tuple[str, dict]:
    args = ["-p", prompt, "--output-format", "json"]
    if extra_flags:
        for f in extra_flags:
            if f not in ["--output-format", "json", "text"]:
                args.append(f)
    raw = _exec_cli(binary, args, cwd)
    try:
        data = json.loads(raw)
        if data.get("is_error"):
            err_msg = data.get("result") or data.get("api_error_status") or "Unbekannter Fehler"
            if is_rate_limit(str(err_msg)):
                r_time = extract_reset_time(str(err_msg))
                r_secs = parse_reset_seconds(r_time) if r_time else None
                raise RateLimitError(binary, str(err_msg), r_time, r_secs)
            raise RuntimeError(f"Claude Fehler: {err_msg}")

        text = data.get("result", "")
        usage = data.get("usage", {})
        inp = usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
        out = usage.get("output_tokens", 0)
        tot = inp + out
        cost = float(data.get("total_cost_usd", 0.0))

        model_name = None
        model_usage = data.get("modelUsage", {})
        if model_usage:
            model_name = list(model_usage.keys())[0]
        if not model_name:
            model_name = extract_flag_value(extra_flags, "--model")
        effort_val = extract_flag_value(extra_flags, "--effort")

        metrics = {
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": tot,
            "cost_usd": cost,
            "model": model_name,
            "effort": effort_val
        }
        return text, metrics
    except json.JSONDecodeError:
        return raw, {
            "input_tokens": len(prompt) // 4,
            "output_tokens": len(raw) // 4,
            "total_tokens": (len(prompt) + len(raw)) // 4,
            "cost_usd": 0.0,
            "model": extract_flag_value(extra_flags, "--model"),
            "effort": extract_flag_value(extra_flags, "--effort")
        }


def _exec_agy(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> tuple[str, dict]:
    args = ["-p", prompt, "--output-format", "json"]
    if extra_flags:
        for f in extra_flags:
            if f not in ["--output-format", "json", "text"]:
                args.append(f)
    raw = _exec_cli(binary, args, cwd)
    try:
        data = json.loads(raw)
        if data.get("status") == "ERROR":
            err_msg = data.get("response") or "Unbekannter Fehler"
            if is_rate_limit(str(err_msg)):
                r_time = extract_reset_time(str(err_msg))
                r_secs = parse_reset_seconds(r_time) if r_time else None
                raise RateLimitError(binary, str(err_msg), r_time, r_secs)
            raise RuntimeError(f"Antigravity Fehler: {err_msg}")

        text = data.get("response", "")
        usage = data.get("usage", {})
        inp = usage.get("input_tokens", 0)
        out = usage.get("output_tokens", 0)
        tot = usage.get("total_tokens", inp + out)

        model_name = extract_flag_value(extra_flags, "--model")
        effort_val = extract_flag_value(extra_flags, "--effort")
        if not effort_val and usage.get("thinking_tokens", 0) > 0:
            effort_val = f"high ({usage['thinking_tokens']} thinking tokens)"

        metrics = {
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": tot,
            "cost_usd": 0.0,
            "model": model_name,
            "effort": effort_val
        }
        return text, metrics
    except json.JSONDecodeError:
        return raw, {
            "input_tokens": len(prompt) // 4,
            "output_tokens": len(raw) // 4,
            "total_tokens": (len(prompt) + len(raw)) // 4,
            "cost_usd": 0.0,
            "model": extract_flag_value(extra_flags, "--model"),
            "effort": extract_flag_value(extra_flags, "--effort")
        }


def _exec_gemini(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> tuple[str, dict]:
    args = ["-p", prompt]
    if extra_flags:
        args.extend(extra_flags)
    raw = _exec_cli(binary, args, cwd)
    return raw, {
        "input_tokens": len(prompt) // 4,
        "output_tokens": len(raw) // 4,
        "total_tokens": (len(prompt) + len(raw)) // 4,
        "cost_usd": 0.0
    }


def _exec_codex(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> tuple[str, dict]:
    sandbox = "workspace-write" if extra_flags and "--dangerously-skip-permissions" in extra_flags else "read-only"
    args = ["exec", "-s", sandbox, prompt]
    raw = _exec_cli(binary, args, cwd)
    return raw, {
        "input_tokens": len(prompt) // 4,
        "output_tokens": len(raw) // 4,
        "total_tokens": (len(prompt) + len(raw)) // 4,
        "cost_usd": 0.0
    }


def detect_installed_agents() -> dict[str, AgentCLI]:
    agents = {}
    if shutil.which("claude"):
        agents["claude"] = AgentCLI("Claude Code", "claude", _exec_claude)
    if shutil.which("agy"):
        agents["agy"] = AgentCLI("Antigravity (agy)", "agy", _exec_agy)
    if shutil.which("gemini"):
        agents["gemini"] = AgentCLI("Gemini CLI", "gemini", _exec_gemini)
    if shutil.which("codex"):
        agents["codex"] = AgentCLI("Codex CLI", "codex", _exec_codex)
    return agents


def load_project_context(project_path: Path) -> str:
    if not project_path.exists():
        return ""
    context = []

    for rule_file in ["CLAUDE.md", "AGENTS.md", ".claude/rules.md"]:
        rf = project_path / rule_file
        if rf.exists():
            context.append(f"### Projekt-Instruktionen ({rule_file}):\n{rf.read_text(encoding='utf-8', errors='ignore').strip()}\n")
            break

    knowledge_dir = project_path / "knowledge"
    if knowledge_dir.exists() and knowledge_dir.is_dir():
        k_files = [f for f in knowledge_dir.glob("*") if f.is_file()]
        if k_files:
            context.append("### Verfügbares Projekt-Wissen (knowledge/):")
            for kf in k_files:
                snippet = kf.read_text(encoding='utf-8', errors='ignore')[:500]
                context.append(f"--- Datei: {kf.name} ---\n{snippet}\n")

    return "\n".join(context)


def sanitize_filename(text: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9_\-\s]', '', text)
    cleaned = re.sub(r'\s+', '_', cleaned).strip('_')
    return cleaned[:30] or "task"


def check_and_clean_done_marker(session_dir: Path, project_path: Path) -> bool:
    """Prüft, ob die Fertigmeldung (.done) existiert. Liegt im Session-Ordner."""
    session_done = session_dir / ".done"
    root_done = project_path / ".done"
    if session_done.exists():
        return True
    if root_done.exists():
        try:
            shutil.move(str(root_done), str(session_done))
        except Exception:
            session_done.touch()
            try: root_done.unlink()
            except Exception: pass
        return True
    return False

def get_permission_flags(binary: str) -> list[str]:
    """Gibt die passenden Flags für Schreib-/Tool-Rechte zurück."""
    if binary in ["claude", "agy"]:
        return ["--dangerously-skip-permissions"]
    elif binary == "gemini":
        return ["-y"]
    elif binary == "codex":
        return ["-s", "workspace-write"]
    return []


def is_permission_error_response(text: str) -> bool:
    """Prüft, ob das Modell versehentlich eine Berechtigungs-Fehlermeldung statt des Plans zurückgegeben hat."""
    indicators = [
        "Schreibberechtigung für",
        "Permission-Dialog",
        "Permission-Prompt",
        "Permission denied",
        "Write-Tool-Aufruf",
        "keine Berechtigung, Dateien zu schreiben",
        "keine Berechtigung",
        "Schreibzugriff auf",
        "Berechtigung nicht erteilt"
    ]
    text_lower = text.lower()
    return any(ind.lower() in text_lower for ind in indicators) and len(text.strip().splitlines()) < 15


def extract_questions(text: str) -> str | None:
    """Extrahiert Fragen an den Nutzer, falls ein Agent welche formuliert hat."""
    patterns = [
        r'(?:###|##)\s*(?:FRAGEN\s+AN\s+DEN\s+NUTZER|OFFENE\s+FRAGEN|RÜCKFRAGEN|QUESTIONS\s+FOR\s+USER)[:\s]*(.*?)(?=(?:\n###|\n##|\Z))',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.DOTALL)
        if m:
            content = m.group(1).strip()
            if "?" in content or "-" in content or "1." in content:
                return content
    return None


# ==========================================
# Session & State Management (Resume-Support)
# ==========================================
def save_session_state(session_dir: Path, state: dict):
    state_file = session_dir / "state.json"
    state["updated_at"] = datetime.datetime.now().isoformat()
    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def load_session_state(session_dir: Path) -> dict:
    state_file = session_dir / "state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def find_latest_session(loop_dir: Path) -> Path | None:
    sessions_dir = loop_dir / "sessions"
    if not sessions_dir.exists():
        return None
    sessions = sorted([p for p in sessions_dir.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
    return sessions[0] if sessions else None


def get_alternative_agent(current_agent: AgentCLI, agents: dict[str, AgentCLI]) -> AgentCLI | None:
    """Findet eine alternative installierte CLI für Modell-Wechsel bei Limits."""
    if current_agent.binary == "claude" and "agy" in agents:
        return agents["agy"]
    elif current_agent.binary == "agy" and "claude" in agents:
        return agents["claude"]
    for k, a in agents.items():
        if a.binary != current_agent.binary:
            return a
    return None


def handle_rate_limit(
    current_agent: AgentCLI,
    agents: dict[str, AgentCLI],
    err: RateLimitError,
    session_dir: Path,
    state: dict,
    auto_switch: bool = False
) -> tuple[str, AgentCLI | None]:
    """Behandelt RateLimit-Fehler interaktiv oder per automatischem Modell-Wechsel."""
    alt_agent = get_alternative_agent(current_agent, agents)

    if auto_switch and alt_agent:
        print(f"\n🔄 Auto-Switch aktiv: Wechsle automatisch von {current_agent.name} zu {alt_agent.name}...")
        return "switch", alt_agent

    print("\n" + "=" * 65)
    print(f"🚨 AI-LIMIT ERREICHT: {current_agent.name} meldet Sitzungs- / Ratenlimit!")
    print(f"   Grund: {err.message}")
    if err.reset_time:
        print(f"   Reset erwartet: {err.reset_time}")
    print("=" * 65)
    print("Wie möchtest du fortfahren?")
    if alt_agent:
        print(f"  [1] 🔄 Modell-Wechsel -> Zu {alt_agent.name} wechseln und sofort weiterarbeiten")
    else:
        print(f"  [1] 🔄 Modell-Wechsel -> (Keine Alternative im PATH gefunden)")
    wait_info = f" ({err.reset_time})" if err.reset_time else ""
    print(f"  [2] ⏳ Warten         -> Countdown starten{wait_info} und automatisch wiederholen")
    print(f"  [3] 💾 Beenden        -> Stand sichern und beenden (Fortsetzen später mit 'claudegravity -c')")
    print("-" * 65)

    try:
        choice = input("Auswahl [1/2/3] (Standard: 1): ").strip()
    except (EOFError, KeyboardInterrupt):
        return "exit", None

    if choice in ["", "1"] and alt_agent:
        return "switch", alt_agent
    elif choice in ["2", "wait", "w"]:
        secs = err.reset_seconds
        if not secs:
            try:
                user_min = input("Wieviele Minuten soll gewartet werden? [Standard: 15]: ").strip()
                secs = int(user_min) * 60 if user_min else 15 * 60
            except (ValueError, EOFError, KeyboardInterrupt):
                secs = 15 * 60
        ok = wait_countdown(secs, err.reset_time or f"{secs//60} Min")
        if ok:
            return "wait", current_agent
        else:
            return "exit", None
    elif choice in ["3", "exit", "q"]:
        return "exit", None
    else:
        if alt_agent:
            return "switch", alt_agent
        return "exit", None


def safe_agent_run(
    agent: AgentCLI,
    prompt: str,
    cwd: Path,
    flags: list[str],
    agents: dict[str, AgentCLI],
    session_dir: Path,
    state: dict,
    auto_switch: bool,
    role: str = "planner",
    metrics_tracker: SessionMetrics | None = None
) -> tuple[str, AgentCLI, list[str]]:
    """Führt einen Prompt aus und fängt Raten- und Sitzungslimits mit Wiederholungs-Logik ab."""
    while not STOP_REQUESTED:
        try:
            res = agent.run(prompt, cwd=cwd, extra_flags=flags)
            return res, agent, flags
        except RateLimitError as err:
            action, new_agent = handle_rate_limit(agent, agents, err, session_dir, state, auto_switch=auto_switch)
            if action == "switch" and new_agent:
                if role == "builder":
                    role_label = "Bauleiter"
                    role_title = "🔨 Bauleiter (Bau & Umsetzung)"
                elif role == "planner":
                    role_label = "Architekt"
                    role_title = "🏗️ Architekt (Planung & Entwurf)"
                else:
                    role_label = "Prüfstatiker"
                    role_title = "🧐 Prüfstatiker (Prüfung & Review)"
                print(f"🔄 Rolle '{role_label}' wechselt zu {new_agent.name}!")
                agent = new_agent
                agent.role = role_title
                if metrics_tracker:
                    agent.metrics_tracker = metrics_tracker
                flags = get_permission_flags(new_agent.binary)
                state[f"{role}_binary"] = new_agent.binary
                state[f"{role}_name"] = new_agent.name
                save_session_state(session_dir, state)
                continue
            elif action == "wait":
                continue
            else:
                save_session_state(session_dir, state)
                print("\n💾 Sitzung gesichert. Setze jederzeit fort mit 'claudegravity -c'.")
                sys.exit(0)
    return "", agent, flags


# ==========================================
# Plan-Erstellung & Adversarial Review
# ==========================================
def run_adversarial_plan(
    planner: AgentCLI,
    reviewer: AgentCLI,
    task: str,
    project_path: Path,
    project_ctx: str,
    session_dir: Path,
    state: dict,
    agents: dict[str, AgentCLI],
    auto_switch: bool = False,
    planner_flags: list[str] | None = None,
    reviewer_flags: list[str] | None = None,
    max_rounds: int = 2,
    ask_mode: bool = False
) -> tuple[bool, Path, AgentCLI, AgentCLI, list[str], list[str]]:
    loop_dir = project_path / ".dual-loop"

    # Alte temporäre Dateien im Root von .dual-loop aufräumen
    for legacy in [loop_dir / "PLAN.md", loop_dir / "REVIEW.md", loop_dir / "PLAN-REVIEW-LOG.md"]:
        if legacy.exists():
            try:
                legacy.unlink()
            except Exception:
                pass

    log_file = session_dir / "LOG.md"
    plan_v1_file = session_dir / "PLAN_v1.md"
    current_plan_file = plan_v1_file

    planner_flags = list(planner_flags or [])
    reviewer_flags = list(reviewer_flags or [])

    # Wenn Plan v1 noch nicht existiert (oder von vorn begonnen wird):
    if not plan_v1_file.exists():
        p_desc = f"{planner.name}" + (f" (`{planner.model}`)" if planner.model else "") + (f" [{planner.effort}]" if planner.effort else "")
        print(f"\n📁 Session-Ordner: {session_dir.relative_to(project_path)}")
        print(f"🚀 Phase 1: Plan-Entwurf durch 🏗️ Architekt ({p_desc}) im Kontext von {project_path.name}...")
        print(f"⏳ Warte auf 🏗️ Architekt ({planner.name})...", flush=True)

        prompt_plan = (
            f"Du bist der leitende Software-Architekt für das Projekt in '{project_path}'.\n"
            f"Erstelle einen präzisen, token-effizienten Implementierungsplan für folgende Aufgabe:\n"
            f"Aufgabe: {task}\n\n"
            f"{project_ctx}\n\n"
            f"Enthalte: Betroffene Dateien, Architektur, Randfälle und Testkriterien."
            f"{PLANNING_DIRECTIVE}"
        )
        if ask_mode:
            prompt_plan += (
                "\n\nFRAGEN-MODUS AKTIV: Falls es wichtige Unklarheiten, Annahmen oder architektonische Alternativen gibt, "
                "stelle bis zu 3 konkrete, nummerierte Fragen an den Nutzer unter der Überschrift '### FRAGEN AN DEN NUTZER:'. "
                "Formuliere darunter deinen initialen Entwurf."
            )
        plan, planner, planner_flags = safe_agent_run(
            agent=planner,
            prompt=prompt_plan,
            cwd=project_path,
            flags=planner_flags,
            agents=agents,
            session_dir=session_dir,
            state=state,
            auto_switch=auto_switch,
            role="planner"
        )

        # Sicherheitsprüfung: Hat Modell versehentlich eine Permission-Meldung zurückgegeben?
        if is_permission_error_response(plan):
            print("⚠️ Modell versuchte eine Datei anzulegen. Erzwinge reine Textausgabe...")
            retry_prompt = prompt_plan + "\nACHTUNG: Lege KEINE Datei an! Gib den Plan ausschließlich als Text aus!"
            plan, planner, planner_flags = safe_agent_run(
                agent=planner,
                prompt=retry_prompt,
                cwd=project_path,
                flags=planner_flags,
                agents=agents,
                session_dir=session_dir,
                state=state,
                auto_switch=auto_switch,
                role="planner"
            )

        if ask_mode:
            questions = extract_questions(plan)
            if questions:
                print("\n" + "=" * 60)
                print(f"❓ 🏗️ Architekt ({planner.name}) hat Rückfragen an dich:")
                print("=" * 60)
                print(questions)
                print("-" * 60)
                try:
                    user_ans = input("📝 Deine Antwort / Klärung (oder [Enter] zum Überspringen): ").strip()
                except (EOFError, KeyboardInterrupt):
                    user_ans = ""
                if user_ans:
                    print(f"⏳ 🏗️ Architekt ({planner.name}) bezieht deine Vorgaben in Plan v1 ein...", flush=True)
                    prompt_refine = (
                        f"Du hattest dem Nutzer folgende Fragen gestellt:\n{questions}\n\n"
                        f"Der Nutzer hat wie folgt geantwortet:\n{user_ans}\n\n"
                        f"Bisheriger Entwurf:\n{plan}\n\n"
                        f"Finalisiere nun den Plan v1 vollständig unter Berücksichtigung dieser Nutzer-Entscheidungen."
                        f"{PLANNING_DIRECTIVE}"
                    )
                    plan, planner, planner_flags = safe_agent_run(
                        agent=planner,
                        prompt=prompt_refine,
                        cwd=project_path,
                        flags=planner_flags,
                        agents=agents,
                        session_dir=session_dir,
                        state=state,
                        auto_switch=auto_switch,
                        role="planner"
                    )
                    if is_permission_error_response(plan):
                        plan, planner, planner_flags = safe_agent_run(
                            agent=planner,
                            prompt=prompt_refine + "\nACHTUNG: Lege KEINE Datei an! Gib den Plan als Text aus!",
                            cwd=project_path,
                            flags=planner_flags,
                            agents=agents,
                            session_dir=session_dir,
                            state=state,
                            auto_switch=auto_switch,
                            role="planner"
                        )

        plan_v1_file.write_text(plan, encoding="utf-8")
        current_plan_file = plan_v1_file
        print(f"📄 Plan v1 gespeichert in {plan_v1_file.relative_to(project_path)}")
    else:
        # Resume: Den neuesten Plan aus der Session laden (aber Permission-Errors überspringen)
        existing_plans = sorted(session_dir.glob("PLAN_v*.md"), key=lambda p: p.name)
        active_plan_file_source = existing_plans[-1]
        plan_content = active_plan_file_source.read_text(encoding="utf-8")

        if is_permission_error_response(plan_content) and len(existing_plans) > 1:
            print(f"⚠️ {active_plan_file_source.name} enthielt einen Berechtigungsfehler. Nutze Vorgängerversion.")
            active_plan_file_source = existing_plans[-2]
            plan_content = active_plan_file_source.read_text(encoding="utf-8")

        plan = plan_content
        current_plan_file = active_plan_file_source
        print(f"🔄 Wiederaufnahme: Geladen {active_plan_file_source.name}")

    start_round = state.get("rounds_completed", 0) + 1
    approved = state.get("plan_approved", False)

    if approved:
        print("🎉 Plan wurde in einer früheren Sitzung bereits genehmigt!")
        return True, current_plan_file, planner, reviewer, planner_flags, reviewer_flags

    p_details = f"{planner.name}" + (f" (`{planner.model}`)" if planner.model else "") + (f" [{planner.effort}]" if planner.effort else "")
    r_details = f"{reviewer.name}" + (f" (`{reviewer.model}`)" if reviewer.model else "") + (f" [{reviewer.effort}]" if reviewer.effort else "")
    log_entry = [
        f"\n## [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Session: {session_dir.name}",
        f"- **Aufgabe:** {task}",
        f"- **🏗️ Architekt (Planung & Bau):** {p_details}",
        f"- **🧐 Prüfstatiker (Prüfung & Review):** {r_details}",
        f"- **Session-Pfad:** `{session_dir.relative_to(project_path)}`"
    ]

    for r in range(start_round, max_rounds + 1):
        if STOP_REQUESTED:
            state["rounds_completed"] = r - 1
            save_session_state(session_dir, state)
            return False, current_plan_file, planner, reviewer, planner_flags, reviewer_flags

        r_desc = f"{reviewer.name}" + (f" (`{reviewer.model}`)" if reviewer.model else "") + (f" [{reviewer.effort}]" if reviewer.effort else "")
        print(f"\n🔍 Phase 2: Unabhängiges Review (Runde {r}/{max_rounds}) durch 🧐 Prüfstatiker ({r_desc})...")
        print(f"⏳ Warte auf Review von 🧐 Prüfstatiker ({reviewer.name})...", flush=True)

        prompt_rev = (
            f"Du bist der unabhängige Prüfstatiker und Code-Auditor für das Projekt in '{project_path}'.\n"
            f"Prüfe und grille den folgenden Plan des Architekten unbarmherzig auf Schwachstellen, Race Conditions, fehlende Tests, Sicherheitslücken und architektonische Risiken:\n\n"
            f"Aufgabe: {task}\n\n"
            f"Plan des Architekten:\n{plan}\n\n"
            f"Antworte strukturiert mit:\n"
            f"VERDICT: APPROVED (oder VERDICT: REVISE)\n"
            f"KRITIK:\n- [Punkte...]\n"
            f"EMPFEHLUNGEN:\n- [Punkte...]"
        )
        if ask_mode:
            prompt_rev += (
                "\n\nFRAGEN-MODUS AKTIV: Wenn du kritische Zielkonflikte, Risiken oder Architektur-Entscheidungen siehst, "
                "die zwingend menschlicher Klärung bedürfen, stelle diese gezielt unter '### FRAGEN AN DEN NUTZER:'."
            )
        review, reviewer, reviewer_flags = safe_agent_run(
            agent=reviewer,
            prompt=prompt_rev,
            cwd=project_path,
            flags=reviewer_flags,
            agents=agents,
            session_dir=session_dir,
            state=state,
            auto_switch=auto_switch,
            role="reviewer"
        )

        review_r_file = session_dir / f"REVIEW_round{r}.md"
        review_r_file.write_text(review, encoding="utf-8")
        print(f"📋 Review gespeichert in {review_r_file.relative_to(project_path)}")

        is_approved = "VERDICT: APPROVED" in review
        verdict_str = "APPROVED" if is_approved else "REVISE"
        log_entry.append(f"  - Review Runde {r}: **VERDICT: {verdict_str}**")

        state["rounds_completed"] = r
        if is_approved:
            print(f"🎉 Plan von 🧐 Prüfstatiker ({reviewer.name}) genehmigt!")
            approved = True
            state["plan_approved"] = True
            save_session_state(session_dir, state)
            break
        elif r < max_rounds:
            user_rev_feedback = ""
            if ask_mode:
                rev_questions = extract_questions(review)
                if rev_questions:
                    print("\n" + "=" * 60)
                    print(f"❓ 🧐 Prüfstatiker ({reviewer.name}) hat Rückfragen an dich:")
                    print("=" * 60)
                    print(rev_questions)
                    print("-" * 60)
                    try:
                        user_rev_ans = input("📝 Deine Antwort / Klärung (oder [Enter] zum Überspringen): ").strip()
                    except (EOFError, KeyboardInterrupt):
                        user_rev_ans = ""
                    if user_rev_ans:
                        user_rev_feedback = f"\n\nDer Nutzer hat auf die Rückfragen folgendes klargestellt:\n{user_rev_ans}\n"

            print(f"⚠️ Kritikpunkte von 🧐 Prüfstatiker ({reviewer.name}). 🏗️ Architekt ({planner.name}) bessert den Plan nach...")
            print(f"⏳ Warte auf Überarbeitung durch 🏗️ Architekt ({planner.name})...", flush=True)
            prompt_fix = (
                f"Der Prüfstatiker ({reviewer.name}) hat folgende statische & sicherheitsrelevante Kritikpunkte am Plan geäußert:\n\n"
                f"{review}\n"
                f"{user_rev_feedback}\n"
                f"Bisheriger Plan:\n{plan}\n\n"
                f"Als Architekt: Bitte überarbeite den Plan und behebe alle genannten Mängel vollständig."
                f"{PLANNING_DIRECTIVE}"
            )
            plan, planner, planner_flags = safe_agent_run(
                agent=planner,
                prompt=prompt_fix,
                cwd=project_path,
                flags=planner_flags,
                agents=agents,
                session_dir=session_dir,
                state=state,
                auto_switch=auto_switch,
                role="planner"
            )

            # Prüfen ob Modell trotz Directive einen Permission-Fehler zurückgab
            if is_permission_error_response(plan):
                print("⚠️ Modell versuchte erneut eine Datei anzulegen. Erzwinge reinen Text...")
                retry_fix = prompt_fix + "\nACHTUNG: Lege KEINE Datei wie docs/... an! Gib den Plan als Text auf stdout aus!"
                plan, planner, planner_flags = safe_agent_run(
                    agent=planner,
                    prompt=retry_fix,
                    cwd=project_path,
                    flags=planner_flags,
                    agents=agents,
                    session_dir=session_dir,
                    state=state,
                    auto_switch=auto_switch,
                    role="planner"
                )

            plan_next_file = session_dir / f"PLAN_v{r+1}.md"
            plan_next_file.write_text(plan, encoding="utf-8")
            current_plan_file = plan_next_file
            print(f"📄 Plan v{r+1} gespeichert in {plan_next_file.relative_to(project_path)}")
            save_session_state(session_dir, state)
        else:
            print("🛑 Maximale Review-Runden erreicht.")
            approved = False
            state["plan_approved"] = False
            save_session_state(session_dir, state)

    log_entry.append(f"- **Ergebnis:** {'Genehmigt' if approved else 'Review-Limit erreicht'}\n")
    with open(log_file, "a", encoding="utf-8") as f_log:
        f_log.write("\n".join(log_entry) + "\n")

    return approved, current_plan_file, planner, reviewer, planner_flags, reviewer_flags


# ==========================================
# Interaktive Plan-Bestätigung & Change-Routing
# ==========================================
def handle_plan_approval_and_changes(
    plan_file: Path,
    planner: AgentCLI,
    reviewer: AgentCLI,
    task: str,
    project_path: Path,
    session_dir: Path,
    state: dict,
    agents: dict[str, AgentCLI],
    auto_switch: bool = False,
    planner_flags: list[str] | None = None,
    reviewer_flags: list[str] | None = None
) -> tuple[bool, Path, AgentCLI, AgentCLI, list[str], list[str]]:
    planner_flags = list(planner_flags or [])
    reviewer_flags = list(reviewer_flags or [])
    while not STOP_REQUESTED:
        p_desc = f"{planner.name}" + (f" (`{planner.model}`)" if planner.model else "") + (f" [{planner.effort}]" if planner.effort else "")
        r_desc = f"{reviewer.name}" + (f" (`{reviewer.model}`)" if reviewer.model else "") + (f" [{reviewer.effort}]" if reviewer.effort else "")
        print("\n" + "=" * 60)
        print("📋 PLAN-STATUS: Fertiggestellt & Geprüft")
        print(f"📄 Aktuelle Plan-Datei             : {plan_file.relative_to(project_path)}")
        print(f"🏗️ Architekt (Planung & Bau)       : {p_desc}")
        print(f"🧐 Prüfstatiker (Prüfung & Review) : {r_desc}")
        print("=" * 60)
        print("Möchtest du den Plan freigeben, Rollen tauschen oder Änderungen vornehmen?")
        print("  [1] Approve  -> Plan genehmigen & weiter zur Implementierung")
        print("  [2] Changes  -> Änderungen/Feedback anbringen")
        print("  [3] Swap     -> Rollen tauschen (Architekt <-> Prüfstatiker)")
        print("  [4] Anzeigen -> Plan direkt hier im Terminal lesen")
        print("  [5] Beenden  -> Abbrechen (Fortsetzen später mit --resume möglich)")
        print("-" * 60)

        try:
            choice = input("Auswahl [1/2/3/4/5] (Standard: 1): ").strip()
        except (EOFError, KeyboardInterrupt):
            return False, plan_file, planner, reviewer, planner_flags, reviewer_flags

        if choice in ["", "1", "approve", "a"]:
            state["user_approved"] = True
            save_session_state(session_dir, state)
            return True, plan_file, planner, reviewer, planner_flags, reviewer_flags

        elif choice in ["3", "swap", "s"]:
            planner, reviewer = reviewer, planner
            planner.role = "🏗️ Architekt (Planung & Entwurf)"
            reviewer.role = "🧐 Prüfstatiker (Prüfung & Review)"

            yolo_active = state.get("yolo_enabled", False)
            planner_flags = get_permission_flags(planner.binary) if yolo_active else []
            reviewer_flags = []
            if planner.model:
                planner_flags.extend(["--model", planner.model])
            if planner.effort and planner.binary == "agy":
                planner_flags.extend(["--effort", planner.effort])
            if reviewer.model:
                reviewer_flags.extend(["--model", reviewer.model])
            if reviewer.effort and reviewer.binary == "agy":
                reviewer_flags.extend(["--effort", reviewer.effort])

            state["swap_roles"] = True
            state["planner_binary"] = planner.binary
            state["reviewer_binary"] = reviewer.binary
            save_session_state(session_dir, state)
            print(f"\n🔄 Rollen erfolgreich getauscht:")
            print(f"   🏗️ Neuer Architekt (Planung & Entwurf): {planner.name}")
            print(f"   🧐 Neuer Prüfstatiker (Prüfung & Review): {reviewer.name}")
            continue

        elif choice in ["4", "view", "v"]:
            print("\n" + "-" * 50)
            print(plan_file.read_text(encoding="utf-8"))
            print("-" * 50)
            continue

        elif choice in ["5", "exit", "q"]:
            print("Abgebrochen. Du kannst diesen Stand jederzeit mit 'claudegravity --resume' fortsetzen.")
            return False, plan_file, planner, reviewer, planner_flags, reviewer_flags

        elif choice in ["2", "changes", "c"]:
            print("\n" + "=" * 60)
            print("💬 WO / WIE MÖCHTEST DU DIE ÄNDERUNGEN VORNEHMEN?")
            print("=" * 60)
            print("[UI-Varianten (Graphische Oberfläche)]:")
            print("  [1] Im Editor öffnen (VS Code / Antigravity / Cursor / System)")
            print("      -> Öffnet die Plan-Datei direkt zum Bearbeiten")
            print("  [2] Claude UI (Web / Desktop)")
            print("      -> Zeigt den Plan-Pfad zum einfachen Kopieren in die Claude Web-UI")
            print("\n[CLI-Varianten (Terminal)]:")
            print("  [3] Feedback direkt hier eintippen")
            print("      -> KI überarbeitet den Plan anhand deiner Anweisung automatisch")
            print(f"  [4] Interaktive {planner.name} CLI-Session (Architekt) starten")
            print(f"  [5] Interaktive {reviewer.name} CLI-Session (Prüfstatiker) starten")
            print("  [6] Zurück zum Hauptmenü")
            print("-" * 60)

            try:
                c_choice = input("Auswahl [1-6]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return False, plan_file, planner, reviewer, planner_flags, reviewer_flags

            if c_choice == "1":
                editor = os.environ.get("EDITOR", "xdg-open")
                print(f"🚀 Öffne {plan_file.name} mit {editor}...")
                subprocess.run([editor, str(plan_file)])
                input("\nDrücke [Enter], sobald du mit dem Bearbeiten im Editor fertig bist...")
                v_num = len(list(session_dir.glob("PLAN_v*.md"))) + 1
                new_v_file = session_dir / f"PLAN_v{v_num}_manual.md"
                new_v_file.write_text(plan_file.read_text(encoding="utf-8"), encoding="utf-8")
                plan_file = new_v_file
                print(f"💾 Manuell bearbeiteter Plan gesichert als {new_v_file.name}")

            elif c_choice == "2":
                print("\n📋 Plan-Pfad für Claude UI:")
                print(f"   Pfad: {plan_file.resolve()}")
                print("   Kopiere den Inhalt der Datei in deine Claude UI / Web-Chat.")
                input(f"\nDrücke [Enter], wenn du die Änderungen vorgenommen und in {plan_file.name} gespeichert hast...")

            elif c_choice == "3":
                feedback = input("\n📝 Gib deine Änderungswünsche ein: ").strip()
                if feedback:
                    print(f"⏳ {planner.name} überarbeitet den Plan basierend auf deinem Feedback...")
                    old_plan = plan_file.read_text(encoding="utf-8")
                    prompt_user_fix = (
                        f"Der Nutzer hat folgende Änderungswünsche am Plan geäußert:\n\n"
                        f"Feedback: {feedback}\n\n"
                        f"Aktueller Plan:\n{old_plan}\n\n"
                        f"Bitte überarbeite den Plan und gib den vollständigen neuen Markdown-Plan aus."
                        f"{PLANNING_DIRECTIVE}"
                    )
                    new_plan, planner, planner_flags = safe_agent_run(
                        agent=planner,
                        prompt=prompt_user_fix,
                        cwd=project_path,
                        flags=planner_flags,
                        agents=agents,
                        session_dir=session_dir,
                        state=state,
                        auto_switch=auto_switch,
                        role="planner"
                    )
                    v_num = len(list(session_dir.glob("PLAN_v*.md"))) + 1
                    new_v_file = session_dir / f"PLAN_v{v_num}.md"
                    new_v_file.write_text(new_plan, encoding="utf-8")
                    plan_file = new_v_file
                    print(f"✅ Plan aktualisiert und als {new_v_file.name} gesichert!")

            elif c_choice == "4":
                print(f"🚀 Starte interaktive {planner.name}-Sitzung (Architekt) in {project_path}...")
                subprocess.run([planner.binary], cwd=str(project_path))
                print(f"Zurück im Loop.")

            elif c_choice == "5":
                print(f"🚀 Starte interaktive {reviewer.name}-Sitzung (Prüfstatiker) in {project_path}...")
                subprocess.run([reviewer.binary], cwd=str(project_path))
                print(f"Zurück im Loop.")

            elif c_choice == "6":
                continue

    return False, plan_file, planner, reviewer, planner_flags, reviewer_flags


def main():
    parser = argparse.ArgumentParser(description="ClaudeGravity Loop - Cross-Model Adversarial & Autonomous Execution Loop")
    parser.add_argument("task", nargs="?", default="", help="Die Aufgabe für den Loop")
    parser.add_argument("-p", "--project", default=".", help="Pfad zum Ziel-Projekt (absolut oder relativ, Standard: .)")
    parser.add_argument("-m", "--max-iterations", type=int, default=10, help="Maximale autonome Iterationen (Standard: 10)")
    parser.add_argument("-c", "--resume", "--continue", dest="resume", action="store_true", help="Unterbrochene Sitzung fortsetzen")
    parser.add_argument("-i", "--ask", "--interview", "--clarify", action="store_true", help="Fragen-Modus: Beide Agenten stellen bei Unklarheiten gezielte Fragen an dich, bevor der Plan finalisiert wird")
    parser.add_argument("--planner", "--architekt", default=None, help="Explizite CLI für Architekt / Planung (z.B. claude oder agy)")
    parser.add_argument("--reviewer", "--pruefstatiker", default=None, help="Explizite CLI für Prüfstatiker / Review (z.B. agy oder claude)")
    parser.add_argument("--builder", "--bauer", default=None, help="Explizite CLI für Bauleiter / Umsetzung (Phase 3, z.B. claude oder agy, Standard: folgt Architekt)")
    parser.add_argument("--swap", "--swap-roles", "--reverse", action="store_true", help="Rollen tauschen: Antigravity wird Architekt (Planung), Claude wird Prüfstatiker (Review)")
    parser.add_argument("--planner-model", "--architekt-model", default=None, help="Modell für den Architekten (z.B. sonnet, opus, gemini-2.5-pro)")
    parser.add_argument("--reviewer-model", "--pruefstatiker-model", default=None, help="Modell für den Prüfstatiker (z.B. gemini-2.5-pro, sonnet, opus)")
    parser.add_argument("--builder-model", "--bauer-model", default=None, help="Modell für den Bauleiter in Phase 3 (z.B. claude-3-5-haiku, gemini-2.5-flash, sonnet)")
    parser.add_argument("--effort", default=None, choices=["low", "medium", "high", "xhigh", "max"], help="Reasoning-Intensität / Thinking Effort (für agy)")
    parser.add_argument("--reviewer-effort", "--pruefstatiker-effort", default=None, choices=["low", "medium", "high", "xhigh", "max"], help="Spezifische Reasoning-Intensität für den Prüfstatiker (für agy)")
    parser.add_argument("--planner-effort", "--architekt-effort", default=None, choices=["low", "medium", "high", "xhigh", "max"], help="Spezifische Reasoning-Intensität für den Architekten (falls agy)")
    parser.add_argument("--builder-effort", "--bauer-effort", default=None, choices=["low", "medium", "high", "xhigh", "max"], help="Reasoning-Intensität für den Bauleiter in Phase 3 (für agy)")
    parser.add_argument("--strategy", "--preset", default="balanced", choices=["best-code", "quality", "eco", "economy", "cost", "balanced"], help="Optimierungs-Strategie: best-code (beste Qualität), eco (geringste Kosten / bis zu 70%% Ersparnis), balanced (ausgewogen, Standard)")
    parser.add_argument("--dry-run", action="store_true", help="Trockenlauf: Zeigt Rollen, Modelle, Kosten-Analyse und generierten Befehl ohne Ausführung")
    parser.add_argument("--auto-switch", "--fallback", action="store_true", help="Bei Erreichen eines AI-Limits automatisch zum alternativen Modell wechseln")
    parser.add_argument("--yolo", "--auto-approve", action="store_true", help="Automatisch volle Schreib- und Toolrechte erteilen (keine Nachfrage)")
    parser.add_argument("--check", "--info", action="store_true", help="Installierte AI-CLIs, Standard-Modelle und Rollenkonfiguration anzeigen")
    parser.add_argument("-d", "--delay", type=int, default=3, help="Pause zwischen Runden in Sekunden")

    args = parser.parse_args()

    agents = detect_installed_agents()

    if args.check:
        print("🔍 Erkannte AI-CLIs auf deinem System:")
        for key, agent in agents.items():
            print(f"  [x] {agent.name} (`{agent.binary}` im PATH)")
        print("\n" + "=" * 68)
        print("🎯 Standard-Belegung (wenn NICHTS explizit angegeben wird):")
        print("=" * 68)
        print("1. 🏗️ Architekt (Phase 1: Planung & Entwurf):")
        print("   • CLI           : Claude Code (`claude`)")
        print("   • Standardmodell: Claude Sonnet 5 / 3.7 Sonnet (CLI-Default)")
        print("   • Thinking-Effort: high (CLI-Default)")
        print("   • Aufgabe       : Entwirft den Plan (Phase 1) [nur ~10-15% aller Tokens]")
        print("\n2. 🧐 Prüfstatiker (Phase 2: Prüfung & Review / Stresstest):")
        print("   • CLI           : Google Antigravity (`agy`)")
        print("   • Standardmodell: Gemini 4 Argon / Gemini 2.5 Pro (CLI-Default)")
        print("   • Thinking-Effort: high (CLI-Default)")
        print("   • Aufgabe       : Grillt den Plan unabhängig auf Schwachstellen (Phase 2) [nur ~5-10% aller Tokens]")
        print("\n3. 🔨 Bauleiter (Phase 3: Bau & Umsetzung / Implementation):")
        print("   • CLI           : Folgt dem Architekten (oder separat via --bauer / --builder)")
        print("   • Standardmodell: Folgt dem Architekten (oder Sparmodell via --bauer-model)")
        print("   • Thinking-Effort: CLI-Default (oder steuerbar via --bauer-effort)")
        print("   • Aufgabe       : Setzt den Plan autonom im Code um [verbraucht ~80-90% aller Tokens!]")
        print("=" * 68)
        print("\n💡 Kostenspar-Tipp (Warum Planung & Bau trennen?):")
        print("  Planung & Prüfung benötigen hohes Denkvermögen, aber wenige Tokens.")
        print("  Der Bau-Loop (Phase 3) verbraucht fast das gesamte Kontingent!")
        print("  Mit '--strategy eco' oder '--bauer-model claude-3-5-haiku / gemini-2.5-flash'")
        print("  sparst du bis zu 70% deiner Token-Kosten bei maximaler Architektur-Qualität!")
        print("=" * 68)
        print("\n⚙️  Rollen- und Modell-Steuerung (Anpassungen per Flag):")
        print("  - Strategie-Presets      : --strategy <best-code|eco|balanced> (eco = bis zu 70% günstiger)")
        print("  - Trockenlauf            : --dry-run (zeigt Rollen, Modelle & Befehl ohne Ausführung)")
        print("  - Rollen umkehren        : --swap / --swap-roles (Antigravity = Architekt, Claude = Prüfstatiker)")
        print("  - Architekt festlegen    : --architekt / --planner <claude|agy|gemini|codex>")
        print("  - Prüfstatiker festlegen : --pruefstatiker / --reviewer <agy|claude|gemini|codex>")
        print("  - Bauleiter festlegen    : --bauer / --builder <claude|agy|gemini|codex>")
        print("  - Architekt-Modell       : --architekt-model / --planner-model <name> (z.B. sonnet, gemini-2.5-pro)")
        print("  - Prüfstatiker-Modell    : --pruefstatiker-model / --reviewer-model <name> (z.B. gemini-2.5-pro, sonnet)")
        print("  - Bauleiter-Modell       : --bauer-model / --builder-model <name> (z.B. claude-3-5-haiku, gemini-2.5-flash)")
        print("  - Reasoning-Effort       : --effort / --pruefstatiker-effort / --architekt-effort / --bauer-effort")
        print("  - Auto-Fallback bei Limit: --auto-switch / --fallback (wechselt bei Kontingentlimit nahtlos zum Alternativmodell)")
        print("  - Fragen-Modus aktivieren: -i / --ask (Agenten stellen bei Unklarheiten gezielte Fragen an dich)")
        print("  - Token & Kosten-Audit   : Automatisch aktiv (wird in .done auditiert inkl. Rolle, Modell & Effort)")
        if len(agents) >= 2:
            print("\n🚀 Mindestens 2 Modelle vorhanden. Dual-Loop ist voll einsatzbereit!")
        else:
            print("\n⚠️ Hinweis: Für echte Cross-Model Reviews werden mindestens 2 CLIs empfohlen (z.B. claude und agy).")
        return

    project_path = Path(args.project).resolve()
    if not project_path.exists():
        sys.exit(f"Fehler: Projektordner '{project_path}' existiert nicht.")

    if args.dry_run:
        dry_task = args.task or "Refaktoriere das Modul und erstelle Unit-Tests"
        swap_roles = args.swap
        architekt_choice = args.planner
        pruefstatiker_choice = args.reviewer

        if swap_roles:
            if not architekt_choice and "agy" in agents:
                architekt_choice = "agy"
            elif not architekt_choice and "gemini" in agents:
                architekt_choice = "gemini"
            if not pruefstatiker_choice and "claude" in agents:
                pruefstatiker_choice = "claude"

        if architekt_choice and architekt_choice in agents:
            planner = agents[architekt_choice]
        elif "claude" in agents and not swap_roles:
            planner = agents["claude"]
        else:
            planner = list(agents.values())[0]

        remaining = [a for k, a in agents.items() if a.binary != planner.binary]
        if pruefstatiker_choice and pruefstatiker_choice in agents:
            reviewer = agents[pruefstatiker_choice]
        elif remaining:
            agy_cand = [a for a in remaining if a.binary == "agy"]
            reviewer = agy_cand[0] if agy_cand else remaining[0]
        else:
            reviewer = planner

        if swap_roles and not args.planner and not args.reviewer:
            if planner.binary == "claude" and reviewer.binary == "agy":
                planner, reviewer = reviewer, planner

        builder_choice = args.builder or planner.binary
        builder = agents.get(builder_choice, planner)

        # Strategy
        strat = (args.strategy or "balanced").lower()
        if strat in ["quality", "best"]:
            strat = "best-code"
        elif strat in ["economy", "cost"]:
            strat = "eco"

        default_p_effort = None
        default_r_effort = None
        default_b_effort = None
        default_b_model = None

        if strat == "best-code":
            default_p_effort = "high"
            default_r_effort = "high"
            default_b_effort = "high"
        elif strat == "eco":
            default_p_effort = "medium"
            default_r_effort = "medium"
            default_b_effort = "low"
            default_b_model = "claude-3-5-haiku" if builder.binary == "claude" else "gemini-2.5-flash"
        else:
            default_p_effort = "high" if planner.binary == "agy" else None
            default_r_effort = "high" if reviewer.binary == "agy" else None

        p_model = args.planner_model or ("claude-sonnet (CLI Default)" if planner.binary == "claude" else ("gemini-2.5-pro (CLI Default)" if planner.binary in ["agy", "gemini"] else "CLI Default"))
        p_effort = args.planner_effort or args.effort or default_p_effort or ("high (CLI Default)" if planner.binary == "agy" else None)

        r_model = args.reviewer_model or ("gemini-2.5-pro (CLI Default)" if reviewer.binary in ["agy", "gemini"] else ("claude-sonnet (CLI Default)" if reviewer.binary == "claude" else "CLI Default"))
        r_effort = args.reviewer_effort or args.effort or default_r_effort or ("high (CLI Default)" if reviewer.binary == "agy" else None)

        b_model = args.builder_model or default_b_model or p_model
        b_effort = args.builder_effort or default_b_effort or ("CLI Default" if builder.binary == "agy" else None)

        print("\n" + "=" * 68)
        print("🔍 ClaudeGravity Loop — Trockenlauf (Dry Run)")
        print("=" * 68)
        print(f"📌 Aufgabe        : {dry_task}")
        print(f"🎯 Strategie      : {strat.upper()}")
        print(f"📁 Ziel-Projekt   : {project_path}")
        print("\n1. 🏗️ Architekt (Phase 1: Planung & Entwurf):")
        print(f"   • CLI           : {planner.name} (`{planner.binary}`)")
        print(f"   • Modell        : {p_model}")
        print(f"   • Effort        : {p_effort or 'Standard'}")
        print(f"   • Token-Anteil  : Leichtgewichtig (~10-15% aller Tokens)")
        print("\n2. 🧐 Prüfstatiker (Phase 2: Prüfung & Review / Stresstest):")
        print(f"   • CLI           : {reviewer.name} (`{reviewer.binary}`)")
        print(f"   • Modell        : {r_model}")
        print(f"   • Effort        : {r_effort or 'Standard'}")
        print(f"   • Token-Anteil  : Leichtgewichtig (~5-10% aller Tokens)")
        print("\n3. 🔨 Bauleiter (Phase 3: Bau & Umsetzung / Implementation):")
        print(f"   • CLI           : {builder.name} (`{builder.binary}`)")
        print(f"   • Modell        : {b_model}")
        print(f"   • Effort        : {b_effort or 'Standard'}")
        print(f"   • Token-Anteil  : Schwergewicht (~80-90% aller Tokens!)")
        print("\n💡 Wirtschaftlichkeits- & Qualitäts-Analyse:")
        if strat == "eco":
            print(f"   • Spareffekt: Bis zu ~70% Kosten- und Tokenersparnis!")
            print(f"   • Grund: Phase 1 & 2 nutzen solide Architekturplanung. Das ressourcenintensive")
            print(f"     Bauen in Phase 3 wird an das Spar-Modell `{b_model}` delegiert.")
        elif strat == "best-code":
            print(f"   • Fokus: Höchste Code-Qualität, tiefes Reasoning und maximale Fehlertoleranz.")
            print(f"   • Alle Phasen laufen auf Flaggschiff-Modellen mit hohem Reasoning.")
        else:
            print(f"   • Ausgewogenes Standard-Verhältnis zwischen starker Planung und stabiler Umsetzung.")

        cmd_parts = ["claudegravity", f'"{dry_task}"']
        if strat != "balanced":
            cmd_parts.append(f"--strategy {strat}")
        if args.planner_model:
            cmd_parts.append(f"--architekt-model {args.planner_model}")
        if args.reviewer_model:
            cmd_parts.append(f"--pruefstatiker-model {args.reviewer_model}")
        if args.builder_model:
            cmd_parts.append(f"--bauer-model {args.builder_model}")
        elif default_b_model:
            cmd_parts.append(f"--bauer-model {default_b_model}")
        if args.effort:
            cmd_parts.append(f"--effort {args.effort}")
        if args.swap:
            cmd_parts.append("--swap")
        if args.ask:
            cmd_parts.append("-i")
        if args.yolo:
            cmd_parts.append("--yolo")
        if args.auto_switch:
            cmd_parts.append("--auto-switch")
        if args.project != ".":
            cmd_parts.append(f"-p {args.project}")

        print("\n🚀 Generierter Shell-Befehl (zum Starten):")
        print(f"   {' '.join(cmd_parts)}")
        print("=" * 68)
        return

    loop_dir = project_path / ".dual-loop"
    loop_dir.mkdir(exist_ok=True)

    # Veraltete Dateien im Root von .dual-loop bereinigen (nur noch sessions/ darin)
    for legacy in [loop_dir / "PLAN.md", loop_dir / "REVIEW.md", loop_dir / "PLAN-REVIEW-LOG.md"]:
        if legacy.exists():
            try:
                legacy.unlink()
            except Exception:
                pass

    # ==========================================
    # Resume / Fortsetzen prüfen
    # ==========================================
    session_dir = None
    state = {}
    latest_sess = find_latest_session(loop_dir)

    if args.resume:
        if not latest_sess:
            sys.exit("Fehler: Keine frühere Sitzung zum Fortsetzen gefunden.")
        session_dir = latest_sess
        state = load_session_state(session_dir)
        task = state.get("task", args.task)
        print(f"🔄 Setze letzte Sitzung fort: {session_dir.name}")
        print(f"📌 Ursprüngliche Aufgabe: {task}")
    elif not args.task and latest_sess:
        state_candidate = load_session_state(latest_sess)
        if state_candidate and state_candidate.get("phase") != "completed":
            print(f"\n🔍 Unterbrochene Sitzung gefunden: {latest_sess.name}")
            print(f"📌 Aufgabe: {state_candidate.get('task')}")
            try:
                res_ans = input("Möchtest du diese Sitzung fortsetzen? [J/n]: ")
            except (EOFError, KeyboardInterrupt):
                res_ans = "n"
            if res_ans.strip().lower() in ["", "j", "ja", "y", "yes"]:
                session_dir = latest_sess
                state = state_candidate
                task = state.get("task")
            else:
                parser.print_help()
                sys.exit(1)
        else:
            parser.print_help()
            sys.exit(1)
    elif not args.task:
        parser.print_help()
        sys.exit(1)
    else:
        task = args.task
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = sanitize_filename(task)
        session_dir = loop_dir / "sessions" / f"{timestamp}_{slug}"
        session_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "session_id": session_dir.name,
            "task": task,
            "created_at": datetime.datetime.now().isoformat(),
            "phase": "plan",
            "rounds_completed": 0,
            "plan_approved": False,
            "last_iteration": 0,
            "max_iterations": args.max_iterations
        }
        save_session_state(session_dir, state)

    # Paarung festlegen
    swap_roles = args.swap or state.get("swap_roles", False)
    if args.swap:
        state["swap_roles"] = True

    architekt_choice = args.planner
    pruefstatiker_choice = args.reviewer

    if swap_roles:
        if not architekt_choice and "agy" in agents:
            architekt_choice = "agy"
        elif not architekt_choice and "gemini" in agents:
            architekt_choice = "gemini"
        if not pruefstatiker_choice and "claude" in agents:
            pruefstatiker_choice = "claude"

    if architekt_choice and architekt_choice in agents:
        planner_base = agents[architekt_choice]
    elif "claude" in agents and not swap_roles:
        planner_base = agents["claude"]
    else:
        planner_base = list(agents.values())[0]

    remaining = [a for k, a in agents.items() if a.binary != planner_base.binary]
    if pruefstatiker_choice and pruefstatiker_choice in agents:
        reviewer_base = agents[pruefstatiker_choice]
    elif remaining:
        agy_cand = [a for a in remaining if a.binary == "agy"]
        reviewer_base = agy_cand[0] if agy_cand else remaining[0]
    else:
        reviewer_base = planner_base

    if swap_roles and not args.planner and not args.reviewer:
        if planner_base.binary == "claude" and reviewer_base.binary == "agy":
            planner_base, reviewer_base = reviewer_base, planner_base

    builder_choice = args.builder or state.get("builder_binary") or planner_base.binary
    builder_base = agents.get(builder_choice, planner_base)

    # ==========================================
    # Metriken (Token & Kosten-Tracking)
    # ==========================================
    session_metrics = SessionMetrics.from_dict(state.get("metrics"))

    planner = create_agent(planner_base.binary, agents, role="🏗️ Architekt (Planung & Entwurf)", metrics_tracker=session_metrics)
    reviewer = create_agent(reviewer_base.binary, agents, role="🧐 Prüfstatiker (Prüfung & Review)", metrics_tracker=session_metrics)
    builder = create_agent(builder_base.binary, agents, role="🔨 Bauleiter (Bau & Umsetzung)", metrics_tracker=session_metrics)

    # ==========================================
    # Rechte-, Modell- & Effort-Steuerung
    # ==========================================
    planner_perm_flags = []
    reviewer_perm_flags = []
    builder_perm_flags = []
    yolo_active = args.yolo or state.get("yolo_enabled", False)

    if yolo_active:
        planner_perm_flags = get_permission_flags(planner.binary)
        reviewer_perm_flags = get_permission_flags(reviewer.binary)
        builder_perm_flags = get_permission_flags(builder.binary)
        state["yolo_enabled"] = True
        save_session_state(session_dir, state)
        print(f"🔓 YOLO-Modus aktiv: Volle Tool- & Schreibrechte erteilt ({' '.join(planner_perm_flags)}).")

    planner_flags = list(planner_perm_flags)
    reviewer_flags = list(reviewer_perm_flags)
    builder_flags = list(builder_perm_flags)

    # Strategie auflösen
    strat = (args.strategy or state.get("strategy") or "balanced").lower()
    if strat in ["quality", "best"]:
        strat = "best-code"
    elif strat in ["economy", "cost"]:
        strat = "eco"
    state["strategy"] = strat

    default_p_effort = None
    default_r_effort = None
    default_b_effort = None
    default_b_model = None

    if strat == "best-code":
        default_p_effort = "high"
        default_r_effort = "high"
        default_b_effort = "high"
    elif strat == "eco":
        default_p_effort = "medium"
        default_r_effort = "medium"
        default_b_effort = "low"
        default_b_model = "claude-3-5-haiku" if builder.binary == "claude" else "gemini-2.5-flash"
    else:  # balanced
        default_p_effort = "high" if planner.binary == "agy" else None
        default_r_effort = "high" if reviewer.binary == "agy" else None

    # Modell für Architekt
    planner_model = args.planner_model or state.get("planner_model")
    if planner_model:
        planner_flags.extend(["--model", planner_model])
        state["planner_model"] = planner_model
        planner.model = planner_model
    else:
        planner.model = "claude-sonnet (CLI Default)" if planner.binary == "claude" else ("gemini-2.5-pro (CLI Default)" if planner.binary in ["agy", "gemini"] else "CLI Default")

    p_effort = args.planner_effort or args.effort or state.get("planner_effort") or default_p_effort
    if p_effort:
        if planner.binary == "agy":
            planner_flags.extend(["--effort", p_effort])
        state["planner_effort"] = p_effort
        planner.effort = p_effort
    else:
        planner.effort = "high (CLI Default)" if planner.binary == "agy" else None

    # Modell für Prüfstatiker
    reviewer_model = args.reviewer_model or state.get("reviewer_model")
    if reviewer_model:
        reviewer_flags.extend(["--model", reviewer_model])
        state["reviewer_model"] = reviewer_model
        reviewer.model = reviewer_model
    else:
        reviewer.model = "gemini-2.5-pro (CLI Default)" if reviewer.binary in ["agy", "gemini"] else ("claude-sonnet (CLI Default)" if reviewer.binary == "claude" else "CLI Default")

    r_effort = args.reviewer_effort or args.effort or state.get("reviewer_effort") or default_r_effort
    if r_effort:
        if reviewer.binary == "agy":
            reviewer_flags.extend(["--effort", r_effort])
        state["reviewer_effort"] = r_effort
        reviewer.effort = r_effort
    else:
        reviewer.effort = "high (CLI Default)" if reviewer.binary == "agy" else None

    # Modell für Bauleiter (Phase 3)
    builder_model = args.builder_model or state.get("builder_model") or default_b_model
    if builder_model:
        builder_flags.extend(["--model", builder_model])
        state["builder_model"] = builder_model
        builder.model = builder_model
    else:
        builder.model = planner.model

    b_effort = args.builder_effort or state.get("builder_effort") or default_b_effort
    if b_effort:
        if builder.binary == "agy":
            builder_flags.extend(["--effort", b_effort])
        state["builder_effort"] = b_effort
        builder.effort = b_effort
    else:
        builder.effort = planner.effort if builder.binary == planner.binary else ("CLI Default" if builder.binary == "agy" else None)

    # Auto-Switch Modus
    auto_switch = args.auto_switch or state.get("auto_switch", False)
    if auto_switch:
        state["auto_switch"] = True

    # Fragen-Modus
    ask_mode = args.ask or state.get("ask_mode", False)
    if ask_mode:
        state["ask_mode"] = True
    save_session_state(session_dir, state)

    print(f"\n=======================================================")
    print(f"[*] ClaudeGravity Loop gestartet")
    print(f"[*] Ziel-Projekt      : {project_path}")
    print(f"[*] Strategie         : {strat.upper()}")
    p_info = f"{planner.name}"
    if planner.model:
        p_info += f" (Modell: {planner.model})"
    if planner.effort:
        p_info += f" [Effort: {planner.effort}]"
    print(f"[*] 🏗️ Architekt      : {p_info}")

    r_info = f"{reviewer.name}"
    if reviewer.model:
        r_info += f" (Modell: {reviewer.model})"
    if reviewer.effort:
        r_info += f" [Effort: {reviewer.effort}]"
    print(f"[*] 🧐 Prüfstatiker   : {r_info}")

    b_info = f"{builder.name}"
    if builder.model:
        b_info += f" (Modell: {builder.model})"
    if builder.effort:
        b_info += f" [Effort: {builder.effort}]"
    print(f"[*] 🔨 Bauleiter      : {b_info}")

    if ask_mode:
        print(f"[*] Modus             : ❓ Fragen-Modus aktiv (--ask)")
    if auto_switch:
        print(f"[*] Fallback          : 🔄 Auto-Switch aktiv (--auto-switch)")
    if swap_roles:
        print(f"[*] Rollen-Status     : 🔄 Rollen getauscht (--swap)")
    print(f"[*] Session-ID        : {session_dir.name}")
    print(f"=======================================================\n")

    project_ctx = load_project_context(project_path)

    # ==========================================
    # 1. & 2. Phase: Adversarial Plan Review
    # ==========================================
    existing_plans = sorted(session_dir.glob("PLAN_v*.md"), key=lambda p: p.name)
    plan_file = existing_plans[-1] if existing_plans else session_dir / "PLAN_v1.md"

    if state.get("phase") in ["plan", "review"] or not state.get("user_approved", False):
        state["phase"] = "review"
        save_session_state(session_dir, state)

        # Plan erstellen / Review durchführen mit planner_flags
        review_ok, plan_file, planner, reviewer, planner_flags, reviewer_flags = run_adversarial_plan(
            planner=planner,
            reviewer=reviewer,
            task=task,
            project_path=project_path,
            project_ctx=project_ctx,
            session_dir=session_dir,
            state=state,
            agents=agents,
            auto_switch=auto_switch,
            planner_flags=planner_flags,
            reviewer_flags=reviewer_flags,
            max_rounds=2,
            ask_mode=ask_mode
        )

        if STOP_REQUESTED:
            return

        # Interaktive Freigabe & Change-Routing (Approve / Changes / Swap)
        user_confirmed, plan_file, planner, reviewer, planner_flags, reviewer_flags = handle_plan_approval_and_changes(
            plan_file, planner, reviewer, task, project_path, session_dir, state,
            agents=agents, auto_switch=auto_switch, planner_flags=planner_flags, reviewer_flags=reviewer_flags
        )

        if not user_confirmed or STOP_REQUESTED:
            print("Implementierung nicht gestartet.")
            return

        state["phase"] = "build"
        state["user_approved"] = True
        save_session_state(session_dir, state)

    if not args.builder:
        # Falls kein separater Bauleiter gesetzt ist, baut der freigegebene Architekt
        builder = create_agent(
            planner.binary,
            agents,
            role="🔨 Bauleiter (Bau & Umsetzung)",
            model=builder_model,
            effort=b_effort,
            metrics_tracker=session_metrics
        )

    # Falls YOLO noch nicht aktiv war, vor Phase 3 fragen
    if not yolo_active:
        try:
            print("\n⚙️  Berechtigungs-Prüfung für Phase 3 (Implementierung):")
            perm_ans = input(f"Soll 🔨 Bauleiter ({builder.name}) volle Schreib-/Tool-Rechte erhalten ({' / '.join(get_permission_flags(builder.binary))})? [J/n]: ")
            if perm_ans.strip().lower() in ["", "j", "ja", "y", "yes"]:
                builder_perm_flags = get_permission_flags(builder.binary)
                for f in builder_perm_flags:
                    if f not in builder_flags:
                        builder_flags.insert(0, f)
                state["yolo_enabled"] = True
                save_session_state(session_dir, state)
                print(f"🔓 Schreibberechtigung aktiviert ({' '.join(builder_perm_flags)}).")
            else:
                print("🔒 Eingeschränkter Modus: Bestätigung bei jedem Tool-Call erforderlich.")
        except (EOFError, KeyboardInterrupt):
            pass

    # ==========================================
    # 3. Phase: Autonomer Implementierungs-Loop
    # ==========================================
    logs_dir = project_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    session_log = logs_dir / f"loop_{session_dir.name}.log"

    print(f"\n🔨 Phase 3: Starte Implementierungs-Loop in {project_path}...")
    b_build_desc = f"{builder.name}" + (f" (`{builder.model}`)" if builder.model else "") + (f" [{builder.effort}]" if builder.effort else "")
    print(f"🔨 Ausführender Bauleiter: {b_build_desc}")
    start_iter = state.get("last_iteration", 0) + 1
    max_iters = args.max_iterations

    for iteration in range(start_iter, max_iters + 1):
        if STOP_REQUESTED:
            break

        if check_and_clean_done_marker(session_dir, project_path):
            done_file = session_dir / ".done"
            print(f"\n🎉 Fertigmeldung ({done_file.relative_to(project_path)}) gefunden! Aufgabe erfolgreich abgeschlossen.")
            append_metrics_to_done(session_dir, project_path, session_metrics)
            print(format_metrics_report(session_metrics))
            state["phase"] = "completed"
            state["metrics"] = session_metrics.to_dict()
            save_session_state(session_dir, state)
            break

        state["last_iteration"] = iteration
        state["metrics"] = session_metrics.to_dict()
        save_session_state(session_dir, state)

        timestamp = datetime.datetime.now().isoformat()
        log_header = f"\n{'='*20} Iteration {iteration}/{max_iters} @ {timestamp} {'='*20}\n"
        print(log_header, flush=True)

        rel_done_path = (session_dir / ".done").relative_to(project_path)
        prompt_build = (
            f"Führe den genehmigten Plan ({plan_file.relative_to(project_path)}) für folgende Aufgabe aus:\n{task}\n\n"
            f"Erstelle oder modifiziere die benötigten Dateien im Projektverzeichnis. Führe Tests durch.\n\n"
            f"WICHTIG ZUM ABSCHLUSS: Wenn alle Anforderungen vollständig erfüllt und getestet sind, "
            f"erstelle die Fertigmeldungs-Datei genau im Session-Ordner unter: '{rel_done_path}' (NICHT im Projekt-Hauptverzeichnis)."
        )

        try:
            print(f"⏳ Warte auf 🔨 Bauleiter ({builder.name}) (führt genehmigten Plan aus)...", flush=True)
            res, builder, builder_flags = safe_agent_run(
                agent=builder,
                prompt=prompt_build,
                cwd=project_path,
                flags=builder_flags,
                agents=agents,
                session_dir=session_dir,
                state=state,
                auto_switch=auto_switch,
                role="builder",
                metrics_tracker=session_metrics
            )
            print(f"\n📋 Zusammenfassung von 🔨 Bauleiter ({builder.name}) [Iteration {iteration}]:")
            print(res)

            with open(session_log, "a", encoding="utf-8") as f_log:
                f_log.write(log_header)
                f_log.write(res + "\n")

        except Exception as exc:
            print(f"[!] Fehler bei Iteration {iteration}: {exc}")

        state["metrics"] = session_metrics.to_dict()
        save_session_state(session_dir, state)

        if check_and_clean_done_marker(session_dir, project_path):
            done_file = session_dir / ".done"
            print(f"\n🎉 Fertigmeldung ({done_file.relative_to(project_path)}) gefunden! Aufgabe erfolgreich abgeschlossen.")
            append_metrics_to_done(session_dir, project_path, session_metrics)
            print(format_metrics_report(session_metrics))
            state["phase"] = "completed"
            save_session_state(session_dir, state)
            break

        if STOP_REQUESTED:
            break

        if args.delay > 0:
            time.sleep(args.delay)

    if not check_and_clean_done_marker(session_dir, project_path):
        print(f"\n[+] Maximale Rundenanzahl ({max_iters}) erreicht. Stand gesichert.")
        print(f"💡 Du kannst jederzeit mit 'claudegravity -c' weitere Runden anhängen.")
        append_metrics_to_done(session_dir, project_path, session_metrics)
        print(format_metrics_report(session_metrics))

    print("\n[*] ClaudeGravity Loop beendet.")


if __name__ == "__main__":
    main()
