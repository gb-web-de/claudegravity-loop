"""Projekt- und Session-Verwaltung: Kontext, Git-Workspace, Rechte-Flags, Review-Auswertung, Logs und Sitzungsstand."""

import contextlib
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .common import SETTINGS, say
from .safety import is_sensitive_path, mask_secrets
from .errors import AUDIT_EVENT_CODES, error_doc_link, error_entry
from .metrics import AUDIT_EVENT_LABELS
from .backends import DEFAULT_MODEL_LABEL

if TYPE_CHECKING:
    from .backends import AgentCLI
    from .metrics import SessionMetrics


def task_keywords(task: str) -> set[str]:
    """Wörter ab vier Buchstaben aus der Aufgabe, kleingeschrieben, für die Suche nach passendem Wissen."""
    return {w.lower() for w in re.findall(r"[\wäöüß]{4,}", task)}


def load_project_context(project_path: Path, task: str = "") -> str:
    """Projekt-Regeln und knowledge/ für die Prompts.

    CLAUDE.md und AGENTS.md werden beide geladen (gleicher Inhalt nur einmal). Aus knowledge/
    kommen bei bekannter Aufgabe nur passende Dateien mit Auszug, der Rest nur als Name.
    """
    if not project_path.exists():
        return ""
    context = []

    seen: set[str] = set()
    for rule_file in ["CLAUDE.md", "AGENTS.md", ".claude/rules.md"]:
        rf = project_path / rule_file
        if rf.is_file():
            text = rf.read_text(encoding="utf-8", errors="ignore").strip()
            if text and text not in seen:
                seen.add(text)
                context.append(f"### Projekt-Instruktionen ({rule_file}):\n{text}\n")

    knowledge_dir = project_path / "knowledge"
    if knowledge_dir.exists() and knowledge_dir.is_dir():
        k_files = sorted(f for f in knowledge_dir.glob("*") if f.is_file() and not is_sensitive_path(f.name))
        if k_files:
            keywords = task_keywords(task)
            context.append("### Verfügbares Projekt-Wissen (knowledge/):")
            names_only = []
            for kf in k_files:
                content = kf.read_text(encoding="utf-8", errors="ignore")
                haystack = (kf.stem.replace("_", " ").replace("-", " ") + " " + content[:4000]).lower()
                if not keywords or any(k in haystack for k in keywords):
                    context.append(f"--- Datei: {kf.name} ---\n{content[:500]}\n")
                else:
                    names_only.append(kf.name)
            if names_only:
                context.append("Weitere Dateien (bei Bedarf selbst lesen): " + ", ".join(names_only))

    return "\n".join(context)


def sanitize_filename(text: str) -> str:
    """Aufgabentext als kurzer, sicherer Teil eines Ordnernamens (höchstens 30 Zeichen)."""
    cleaned = re.sub(r"[^a-zA-Z0-9_\-\s]", "", text)
    cleaned = re.sub(r"\s+", "_", cleaned).strip("_")
    return cleaned[:30] or "task"


def task_preview(task: str, limit: int = 160) -> str:
    """Erste Zeile der Aufgabe für Statuszeilen; lange oder mehrzeilige Aufgaben (z. B. aus einem Issue) gekürzt mit „…“."""
    text = (task or "").strip()
    first = text.splitlines()[0] if text else ""
    if len(first) > limit:
        return first[: limit - 1].rstrip() + "…"
    return first + (" …" if first != text else "")


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
            with contextlib.suppress(Exception):
                root_done.unlink()
        return True
    return False


# ==========================================
# Git-Workspace (Worktree) pro Session
# ==========================================
def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)


def is_git_repo(path: Path) -> bool:
    """True, wenn path in einem Git-Repository mit mindestens einem Commit liegt."""
    if not shutil.which("git"):
        return False
    return _git(path, "rev-parse", "--verify", "HEAD").returncode == 0


def worktree_is_valid(path: Path) -> bool:
    """True, wenn path ein funktionierender Git-Worktree ist (die .git-Datei zeigt auf vorhandene Verwaltungsdaten)."""
    if not (path / ".git").exists():
        return False
    res = _git(path, "rev-parse", "--is-inside-work-tree")
    return res.returncode == 0 and res.stdout.strip() == "true"


