"""Die Phasen eines Laufs nach dem Start: Session, Rollen, Plan, Bau-Vorbereitung, Bau-Loop und Abschluss."""

import argparse
import contextlib
import dataclasses
import datetime
import sys
import time
from pathlib import Path

from .common import ENDPOINT_BINARIES, LOCAL_BACKEND_ORDER, SETTINGS, STAGE_MAX_TRIES, say
from .safety import redact_secrets
from .errors import fail, format_error
from .metrics import SessionMetrics, append_metrics_to_done, format_metrics_report
from .backends import AgentCLI, DEFAULT_MODEL_LABEL, create_agent, describe_agent, effort_label
from .session import (
    acquire_worktree,
    append_log,
    check_and_clean_done_marker,
    find_latest_session,
    findings_digest,
    get_permission_flags,
    get_readonly_flags,
    is_git_repo,
    load_project_context,
    load_session_state,
    log_event,
    release_worktree,
    role_flags,
    sanitize_filename,
    save_session_state,
    sha256_file,
)
from .budget import format_budget
from .planning import handle_plan_approval_and_changes, run_adversarial_plan
from .roles import (
    ESCALATE_AFTER_DEFAULT,
    choose_escalation,
    normalize_strategy,
    pick_inspector,
    pick_plan_roles,
    stages_wanted,
)
from .build import (
    BuildContext,
    builder_resume_flags,
    collect_build_changes,
    compose_build_prompt,
    edit_errors_note,
    git_head,
    parse_stages,
    plan_excerpt,
    run_build_call,
    run_inspection,
    run_proof_check,
    stage_file_context,
)
from .wizard import print_welcome


@dataclasses.dataclass
class RunContext:
    """Stand eines Laufs zwischen den Phasen: Rollen, Flags, Pfade und Einstellungen."""

    args: argparse.Namespace
    agents: dict
    project_path: Path
    session_dir: Path
    state: dict
    task: str
    metrics: SessionMetrics
    strategy: str
    planner: AgentCLI
    reviewer: AgentCLI
    builder: AgentCLI
    planner_flags: list[str]
    reviewer_flags: list[str]
    builder_flags: list[str]
    builder_model: str | None
    builder_effort: str | None
    yolo_active: bool
    auto_switch: bool
    swap_roles: bool
    use_worktree: bool
    merge_worktree: bool
    ask_mode: bool
    plan_file: Path | None = None
    session_log: Path | None = None
    work_path: Path | None = None
    in_worktree: bool = False
    proof_cmd: str | None = None
    inspector: AgentCLI | None = None
    inspector_flags: list[str] = dataclasses.field(default_factory=list)
    max_iters: int = 0


def open_session(args: argparse.Namespace, project_path: Path, config_report: dict) -> tuple[Path, dict, str]:
    """Neue Session anlegen oder eine unterbrochene fortsetzen. Liefert (Session-Ordner, Stand, Aufgabe)."""
    loop_dir = project_path / ".dual-loop"
    loop_dir.mkdir(exist_ok=True)

    # Veraltete Dateien im Root von .dual-loop bereinigen (nur noch sessions/ darin)
    for legacy in [loop_dir / "PLAN.md", loop_dir / "REVIEW.md", loop_dir / "PLAN-REVIEW-LOG.md"]:
        if legacy.exists():
            with contextlib.suppress(Exception):
                legacy.unlink()

    # ==========================================
    # Resume / Fortsetzen prüfen
    # ==========================================
    session_dir = None
    state = {}
    latest_sess = find_latest_session(loop_dir)

    if args.resume:
        if not latest_sess:
            fail("CG-1004", str(project_path))
        session_dir = latest_sess
        state = load_session_state(session_dir)
        task = state.get("task", args.task)
        say(f"🔄 Setze letzte Sitzung fort: {session_dir.name}")
        say(f"📌 Ursprüngliche Aufgabe: {task}")
    elif not args.task and latest_sess:
        state_candidate = load_session_state(latest_sess)
        if state_candidate and state_candidate.get("phase") != "completed":
            say(f"\n🔍 Unterbrochene Sitzung gefunden: {latest_sess.name}")
            say(f"📌 Aufgabe: {state_candidate.get('task')}")
            try:
                res_ans = input("Möchtest du diese Sitzung fortsetzen? [J/n]: ")
            except (EOFError, KeyboardInterrupt):
                res_ans = "n"
            if res_ans.strip().lower() in ["", "j", "ja", "y", "yes"]:
                session_dir = latest_sess
                state = state_candidate
                task = state.get("task")
            else:
                print_welcome()
                sys.exit(1)
        else:
            print_welcome()
            sys.exit(1)
    elif not args.task:
        print_welcome()
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
            "max_iterations": args.max_iterations or 10,
        }
        template = config_report.get("template")
        if template:
            state["template"] = template["name"]
            if template.get("hint"):
                task = f"{task}\n\nVorgehen ({template['name']}): {template['hint']}"
                state["task"] = task
        save_session_state(session_dir, state)
    return session_dir, state, task


