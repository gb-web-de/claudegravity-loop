#!/usr/bin/env python3
"""
ClaudeGravity Loop - Cross-Model Adversarial & Autonomous Execution Loop
Auto-detects available CLIs (Claude Code, Google Antigravity agy, Gemini CLI, Codex).
Supports any local or external project path (-p /path/to/project or -p ../project).
Provides versioned plan archives, review logs, and full write-tool permission control.
"""

import argparse
import datetime
import os
import re
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

STOP_REQUESTED = False


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


def get_permission_flags(binary: str) -> list[str]:
    """Gibt die passenden Flags für Schreib-/Tool-Rechte zurück."""
    if binary in ["claude", "agy"]:
        return ["--dangerously-skip-permissions"]
    elif binary == "gemini":
        return ["-y"]
    elif binary == "codex":
        return ["-s", "workspace-write"]
    return []


def run_adversarial_plan(planner: AgentCLI, reviewer: AgentCLI, task: str, project_path: Path, project_ctx: str, max_rounds: int = 2) -> tuple[bool, Path]:
    loop_dir = project_path / ".dual-loop"
    active_plan_file = loop_dir / "PLAN.md"
    active_review_file = loop_dir / "REVIEW.md"
    log_file = loop_dir / "PLAN-REVIEW-LOG.md"

    # Neues Session-Verzeichnis für jede Ausführung erstellen (kein Überschreiben alter Pläne!)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = sanitize_filename(task)
    session_dir = loop_dir / "sessions" / f"{timestamp}_{slug}"
    session_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📁 Session-Ordner angelegt: {session_dir.relative_to(project_path)}")
    print(f"🚀 Phase 1: Plan-Entwurf durch {planner.name} (im Kontext von {project_path.name})...")
    print(f"⏳ Warte auf {planner.name}...", flush=True)

    prompt_plan = (
        f"Du bist der leitende Software-Architekt für das Projekt in '{project_path}'.\n"
        f"Erstelle einen präzisen, token-effizienten Implementierungsplan für folgende Aufgabe:\n"
        f"Aufgabe: {task}\n\n"
        f"{project_ctx}\n\n"
        f"Enthalte: Betroffene Dateien, Architektur, Randfälle und Testkriterien. Antworte nur mit dem Markdown-Plan."
    )
    plan = planner.run(prompt_plan, cwd=project_path)

    # Plan v1 speichern (im Session-Archiv UND als aktive PLAN.md)
    plan_v1_file = session_dir / "PLAN_v1.md"
    plan_v1_file.write_text(plan, encoding="utf-8")
    active_plan_file.write_text(plan, encoding="utf-8")
    print(f"📄 Plan v1 gespeichert in {plan_v1_file.relative_to(project_path)} & {active_plan_file.relative_to(project_path)}")

    # Audit Log Header
    log_entry = [
        f"\n## [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Session: {slug}",
        f"- **Aufgabe:** {task}",
        f"- **Planer:** {planner.name} | **Prüfer:** {reviewer.name}",
        f"- **Session-Pfad:** `{session_dir.relative_to(project_path)}`",
        f"- **Runde 1:** Plan v1 erstellt"
    ]

    approved = False
    for r in range(1, max_rounds + 1):
        if STOP_REQUESTED:
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
        review = reviewer.run(prompt_rev, cwd=project_path)

        # Review archivieren
        review_r_file = session_dir / f"REVIEW_round{r}.md"
        review_r_file.write_text(review, encoding="utf-8")
        active_review_file.write_text(review, encoding="utf-8")
        print(f"📋 Review gespeichert in {review_r_file.relative_to(project_path)}")

        is_approved = "VERDICT: APPROVED" in review
        verdict_str = "APPROVED" if is_approved else "REVISE"
        log_entry.append(f"  - Review Runde {r}: **VERDICT: {verdict_str}** ([Details]({review_r_file.name}))")

        if is_approved:
            print(f"🎉 Plan von {reviewer.name} genehmigt!")
            approved = True
            break
        elif r < max_rounds:
            print(f"⚠️ Kritikpunkte von {reviewer.name}. {planner.name} bessert den Plan nach...")
            print(f"⏳ Warte auf Überarbeitung durch {planner.name}...", flush=True)
            prompt_fix = (
                f"Der Reviewer ({reviewer.name}) hat folgende Kritikpunkte am Plan geäußert:\n\n"
                f"{review}\n\n"
                f"Bitte überarbeite den Plan ({plan}) und behebe alle genannten Mängel."
            )
            plan = planner.run(prompt_fix, cwd=project_path)

            # Neue Version speichern
            plan_next_file = session_dir / f"PLAN_v{r+1}.md"
            plan_next_file.write_text(plan, encoding="utf-8")
            active_plan_file.write_text(plan, encoding="utf-8")
            print(f"📄 Plan v{r+1} gespeichert in {plan_next_file.relative_to(project_path)}")
            log_entry.append(f"- **Runde {r+1}:** Plan v{r+1} erstellt ([Details]({plan_next_file.name}))")
        else:
            print("🛑 Maximale Review-Runden erreicht. Manuelle Prüfung empfohlen.")
            approved = False

    # Audit Log fortschreiben
    log_entry.append(f"- **Ergebnis:** {'Genehmigt' if approved else 'Nicht genehmigt (Limit erreicht)'}\n")
    with open(log_file, "a", encoding="utf-8") as f_log:
        f_log.write("\n".join(log_entry) + "\n")
    print(f"📜 Audit-Log aktualisiert in {log_file.relative_to(project_path)}")

    return approved, active_plan_file