def _make_writable_and_retry(func, path, _exc_info) -> None:
    """rmtree-Fehlerhandler: Schreibschutz entfernen (Windows, read-only Git-Objekte) und erneut versuchen."""
    import stat

    with contextlib.suppress(OSError):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        parent = os.path.dirname(path)
        if parent:
            os.chmod(parent, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
    func(path)


def remove_tree(path: Path) -> list[str]:
    """Löscht einen Ordner so weit wie möglich und liefert die Pfade, die sich nicht löschen ließen.

    Schreibgeschützte Dateien (typisch unter Windows) werden vorher beschreibbar gemacht. Was einem anderen
    Benutzer gehört (z. B. root nach einem Docker-Lauf), bleibt stehen und wird gemeldet."""
    leftovers: list[str] = []

    def onerror(func, p, exc_info):
        try:
            _make_writable_and_retry(func, p, exc_info)
        except OSError:
            leftovers.append(str(p))

    if path.exists():
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=lambda func, p, exc: onerror(func, p, None))
        else:
            shutil.rmtree(path, onerror=onerror)
    return leftovers


def _drop_worktree_dir(project_path: Path, wt_path: Path) -> bool:
    """Entfernt einen Worktree-Ordner, auch wenn git ihn nicht mehr (vollständig) kennt; meldet Reste mit Abhilfe."""
    leftovers = remove_tree(wt_path)
    _git(project_path, "worktree", "prune")
    if not leftovers:
        return True
    say(
        f"[!] {len(leftovers)} Datei(en) im Workspace ließen sich nicht löschen (gehören vermutlich einem anderen Benutzer, z. B. root nach Docker)."
    )
    for item in leftovers[:5]:
        say(f"    • {item}")
    if os.name == "nt":
        say(f'   👉 Programme schließen, die dort Dateien offen halten, dann: rmdir /s /q "{wt_path}"')
    else:
        say(f'   👉 Von Hand aufräumen: sudo rm -rf "{wt_path}" && git -C "{project_path}" worktree prune')
    return False


def acquire_worktree(project_path: Path, session_dir: Path, state: dict) -> Path:
    """Legt (oder reaktiviert) den isolierten Git-Workspace der Session an.

    Der Workspace liegt unter <session>/workspace auf dem Branch loop/<session-id>,
    abgezweigt vom aktuellen HEAD des Projekts. Gibt den Pfad zurück, in dem der
    Bauleiter arbeitet (bei Fehlern fällt er auf das Projektverzeichnis zurück).
    """
    wt = state.get("worktree") or {}
    wt_path = Path(wt.get("path") or (session_dir / "workspace"))
    branch = wt.get("branch") or f"loop/{session_dir.name}"

    if worktree_is_valid(wt_path):
        return wt_path
    if wt_path.exists():
        # Reste eines halb gelöschten Worktrees (z. B. nach „Keine Berechtigung“) verhindern ein neues `worktree add`
        say(f"[!] Git-Workspace {wt_path} ist beschädigt und wird neu angelegt (Commits auf dem Branch bleiben erhalten).")
        _drop_worktree_dir(project_path, wt_path)

    base_branch = wt.get("base_branch")
    if not base_branch:
        res = _git(project_path, "rev-parse", "--abbrev-ref", "HEAD")
        base_branch = res.stdout.strip() if res.returncode == 0 else "HEAD"

    _git(project_path, "worktree", "prune")
    if _git(project_path, "rev-parse", "--verify", f"refs/heads/{branch}").returncode == 0:
        res = _git(project_path, "worktree", "add", str(wt_path), branch)
    else:
        res = _git(project_path, "worktree", "add", "-b", branch, str(wt_path), "HEAD")

    if res.returncode != 0:
        say(f"[!] Git-Workspace konnte nicht angelegt werden, arbeite direkt im Projekt: {res.stderr.strip()}")
        return project_path

    state["worktree"] = {"path": str(wt_path), "branch": branch, "base_branch": base_branch, "released": False}
    save_session_state(session_dir, state)
    say(f"🌿 Git-Workspace angelegt: {wt_path} (Branch `{branch}` von `{base_branch}`)")
    return wt_path