def setup_run(args: argparse.Namespace, agents: dict, project_path: Path, session_dir: Path, state: dict, task: str) -> "RunContext":
    """Rollen besetzen, Rechte, Strategie, Modelle und Effort festlegen; alles landet im Sitzungsstand."""
    swap_roles = args.swap or state.get("swap_roles", False)
    if args.swap:
        state["swap_roles"] = True

    planner_base, reviewer_base = pick_plan_roles(agents, args.planner, args.reviewer, swap_roles, bool(args.planner or args.reviewer))

    builder_choice = args.builder or state.get("builder_binary") or planner_base.binary
    builder_base = agents.get(builder_choice, planner_base)

    # ==========================================
    # Metriken (Token & Kosten-Tracking)
    # ==========================================
    session_metrics = SessionMetrics.from_dict(state.get("metrics"))
    state.pop("abort_reason", None)
    if SETTINGS.budget and SETTINGS.budget.active:
        SETTINGS.budget.context = {"state": state, "session_dir": session_dir, "metrics": session_metrics}
        say(
            "[*] Budget            : "
            + ", ".join(f"{label} {format_budget(*limit)}" for _, label, limit, hard in SETTINGS.budget.limits() if hard)
            + (f"; Warnung ab {format_budget(*SETTINGS.budget.warn_total)}" if SETTINGS.budget.warn_total else "")
        )

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

    # Architekt und Prüfstatiker lesen nur, auch mit --yolo. Schreibrechte bekommt allein der Bauleiter.
    planner_perm_flags = get_readonly_flags(planner.binary)
    reviewer_perm_flags = get_readonly_flags(reviewer.binary)
    if yolo_active:
        builder_perm_flags = get_permission_flags(builder.binary)
        state["yolo_enabled"] = True
        save_session_state(session_dir, state)
        say(
            f"🔓 YOLO-Modus aktiv: Bauleiter erhält volle Tool- & Schreibrechte ({' '.join(builder_perm_flags)}); Architekt und Prüfstatiker bleiben lesend."
        )

    planner_flags = list(planner_perm_flags)
    reviewer_flags = list(reviewer_perm_flags)
    builder_flags = list(builder_perm_flags)

    # Strategie auflösen
    strat = normalize_strategy(args.strategy or state.get("strategy") or "balanced")
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
        default_b_model = {"claude": "claude-3-5-haiku", "agy": "gemini-2.5-flash", "gemini": "gemini-2.5-flash"}.get(builder.binary)
    elif strat == "local-free":
        default_p_effort = "high"
        default_r_effort = "high"
        default_b_effort = "low"
        if not args.builder:
            for k in LOCAL_BACKEND_ORDER:
                if k in agents:
                    builder_base = agents[k]
                    builder = create_agent(
                        builder_base.binary, agents, role="🔨 Bauleiter (Bau & Umsetzung)", metrics_tracker=session_metrics
                    )
                    break
        default_b_model = args.builder_model or (
            "qwen2.5-coder:32b"
            if "endpoint" in builder.binary
            else ("qwen2.5-coder:latest" if "ollama" in builder.binary else "local-model")
        )
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
        planner.model = DEFAULT_MODEL_LABEL

    p_effort = args.planner_effort or args.effort or state.get("planner_effort") or default_p_effort
    if p_effort:
        if planner.binary in ("agy", "codex"):
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
        reviewer.model = DEFAULT_MODEL_LABEL

    r_effort = args.reviewer_effort or args.effort or state.get("reviewer_effort") or default_r_effort
    if r_effort:
        if reviewer.binary in ("agy", "codex"):
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
        builder.model = planner.model if builder.binary == planner.binary else DEFAULT_MODEL_LABEL

    b_effort = args.builder_effort or state.get("builder_effort") or default_b_effort
    if b_effort:
        if builder.binary in ("agy", "codex"):
            builder_flags.extend(["--effort", b_effort])
        state["builder_effort"] = b_effort
        builder.effort = b_effort
    else:
        builder.effort = planner.effort if builder.binary == planner.binary else ("CLI Default" if builder.binary == "agy" else None)

    # Auto-Switch Modus
    auto_switch = args.auto_switch or state.get("auto_switch", False)
    if auto_switch:
        state["auto_switch"] = True

    # Git-Workspace pro Session (Standard bei Git-Projekten)
    use_worktree = (state["worktree"].get("enabled", True) if state.get("worktree") else args.worktree) and is_git_repo(project_path)
    if not use_worktree and not state.get("worktree"):
        state["worktree"] = {"enabled": False}
    merge_worktree = args.merge or state.get("merge_worktree", False)
    if merge_worktree:
        state["merge_worktree"] = True

    # Fragen-Modus
    ask_mode = args.ask or state.get("ask_mode", False)
    if ask_mode:
        state["ask_mode"] = True
    save_session_state(session_dir, state)
    return RunContext(
        args=args,
        agents=agents,
        project_path=project_path,
        session_dir=session_dir,
        state=state,
        task=task,
        metrics=session_metrics,
        strategy=strat,
        planner=planner,
        reviewer=reviewer,
        builder=builder,
        planner_flags=planner_flags,
        reviewer_flags=reviewer_flags,
        builder_flags=builder_flags,
        builder_model=builder_model,
        builder_effort=b_effort,
        yolo_active=yolo_active,
        auto_switch=auto_switch,
        swap_roles=swap_roles,
        use_worktree=use_worktree,
        merge_worktree=merge_worktree,
        ask_mode=ask_mode,
    )


