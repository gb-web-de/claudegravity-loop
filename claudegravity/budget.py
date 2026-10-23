"""Budget-Grenzen und Kostenschätzung aus früheren Sessions."""

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from .common import HYBRID_STRATEGIES, SETTINGS, say
from .errors import fail
from .metrics import format_metrics_report, role_key
from .session import append_log, log_event, save_session_state

if TYPE_CHECKING:
    from .metrics import SessionMetrics


# ==========================================
# Budget: harte und weiche Grenzen für Tokens und gemeldete Kosten
# ==========================================
class BudgetExceeded(BaseException):
    """BaseException, damit allgemeine `except Exception`-Blöcke im Bau-Loop den Abbruch nicht schlucken."""


BUDGET_ROLE_ALIASES = {
    "architekt": "planner", "planner": "planner",
    "pruefstatiker": "reviewer", "prüfstatiker": "reviewer", "reviewer": "reviewer",
    "bauleiter": "builder", "bauer": "builder", "builder": "builder",
    "abnahme": "inspector", "inspector": "inspector",
}
BUDGET_ROLE_LABELS = {"planner": "Architekt", "reviewer": "Prüfstatiker", "builder": "Bauleiter", "inspector": "Abnahme"}
BUDGET_AUTO_WARN = 0.8  # ohne --budget-warn: Warnung bei 80 % einer harten Grenze


def parse_budget(text: str) -> tuple[str, float]:
    """'2.50usd', '$2.50' -> ('usd', 2.5); '500k', '1.2m', '80000 tokens' -> ('tokens', ...)."""
    raw = str(text).strip().lower().replace(" ", "").replace(",", ".")
    if raw.startswith("$") or raw.endswith("usd") or raw.endswith("$"):
        number = raw.strip("$").removesuffix("usd").strip("$")
        unit = "usd"
    else:
        number = raw.removesuffix("tokens").removesuffix("token")
        unit = "tokens"
    factor = 1.0
    if unit == "tokens" and number[-1:] in ("k", "m"):
        factor = 1_000 if number[-1] == "k" else 1_000_000
        number = number[:-1]
    try:
        value = float(number) * factor
    except ValueError:
        raise ValueError(f"Budget {text!r} nicht lesbar (Beispiele: 500k, 1.5m, 80000, 2.50usd, $2.50)") from None
    if value <= 0:
        raise ValueError(f"Budget {text!r} muss größer als 0 sein")
    return unit, value


def format_budget(unit: str, value: float) -> str:
    if unit == "usd":
        return f"{value:.2f} USD" if value >= 0.1 else f"{value:.4f} USD"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M Tokens"
    return f"{value / 1000:.0f}k Tokens" if value >= 10_000 else f"{value:.0f} Tokens"


class Budget:
    """Prüft nach jedem KI-Aufruf den Verbrauch gegen die Grenzen. USD zählt nur, was Anbieter melden."""

    def __init__(self, max_total: str | None = None, warn_total: str | None = None, roles: str | None = None):
        self.max_total = parse_budget(max_total) if max_total else None
        self.warn_total = parse_budget(warn_total) if warn_total else None
        self.roles: dict[str, tuple[str, float]] = {}
        for part in filter(None, (p.strip() for p in (roles or "").split(","))):
            if "=" not in part:
                raise ValueError(f"Rollen-Budget {part!r}: erwartet ROLLE=WERT, z. B. bauleiter=300k")
            name, value = part.split("=", 1)
            role = BUDGET_ROLE_ALIASES.get(name.strip().lower())
            if not role:
                raise ValueError(f"Rollen-Budget {part!r}: unbekannte Rolle (architekt, pruefstatiker, bauleiter, abnahme)")
            self.roles[role] = parse_budget(value)
        self.warned: set[str] = set()
        self.context: dict = {}

    @property
    def active(self) -> bool:
        return bool(self.max_total or self.warn_total or self.roles)

    @staticmethod
    def usage(metrics: "SessionMetrics") -> dict:
        used = {"total": {"tokens": metrics.total_tokens, "usd": metrics.cost_usd}}
        for entry in metrics.by_agent.values():
            role = role_key(entry.get("role", ""))
            if role:
                bucket = used.setdefault(role, {"tokens": 0, "usd": 0.0})
                bucket["tokens"] += entry.get("total_tokens", 0)
                bucket["usd"] += entry.get("cost_usd", 0.0)
        return used

    def limits(self) -> list[tuple[str, str, tuple[str, float], bool]]:
        """(Schlüssel, Bezeichnung, Grenze, hart?)"""
        out = []
        if self.max_total:
            out.append(("total", "Gesamtbudget", self.max_total, True))
            if not self.warn_total:
                out.append(("total", "Gesamtbudget (80 %)", (self.max_total[0], self.max_total[1] * BUDGET_AUTO_WARN), False))
        if self.warn_total:
            out.append(("total", "Warnschwelle", self.warn_total, False))
        for role, limit in self.roles.items():
            out.append((role, f"Budget {BUDGET_ROLE_LABELS[role]}", limit, True))
            out.append((role, f"Budget {BUDGET_ROLE_LABELS[role]} (80 %)", (limit[0], limit[1] * BUDGET_AUTO_WARN), False))
        return out

    def check(self, metrics: "SessionMetrics") -> list[str]:
        """Liefert neue Warnungen; wirft BudgetExceeded, sobald eine harte Grenze erreicht ist."""
        used = self.usage(metrics)
        warnings = []
        for key, label, (unit, value), hard in self.limits():
            spent = used.get(key, {}).get(unit, 0)
            if spent < value:
                continue
            text = f"{label} {format_budget(unit, value)} erreicht (verbraucht: {format_budget(unit, spent)})"
            if hard:
                raise BudgetExceeded(text)
            if label not in self.warned:
                self.warned.add(label)
                warnings.append(text)
        return warnings

    def status(self, metrics: "SessionMetrics") -> str | None:
        if not self.max_total:
            return None
        unit, value = self.max_total
        spent = self.usage(metrics)["total"][unit]
        return f"Budget {spent / value:.0%} von {format_budget(unit, value)}"