def release_worktree(project_path: Path, session_dir: Path, state: dict, task: str, merge: bool = False) -> bool:
    """Committet offene Änderungen im Session-Workspace, entfernt den Worktree und
    merged den Branch optional zurück. Der Branch bleibt erhalten, sofern nicht gemerged."""
    wt = state.get("worktree")
    if not wt or wt.get("released"):
        return True
    wt_path = Path(wt["path"])
    branch = wt["branch"]
    base_branch = wt.get("base_branch", "HEAD")

    if wt_path.exists() and not worktree_is_valid(wt_path):
        # Ein früherer Versuch hat die Git-Verwaltung schon entfernt; committet wurde davor. Nur noch den Ordner aufräumen.
        say(f"[!] Git-Workspace {wt_path} ist kein gültiger Worktree mehr, räume nur noch den Ordner auf.")
        _drop_worktree_dir(project_path, wt_path)
    elif wt_path.exists():
        _git(wt_path, "add", "-A")
        if _git(wt_path, "diff", "--cached", "--quiet").returncode == 1:
            msg = f"claudegravity: {task[:72]}\n\nSession: {session_dir.name}"
            res = _git(wt_path, "commit", "-m", msg)
            if res.returncode != 0:
                res = _git(wt_path, "-c", "user.name=ClaudeGravity Loop", "-c", "user.email=claudegravity@localhost", "commit", "-m", msg)
            if res.returncode != 0:
                say(f"[!] Änderungen im Workspace konnten nicht committet werden, Workspace bleibt bestehen: {res.stderr.strip()}")
                return False
            say(f"💾 Änderungen auf Branch `{branch}` committet.")

        pending = _git(wt_path, "status", "--porcelain")
        if pending.returncode != 0 or pending.stdout.strip():
            say(f"[!] Im Workspace liegen noch nicht committete Änderungen, er bleibt bestehen: {wt_path}")
            return False
        # Alles ist committet; --force entfernt nur noch ignorierte Dateien (Caches, vendor/ …)
        res = _git(project_path, "worktree", "remove", "--force", str(wt_path))
        if res.returncode != 0:
            # Alles ist committet. git bricht aber z. B. an fremden Dateien ab (root nach Docker, Windows-Sperren)
            # und lässt einen halben Worktree zurück. Selbst aufräumen und als freigegeben markieren,
            # damit ein zweiter Durchlauf nicht auf den kaputten Ordner trifft.
            say(f"[!] git konnte den Workspace nicht vollständig entfernen: {res.stderr.strip()}")
            _drop_worktree_dir(project_path, wt_path)
    _git(project_path, "worktree", "prune")

    merged = False
    if merge and base_branch != "HEAD":
        current = _git(project_path, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if current != base_branch:
            say(f"[!] Merge übersprungen: Projekt steht auf `{current}`, nicht auf `{base_branch}`.")
        else:
            res = _git(project_path, "merge", "--no-ff", "--no-edit", branch)
            if res.returncode == 0:
                _git(project_path, "branch", "-d", branch)
                merged = True
                say(f"🔀 Branch `{branch}` in `{base_branch}` gemerged und gelöscht.")
            else:
                _git(project_path, "merge", "--abort")
                say(
                    f"[!] Merge von `{branch}` fehlgeschlagen (Konflikt?), Branch bleibt erhalten: {res.stdout.strip() or res.stderr.strip()}"
                )

    wt["released"] = True
    wt["merged"] = merged
    save_session_state(session_dir, state)
    say("🧹 Git-Workspace freigegeben.")
    if not merged:
        say(f"💡 Ergebnis liegt auf Branch `{branch}` (übernehmen mit: git merge {branch})")
    return True


# Architekt, Prüfstatiker und Abnahme lesen nur. Claude bekommt dafür ausschließlich
# Read/Glob/Grep, kein MCP; alles andere wird ohne Nachfrage abgelehnt.
CLAUDE_READONLY_FLAGS = [
    "--permission-mode",
    "dontAsk",
    "--tools",
    "Read,Glob,Grep",
    "--allowedTools",
    "Read,Glob,Grep",
    "--strict-mcp-config",
    "--mcp-config",
    '{"mcpServers":{}}',
]
# Copilot CLI: --deny-tool hat Vorrang vor --allow-all-tools; damit bleiben Lesewerkzeuge ohne Nachfrage nutzbar
COPILOT_READONLY_FLAGS = ["--allow-all-tools", "--deny-tool", "write", "--deny-tool", "shell", "--disable-builtin-mcps"]


def get_readonly_flags(binary: str) -> list[str]:
    """Flags für Rollen, die nie schreiben dürfen (Architekt, Prüfstatiker, Abnahme), auch nicht mit --yolo."""
    if binary == "claude":
        return list(CLAUDE_READONLY_FLAGS)
    if binary == "codex":
        return ["-s", "read-only"]
    if binary == "agy":
        return ["--mode", "plan"]
    if binary == "gemini":
        return ["--approval-mode", "plan"]
    if binary in ("copilot", "gh"):
        # Ohne Freigabe würde die CLI im Skriptmodus nachfragen; Schreiben, Shell und eingebaute MCP-Server bleiben gesperrt
        return list(COPILOT_READONLY_FLAGS)
    return []


def role_flags(binary: str, role: str, write_allowed: bool) -> list[str]:
    """Rechte-Flags je Rolle: nur der Bauleiter bekommt (nach Freigabe) Schreibrechte."""
    if role == "builder" and write_allowed:
        return get_permission_flags(binary)
    if role == "builder":
        return []
    return get_readonly_flags(binary)


def get_permission_flags(binary: str) -> list[str]:
    """Gibt die passenden Flags für Schreib-/Tool-Rechte zurück (nur für den Bauleiter)."""
    if binary in ["claude", "agy"]:
        return ["--dangerously-skip-permissions"]
    elif binary == "gemini":
        return ["-y"]
    elif binary == "codex":
        return ["-s", "workspace-write"]
    elif binary in ("copilot", "gh"):
        return ["--allow-all-tools"]
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
        "Berechtigung nicht erteilt",
    ]
    text_lower = text.lower()
    return any(ind.lower() in text_lower for ind in indicators) and len(text.strip().splitlines()) < 15