def print_run_banner(run: "RunContext") -> None:
    """Kopf des Laufs: Rollen, Modi und Session; legt fest, ob der Architekt in Etappen plant."""
    args, project_path, session_dir, state, task = run.args, run.project_path, run.session_dir, run.state, run.task
    planner, reviewer, builder, strat = run.planner, run.reviewer, run.builder, run.strategy
    ask_mode, auto_switch, swap_roles, use_worktree, merge_worktree = (
        run.ask_mode,
        run.auto_switch,
        run.swap_roles,
        run.use_worktree,
        run.merge_worktree,
    )
    say("\n=======================================================")
    say("[*] ClaudeGravity Loop gestartet")
    say(f"[*] Ziel-Projekt      : {project_path}")
    say(f"[*] Strategie         : {strat.upper()}")
    p_info = f"{planner.name}"
    if planner.model:
        p_info += f" (Modell: {planner.model})"
    if planner.effort:
        p_info += f" [Effort: {effort_label(planner.binary, planner.effort)}]"
    say(f"[*] 🏗️ Architekt      : {p_info}")

    r_info = f"{reviewer.name}"
    if reviewer.model:
        r_info += f" (Modell: {reviewer.model})"
    if reviewer.effort:
        r_info += f" [Effort: {effort_label(reviewer.binary, reviewer.effort)}]"
    say(f"[*] 🧐 Prüfstatiker   : {r_info}")

    b_info = f"{builder.name}"
    if builder.model:
        b_info += f" (Modell: {builder.model})"
    if builder.effort:
        b_info += f" [Effort: {effort_label(builder.binary, builder.effort)}]"
    say(f"[*] 🔨 Bauleiter      : {b_info}")

    if ask_mode:
        say("[*] Modus             : ❓ Fragen-Modus aktiv (--ask)")
    if auto_switch:
        say("[*] Fallback          : 🔄 Auto-Switch aktiv (--auto-switch)")
    if swap_roles:
        say("[*] Rollen-Status     : 🔄 Rollen getauscht (--swap)")
    if use_worktree:
        say("[*] Git-Workspace     : 🌿 eigener Worktree pro Session" + (" (Merge nach .done)" if merge_worktree else ""))
    task_secrets = redact_secrets(task)[1]
    if task_secrets:
        cloud_roles = [a.name for a in (planner, reviewer, builder) if not a.local]
        if SETTINGS.shield:
            say(
                f"🛡️  Aufgabe enthält mögliche Zugangsdaten ({', '.join(task_secrets)}); sie werden vor dem Versand an Cloud-Modelle geschwärzt."
            )
        elif cloud_roles:
            say(
                f"⚠️  Aufgabe enthält mögliche Zugangsdaten ({', '.join(task_secrets)}) und der Datenschutzschild ist aus: "
                f"sie gehen im Klartext an {', '.join(dict.fromkeys(cloud_roles))}. Besser als Umgebungsvariable übergeben."
            )
        append_log(session_dir, f"Aufgabe enthält mögliche Zugangsdaten: {', '.join(task_secrets)}")

    # Etappen-Modus: hängt vom Bauleiter ab, der in Phase 3 tatsächlich baut
    expected_builder = builder.binary if (args.builder or strat == "local-free") else planner.binary
    stage_pref = (state.get("stage_mode") if args.resume else None) or args.etappen
    state["stage_mode"] = stage_pref
    SETTINGS.stage_planning = stages_wanted(stage_pref, expected_builder)
    if SETTINGS.stage_planning:
        say("[*] Etappen-Modus     : 🧩 Plan in Etappen, Bauleiter setzt sie einzeln um (--etappen aus schaltet ab)")
    say(f"[*] Session-ID        : {session_dir.name}")
    say("=======================================================\n")


def run_plan_phase(run: "RunContext") -> bool:
    """Phase 1 und 2: Plan entwerfen, unabhängig prüfen und freigeben. False, wenn nicht gebaut werden soll."""
    args, agents, project_path, session_dir, state, task = run.args, run.agents, run.project_path, run.session_dir, run.state, run.task
    planner, reviewer, planner_flags, reviewer_flags = run.planner, run.reviewer, run.planner_flags, run.reviewer_flags
    auto_switch, ask_mode = run.auto_switch, run.ask_mode
    project_ctx = load_project_context(project_path, task)

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
            max_rounds=max(1, args.max_rounds),
            ask_mode=ask_mode,
        )

        if SETTINGS.stop_requested:
            return False

        if args.approve_plan or state.get("approve_plan"):
            # Freigabe ohne Terminal: nur ein vom Prüfstatiker genehmigter Plan wird gebaut
            state["approve_plan"] = True
            if not review_ok:
                say(f"🛑 Der Prüfstatiker hat {plan_file.name} nicht freigegeben. Ohne Rückfrage (--plan-auto) wird nicht gebaut.")
                append_log(session_dir, "Plan nicht freigegeben, Bau mit --plan-auto nicht gestartet")
                save_session_state(session_dir, state)
                return False
            say(f"✅ {plan_file.name} vom Prüfstatiker genehmigt, Freigabe ohne Rückfrage (--plan-auto).")
            append_log(session_dir, f"{plan_file.name} automatisch freigegeben (--plan-auto)")
            user_confirmed = True
        else:
            # Interaktive Freigabe & Change-Routing (Approve / Changes / Swap)
            user_confirmed, plan_file, planner, reviewer, planner_flags, reviewer_flags = handle_plan_approval_and_changes(
                plan_file,
                planner,
                reviewer,
                task,
                project_path,
                session_dir,
                state,
                agents=agents,
                auto_switch=auto_switch,
                planner_flags=planner_flags,
                reviewer_flags=reviewer_flags,
            )

        if not user_confirmed or SETTINGS.stop_requested:
            say("Implementierung nicht gestartet.")
            return False

        state["phase"] = "build"
        state["user_approved"] = True
        save_session_state(session_dir, state)
    run.plan_file, run.planner, run.reviewer, run.planner_flags, run.reviewer_flags = (
        plan_file,
        planner,
        reviewer,
        planner_flags,
        reviewer_flags,
    )
    return True