def main():
    parser = argparse.ArgumentParser(description="ClaudeGravity Loop - Cross-Model Adversarial & Autonomous Execution Loop")
    parser.add_argument("task", nargs="?", help="Die Aufgabe für den Loop")
    parser.add_argument("-p", "--project", default=".", help="Pfad zum Ziel-Projekt (absolut oder relativ, Standard: .)")
    parser.add_argument("-m", "--max-iterations", type=int, default=10, help="Maximale autonome Iterationen (Standard: 10)")
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

    if not args.task:
        parser.print_help()
        sys.exit(1)

    project_path = Path(args.project).resolve()
    if not project_path.exists():
        sys.exit(f"Fehler: Projektordner '{project_path}' existiert nicht.")

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

    print(f"\n=======================================================")
    print(f"[*] ClaudeGravity Loop gestartet")
    print(f"[*] Ziel-Projekt : {project_path}")
    print(f"[*] Planer/Bau   : {planner.name}")
    print(f"[*] Prüfer/Review: {reviewer.name}")
    print(f"=======================================================\n")

    project_ctx = load_project_context(project_path)

    # 1. & 2. Phase: Adversarial Plan Review mit Versionierung
    approved, plan_file = run_adversarial_plan(planner, reviewer, args.task, project_path, project_ctx, max_rounds=2)
    if not approved and not STOP_REQUESTED:
        try:
            choice = input("\nPlan nicht vollständig genehmigt. Trotzdem mit Implementierung fortfahren? (j/N): ")
        except (EOFError, KeyboardInterrupt):
            choice = "n"
        if choice.lower() not in ["j", "ja", "y", "yes"]:
            print("Abbruch durch Nutzer.")
            return

    # Rechte-Steuerung für Phase 3 (Build)
    perm_flags = []
    if args.yolo:
        give_permissions = True
    else:
        try:
            print("\n⚙️  Berechtigungs-Prüfung für Phase 3 (Implementierung):")
            perm_ans = input(f"Soll {planner.name} volle Schreib-/Tool-Rechte erhalten ({' / '.join(get_permission_flags(planner.binary))})? [J/n]: ")
            give_permissions = perm_ans.strip().lower() in ["", "j", "ja", "y", "yes"]
        except (EOFError, KeyboardInterrupt):
            give_permissions = False

    if give_permissions:
        perm_flags = get_permission_flags(planner.binary)
        print(f"🔓 Schreibberechtigung aktiviert ({' '.join(perm_flags)}).")
    else:
        print("🔒 Eingeschränkter Modus: Änderungen müssen einzeln bestätigt werden.")

    # 3. Phase: Autonomer Implementierungs-Loop im Projektverzeichnis
    logs_dir = project_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    session_log = logs_dir / f"loop_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    print(f"\n🔨 Phase 3: Starte Implementierungs-Loop in {project_path}...")
    iteration = 0
    while not STOP_REQUESTED:
        iteration += 1
        if args.max_iterations > 0 and iteration > args.max_iterations:
            print(f"[+] Maximale Rundenanzahl ({args.max_iterations}) erreicht. Fertig.")
            break

        done_flag = project_path / ".done"
        if done_flag.exists():
            print(f"\n🎉 Fertigmeldung ({done_flag}) gefunden! Aufgabe erfolgreich abgeschlossen.")
            break

        timestamp = datetime.datetime.now().isoformat()
        log_header = f"\n{'='*20} Iteration {iteration} @ {timestamp} {'='*20}\n"
        print(log_header, flush=True)

        prompt_build = (
            f"Führe den genehmigten Plan ({plan_file}) für folgende Aufgabe aus:\n{args.task}\n\n"
            f"Erstelle oder modifiziere die benötigten Dateien im Projektverzeichnis. Führe Tests durch. "
            f"Wenn alle Anforderungen erfüllt und getestet sind, erstelle die Datei .done im Projektverzeichnis."
        )

        try:
            cmd = [planner.binary, "-p", prompt_build] + perm_flags
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

    print("\n[*] ClaudeGravity Loop beendet.")


if __name__ == "__main__":
    main()