def handle_budget_exceeded(exc: BudgetExceeded) -> None:
    """Sichert Stand und Bericht mit Abbruchgrund, dann Ende mit CG-1404."""
    ctx = SETTINGS.budget.context if SETTINGS.budget else {}
    state, session_dir, metrics = ctx.get("state"), ctx.get("session_dir"), ctx.get("metrics")
    if state is not None and session_dir is not None:
        state["abort_reason"] = f"Budget: {exc}"
        if metrics is not None:
            state["metrics"] = metrics.to_dict()
            (session_dir / "AUDIT.md").write_text(format_metrics_report(metrics, state), encoding="utf-8")
        save_session_state(session_dir, state)
        append_log(session_dir, f"Abbruch: Budget: {exc}")
        log_event(session_dir, "session_end", level="error", phase=state.get("phase"), success=False,
                  abort_reason=state["abort_reason"], code="CG-1404")
    say("\n🛑 Hartes Budget erreicht, Lauf beendet. Stand gesichert.")
    fail("CG-1404", str(exc), exit_code=3)


# ==========================================
# Kostenschätzung vorab (aus den Kennzahlen früherer Sessions)
# ==========================================
KPI_JSON_RE = re.compile(r"KPI v1\).*?```json\s*\n(\{.*?\})\s*\n```", re.S)
ESTIMATE_HISTORY_LIMIT = 20
ESTIMATE_MIN_SAME_STRATEGY = 2


def read_session_kpi(session_dir: Path) -> dict | None:
    """Liest den KPI-JSON-Block aus `.done` oder `AUDIT.md` einer Session."""
    for name in (".done", "AUDIT.md"):
        try:
            text = (session_dir / name).read_text(encoding="utf-8")
        except OSError:
            continue
        found = KPI_JSON_RE.findall(text)
        if not found:
            continue
        try:
            kpi = json.loads(found[-1])
        except json.JSONDecodeError:
            continue
        if isinstance(kpi, dict) and kpi.get("version") == 1:
            return kpi
    return None


def collect_kpi_history(project_path: Path, limit: int = ESTIMATE_HISTORY_LIMIT) -> list[dict]:
    """Kennzahlen der letzten Sessions des Projekts, neueste zuerst."""
    sessions_dir = project_path / ".dual-loop" / "sessions"
    if not sessions_dir.is_dir():
        return []
    history = []
    for session in sorted((p for p in sessions_dir.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True):
        kpi = read_session_kpi(session)
        if kpi:
            history.append(kpi)
            if len(history) >= limit:
                break
    return history


def spread(values: list[float]) -> tuple[float, float, float] | None:
    """(günstigster, erwarteter = Median, ungünstigster Fall)"""
    values = sorted(v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool))
    if not values:
        return None
    mid = len(values) // 2
    median = values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2
    return values[0], median, values[-1]