def prepare_build(run: "RunContext") -> None:
    """Vor Phase 3: tatsächlichen Bauleiter und seine Rechte festlegen, Arbeitsbereich, Prüfbefehl und Abnahme vorbereiten."""
    args, agents, project_path, session_dir, state = run.args, run.agents, run.project_path, run.session_dir, run.state
    use_worktree = run.use_worktree
    planner, reviewer, builder, strat, plan_file = run.planner, run.reviewer, run.builder, run.strategy, run.plan_file
    builder_model, b_effort, yolo_active, session_metrics = run.builder_model, run.builder_effort, run.yolo_active, run.metrics
    if not args.builder and strat != "local-free":
        # Falls kein separater Bauleiter gesetzt ist, baut der freigegebene Architekt
        builder = create_agent(
            planner.binary,
            agents,
            role="🔨 Bauleiter (Bau & Umsetzung)",
            model=builder_model,
            effort=b_effort,
            metrics_tracker=session_metrics,
        )

    # Rechte- und Modell-Flags passend zum tatsächlichen Bauleiter neu aufbauen
    builder_flags = role_flags(builder.binary, "builder", yolo_active)
    if builder_model:
        builder_flags.extend(["--model", builder_model])
    if b_effort and builder.binary in ("agy", "codex"):
        builder_flags.extend(["--effort", b_effort])

    # Falls YOLO noch nicht aktiv war, vor Phase 3 fragen
    if not yolo_active:
        try:
            say("\n⚙️  Berechtigungs-Prüfung für Phase 3 (Implementierung):")
            perm_ans = input(
                f"Soll 🔨 Bauleiter ({builder.name}) volle Schreib-/Tool-Rechte erhalten ({' / '.join(get_permission_flags(builder.binary))})? [J/n]: "
            )
            if perm_ans.strip().lower() in ["", "j", "ja", "y", "yes"]:
                builder_perm_flags = get_permission_flags(builder.binary)
                for f in builder_perm_flags:
                    if f not in builder_flags:
                        builder_flags.insert(0, f)
                state["yolo_enabled"] = True
                save_session_state(session_dir, state)
                say(f"🔓 Schreibberechtigung aktiviert ({' '.join(builder_perm_flags)}).")
            else:
                say("🔒 Eingeschränkter Modus: Bestätigung bei jedem Tool-Call erforderlich.")
        except (EOFError, KeyboardInterrupt):
            pass

    # ==========================================
    # 3. Phase: Autonomer Implementierungs-Loop
    # ==========================================
    logs_dir = project_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    session_log = logs_dir / f"loop_{session_dir.name}.log"

    work_path = acquire_worktree(project_path, session_dir, state) if use_worktree else project_path
    in_worktree = work_path != project_path

    # Abnahme (Phase 4): Der Bauleiter darf seine Arbeit nicht selbst für fertig erklären.
    proof_cmd = args.proof or state.get("proof")
    if proof_cmd:
        state["proof"] = proof_cmd
    inspect_enabled = args.inspect and state.get("inspect", True)
    if not inspect_enabled:
        state["inspect"] = False
        append_log(session_dir, "Abnahme durch anderen Anbieter ausdrücklich abgeschaltet (--no-inspect)")
    inspector = None
    inspector_flags: list[str] = []
    if inspect_enabled:
        inspector_choice = args.inspector or state.get("inspector_binary")
        candidates = []
        if inspector_choice and inspector_choice in agents:
            candidates.append(create_agent(inspector_choice, agents, role="🔎 Abnahme", metrics_tracker=session_metrics))
        candidates += [reviewer, planner]
        inspector = pick_inspector(builder, candidates, agents)
        if inspector is not None and inspector not in (reviewer, planner):
            inspector = create_agent(inspector.binary, agents, role="🔎 Abnahme", metrics_tracker=session_metrics)
        if inspector is not None:
            inspector_model = (
                args.inspector_model
                or state.get("inspector_model")
                or (inspector.model if inspector.model != DEFAULT_MODEL_LABEL else None)
            )
            inspector_effort = args.inspector_effort or state.get("inspector_effort") or inspector.effort
            inspector_flags = get_readonly_flags(inspector.binary)
            if inspector_model:
                inspector_flags.extend(["--model", inspector_model])
                state["inspector_model"] = inspector_model
            if inspector_effort and inspector.binary in ("agy", "codex"):
                inspector_flags.extend(["--effort", inspector_effort])
            state["inspector_binary"] = inspector.binary
            say(f"🔎 Abnahme des fertigen Codes durch: {describe_agent(inspector)}")
        else:
            say("⚠️ Keine unabhängige Abnahme möglich: Es ist kein zweiter Anbieter verfügbar. Der Bauleiter prüft sich selbst.")
            append_log(session_dir, "Keine unabhängige Abnahme möglich (nur ein Anbieter verfügbar)")
    save_session_state(session_dir, state)

    if not state.get("build_base"):
        state["build_base"] = git_head(work_path)
        state["build_plan_sha256"] = sha256_file(plan_file) if plan_file.exists() else None
        save_session_state(session_dir, state)
    elif plan_file.exists() and state.get("build_plan_sha256") not in (None, sha256_file(plan_file)):
        say(f"⚠️ {plan_file.name} hat sich seit Baubeginn geändert. Der Bauleiter arbeitet mit der neuen Fassung weiter.")
        append_log(session_dir, f"{plan_file.name} nach Baubeginn geändert")
        state["build_plan_sha256"] = sha256_file(plan_file)
    run.builder, run.builder_flags, run.session_log, run.work_path, run.in_worktree = (
        builder,
        builder_flags,
        session_log,
        work_path,
        in_worktree,
    )
    run.proof_cmd, run.inspector, run.inspector_flags = proof_cmd, inspector, inspector_flags