def extract_questions(text: str) -> str | None:
    """Extrahiert Fragen an den Nutzer, falls ein Agent welche formuliert hat."""
    patterns = [
        r"(?:###|##)\s*(?:FRAGEN\s+AN\s+DEN\s+NUTZER|OFFENE\s+FRAGEN|RÜCKFRAGEN|QUESTIONS\s+FOR\s+USER)[:\s]*(.*?)(?=(?:\n###|\n##|\Z))",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.DOTALL)
        if m:
            content = m.group(1).strip()
            if "?" in content or "-" in content or "1." in content:
                return content
    return None


VERDICT_LINE = re.compile(r"^[\s>*_#`-]*VERDICT[\s*_`]*[:=][\s*_`]*(APPROVED|REVISE|BLOCKED)[\s*_`.!]*$", re.IGNORECASE)
FINDING_LINE = re.compile(
    r"^\s*(?:[-*]|\d+[.)])\s*\[?\**(KRITISCH|CRITICAL|HOCH|HIGH|MITTEL|MEDIUM|NIEDRIG|LOW)\**\]?\s*[:\-–]?\s*(.*)$", re.IGNORECASE
)
SEVERITY = {
    "kritisch": "high",
    "critical": "high",
    "hoch": "high",
    "high": "high",
    "mittel": "medium",
    "medium": "medium",
    "niedrig": "low",
    "low": "low",
}

REVIEW_FORMAT = (
    "Antwortformat (verbindlich):\n"
    "BEFUNDE:\n"
    "- [HOCH|MITTEL|NIEDRIG] <Datei oder Abschnitt>: <Problem mit Beleg> -> <konkreter Fix>\n"
    "(oder genau eine Zeile '- keine')\n"
    "EMPFEHLUNGEN:\n"
    "- <optionale Hinweise>\n"
    "Schließe mit einer eigenen letzten Zeile im Format `VERDICT: <APPROVED|REVISE|BLOCKED>`.\n"
    "APPROVED nur, wenn kein HOCH- oder MITTEL-Befund offen ist; BLOCKED, wenn dir Belege fehlen, um zu urteilen."
)


