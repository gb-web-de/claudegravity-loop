"""Aufruf einer Rolle mit Neuversuchen, Limit-Menü, Rechte-Audit, Budget und Statuszeile."""

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .common import (
    RateLimitError,
    SETTINGS,
    backoff_delay,
    interruptible_sleep,
    is_transient_error,
    retry_policy,
    say,
    wait_countdown,
)
from .safety import mask_secrets, redact_secrets
from .metrics import SessionMetrics
from .backends import AgentCLI, describe_agent
from .session import (
    append_log,
    fingerprint_changes,
    log_event,
    record_audit_event,
    role_flags,
    save_session_state,
    workspace_fingerprint,
)
from .budget import format_budget

if TYPE_CHECKING:
    from .budget import Budget


def get_alternative_agent(current_agent: AgentCLI, agents: dict[str, AgentCLI], exclude: set[str] | None = None) -> AgentCLI | None:
    """Findet eine alternative installierte CLI für Modell-Wechsel bei Limits.

    `exclude` enthält die Anbieter der Gegenrolle: Ein Wechsel darf nie dazu führen,
    dass derselbe Anbieter plant und prüft (bzw. baut und abnimmt).
    """
    blocked = {current_agent.binary} | set(exclude or ())
    preferred = {"claude": "agy", "agy": "claude"}.get(current_agent.binary)
    if preferred and preferred in agents and preferred not in blocked:
        return agents[preferred]
    for a in agents.values():
        if a.binary not in blocked:
            return a
    return None


def handle_rate_limit(
    current_agent: AgentCLI,
    agents: dict[str, AgentCLI],
    err: RateLimitError,
    session_dir: Path,
    state: dict,
    auto_switch: bool = False,
    exclude: set[str] | None = None,
) -> tuple[str, AgentCLI | None]:
    """Behandelt RateLimit-Fehler interaktiv oder per automatischem Modell-Wechsel."""
    alt_agent = get_alternative_agent(current_agent, agents, exclude)

    if auto_switch and alt_agent:
        say(f"\n🔄 Auto-Switch aktiv: Wechsle automatisch von {describe_agent(current_agent)} zu {alt_agent.name}...")
        return "switch", alt_agent

    say("\n" + "=" * 65)
    if err.transient:
        say(f"🚨 [CG-1302] STÖRUNG: {describe_agent(current_agent)} antwortet auch nach automatischen Neuversuchen nicht!")
    else:
        say(f"🚨 [CG-1301] AI-LIMIT ERREICHT: {describe_agent(current_agent)} meldet Sitzungs- / Ratenlimit!")
    say(f"   Grund: {err.message}")
    if err.reset_time:
        say(f"   Reset erwartet: {err.reset_time}")
    say("=" * 65)
    say("Wie möchtest du fortfahren?")
    if alt_agent:
        say(f"  [1] 🔄 Modell-Wechsel -> Zu {alt_agent.name} wechseln und sofort weiterarbeiten")
    else:
        say("  [1] 🔄 Modell-Wechsel -> (Keine Alternative, die nicht schon die Gegenrolle hat)")
    wait_info = f" ({err.reset_time})" if err.reset_time else ""
    say(f"  [2] ⏳ Warten         -> Countdown starten{wait_info} und automatisch wiederholen")
    say("  [3] 💾 Beenden        -> Stand sichern und beenden (Fortsetzen später mit 'claudegravity -c')")
    say("-" * 65)

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
        ok = wait_countdown(secs, err.reset_time or f"{secs // 60} Min")
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


PROGRESS_ROLE_LABELS = {"planner": "🏗️ Architekt", "reviewer": "🧐 Prüfstatiker", "builder": "🔨 Bauleiter", "inspector": "🔎 Abnahme"}


def format_duration(seconds: float) -> str:
    """Dauer als "12 s" oder "3 min 5 s"."""
    seconds = int(seconds)
    return f"{seconds // 60} min {seconds % 60} s" if seconds >= 60 else f"{seconds} s"