def estimate_run(history: list[dict], strategy: str, max_iterations: int) -> dict:
    """Schätzt Bau-Runden, Tokens und gemeldete Kosten. Ohne Verlauf nur Runden; Kosten nie aus einer Preistabelle."""
    same = [k for k in history if k.get("strategy") == strategy]
    basis = same if len(same) >= ESTIMATE_MIN_SAME_STRATEGY else history
    if not basis:
        expected = min(3, max_iterations)
        return {"source": "heuristik", "sessions": 0, "strategy_match": False,
                "rounds": (1, expected, max_iterations), "tokens": None, "cost_usd": None,
                "cost_sessions": 0, "rework_rate": None, "success_rate": None}
    costed = [k["cost_usd_task"] for k in basis if (k.get("cost_usd_task") or 0) > 0]
    rounds = spread([k.get("build_rounds") for k in basis if k.get("build_rounds")])
    if rounds:
        rounds = tuple(min(int(round(r)), max_iterations) for r in rounds)
    successes = [k for k in basis if k.get("success")]
    return {
        "source": "verlauf",
        "sessions": len(basis),
        "strategy_match": basis is same,
        "rounds": rounds,
        "tokens": spread([k.get("tokens_total") for k in basis if k.get("tokens_total")]),
        "cost_usd": spread(costed) if costed else None,
        "cost_sessions": len(costed),
        "rework_rate": (spread([k.get("rework_rate") for k in basis]) or (None, None, None))[1],
        "success_rate": len(successes) / len(basis),
    }


def estimate_hints(est: dict, strategy: str, budget: "Budget | None", has_local: bool,
                   proof: str | None) -> list[str]:
    """Spar- und Sicherheitshinweise passend zur Schätzung."""
    hints = []
    worst = {"tokens": est["tokens"][2] if est["tokens"] else None,
             "usd": est["cost_usd"][2] if est["cost_usd"] else None}
    if budget and budget.max_total:
        unit, limit = budget.max_total
        if worst[unit] is not None and worst[unit] >= limit:
            hints.append(f"Im ungünstigsten Fall reicht --budget-max {format_budget(unit, limit)} nicht "
                         f"(bisher bis {format_budget(unit, worst[unit])}); der Lauf bricht dann mit gesichertem Stand ab.")
    elif worst["usd"]:
        hints.append(f"--budget-max {format_budget('usd', worst['usd'] * 1.2)} begrenzt den ungünstigsten Fall mit etwas Luft.")
    elif worst["tokens"]:
        hints.append(f"--budget-max {format_budget('tokens', worst['tokens'] * 1.2)} begrenzt den ungünstigsten Fall mit etwas Luft.")
    if est["cost_usd"] and strategy not in ("local-free", *HYBRID_STRATEGIES):
        if has_local:
            hints.append("Mit --strategy hybrid oder local-free baut ein lokales Modell; Bau-Runden kosten dann 0 USD.")
        elif strategy != "eco":
            hints.append("Mit --strategy eco baut ein Spar-Modell; ein lokales Modell (Ollama, LM Studio) spart den Bau ganz.")
    if est["rework_rate"] is not None and est["rework_rate"] >= 0.5:
        hints.append(f"Viel Nacharbeit bisher (Median {est['rework_rate']:.0%})"
                     + (": ein --proof-Befehl gibt dem Bauleiter früh ein klares Signal." if not proof
                        else ": kleinere Aufgaben oder --etappen an senken die Runden."))
    return hints


def format_estimate(est: dict, hints: list[str]) -> list[str]:
    def triple(values, fmt) -> str:
        return " · ".join(f"{name} {fmt(v)}" for name, v in zip(("günstig", "erwartet", "ungünstig"), values, strict=True))
    lines = ["\n💰 Kostenschätzung vorab:"]
    if est["source"] == "heuristik":
        lines.append(f"   • Bau-Runden    : {triple(est['rounds'], lambda v: str(v))} (Faustregel, noch kein Verlauf)")
        lines.append("   • Tokens/Kosten : noch keine Kennzahlen in diesem Projekt. Nach dem ersten Lauf schätzt der")
        lines.append("     Trockenlauf aus deinen eigenen Sessions; USD nur, wenn Anbieter Kosten melden.")
    else:
        basis = f"{est['sessions']} frühere Session(s)" + (" mit gleicher Strategie" if est["strategy_match"] else " (alle Strategien)")
        lines.append(f"   • Grundlage     : {basis}, Erfolgsquote {est['success_rate']:.0%}")
        if est["rounds"]:
            lines.append(f"   • Bau-Runden    : {triple(est['rounds'], lambda v: str(v))}")
        if est["tokens"]:
            lines.append(f"   • Tokens        : {triple(est['tokens'], lambda v: format_budget('tokens', v))}")
        if est["cost_usd"]:
            lines.append(f"   • Kosten        : {triple(est['cost_usd'], lambda v: format_budget('usd', v))}"
                         f" (gemeldet in {est['cost_sessions']} von {est['sessions']} Sessions)")
        else:
            lines.append("   • Kosten        : keine gemeldet (Abo-CLIs und lokale Modelle melden keine; Tokens oben zum Nachrechnen)")
    lines.extend(f"   • Tipp: {hint}" for hint in hints)
    return lines
