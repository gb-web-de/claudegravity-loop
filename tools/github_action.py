#!/usr/bin/env python3
"""GitHub Action: startet den Loop für ein Issue und öffnet bei Erfolg einen Pull Request.

Liest die Eingaben der Action aus der Umgebung (CG_ISSUE, CG_ARGS, CG_PROOF, CG_DRAFT, CG_LANG, CG_COMMENT, CG_WORKDIR),
startet `python -m claudegravity --from-issue … --open-pr --plan-auto --yolo` und schreibt danach `pull-request`,
`success` und `session` nach $GITHUB_OUTPUT sowie eine Zusammenfassung nach $GITHUB_STEP_SUMMARY. Mit CG_COMMENT=true
bekommt das Issue einen Kommentar mit dem Ergebnis (über gh). Keine Shell: weitere Optionen werden mit shlex zerlegt.

Lokal ausprobieren (ohne Lauf, zeigt nur den Befehl):
    CG_ISSUE=12 CG_ARGS="--dry-run" python3 tools/github_action.py
"""

import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from claudegravity.github import parse_issue_ref  # noqa: E402
from claudegravity.session import find_latest_session, load_session_state  # noqa: E402

TRUE = {"1", "true", "yes", "ja", "on"}
TEXTS = {
    "de": {
        "title": "### ClaudeGravity Loop",
        "issue": "Issue",
        "result": "Ergebnis",
        "ok": "✅ erfolgreich",
        "failed": "❌ nicht abgeschlossen",
        "reason": "Grund",
        "pr": "Pull Request",
        "session": "Sitzung",
        "report": "Bericht",
        "no_session": "Der Loop hat keine Sitzung angelegt (Ausgabe des Schritts prüfen).",
        "comment_ok": "🤖 ClaudeGravity hat einen Pull Request geöffnet: {}",
        "comment_failed": "🤖 ClaudeGravity hat das Issue nicht abgeschlossen: {}. Details im Lauf: {}",
        "no_issue": "❌ Kein Issue: Eingabe `issue` setzen oder die Action über ein Issue-Ereignis starten.",
    },
    "en": {
        "title": "### ClaudeGravity Loop",
        "issue": "Issue",
        "result": "Result",
        "ok": "✅ succeeded",
        "failed": "❌ not completed",
        "reason": "Reason",
        "pr": "Pull request",
        "session": "Session",
        "report": "Report",
        "no_session": "The loop did not create a session (check the step output).",
        "comment_ok": "🤖 ClaudeGravity opened a pull request: {}",
        "comment_failed": "🤖 ClaudeGravity did not complete the issue: {}. Details in the run: {}",
        "no_issue": "❌ No issue: set the `issue` input or start the action from an issue event.",
    },
}


def texts(env: dict) -> dict:
    """Texte in der Sprache der Action (CG_LANG en, sonst Deutsch)."""
    return TEXTS["en" if env.get("CG_LANG", "").strip().lower() == "en" else "de"]


def action_argv(env: dict) -> list[str]:
    """Aufruf des Loops aus den Eingaben der Action. SystemExit ohne Issue."""
    issue = env.get("CG_ISSUE", "").strip()
    if not issue:
        raise SystemExit(texts(env)["no_issue"])
    argv = [sys.executable, "-m", "claudegravity", "--from-issue", issue, "--plan-auto", "--yolo", "--no-guide"]
    argv.append("--pr-draft" if env.get("CG_DRAFT", "").strip().lower() in TRUE else "--open-pr")
    if env.get("CG_PROOF", "").strip():
        argv += ["--proof", env["CG_PROOF"].strip()]
    if env.get("CG_LANG", "").strip():
        argv += ["--lang", env["CG_LANG"].strip()]
    return argv + shlex.split(env.get("CG_ARGS", ""))