def parse_review(text: str) -> dict:
    """Liest Urteil und Befunde aus einer Prüfer-Antwort.

    Das Urteil zählt nur als eigene Zeile, und zwar die letzte. Eine wiederholte Vorlage
    oder ein Satz wie "kein VERDICT: APPROVED" genehmigt also nichts.
    """
    verdict = None
    for line in reversed(text.splitlines()):
        m = VERDICT_LINE.match(line.strip())
        if m:
            verdict = m.group(1).upper()
            break
    findings = []
    for line in text.splitlines():
        m = FINDING_LINE.match(line)
        if m:
            findings.append({"severity": SEVERITY[m.group(1).lower()], "text": m.group(2).strip()})
    return {"verdict": verdict, "findings": findings}


def review_decision(parsed: dict) -> tuple[bool, str]:
    """Entscheidet, ob ein Review als Freigabe zählt. Unklare Antworten sind nie eine Freigabe."""
    verdict = parsed.get("verdict")
    findings = parsed.get("findings") or []
    material = [f for f in findings if f["severity"] in ("high", "medium")]
    if verdict == "APPROVED" and material:
        return False, f"APPROVED trotz {len(material)} HOCH/MITTEL-Befund(en), zählt als REVISE"
    if verdict == "APPROVED":
        return True, "APPROVED"
    if verdict == "REVISE" and findings and not material:
        return True, "REVISE mit nur NIEDRIG-Befunden, zählt als Freigabe mit Hinweisen"
    if verdict == "BLOCKED":
        return False, "BLOCKED: dem Prüfer fehlen Belege"
    if verdict is None:
        return False, "kein lesbares VERDICT, zählt nicht als Freigabe"
    return False, "REVISE"


def findings_digest(review: str) -> str:
    """Nur die Befunde für den Architekten bzw. Bauleiter, statt der ganzen Prüfer-Antwort."""
    parsed = parse_review(review)
    if not parsed["findings"]:
        return review
    labels = {"high": "HOCH", "medium": "MITTEL", "low": "NIEDRIG"}
    return "\n".join(f"- [{labels[f['severity']]}] {f['text']}" for f in parsed["findings"])


def sha256_file(path: Path) -> str:
    """SHA-256 des Dateiinhalts als Hex-Text."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def next_plan_file(session_dir: Path) -> Path:
    """Nächste freie Plan-Version; überschreibt nie eine ältere."""
    nums = [int(m.group(1)) for p in session_dir.glob("PLAN_v*.md") if (m := re.match(r"PLAN_v(\d+)", p.name))]
    return session_dir / f"PLAN_v{max(nums, default=0) + 1}.md"


def plan_diff(old: str, new: str) -> str:
    """Unified Diff zwischen geprüftem und neuem Plan, damit der Prüfstatiker nur Änderungen liest."""
    import difflib

    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), "geprüfter_plan", "neuer_plan", n=2))


LOG_FORMATS = ("text", "json")


def log_event(session_dir: Path | None, event: str, **fields) -> None:
    """Eine JSON-Zeile pro Ereignis in events.jsonl (nur mit --log-format json); Texte werden geschwärzt."""
    if SETTINGS.log_format != "json" or session_dir is None:
        return
    record = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "session": session_dir.name, "event": event}
    for key, value in fields.items():
        if value is not None:
            record[key] = mask_secrets(value) if isinstance(value, str) else value
    try:
        with open(session_dir / "events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def append_log(session_dir: Path, line: str) -> None:
    """Zeile mit Uhrzeit an LOG.md der Session anhängen (Geheimnisse geschwärzt) und als Ereignis protokollieren."""
    line = mask_secrets(line)
    try:
        with open(session_dir / "LOG.md", "a", encoding="utf-8") as f:
            f.write(f"- [{datetime.datetime.now().strftime('%H:%M:%S')}] {line}\n")
    except OSError:
        pass
    log_event(session_dir, "log", message=line)


def record_audit_event(session_dir: Path | None, kind: str, detail: str, metrics: "SessionMetrics | None" = None) -> None:
    """Hält Sicherheitsereignisse fest: LOG.md, audit-events.jsonl im Session-Ordner und Zähler im .done-Audit."""
    detail = mask_secrets(detail)
    label = AUDIT_EVENT_LABELS.get(kind, kind)
    code = AUDIT_EVENT_CODES.get(kind)
    say(
        f"🛑 Audit{f' [{code}]' if code else ''}: {label}: {detail}"
        + (f"\n   👉 {error_entry(code)[1]}\n   📖 {error_doc_link(code)}" if code else "")
    )
    if metrics is not None:
        metrics.note_audit(kind)
    if session_dir is None:
        return
    append_log(session_dir, f"🛑 Audit: {label}: {detail}")
    log_event(session_dir, "audit", level="warning", kind=kind, code=code, detail=detail)
    try:
        with open(session_dir / "audit-events.jsonl", "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {"time": datetime.datetime.now().isoformat(timespec="seconds"), "kind": kind, "detail": detail}, ensure_ascii=False
                )
                + "\n"
            )
    except OSError:
        pass


def workspace_fingerprint(path: Path) -> dict | None:
    """Stand des Arbeitsverzeichnisses (geänderte und neue Dateien mit Größe und Zeitstempel); None ohne Git."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=str(path),
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    state: dict = {}
    for entry in res.stdout.decode("utf-8", "replace").split("\0"):
        if len(entry) < 4:
            continue
        rel = entry[3:]
        if rel.startswith(".dual-loop/") or rel == ".dual-loop":
            continue  # Arbeitsordner des Loops selbst
        try:
            st = (path / rel).stat()
            state[rel] = (entry[:2], st.st_size, st.st_mtime_ns)
        except OSError:
            state[rel] = (entry[:2], None, None)
    return state