def run_build_phase(run: "RunContext") -> None:
    """Phase 3 und 4: Bau-Loop (klassisch oder in Etappen) mit Prüfbefehl, Eskalation und Abnahme."""
    args, agents, project_path, session_dir, state, task = run.args, run.agents, run.project_path, run.session_dir, run.state, run.task
    planner, builder, builder_flags, plan_file = run.planner, run.builder, run.builder_flags, run.plan_file
    inspector, inspector_flags, proof_cmd = run.inspector, run.inspector_flags, run.proof_cmd
    work_path, in_worktree, session_log, merge_worktree = run.work_path, run.in_worktree, run.session_log, run.merge_worktree
    auto_switch, yolo_active, session_metrics = run.auto_switch, run.yolo_active, run.metrics
    inspections_used = 0
    pending_feedback = state.get("pending_feedback", "")

    def finish_session():
        done_file = session_dir / ".done"
        say(f"\n🎉 Fertigmeldung ({done_file.relative_to(project_path)}) gefunden! Aufgabe erfolgreich abgeschlossen.")
        state["phase"] = "completed"
        append_metrics_to_done(session_dir, project_path, session_metrics, state)
        say(format_metrics_report(session_metrics, state))
        state["pending_feedback"] = ""
        state["metrics"] = session_metrics.to_dict()
        save_session_state(session_dir, state)
        if in_worktree:
            release_worktree(project_path, session_dir, state, task, merge=merge_worktree)

    def reject_done(feedback: str):
        nonlocal pending_feedback
        with contextlib.suppress(OSError):
            (session_dir / ".done").unlink()
        pending_feedback = feedback
        state["pending_feedback"] = feedback
        save_session_state(session_dir, state)

    def accept_done() -> str:
        """Prüft eine Fertigmeldung: Prüfbefehl, dann Abnahme. Liefert finished, retry oder stop."""
        nonlocal inspections_used
        proof_note = "Prüfbefehl: keiner vereinbart."
        if proof_cmd:
            say(f"🧪 Führe Prüfbefehl aus: {proof_cmd}", flush=True)
            ok, output = run_proof_check(build_ctx, proof_cmd)
            append_log(session_dir, f"Prüfbefehl `{proof_cmd}`: {'grün' if ok else 'rot'}")
            if not ok:
                say("❌ Prüfbefehl ist rot. Fertigmeldung zurückgewiesen.")
                reject_done(f"Der Prüfbefehl `{proof_cmd}` schlägt fehl:\n```\n{output}\n```")
                return "retry"
            proof_note = f"Prüfbefehl `{proof_cmd}` wurde vom Loop selbst ausgeführt und ist grün."
        if inspector is None:
            return "finished"
        if inspections_used >= max(1, args.max_inspections):
            say(
                f"🛑 Abnahme-Limit ({args.max_inspections}) erreicht. Offene Befunde stehen in {session_dir.relative_to(project_path)}/INSPECTION_round*.md."
            )
            append_log(session_dir, "Abnahme-Limit erreicht, Aufgabe bleibt offen")
            state["phase"] = "inspection_open"
            state["abort_reason"] = f"Abnahme-Limit ({args.max_inspections}) erreicht, Befunde offen"
            save_session_state(session_dir, state)
            return "stop"
        inspections_used += 1
        round_no = state.get("inspection_rounds", 0) + 1
        state["inspection_rounds"] = round_no
        say(f"\n🔎 Phase 4: Abnahme (Runde {round_no}) durch {describe_agent(inspector)}...", flush=True)
        changes = collect_build_changes(work_path, state.get("build_base"))
        approved_build, reason, answer = run_inspection(
            inspector,
            inspector_flags,
            builder,
            task,
            plan_file.read_text(encoding="utf-8"),
            changes,
            proof_note,
            work_path,
            session_dir,
            state,
            agents,
            auto_switch,
            round_no,
        )
        if approved_build:
            say(f"✅ Abnahme erteilt ({reason}).")
            return "finished"
        say(f"⚠️ Abnahme verweigert ({reason}). Der Bauleiter bessert nach.")
        session_metrics.count("inspection_rejected")
        reject_done(f"Die unabhängige Abnahme hat die Fertigmeldung zurückgewiesen. Befunde:\n{findings_digest(answer)}")
        if inspections_used >= max(1, args.max_inspections):
            say(
                f"🛑 Abnahme-Limit ({args.max_inspections}) erreicht. Befunde: {session_dir.relative_to(project_path)}/INSPECTION_round{round_no}.md"
            )
            append_log(session_dir, "Abnahme-Limit erreicht, Aufgabe bleibt offen")
            state["phase"] = "inspection_open"
            state["abort_reason"] = f"Abnahme-Limit ({args.max_inspections}) erreicht, Befunde offen"
            save_session_state(session_dir, state)
            return "stop"
        return "retry"

    say(f"\n🔨 Phase 3: Starte Implementierungs-Loop in {work_path}...")
    b_build_desc = (
        f"{builder.name}" + (f" (`{builder.model}`)" if builder.model else "") + (f" [{builder.effort}]" if builder.effort else "")
    )
    say(f"🔨 Ausführender Bauleiter: {b_build_desc}")
    start_iter = state.get("last_iteration", 0) + 1
    outcome = None

    # Etappen-Modus: Etappen aus dem genehmigten Plan, jede einzeln gebaut und mit --proof geprüft
    is_endpoint_builder = builder.binary in ENDPOINT_BINARIES
    plan_text_now = plan_file.read_text(encoding="utf-8", errors="ignore") if plan_file.exists() else ""
    stages: list[str] = []
    stage_mode = False
    if state.get("phase") == "stage_open":
        state["phase"] = "build"
    if stages_wanted(state.get("stage_mode") or args.etappen, builder.binary):
        if state.get("stages") and state.get("stages_plan_sha256") == state.get("build_plan_sha256"):
            stages = list(state["stages"])
        else:
            stages = parse_stages(plan_text_now)
            state["stages"] = stages
            state["stage_index"] = 0
            state["stages_plan_sha256"] = state.get("build_plan_sha256")
        stage_mode = len(stages) >= 2 or (len(stages) == 1 and (state.get("stage_mode") or args.etappen) in ("an", "on"))
        if not stage_mode:
            say(
                "ℹ️  Der Plan enthält keinen Abschnitt `## Etappen` mit mindestens zwei Etappen. Der Bauleiter baut den ganzen Plan auf einmal."
            )
            append_log(session_dir, "Etappen-Modus: keine Etappen im Plan, normaler Bau")
    stage_index = state.get("stage_index", 0) if stage_mode else 0
    stage_tries = 0
    if stage_mode:
        say(f"🧩 Etappen-Modus: {len(stages)} Etappen, weiter mit Etappe {min(stage_index + 1, len(stages))}.")
        for i, s in enumerate(stages, 1):
            say(f"   {'✓' if i <= stage_index else '•'} {i}. {s}")
        if not proof_cmd:
            say("⚠️  Ohne --proof gilt jede Etappe nach einer Bau-Runde als erledigt. Mit --proof prüft der Loop jede Etappe selbst.")
    if args.max_iterations:
        max_iters = args.max_iterations
    elif stage_mode:
        max_iters = start_iter - 1 + (len(stages) - stage_index) * 2 + 2
    else:
        max_iters = 10
    build_ctx = BuildContext(
        work_path=work_path,
        session_dir=session_dir,
        session_log=session_log,
        state=state,
        metrics=session_metrics,
        agents=agents,
        auto_switch=auto_switch,
        inspector=inspector,
        written_so_far=list(state.get("written_files", [])),
        resume_builder=not getattr(args, "builder_fresh", False),
    )
    # Bauleiter-Sitzung nur fortsetzen, wenn sie aus dieser Session stammt (nicht etwa die des Architekten)
    saved = state.get("builder_session") or {}
    builder.session_id = saved.get("id") if args.resume and saved.get("binary") == builder.binary else None
    state["iteration_limit"] = max_iters
    state["stage_mode_active"] = stage_mode

    # Eskalation: lokaler Bauleiter scheitert mehrfach in Folge -> einmalig auf eine Cloud-CLI wechseln
    escalate_choice = args.escalate if args.escalate is not None else state.get("escalate")
    escalate_after = max(1, args.escalate_after or state.get("escalate_after") or ESCALATE_AFTER_DEFAULT)
    if escalate_choice:
        state["escalate"], state["escalate_after"] = escalate_choice, escalate_after
    fail_streak = 0
    escalation_refused = False

    def note_build_round(ok: bool, reason: str) -> None:
        nonlocal fail_streak, builder, builder_flags, is_endpoint_builder, stage_tries, escalation_refused
        if ok:
            fail_streak = 0
            return
        fail_streak += 1
        if not escalate_choice or state.get("escalation") or fail_streak < escalate_after or not builder.local:
            return
        write_allowed = bool(yolo_active or state.get("yolo_enabled"))
        key, why = choose_escalation(builder, agents, escalate_choice, inspector, prefer=planner.binary, write_allowed=write_allowed)
        if not key:
            if not escalation_refused:
                escalation_refused = True
                say(f"⚠️ Eskalation nicht möglich: {why}. {builder.name} baut weiter.")
                append_log(session_dir, f"Eskalation nicht möglich: {why}")
            return
        previous = builder
        builder = create_agent(key, agents, role="🔨 Bauleiter (Bau & Umsetzung)", metrics_tracker=session_metrics)
        builder_flags = role_flags(builder.binary, "builder", write_allowed)
        is_endpoint_builder = builder.binary in ENDPOINT_BINARIES
        detail = f"{fail_streak} erfolglose Bau-Runden in Folge (zuletzt: {reason})"
        state["escalation"] = {"from": previous.name, "to": builder.name, "iteration": state.get("last_iteration"), "reason": detail}
        state["builder_binary"], state["builder_name"] = builder.binary, builder.name
        session_metrics.count("escalations")
        fail_streak = 0
        stage_tries = 0
        say(f"⬆️ Eskalation: {previous.name} → {builder.name} nach {detail}.")
        append_log(session_dir, f"Eskalation Bauleiter {previous.name} → {builder.name}: {detail}")
        log_event(session_dir, "escalation", level="warning", **state["escalation"])
        save_session_state(session_dir, state)

    for iteration in range(start_iter, max_iters + 1):
        if SETTINGS.stop_requested:
            break

        if stage_mode:
            state["last_iteration"] = iteration
            stage_text = stages[stage_index]
            stage_label = f"Etappe {stage_index + 1}/{len(stages)}"
            say(f"\n{'=' * 20} Iteration {iteration}/{max_iters} · {stage_label} {'=' * 20}\n{stage_text}\n", flush=True)
            done_list = "\n".join(f"- [x] {s}" for s in stages[:stage_index]) or "- (noch keine)"
            plan_ref = plan_file if in_worktree else plan_file.relative_to(project_path)
            file_ctx = (
                stage_file_context(work_path, stage_text + "\n" + pending_feedback, build_ctx.written_so_far) if is_endpoint_builder else ""
            )
            prompt_build = compose_build_prompt(
                task,
                plan_ref,
                proof_cmd,
                pending_feedback,
                is_endpoint_builder,
                plan_text=plan_excerpt(plan_text_now, stage_text + "\n" + pending_feedback),
                file_ctx=file_ctx,
                stage=(stage_label, stage_text, done_list),
            )
            resuming = not is_endpoint_builder and bool(builder_resume_flags(builder, build_ctx.resume_builder))
            prompt_short = (
                compose_build_prompt(
                    task, plan_ref, proof_cmd, pending_feedback, False, stage=(stage_label, stage_text, done_list), resumed=True
                )
                if resuming
                else None
            )
            ok = False
            output = ""
            try:
                res, builder, builder_flags, _ = run_build_call(
                    build_ctx,
                    builder,
                    builder_flags,
                    prompt_short or prompt_build,
                    is_endpoint_builder,
                    wait_note=stage_label + (" · Sitzung fortgesetzt" if resuming else ""),
                    label=stage_label,
                    log_header=f"\n{'=' * 20} Iteration {iteration} · {stage_label} {'=' * 20}\n",
                    full_prompt=prompt_build if resuming else None,
                )
                if proof_cmd:
                    ok, output = run_proof_check(build_ctx, proof_cmd)
                else:
                    ok = True
            except Exception as exc:
                say(f"[!] Fehler bei Iteration {iteration}: {exc}")
                output = str(exc)

            # Eine vorzeitige Fertigmeldung zählt im Etappen-Modus nicht
            if check_and_clean_done_marker(session_dir, work_path):
                with contextlib.suppress(OSError):
                    (session_dir / ".done").unlink()

            if ok:
                note_build_round(True, "")
                say(f"✅ {stage_label} erledigt" + (f" (`{proof_cmd}` grün)." if proof_cmd else "."))
                append_log(session_dir, f"{stage_label} erledigt: {stage_text}")
                stage_index += 1
                stage_tries = 0
                pending_feedback = ""
                state["pending_feedback"] = ""
                if stage_index >= len(stages):
                    outcome = accept_done()
                    if outcome == "finished":
                        state["stage_index"] = stage_index
                        finish_session()
                        break
                    if outcome == "stop":
                        state["stage_index"] = stage_index
                        save_session_state(session_dir, state)
                        break
                    stages.append("Befunde aus der Rückmeldung beheben (Prüfbefehl oder Abnahme), ohne Erledigtes zu beschädigen")
                    state["stages"] = stages
                    say(f"🔁 Nacharbeit als Etappe {len(stages)} angehängt.")
            else:
                stage_tries += 1
                pending_feedback = (
                    f"Der Prüfbefehl `{proof_cmd}` schlägt nach {stage_label} fehl:\n```\n{output}\n```"
                    if proof_cmd
                    else f"Fehler: {output}"
                )
                if build_ctx.edit_errors:
                    pending_feedback += "\n\n" + edit_errors_note(build_ctx.edit_errors)
                state["pending_feedback"] = pending_feedback
                say(f"❌ {stage_label} noch nicht fertig (Versuch {stage_tries}/{STAGE_MAX_TRIES}).")
                note_build_round(False, f"{stage_label} " + ("Prüfbefehl rot" if proof_cmd else "fehlgeschlagen"))
                if stage_tries >= STAGE_MAX_TRIES:
                    say(
                        f"🛑 {stage_label} ist nach {STAGE_MAX_TRIES} Versuchen nicht grün. Stand gesichert; weiter mit 'claudegravity -c'."
                    )
                    state["abort_reason"] = f"{stage_label} nach {STAGE_MAX_TRIES} Versuchen nicht grün"
                    append_log(session_dir, f"{stage_label} nach {STAGE_MAX_TRIES} Versuchen offen")
                    tail = "\n".join((output or "").strip().splitlines()[-30:])
                    append_log(session_dir, f"Letzte Ausgabe des Prüfbefehls:\n```\n{tail}\n```")
                    state["phase"] = "stage_open"
                    state["stage_index"] = stage_index
                    state["metrics"] = session_metrics.to_dict()
                    save_session_state(session_dir, state)
                    break
            state["stage_index"] = stage_index
            state["metrics"] = session_metrics.to_dict()
            save_session_state(session_dir, state)
            if SETTINGS.stop_requested:
                break
            if args.delay > 0:
                time.sleep(args.delay)
            continue

        if check_and_clean_done_marker(session_dir, work_path):
            outcome = accept_done()
            if outcome == "finished":
                finish_session()
                break
            if outcome == "stop":
                break

        state["last_iteration"] = iteration
        state["metrics"] = session_metrics.to_dict()
        save_session_state(session_dir, state)

        timestamp = datetime.datetime.now().isoformat()
        log_header = f"\n{'=' * 20} Iteration {iteration}/{max_iters} @ {timestamp} {'=' * 20}\n"
        say(log_header, flush=True)

        # Im Worktree liegt der (git-ignorierte) Session-Ordner außerhalb des Arbeitsverzeichnisses -> absolute Pfade
        rel_done_path = (session_dir / ".done") if in_worktree else (session_dir / ".done").relative_to(project_path)
        plan_ref = plan_file if in_worktree else plan_file.relative_to(project_path)
        is_endpoint_builder = builder.binary in ENDPOINT_BINARIES
        file_ctx = stage_file_context(work_path, pending_feedback, build_ctx.written_so_far) if is_endpoint_builder else ""
        prompt_build = compose_build_prompt(
            task,
            plan_ref,
            proof_cmd,
            pending_feedback,
            is_endpoint_builder,
            plan_text=plan_text_now,
            file_ctx=file_ctx,
            rel_done_path=rel_done_path,
        )
        resuming = not is_endpoint_builder and bool(builder_resume_flags(builder, build_ctx.resume_builder))
        prompt_short = (
            compose_build_prompt(task, plan_ref, proof_cmd, pending_feedback, False, rel_done_path=rel_done_path, resumed=True)
            if resuming
            else None
        )

        call_failed = ""
        written = []
        try:
            res, builder, builder_flags, written = run_build_call(
                build_ctx,
                builder,
                builder_flags,
                prompt_short or prompt_build,
                is_endpoint_builder,
                wait_note="führt genehmigten Plan aus" + (" · Sitzung fortgesetzt" if resuming else ""),
                label=f"Iteration {iteration}",
                log_header=log_header,
                full_prompt=prompt_build if resuming else None,
            )
            pending_feedback = edit_errors_note(build_ctx.edit_errors)
            state["pending_feedback"] = pending_feedback
        except Exception as exc:
            say(f"[!] Fehler bei Iteration {iteration}: {exc}")
            call_failed = f"Fehler: {str(exc)[:120]}"

        state["metrics"] = session_metrics.to_dict()
        save_session_state(session_dir, state)

        if check_and_clean_done_marker(session_dir, work_path):
            outcome = accept_done()
            if outcome == "finished":
                finish_session()
                break
            if outcome == "stop":
                break
            note_build_round(False, "Fertigmeldung zurückgewiesen")
        elif proof_cmd and not SETTINGS.stop_requested:
            ok, output = run_proof_check(build_ctx, proof_cmd)
            if not ok:
                pending_feedback = "\n\n".join(
                    p for p in (f"Der Prüfbefehl `{proof_cmd}` schlägt noch fehl:\n```\n{output}\n```", pending_feedback) if p
                )
                state["pending_feedback"] = pending_feedback
                save_session_state(session_dir, state)
            note_build_round(ok, call_failed or "Prüfbefehl rot")
        elif call_failed or (is_endpoint_builder and not written):
            note_build_round(False, call_failed or "keine Dateien geliefert")

        if SETTINGS.stop_requested:
            break

        if args.delay > 0:
            time.sleep(args.delay)
    run.max_iters = max_iters