def run_result(project: Path) -> dict:
    """Ergebnis der letzten Sitzung im Projekt: Erfolg, Grund, Pull Request und Bericht (.done oder AUDIT.md)."""
    session = find_latest_session(project / ".dual-loop")
    if session is None:
        return {"session": "", "success": False, "abort_reason": None, "pull_request": "", "issue": None, "report": ""}
    state = load_session_state(session)
    report = ""
    for name in (".done", "AUDIT.md"):
        path = session / name
        if path.exists():
            report = path.read_text(encoding="utf-8", errors="replace")
            break
    return {
        "session": session.name,
        "success": state.get("phase") == "completed",
        "abort_reason": state.get("abort_reason"),
        "pull_request": (state.get("pull_request") or {}).get("url", ""),
        "issue": state.get("issue"),
        "report": report,
    }


def summary_markdown(result: dict, env: dict) -> str:
    """Zusammenfassung für $GITHUB_STEP_SUMMARY."""
    t = texts(env)
    if not result["session"]:
        return f"{t['title']}\n\n{t['no_session']}\n"
    lines = [t["title"], ""]
    issue = result.get("issue") or {}
    if issue:
        lines.append(f"* **{t['issue']}:** [#{issue.get('number')} {issue.get('title', '')}]({issue.get('url', '')})")
    lines.append(f"* **{t['result']}:** {t['ok'] if result['success'] else t['failed']}")
    if not result["success"] and result.get("abort_reason"):
        lines.append(f"* **{t['reason']}:** {result['abort_reason']}")
    if result.get("pull_request"):
        lines.append(f"* **{t['pr']}:** {result['pull_request']}")
    lines.append(f"* **{t['session']}:** `{result['session']}`")
    if result.get("report"):
        lines += ["", f"<details><summary>{t['report']}</summary>", "", result["report"].strip(), "", "</details>"]
    return "\n".join(lines) + "\n"


def comment_text(result: dict, env: dict) -> str:
    """Kommentar für das Issue: Link zum Pull Request oder Grund und Link zum Lauf."""
    t = texts(env)
    if result.get("pull_request"):
        return t["comment_ok"].format(result["pull_request"])
    run_url = ""
    if env.get("GITHUB_SERVER_URL") and env.get("GITHUB_REPOSITORY") and env.get("GITHUB_RUN_ID"):
        run_url = f"{env['GITHUB_SERVER_URL']}/{env['GITHUB_REPOSITORY']}/actions/runs/{env['GITHUB_RUN_ID']}"
    reason = result.get("abort_reason") or (t["failed"] if result["session"] else t["no_session"])
    return t["comment_failed"].format(reason, run_url or "–")


def comment_command(issue_ref: str, body: str) -> list[str]:
    """`gh issue comment` für Nummer, owner/repo#12 oder URL (gh kennt nur Nummer und URL)."""
    try:
        repo, number = parse_issue_ref(issue_ref)
    except ValueError:
        return ["gh", "issue", "comment", issue_ref, "--body", body]
    return ["gh", "issue", "comment", str(number), "--body", body] + (["--repo", repo] if repo else [])


def write_outputs(result: dict, env: dict) -> None:
    """Ausgaben der Action und Zusammenfassung schreiben (nur in GitHub Actions gesetzt)."""
    if env.get("GITHUB_OUTPUT"):
        with open(env["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"pull-request={result.get('pull_request', '')}\n")
            fh.write(f"success={'true' if result['success'] else 'false'}\n")
            fh.write(f"session={result.get('session', '')}\n")
    if env.get("GITHUB_STEP_SUMMARY"):
        with open(env["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(summary_markdown(result, env))


def main() -> int:
    """Loop starten, Ergebnis ausgeben, Issue kommentieren. Exit-Code 0 nur bei Erfolg."""
    env = dict(os.environ)
    project = Path(env.get("CG_WORKDIR") or ".").resolve()
    argv = action_argv(env)
    print("▶ " + shlex.join(argv), flush=True)
    code = subprocess.run(argv + ["-p", str(project)], cwd=project).returncode
    if "--dry-run" in argv:
        return code
    result = run_result(project)
    write_outputs(result, env)
    if env.get("CG_COMMENT", "").strip().lower() in TRUE:
        subprocess.run(comment_command(env.get("CG_ISSUE", "").strip(), comment_text(result, env)), cwd=project, check=False)
    return 0 if result["success"] else (code or 1)


if __name__ == "__main__":
    sys.exit(main())
