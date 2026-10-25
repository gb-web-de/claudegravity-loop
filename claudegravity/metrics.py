"""Token- und Kostenzählung je Rolle und der Kennzahlen-Block (KPI v1) für .done und AUDIT.md."""

import contextlib
import datetime
import json
import shutil
from pathlib import Path

from .common import say


class SessionMetrics:
    """Token, Kosten, Neuversuche, Audit-Ereignisse und Zähler einer Session, je Rolle und Modell aufgeschlüsselt."""

    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.cost_usd = 0.0
        self.by_agent: dict[str, dict] = {}
        self.retries = {"attempts": 0, "recovered": 0, "exhausted": 0}
        self.audit_events: dict[str, int] = {}
        self.counters: dict[str, int] = {}

    def count(self, name: str):
        """Ereigniszähler für die Kennzahlen (z. B. proof_red, inspection_rejected)."""
        self.counters[name] = self.counters.get(name, 0) + 1

    def note_audit(self, kind: str):
        """Rechte-Audit-Ereignis zählen (z. B. blocked_write)."""
        self.audit_events[kind] = self.audit_events.get(kind, 0) + 1

    def note_retry(self, outcome: str):
        """outcome: attempts (Neuversuch gestartet), recovered (danach erfolgreich), exhausted (aufgegeben)."""
        self.retries[outcome] = self.retries.get(outcome, 0) + 1

    def add(
        self,
        agent_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
        role: str | None = None,
        model: str | None = None,
        effort: str | None = None,
    ):
        """Verbrauch eines Aufrufs buchen, gesamt und unter Rolle, Agent, Modell und Effort."""
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
                "calls": 0,
            }

        entry = self.by_agent[tracker_key]
        entry["input_tokens"] += input_tokens
        entry["output_tokens"] += output_tokens
        entry["total_tokens"] += total_tokens
        entry["cost_usd"] += cost_usd
        entry["calls"] = entry.get("calls", 0) + 1
        if role:
            entry["role"] = role
        if model:
            entry["model"] = model
        if effort:
            entry["effort"] = effort

    def to_dict(self) -> dict:
        """Als JSON-taugliches dict für state.json."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd, 4),
            "by_agent": self.by_agent,
            "retries": self.retries,
            "audit_events": self.audit_events,
            "counters": self.counters,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "SessionMetrics":
        """Aus state.json wiederherstellen (für --resume); fehlende Felder bleiben auf 0."""
        m = cls()
        if not data:
            return m
        m.input_tokens = data.get("input_tokens", 0)
        m.output_tokens = data.get("output_tokens", 0)
        m.total_tokens = data.get("total_tokens", 0)
        m.cost_usd = data.get("cost_usd", 0.0)
        m.by_agent = data.get("by_agent", {})
        m.retries.update(data.get("retries") or {})
        m.audit_events.update(data.get("audit_events") or {})
        m.counters.update(data.get("counters") or {})
        return m


KPI_ROLE_KEYS = {"planner": "Architekt", "reviewer": "Prüfstatiker", "builder": "Bauleiter", "inspector": "Abnahme"}


def role_key(role_title: str) -> str | None:
    """Kurzschlüssel (planner, reviewer, builder, inspector) zu einem Rollentitel; None, wenn keiner passt."""
    for key, word in KPI_ROLE_KEYS.items():
        if word in (role_title or ""):
            return key
    return None


def build_kpis(state: dict, metrics: SessionMetrics, now: datetime.datetime | None = None) -> dict:
    """Vergleichbare Kennzahlen einer Session. Kosten nur, soweit Anbieter sie melden (USD)."""
    calls = {k: 0 for k in KPI_ROLE_KEYS}
    cost = {k: 0.0 for k in KPI_ROLE_KEYS}
    tokens = {k: 0 for k in KPI_ROLE_KEYS}
    reporting: list[str] = []
    for usage in metrics.by_agent.values():
        key = role_key(usage.get("role", ""))
        if not key:
            continue
        calls[key] += usage.get("calls", 0)
        cost[key] += usage.get("cost_usd", 0.0)
        tokens[key] += usage.get("total_tokens", 0)
        if usage.get("cost_usd", 0.0) > 0 and usage.get("agent_name") not in reporting:
            reporting.append(usage.get("agent_name"))
    build_rounds = calls["builder"]
    rejections = metrics.counters.get("proof_red", 0) + metrics.counters.get("inspection_rejected", 0)
    rework_rounds = min(max(build_rounds - 1, 0), rejections)
    duration = None
    try:
        started = datetime.datetime.fromisoformat(state["created_at"])
        duration = int(((now or datetime.datetime.now()) - started).total_seconds())
    except (KeyError, TypeError, ValueError):
        pass
    return {
        "version": 1,
        "success": state.get("phase") == "completed",
        "phase": state.get("phase"),
        "strategy": state.get("strategy"),
        "duration_s": duration,
        "plan_review_rounds": state.get("rounds_completed", 0),
        "build_rounds": build_rounds,
        "build_rounds_to_success": build_rounds if state.get("phase") == "completed" else None,
        "stages": len(state.get("stages") or []),
        "proof_runs": metrics.counters.get("proof_green", 0) + metrics.counters.get("proof_red", 0),
        "proof_red": metrics.counters.get("proof_red", 0),
        "inspection_rounds": max(calls["inspector"], state.get("inspection_rounds", 0)),
        "inspection_rejected": metrics.counters.get("inspection_rejected", 0),
        "rework_rounds": rework_rounds,
        "rework_rate": round(rework_rounds / build_rounds, 2) if build_rounds else 0.0,
        "tokens_total": metrics.total_tokens,
        "tokens_by_role": tokens,
        "cost_usd_task": round(metrics.cost_usd, 4),
        "cost_usd_inspection": round(cost["inspector"], 4),
        "cost_usd_by_role": {k: round(v, 4) for k, v in cost.items()},
        "cost_reported_by": reporting,
        "retries": metrics.retries.get("attempts", 0),
        "abort_reason": state.get("abort_reason"),
        "escalation": state.get("escalation"),
    }


def format_kpi_block(kpi: dict) -> str:
    """Kennzahlen-Block (KPI v1) als Markdown für .done und AUDIT.md."""

    def money(value: float) -> str:
        return f"{value:.4f} USD" if value else "0 USD"

    dur = kpi["duration_s"]
    dur_txt = f"{dur // 60} min {dur % 60} s" if dur is not None else "unbekannt"
    to_success = kpi["build_rounds_to_success"]
    who = ", ".join(kpi["cost_reported_by"]) or "kein Anbieter (Abo-CLIs und lokale Modelle melden keine Kosten)"
    lines = [
        "",
        "---",
        "### 📈 Kennzahlen (ClaudeGravity KPI v1)",
        f"* **Ergebnis:** {'erfolgreich' if kpi['success'] else 'offen (' + str(kpi['phase']) + ')'} · Strategie `{kpi['strategy']}` · Dauer {dur_txt}",
        f"* **Kosten je Aufgabe:** {money(kpi['cost_usd_task'])} · **davon Abnahme:** {money(kpi['cost_usd_inspection'])} (gemeldet von: {who})",
        f"* **Runden:** Plan-Review {kpi['plan_review_rounds']} · Bau {kpi['build_rounds']}"
        + (f" (bis Erfolg: {to_success})" if to_success is not None else "")
        + (f" · Etappen {kpi['stages']}" if kpi["stages"] else "")
        + f" · Abnahme {kpi['inspection_rounds']}",
        f"* **Nacharbeit:** {kpi['rework_rounds']} von {kpi['build_rounds']} Bau-Runden (Quote {kpi['rework_rate']:.0%}); "
        f"Prüfbefehl rot {kpi['proof_red']}/{kpi['proof_runs']}, Abnahme verweigert {kpi['inspection_rejected']}",
        *(
            [
                f"* **Eskalation:** Bau-Runde {kpi['escalation'].get('iteration')}: {kpi['escalation'].get('from')} → "
                f"{kpi['escalation'].get('to')} ({kpi['escalation'].get('reason')})"
            ]
            if kpi.get("escalation")
            else []
        ),
        *([f"* **Abbruchgrund:** {kpi['abort_reason']}"] if kpi.get("abort_reason") else []),
        "",
        "```json",
        json.dumps(kpi, ensure_ascii=False),
        "```",
    ]
    return "\n".join(lines)


def format_metrics_report(metrics: SessionMetrics, state: dict | None = None) -> str:
    """Verbrauchsbericht als Markdown: Tokens, Kosten, Aufschlüsselung je Rolle und Audit-Ereignisse."""
    lines = [
        "",
        "---",
        "### 📊 Ressourcen-Verbrauch & Kosten (ClaudeGravity Audit)",
        f"* **Gesamt-Tokens:** {metrics.total_tokens:,} Tokens",
        f"  * **Input-Tokens:** {metrics.input_tokens:,}",
        f"  * **Output-Tokens:** {metrics.output_tokens:,}",
        f"* **Entstandene Kosten (geschätzt):** ~${metrics.cost_usd:.4f} USD",
        "* **Aufschlüsselung nach Rolle, Agent, Modell & Effort:**",
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
            lines.append(
                f"    * **Verbrauch:** {usage['total_tokens']:,} Tokens (Input: {usage['input_tokens']:,}, Output: {usage['output_tokens']:,})"
            )
            lines.append(f"    * **Kosten:** {cost_str}")
    else:
        lines.append("  * Keine detaillierte Modell-Aufschlüsselung verfügbar.")
    if metrics.retries.get("attempts"):
        r = metrics.retries
        lines.append(
            f"* **Automatische Neuversuche:** {r['attempts']} (danach erfolgreich: {r.get('recovered', 0)}, aufgegeben: {r.get('exhausted', 0)})"
        )
    if metrics.audit_events:
        lines.append("* **Sicherheitsereignisse** (Details in `LOG.md` und `audit-events.jsonl`):")
        for kind, count in sorted(metrics.audit_events.items()):
            lines.append(f"  * {AUDIT_EVENT_LABELS.get(kind, kind)}: {count}")
    lines.append(f"* **Audit-Zeitstempel:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    if state is not None:
        return format_kpi_block(build_kpis(state, metrics)) + "\n" + "\n".join(lines)
    return "\n".join(lines)


def append_metrics_to_done(session_dir: Path, project_path: Path, metrics: SessionMetrics, state: dict | None = None):
    """Schreibt den Token- und Kostenbericht in die .done-Datei des Session-Ordners."""
    session_done = session_dir / ".done"
    root_done = project_path / ".done"

    if root_done.exists() and not session_done.exists():
        with contextlib.suppress(Exception):
            shutil.move(str(root_done), str(session_done))

    if not session_done.exists():
        session_done.write_text("# Aufgabe abgeschlossen\n", encoding="utf-8")

    content = session_done.read_text(encoding="utf-8")
    if "ClaudeGravity Audit" not in content:
        report = format_metrics_report(metrics, state)
        with open(session_done, "a", encoding="utf-8") as f:
            f.write(report)
        say(f"📊 Ressourcen-Audit erfolgreich in {session_done.relative_to(project_path)} eingetragen.")


AUDIT_EVENT_LABELS = {
    "blocked_write": "Blockierter Schreibversuch",
    "readonly_changed": "Änderung durch lesende Rolle",
    "secret_in_output": "Mögliche Zugangsdaten in Modellantwort",
    "tests_weakened": "Tests abgeschwächt oder entfernt",
}
