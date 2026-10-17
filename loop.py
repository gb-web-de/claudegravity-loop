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


class AgentCLI:
    def __init__(self, name: str, binary: str, run_fn):
        self.name = name
        self.binary = binary
        self.run_fn = run_fn

    def run(self, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> str:
        return self.run_fn(self.binary, prompt, cwd, extra_flags)


def _exec_cli(binary: str, args: list[str], cwd: Path | None = None) -> str:
    cmd = [binary] + args
    res = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if res.returncode != 0:
        err_msg = res.stderr.strip() or res.stdout.strip() or f"Fehlercode {res.returncode}"
        raise RuntimeError(f"{binary} Fehler (Code {res.returncode}): {err_msg}")
    return res.stdout.strip()


def _exec_claude(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> str:
    args = ["-p", prompt]
    if extra_flags:
        args.extend(extra_flags)
    return _exec_cli(binary, args, cwd)


def _exec_agy(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> str:
    args = ["-p", prompt]
    if extra_flags:
        args.extend(extra_flags)
    return _exec_cli(binary, args, cwd)


def _exec_gemini(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> str:
    args = ["-p", prompt]
    if extra_flags:
        args.extend(extra_flags)
    return _exec_cli(binary, args, cwd)


def _exec_codex(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> str:
    sandbox = "workspace-write" if extra_flags and "--dangerously-skip-permissions" in extra_flags else "read-only"
    args = ["exec", "-s", sandbox, prompt]
    return _exec_cli(binary, args, cwd)


def detect_installed_agents() -> dict[str, AgentCLI]:
    agents = {}
    if shutil.which("claude"):
        agents["claude"] = AgentCLI("Claude Code", "claude", _exec_claude)
    if shutil.which("agy"):
        agents["agy"] = AgentCLI("Antigravity (agy)", "agy", _exec_agy)
    elif shutil.which("gemini"):
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
    planner_flags: list[str] | None = None,
    reviewer_flags: list[str] | None = None,
    max_rounds: int = 2
) -> tuple[bool, Path]:
    loop_dir = project_path / ".dual-loop"
    active_plan_file = loop_dir / "PLAN.md"
    active_review_file = loop_dir / "REVIEW.md"
    log_file = loop_dir / "PLAN-REVIEW-LOG.md"

    plan_v1_file = session_dir / "PLAN_v1.md"

    # Wenn Plan v1 noch nicht existiert (oder von vorn begonnen wird):
    if not plan_v1_file.exists():
        print(f"\n📁 Session-Ordner: {session_dir.relative_to(project_path)}")
        print(f"🚀 Phase 1: Plan-Entwurf durch {planner.name} (im Kontext von {project_path.name})...")
        print(f"⏳ Warte auf {planner.name}...", flush=True)

        prompt_plan = (
            f"Du bist der leitende Software-Architekt für das Projekt in '{project_path}'.\n"
            f"Erstelle einen präzisen, token-effizienten Implementierungsplan für folgende Aufgabe:\n"
            f"Aufgabe: {task}\n\n"
            f"{project_ctx}\n\n"
            f"Enthalte: Betroffene Dateien, Architektur, Randfälle und Testkriterien."
            f"{PLANNING_DIRECTIVE}"
        )
        plan = planner.run(prompt_plan, cwd=project_path, extra_flags=planner_flags)

        # Sicherheitsprüfung: Hat Modell versehentlich eine Permission-Meldung zurückgegeben?
        if is_permission_error_response(plan):
            print("⚠️ Modell versuchte eine Datei anzulegen. Erzwinge reine Textausgabe...")
            retry_prompt = prompt_plan + "\nACHTUNG: Lege KEINE Datei an! Gib den Plan ausschließlich als Text aus!"
            plan = planner.run(retry_prompt, cwd=project_path, extra_flags=planner_flags)

        plan_v1_file.write_text(plan, encoding="utf-8")
        active_plan_file.write_text(plan, encoding="utf-8")
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
        active_plan_file.write_text(plan, encoding="utf-8")
        print(f"🔄 Wiederaufnahme: Geladen {active_plan_file_source.name}")

    start_round = state.get("rounds_completed", 0) + 1
    approved = state.get("plan_approved", False)

    if approved:
        print("🎉 Plan wurde in einer früheren Sitzung bereits genehmigt!")
        return True, active_plan_file

    log_entry = [
        f"\n## [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Session: {session_dir.name}",
        f"- **Aufgabe:** {task}",
        f"- **Planer:** {planner.name} | **Prüfer:** {reviewer.name}",
        f"- **Session-Pfad:** `{session_dir.relative_to(project_path)}`"
    ]

    for r in range(start_round, max_rounds + 1):
        if STOP_REQUESTED:
            state["rounds_completed"] = r - 1
            save_session_state(session_dir, state)
            return False, active_plan_file

        print(f"\n🔍 Phase 2: Unabhängiges Adversarial Review (Runde {r}/{max_rounds}) durch {reviewer.name}...")
        print(f"⏳ Warte auf Review von {reviewer.name}...", flush=True)

        prompt_rev = (
            f"Du bist ein unbarmherziger Sicherheits- und Code-Reviewer für das Projekt in '{project_path}'.\n"
            f"Grille den folgenden Plan auf Schwachstellen, Race Conditions, fehlende Tests und logische Lücken:\n\n"
            f"Aufgabe: {task}\n\n"
            f"Plan:\n{plan}\n\n"
            f"Antworte strukturiert mit:\n"
            f"VERDICT: APPROVED (oder VERDICT: REVISE)\n"
            f"KRITIK:\n- [Punkte...]\n"
            f"EMPFEHLUNGEN:\n- [Punkte...]"
        )
        review = reviewer.run(prompt_rev, cwd=project_path, extra_flags=reviewer_flags)

        review_r_file = session_dir / f"REVIEW_round{r}.md"
        review_r_file.write_text(review, encoding="utf-8")
        active_review_file.write_text(review, encoding="utf-8")
        print(f"📋 Review gespeichert in {review_r_file.relative_to(project_path)}")

        is_approved = "VERDICT: APPROVED" in review
        verdict_str = "APPROVED" if is_approved else "REVISE"
        log_entry.append(f"  - Review Runde {r}: **VERDICT: {verdict_str}**")

        state["rounds_completed"] = r
        if is_approved:
            print(f"🎉 Plan von {reviewer.name} genehmigt!")
            approved = True
            state["plan_approved"] = True
            save_session_state(session_dir, state)
            break
        elif r < max_rounds:
            print(f"⚠️ Kritikpunkte von {reviewer.name}. {planner.name} bessert den Plan nach...")
            print(f"⏳ Warte auf Überarbeitung durch {planner.name}...", flush=True)
            prompt_fix = (
                f"Der Reviewer ({reviewer.name}) hat folgende Kritikpunkte am Plan geäußert:\n\n"
                f"{review}\n\n"
                f"Bisheriger Plan:\n{plan}\n\n"
                f"Bitte überarbeite den Plan und behebe alle genannten Mängel vollständig."
                f"{PLANNING_DIRECTIVE}"
            )
            plan = planner.run(prompt_fix, cwd=project_path, extra_flags=planner_flags)

            # Prüfen ob Modell trotz Directive einen Permission-Fehler zurückgab
            if is_permission_error_response(plan):
                print("⚠️ Modell versuchte erneut eine Datei anzulegen. Erzwinge reinen Text...")
                retry_fix = prompt_fix + "\nACHTUNG: Lege KEINE Datei wie docs/... an! Gib den Plan als Text auf stdout aus!"
                plan = planner.run(retry_fix, cwd=project_path, extra_flags=planner_flags)

            plan_next_file = session_dir / f"PLAN_v{r+1}.md"
            plan_next_file.write_text(plan, encoding="utf-8")
            active_plan_file.write_text(plan, encoding="utf-8")
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

    return approved, active_plan_file


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
    planner_flags: list[str] | None = None
) -> bool:
    while not STOP_REQUESTED:
        print("\n" + "=" * 60)
        print("📋 PLAN-STATUS: Fertiggestellt & Geprüft")
        print(f"📄 Aktuelle Plan-Datei: {plan_file.relative_to(project_path)}")
        print("=" * 60)
        print("Möchtest du den Plan freigeben oder Änderungen vornehmen?")
        print("  [1] Approve  -> Plan genehmigen & weiter zur Implementierung")
        print("  [2] Changes  -> Änderungen/Feedback anbringen")
        print("  [3] Anzeigen -> Plan direkt hier im Terminal lesen")
        print("  [4] Beenden  -> Abbrechen (Fortsetzen später mit --resume möglich)")
        print("-" * 60)

        try:
            choice = input("Auswahl [1/2/3/4] (Standard: 1): ").strip()
        except (EOFError, KeyboardInterrupt):
            return False

        if choice in ["", "1", "approve", "a"]:
            state["user_approved"] = True
            save_session_state(session_dir, state)
            return True

        elif choice in ["3", "view", "v"]:
            print("\n" + "-" * 50)
            print(plan_file.read_text(encoding="utf-8"))
            print("-" * 50)
            continue

        elif choice in ["4", "exit", "q"]:
            print("Abgebrochen. Du kannst diesen Stand jederzeit mit 'claudegravity --resume' fortsetzen.")
            return False

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
            print(f"  [4] Interaktive {planner.name} CLI-Session starten")
            print(f"  [5] Interaktive {reviewer.name} CLI-Session starten")
            print("  [6] Zurück zum Hauptmenü")
            print("-" * 60)

            try:
                c_choice = input("Auswahl [1-6]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return False

            if c_choice == "1":
                editor = os.environ.get("EDITOR", "xdg-open")
                print(f"🚀 Öffne {plan_file.name} mit {editor}...")
                subprocess.run([editor, str(plan_file)])
                input("\nDrücke [Enter], sobald du mit dem Bearbeiten im Editor fertig bist...")
                v_num = len(list(session_dir.glob("PLAN_v*.md"))) + 1
                new_v_file = session_dir / f"PLAN_v{v_num}_manual.md"
                new_v_file.write_text(plan_file.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"💾 Manuell bearbeiteter Plan gesichert als {new_v_file.name}")

            elif c_choice == "2":
                print("\n📋 Plan-Pfad für Claude UI:")
                print(f"   Pfad: {plan_file.resolve()}")
                print("   Kopiere den Inhalt der Datei in deine Claude UI / Web-Chat.")
                input("\nDrücke [Enter], wenn du die Änderungen vorgenommen und in PLAN.md gespeichert hast...")

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
                    new_plan = planner.run(prompt_user_fix, cwd=project_path, extra_flags=planner_flags)
                    v_num = len(list(session_dir.glob("PLAN_v*.md"))) + 1
                    new_v_file = session_dir / f"PLAN_v{v_num}.md"
                    new_v_file.write_text(new_plan, encoding="utf-8")
                    plan_file.write_text(new_plan, encoding="utf-8")
                    print(f"✅ Plan aktualisiert und als {new_v_file.name} gesichert!")

            elif c_choice == "4":
                print(f"🚀 Starte interaktive {planner.name}-Sitzung in {project_path}...")
                subprocess.run([planner.binary], cwd=str(project_path))
                print(f"Zurück im Loop.")

            elif c_choice == "5":
                print(f"🚀 Starte interaktive {reviewer.name}-Sitzung in {project_path}...")
                subprocess.run([reviewer.binary], cwd=str(project_path))
                print(f"Zurück im Loop.")

            elif c_choice == "6":
                continue

    return False


def main():
    parser = argparse.ArgumentParser(description="ClaudeGravity Loop - Cross-Model Adversarial & Autonomous Execution Loop")
    parser.add_argument("task", nargs="?", default="", help="Die Aufgabe für den Loop")
    parser.add_argument("-p", "--project", default=".", help="Pfad zum Ziel-Projekt (absolut oder relativ, Standard: .)")
    parser.add_argument("-m", "--max-iterations", type=int, default=10, help="Maximale autonome Iterationen (Standard: 10)")
    parser.add_argument("-c", "--resume", "--continue", dest="resume", action="store_true", help="Unterbrochene Sitzung fortsetzen")
    parser.add_argument("--planner", default=None, help="Explizite CLI für Planung/Bau (z.B. claude)")
    parser.add_argument("--reviewer", default=None, help="Explizite CLI für Review (z.B. agy oder gemini)")
    parser.add_argument("--yolo", "--auto-approve", action="store_true", help="Automatisch volle Schreib- und Toolrechte erteilen (keine Nachfrage)")
    parser.add_argument("--check", action="store_true", help="Installierte AI-CLIs prüfen")
    parser.add_argument("-d", "--delay", type=int, default=3, help="Pause zwischen Runden in Sekunden")

    args = parser.parse_args()

    agents = detect_installed_agents()

    if args.check:
        print("🔍 Erkannte AI-CLIs auf deinem System:")
        for key, agent in agents.items():
            print(f"  [x] {agent.name} (`{agent.binary}` im PATH)")
        if len(agents) >= 2:
            print("\n🚀 Mindestens 2 Modelle vorhanden. Dual-Loop ist voll einsatzbereit!")
        else:
            print("\n⚠️ Hinweis: Für echte Cross-Model Reviews werden mindestens 2 CLIs empfohlen (z.B. claude und agy).")
        return

    project_path = Path(args.project).resolve()
    if not project_path.exists():
        sys.exit(f"Fehler: Projektordner '{project_path}' existiert nicht.")

    loop_dir = project_path / ".dual-loop"
    loop_dir.mkdir(exist_ok=True)

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
    if args.planner and args.planner in agents:
        planner = agents[args.planner]
    elif "claude" in agents:
        planner = agents["claude"]
    else:
        planner = list(agents.values())[0]

    remaining = [a for k, a in agents.items() if a != planner]
    if args.reviewer and args.reviewer in agents:
        reviewer = agents[args.reviewer]
    elif remaining:
        reviewer = remaining[0]
    else:
        reviewer = planner

    # ==========================================
    # Rechte-Steuerung (YOLO gilt für alle Phasen!)
    # ==========================================
    planner_perm_flags = []
    reviewer_perm_flags = []
    yolo_active = args.yolo or state.get("yolo_enabled", False)

    if yolo_active:
        planner_perm_flags = get_permission_flags(planner.binary)
        reviewer_perm_flags = get_permission_flags(reviewer.binary)
        state["yolo_enabled"] = True
        save_session_state(session_dir, state)
        print(f"🔓 YOLO-Modus aktiv: Volle Tool- & Schreibrechte erteilt ({' '.join(planner_perm_flags)}).")

    print(f"\n=======================================================")
    print(f"[*] ClaudeGravity Loop gestartet")
    print(f"[*] Ziel-Projekt : {project_path}")
    print(f"[*] Planer/Bau   : {planner.name}")
    print(f"[*] Prüfer/Review: {reviewer.name}")
    print(f"[*] Session-ID   : {session_dir.name}")
    print(f"=======================================================\n")

    project_ctx = load_project_context(project_path)

    # ==========================================
    # 1. & 2. Phase: Adversarial Plan Review
    # ==========================================
    plan_file = loop_dir / "PLAN.md"
    if state.get("phase") in ["plan", "review"] or not state.get("user_approved", False):
        state["phase"] = "review"
        save_session_state(session_dir, state)

        # Plan erstellen / Review durchführen mit planner_perm_flags
        review_ok, plan_file = run_adversarial_plan(
            planner=planner,
            reviewer=reviewer,
            task=task,
            project_path=project_path,
            project_ctx=project_ctx,
            session_dir=session_dir,
            state=state,
            planner_flags=planner_perm_flags,
            reviewer_flags=reviewer_perm_flags,
            max_rounds=2
        )

        if STOP_REQUESTED:
            return

        # Interaktive Freigabe & Change-Routing (Approve / Changes)
        user_confirmed = handle_plan_approval_and_changes(
            plan_file, planner, reviewer, task, project_path, session_dir, state, planner_flags=planner_perm_flags
        )

        if not user_confirmed or STOP_REQUESTED:
            print("Implementierung nicht gestartet.")
            return

        state["phase"] = "build"
        state["user_approved"] = True
        save_session_state(session_dir, state)

    # Falls YOLO noch nicht aktiv war, vor Phase 3 fragen
    if not yolo_active:
        try:
            print("\n⚙️  Berechtigungs-Prüfung für Phase 3 (Implementierung):")
            perm_ans = input(f"Soll {planner.name} volle Schreib-/Tool-Rechte erhalten ({' / '.join(get_permission_flags(planner.binary))})? [J/n]: ")
            if perm_ans.strip().lower() in ["", "j", "ja", "y", "yes"]:
                planner_perm_flags = get_permission_flags(planner.binary)
                state["yolo_enabled"] = True
                save_session_state(session_dir, state)
                print(f"🔓 Schreibberechtigung aktiviert ({' '.join(planner_perm_flags)}).")
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
    start_iter = state.get("last_iteration", 0) + 1
    max_iters = args.max_iterations

    for iteration in range(start_iter, max_iters + 1):
        if STOP_REQUESTED:
            break

        if check_and_clean_done_marker(session_dir, project_path):
            done_file = session_dir / ".done"
            print(f"\n🎉 Fertigmeldung ({done_file.relative_to(project_path)}) gefunden! Aufgabe erfolgreich abgeschlossen.")
            state["phase"] = "completed"
            save_session_state(session_dir, state)
            break

        state["last_iteration"] = iteration
        save_session_state(session_dir, state)

        timestamp = datetime.datetime.now().isoformat()
        log_header = f"\n{'='*20} Iteration {iteration}/{max_iters} @ {timestamp} {'='*20}\n"
        print(log_header, flush=True)

        rel_done_path = (session_dir / ".done").relative_to(project_path)
        prompt_build = (
            f"Führe den genehmigten Plan ({plan_file.relative_to(project_path)}) für folgende Aufgabe aus:\n{task}\n\n"
            f"Erstelle oder modifiziere die benötigten Dateien im Projektverzeichnis. Führe Tests durch.\n\n"
            f"WICHTIG ZUM ABSCHLUSS: Wenn alle Anforderungen vollständig erfüllt und getestet sind, "
            f"erstelle die Fertigmeldungs-Datei genau im Session-Ordner unter: \x27{rel_done_path}\x27 (NICHT im Projekt-Hauptverzeichnis)."
        )

        try:
            cmd = [planner.binary, "-p", prompt_build] + planner_perm_flags
            process = subprocess.Popen(
                cmd,
                cwd=str(project_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            with open(session_log, "a", encoding="utf-8") as f_log:
                f_log.write(log_header)
                if process.stdout:
                    for line in process.stdout:
                        sys.stdout.write(line)
                        sys.stdout.flush()
                        f_log.write(line)
                        f_log.flush()

            process.wait()
        except Exception as exc:
            print(f"[!] Fehler bei Iteration {iteration}: {exc}")

        if STOP_REQUESTED:
            break

        if args.delay > 0:
            time.sleep(args.delay)

    if iteration >= max_iters and not check_and_clean_done_marker(session_dir, project_path):
        print(f"\n[+] Maximale Rundenanzahl ({max_iters}) erreicht. Stand gesichert.")
        print(f"💡 Du kannst jederzeit mit 'claudegravity -c' weitere Runden anhängen.")

    print("\n[*] ClaudeGravity Loop beendet.")


if __name__ == "__main__":
    main()