def finish_run(run: "RunContext") -> None:
    """Abschluss: Arbeitsbereich freigeben oder behalten, Abbruchgrund und Kennzahlen ausgeben."""
    project_path, session_dir, state, task = run.project_path, run.session_dir, run.state, run.task
    in_worktree, work_path, merge_worktree = run.in_worktree, run.work_path, run.merge_worktree
    session_metrics, max_iters = run.metrics, run.max_iters
    if state.get("phase") == "completed" and in_worktree and not state["worktree"].get("released"):
        release_worktree(project_path, session_dir, state, task, merge=merge_worktree)
    if state.get("phase") == "stage_open":
        if in_worktree:
            say(f"🌿 Git-Workspace bleibt für die Nacharbeit erhalten: {work_path}")
        say(format_error("CG-1403"))
        say(format_metrics_report(session_metrics, state))
    elif state.get("phase") == "inspection_open":
        if in_worktree:
            say(f"🌿 Git-Workspace bleibt für die Nacharbeit erhalten: {work_path}")
        say(format_error("CG-1402"))
        say(format_metrics_report(session_metrics, state))
    elif state.get("phase") != "completed":
        if in_worktree:
            say(f"🌿 Git-Workspace bleibt für die Fortsetzung erhalten: {work_path}")
        if SETTINGS.stop_requested:
            state["abort_reason"] = "Abgebrochen (Strg+C)"
            say("\n[+] Abgebrochen. Stand gesichert, weiter mit 'claudegravity -c'.")
        else:
            state["abort_reason"] = f"Rundenlimit erreicht ({max_iters} Bau-Runden)"
            say(f"\n[+] Maximale Rundenanzahl ({max_iters}) erreicht. Stand gesichert.")
            say(format_error("CG-1401", f"{max_iters} Runden"))
        save_session_state(session_dir, state)
        # Kein .done anlegen: Das würde eine unfertige Aufgabe beim Fortsetzen als fertig melden.
        (session_dir / "AUDIT.md").write_text(format_metrics_report(session_metrics, state), encoding="utf-8")
        say(format_metrics_report(session_metrics, state))

    if state.get("phase") != "completed" and state.get("abort_reason"):
        say(f"\n⏹️ Abbruchgrund: {state['abort_reason']}")
    log_event(
        session_dir,
        "session_end",
        phase=state.get("phase"),
        success=state.get("phase") == "completed",
        abort_reason=state.get("abort_reason"),
        tokens_total=session_metrics.total_tokens,
        cost_usd_total=round(session_metrics.cost_usd, 4),
        build_rounds=state.get("last_iteration"),
    )
    say("\n[*] ClaudeGravity Loop beendet.")