def format_progress(
    role: str,
    agent_name: str,
    state: dict,
    metrics: "SessionMetrics | None",
    elapsed: float,
    delta_tokens: int,
    budget: "Budget | None" = None,
) -> list[str]:
    """Statuszeilen nach jedem KI-Aufruf: wo der Lauf steht, was er verbraucht hat und was als Nächstes kommt."""
    if role == "builder":
        where = f"Bau-Runde {state.get('last_iteration', 0)}/{state.get('iteration_limit') or state.get('max_iterations') or '?'}"
        stages = state.get("stages") or []
        if stages and state.get("stage_mode_active"):
            where += f" · Etappe {min(state.get('stage_index', 0) + 1, len(stages))}/{len(stages)}"
        proof = state.get("proof")
        nxt = f"Prüfbefehl `{proof}`" if proof else "Fertigmeldung prüfen, sonst nächste Runde"
    elif role == "inspector":
        where = f"Abnahme-Runde {state.get('inspection_rounds', 0)}"
        nxt = "Urteil auswerten: fertig oder Nacharbeit"
    else:
        where = f"Plan-Runde {state.get('rounds_completed', 0) + 1}"
        nxt = "Prüfstatiker prüft den Plan" if role == "planner" else "Urteil auswerten: Freigabe oder Überarbeitung"
    usage = f"+{format_budget('tokens', delta_tokens)}"
    if metrics is not None:
        usage += f" (gesamt {format_budget('tokens', metrics.total_tokens)}"
        usage += f", {format_budget('usd', metrics.cost_usd)} gemeldet)" if metrics.cost_usd > 0 else ")"
    label = PROGRESS_ROLE_LABELS.get(role, role)
    # Endpunkte heißen schon nach ihrer Rolle ("Architekt Endpoint (...)"); dann nur das Symbol voranstellen
    who = f"{label.split()[0]} {agent_name}" if agent_name.startswith(label.split()[-1]) else f"{label} {agent_name}"
    line = f"📍 {where} · {who} fertig nach {format_duration(elapsed)} · {usage}"
    status = budget.status(metrics) if budget and budget.active and metrics is not None else None
    return [line, f"   Weiter: {nxt}" + (f" · {status}" if status else "")]


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
    metrics_tracker: SessionMetrics | None = None,
    exclude: set[str] | None = None,
) -> tuple[str, AgentCLI, list[str]]:
    """Führt einen Prompt aus und fängt Raten- und Sitzungslimits mit Wiederholungs-Logik ab.

    Vorübergehende Störungen (Überlastung, 5xx, abgerissene Verbindung) werden zuerst automatisch
    mit exponentiellem Backoff und Jitter wiederholt; erst danach erscheint das Limit-Menü.
    """
    attempt = 0
    while not SETTINGS.stop_requested:
        try:
            watch = role != "builder"
            before = workspace_fingerprint(cwd) if watch else None
            tracker = metrics_tracker or agent.metrics_tracker
            tokens_before = tracker.total_tokens if tracker is not None else 0
            started = time.monotonic()
            res = agent.run(prompt, cwd=cwd, extra_flags=flags)
            tracker = metrics_tracker or agent.metrics_tracker
            if watch:
                changed = fingerprint_changes(before, workspace_fingerprint(cwd))
                if changed:
                    shown = ", ".join(changed[:5]) + (f" (+{len(changed) - 5})" if len(changed) > 5 else "")
                    record_audit_event(session_dir, "readonly_changed", f"{agent.name} als {role}: {shown}", tracker)
            found = redact_secrets(res)[1] if isinstance(res, str) else []
            if found:
                record_audit_event(session_dir, "secret_in_output", f"{agent.name} ({role}): {', '.join(found)}", tracker)
            if SETTINGS.budget and SETTINGS.budget.active and tracker is not None:
                for warning in SETTINGS.budget.check(tracker):
                    say(f"💶 Budget-Warnung: {warning}")
                    append_log(session_dir, f"Budget-Warnung: {warning}")
            delta = (tracker.total_tokens if tracker is not None else 0) - tokens_before
            log_event(
                session_dir,
                "call",
                role=role,
                agent=agent.name,
                model=agent.reported_model or agent.model,
                phase=state.get("phase"),
                iteration=state.get("last_iteration") if role == "builder" else None,
                duration_s=round(time.monotonic() - started, 1),
                tokens=delta,
                tokens_total=tracker.total_tokens if tracker is not None else None,
                cost_usd_total=round(tracker.cost_usd, 4) if tracker is not None else None,
                retries=attempt or None,
            )
            if SETTINGS.progress:
                for line in format_progress(role, agent.name, state, tracker, time.monotonic() - started, delta, SETTINGS.budget):
                    say(line, flush=True)
            if attempt and metrics_tracker:
                metrics_tracker.note_retry("recovered")
            if attempt:
                append_log(session_dir, f"Neuversuch {attempt} bei {agent.name} erfolgreich")
            return res, agent, flags
        except (RateLimitError, RuntimeError) as exc:
            message = exc.message if isinstance(exc, RateLimitError) else str(exc)
            hard_limit = isinstance(exc, RateLimitError) and bool(exc.reset_time)
            if hard_limit or not is_transient_error(message, local=agent.local):
                if isinstance(exc, RateLimitError):
                    err = exc
                else:
                    raise
            else:
                policy = retry_policy(agent.local)
                if attempt < policy["attempts"]:
                    attempt += 1
                    wait = backoff_delay(attempt, policy["base"], policy["cap"])
                    short = message.strip().splitlines()[0][:160] if message.strip() else type(exc).__name__
                    say(f"🔁 Vorübergehender Fehler bei {describe_agent(agent)}: {short}")
                    say(f"   Neuversuch {attempt}/{policy['attempts']} in {wait:.0f} s ...")
                    append_log(
                        session_dir,
                        f"Vorübergehender Fehler bei {agent.name} ({short}); Neuversuch {attempt}/{policy['attempts']} in {wait:.0f} s",
                    )
                    if metrics_tracker:
                        metrics_tracker.note_retry("attempts")
                    if not interruptible_sleep(wait):
                        break
                    continue
                if metrics_tracker:
                    metrics_tracker.note_retry("exhausted")
                append_log(session_dir, f"{agent.name}: {attempt} Neuversuche ohne Erfolg, Auswahl Wechseln/Warten/Beenden")
                err = RateLimitError(agent.binary, message, transient=True)
            attempt = 0
            action, new_agent = handle_rate_limit(agent, agents, err, session_dir, state, auto_switch=auto_switch, exclude=exclude)
            if action == "switch" and new_agent:
                if role == "builder":
                    role_label = "Bauleiter"
                    role_title = "🔨 Bauleiter (Bau & Umsetzung)"
                elif role == "planner":
                    role_label = "Architekt"
                    role_title = "🏗️ Architekt (Planung & Entwurf)"
                elif role == "inspector":
                    role_label = "Abnahme"
                    role_title = "🔎 Abnahme"
                else:
                    role_label = "Prüfstatiker"
                    role_title = "🧐 Prüfstatiker (Prüfung & Review)"
                say(f"🔄 Rolle '{role_label}' wechselt zu {new_agent.name}!")
                append_log(session_dir, f"Limit bei {agent.name}: Rolle {role_label} wechselt zu {new_agent.name}")
                agent = new_agent
                agent.role = role_title
                agent.session_id = None
                agent.requested_model = None
                if metrics_tracker:
                    agent.metrics_tracker = metrics_tracker
                flags = role_flags(new_agent.binary, role, state.get("yolo_enabled", False))
                state[f"{role}_binary"] = new_agent.binary
                state[f"{role}_name"] = new_agent.name
                save_session_state(session_dir, state)
                continue
            elif action == "wait":
                continue
            else:
                state["abort_reason"] = (
                    f"Beendet im Limit-Menü ({agent.name}: {mask_secrets(err.message.strip().splitlines()[0][:120]) if err.message.strip() else 'Limit'})"
                )
                save_session_state(session_dir, state)
                say(f"\n⏹️ Abbruchgrund: {state['abort_reason']}")
                say("💾 Sitzung gesichert. Setze jederzeit fort mit 'claudegravity -c'.")
                sys.exit(0)
    return "", agent, flags