def fingerprint_changes(before: dict | None, after: dict | None) -> list[str]:
    """Dateien, deren Fingerabdruck sich zwischen zwei Ständen unterscheidet, sortiert."""
    if before is None or after is None:
        return []
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def model_report(agent: "AgentCLI") -> str:
    """Angefordertes und von der CLI gemeldetes Modell getrennt, da CLI-Defaults oft abweichen."""
    requested = agent.requested_model or agent.model or DEFAULT_MODEL_LABEL
    return f"{agent.name}: angefordert `{requested}`, gemeldet `{agent.reported_model or 'unbekannt'}`"


# ==========================================
# Session & State Management (Resume-Support)
# ==========================================
def save_session_state(session_dir: Path, state: dict):
    """Schreibt state.json atomar: erst in eine Temp-Datei, dann umbenennen. Ein Absturz mitten im
    Schreiben hinterlässt so nie eine halbe Datei; der vorige Stand bleibt als state.json.bak."""
    state_file = session_dir / "state.json"
    state["updated_at"] = datetime.datetime.now().isoformat()
    tmp_file = session_dir / "state.json.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(state, indent=2, ensure_ascii=False))
        f.flush()
        with contextlib.suppress(OSError):
            os.fsync(f.fileno())
    if state_file.exists():
        with contextlib.suppress(OSError):
            shutil.copyfile(state_file, session_dir / "state.json.bak")
    os.replace(tmp_file, state_file)


def load_session_state(session_dir: Path) -> dict:
    """Liest state.json; ist sie beschädigt, den letzten guten Stand aus state.json.bak."""
    for name in ("state.json", "state.json.bak"):
        state_file = session_dir / name
        if not state_file.exists():
            continue
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            say(f"⚠️  {state_file} ist beschädigt und wird übersprungen.")
            continue
        if isinstance(data, dict):
            if name != "state.json":
                say(f"♻️  Stand aus {state_file.name} wiederhergestellt (letzte Runde wird ggf. wiederholt).")
            return data
    return {}


def find_latest_session(loop_dir: Path) -> Path | None:
    """Neuester Session-Ordner unter .dual-loop/sessions oder None."""
    sessions_dir = loop_dir / "sessions"
    if not sessions_dir.exists():
        return None
    sessions = sorted([p for p in sessions_dir.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)
    return sessions[0] if sessions else None
