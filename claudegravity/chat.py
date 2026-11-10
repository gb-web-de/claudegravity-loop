"""Chat-Oberfläche im Browser (`claudegravity chat`): Aufgabe schreiben, Plan lesen und freigeben, dem Bau zusehen.

Der Server startet den Loop als eigenen Prozess; Antworten auf Rückfragen gehen als Zeilen an dessen stdin. Das
Gespräch entsteht aus dem Verlauf der Session (timeline.jsonl, geschrieben von watch.py) und den Plan-, Review- und
Abnahme-Dateien. Wie die Live-Ansicht hört der Server nur auf 127.0.0.1, verlangt einen Zufallstoken in der URL und
prüft Host- und Origin-Kopf. Nur Standardbibliothek.
"""

import contextlib
import dataclasses
import datetime
import http.server
import json
import os
import re
import secrets
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

from . import __version__, watch
from .chatpage import CHAT_PAGE
from .common import ANSWER_NEWLINE, CHAT_CHILD_ENV, ENDPOINT_BINARIES, SETTINGS, loop_entry, say, tr
from .safety import mask_secrets
from .backends import check_cli_auth, detect_installed_agents
from .session import is_git_repo, parse_review, plan_files, plan_version, review_decision, task_preview
from .config import global_profile_path
from .wizard import suggest_proof_command

CHAT_PORT = 8766
CHAT_STRATEGIES = ("balanced", "best-code", "eco", "hybrid", "local-free")
CHAT_TEMPLATES = ("bugfix", "feature", "refactor")
CHAT_TASK_LIMIT = 20_000
CHAT_ANSWER_LIMIT = 8_000
CHAT_FILE_LIMIT = 60_000
CHAT_OUTPUT_TAIL = 20_000
CHAT_BODY_LIMIT = 262_144
CHAT_RECENT_LIMIT = 8
CHAT_DIR_LIMIT = 400
CHAT_SETUP_TTL = 300
CHAT_STOP_GRACE = 8.0
# Zeilen aus LOG.md, die der Verlauf schon als eigenes Ereignis zeigt (Prüfbefehl, Abnahme, Etappe, Plan-Änderung)
LOG_COVERED = (
    "Prüfbefehl `",
    "Abnahme Runde ",
    "Etappe ",
    "Letzte Ausgabe des Prüfbefehls",
    "Plan nach Änderungswunsch",
    "Plan vom Nutzer von Hand",
    "🛑 Audit:",
)
# Rückfragen, deren erläuternder Text (detail) als eigene Nachricht ins Gespräch gehört
DETAIL_KINDS = ("questions", "limit")


# ==========================================
# Zuletzt benutzte Projekte
# ==========================================
def chat_store_path() -> Path:
    """Datei mit den zuletzt im Chat benutzten Projekten (neben dem globalen Profil)."""
    return global_profile_path(dict(os.environ)).parent / "chat.json"


def recent_projects() -> list[str]:
    """Zuletzt benutzte Projektordner, neueste zuerst; nur solche, die es noch gibt."""
    try:
        data = json.loads(chat_store_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = data.get("projects") if isinstance(data, dict) else None
    return [p for p in (items or []) if isinstance(p, str) and Path(p).is_dir()][:CHAT_RECENT_LIMIT]


def remember_project(project: Path) -> None:
    """Projektordner an den Anfang der zuletzt benutzten setzen."""
    items = [str(project)] + [p for p in recent_projects() if p != str(project)]
    path = chat_store_path()
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"projects": items[:CHAT_RECENT_LIMIT]}, ensure_ascii=False, indent=1), encoding="utf-8")


def resolve_project(raw: str | None, default: Path) -> Path | None:
    """Projektordner aus einer Angabe der Seite: absoluter Pfad (auch mit ~) zu einem vorhandenen Ordner, sonst None.
    Ohne Angabe gilt der Ordner, mit dem der Chat gestartet wurde."""
    if not raw:
        return default
    path = Path(raw).expanduser()
    if not path.is_absolute():
        return None
    with contextlib.suppress(OSError):
        path = path.resolve()
        if path.is_dir():
            return path
    return None


def list_directories(raw: str | None) -> dict:
    """Unterordner für die Ordnerauswahl der Seite (ohne versteckte); ohne Angabe das Home-Verzeichnis."""
    path = Path(raw).expanduser() if raw else Path.home()
    if not path.is_absolute() or not path.is_dir():
        path = Path.home()
    path = path.resolve()
    names: list[str] = []
    with contextlib.suppress(OSError):
        for entry in os.scandir(path):
            with contextlib.suppress(OSError):
                if entry.is_dir() and not entry.name.startswith("."):
                    names.append(entry.name)
    names.sort(key=str.lower)
    return {
        "path": str(path),
        "parent": str(path.parent) if path.parent != path else None,
        "dirs": names[:CHAT_DIR_LIMIT],
        "truncated": len(names) > CHAT_DIR_LIMIT,
        "git": (path / ".git").exists(),
        "sessions": (path / ".dual-loop" / "sessions").is_dir(),
    }


# ==========================================
# Gespräch aus dem Verlauf einer Session
# ==========================================
def read_timeline(session_dir: Path) -> list[dict]:
    """Zeilen aus timeline.jsonl; unlesbare Zeilen (z. B. halb geschrieben) werden übersprungen."""
    try:
        lines = (session_dir / watch.TIMELINE_FILE).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    entries = []
    for line in lines:
        with contextlib.suppress(ValueError):
            entry = json.loads(line)
            if isinstance(entry, dict) and isinstance(entry.get("type"), str):
                entries.append(entry)
    return entries


def session_file_text(session_dir: Path, name: object) -> str:
    """Inhalt einer Datei aus dem Session-Ordner (Plan, Review, Abnahme), geschwärzt und begrenzt.
    Der Name kommt aus dem Verlauf und darf kein Pfad sein."""
    if not isinstance(name, str) or not name or name != Path(name).name or name.startswith("."):
        return ""
    try:
        text = (session_dir / name).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return mask_secrets(text[:CHAT_FILE_LIMIT]) + ("\n\n…" if len(text) > CHAT_FILE_LIMIT else "")


def answer_message(question: dict | None, entry: dict) -> dict | None:
    """Antwort des Nutzers als Nachricht: bei einer Auswahl deren Beschriftung, sonst der getippte Text."""
    if entry.get("cancelled") or not isinstance(entry.get("answer"), str):
        return None
    value = entry["answer"].strip()
    choices = (question or {}).get("choices") or []
    label = next((c.get("label") for c in choices if str(c.get("value", "")).lower() == value.lower()), None)
    return {
        "type": "answer",
        "time": entry.get("time"),
        "kind": entry.get("kind") or (question or {}).get("kind") or "",
        "value": value,
        "label": label,
        "prompt": (question or {}).get("prompt") or "",
    }


def timeline_messages(session_dir: Path, entries: list[dict]) -> list[dict]:
    """Verlauf in Nachrichten für die Seite übersetzen: Aufgabe, Pläne, Reviews, Antworten, Bau-Runden, Prüfungen, Ende."""
    messages: list[dict] = []
    calls: dict[str, dict] = {}
    question: dict | None = None
    started = False

    def stats(role: str) -> dict | None:
        call = calls.pop(role, None)
        return {"duration_s": call.get("duration_s"), "tokens": call.get("tokens"), "model": call.get("model")} if call else None

    for entry in entries:
        kind, when = entry["type"], entry.get("time")
        if kind == "start":
            if not started:
                messages.append({"type": "task", "time": when, "text": entry.get("task") or ""})
                started = True
            elif entry.get("resumed"):
                messages.append({"type": "resumed", "time": when})
        elif kind == "roles":
            messages.append({"type": "roles", "time": when, **{k: entry.get(k) for k in ("strategy", "planner", "reviewer", "builder")}})
        elif kind == "call":
            calls[str(entry.get("role"))] = entry
        elif kind == "plan":
            name = entry.get("file")
            messages.append(
                {
                    "type": "plan",
                    "time": when,
                    "file": name,
                    "version": plan_version(Path(str(name))),
                    "agent": entry.get("agent"),
                    "source": entry.get("source"),
                    "text": session_file_text(session_dir, name),
                    "stats": stats("planner"),
                }
            )
        elif kind in ("review", "inspection"):
            messages.append(
                {
                    "type": kind,
                    "time": when,
                    "file": entry.get("file"),
                    "round": entry.get("round"),
                    "agent": entry.get("agent"),
                    "approved": bool(entry.get("approved")),
                    "reason": entry.get("reason"),
                    "findings": entry.get("findings"),
                    "text": session_file_text(session_dir, entry.get("file")),
                    "stats": stats("reviewer" if kind == "review" else "inspector"),
                }
            )
        elif kind == "question":
            question = entry
            if entry.get("kind") in DETAIL_KINDS and entry.get("detail"):
                messages.append({"type": "ask", "time": when, "kind": entry.get("kind"), "text": entry.get("detail")})
        elif kind == "answer":
            message = answer_message(question, entry)
            question = None
            if message:
                messages.append(message)
        elif kind == "build_round":
            messages.append(
                {
                    "type": "build",
                    "time": when,
                    "iteration": entry.get("iteration"),
                    "label": entry.get("label"),
                    "agent": entry.get("agent"),
                    "files": entry.get("files") or [],
                    "text": entry.get("summary") or "",
                    "stats": stats("builder"),
                }
            )
        elif kind == "proof":
            messages.append(
                {
                    "type": "proof",
                    "time": when,
                    "ok": bool(entry.get("ok")),
                    "command": entry.get("command"),
                    "output": entry.get("output") or "",
                }
            )
        elif kind == "stage":
            messages.append({"type": "stage", "time": when, **{k: entry.get(k) for k in ("index", "total", "text", "ok")}})
        elif kind == "log":
            text = str(entry.get("message") or "")
            if text and not text.startswith(LOG_COVERED):
                messages.append({"type": "notice", "time": when, "text": text})
        elif kind == "audit":
            messages.append({"type": "notice", "time": when, "level": "warning", "text": f"{entry.get('kind')}: {entry.get('detail')}"})
        elif kind == "escalation":
            messages.append({"type": "escalation", "time": when, **{k: entry.get(k) for k in ("from", "to", "reason")}})
        elif kind == "pull_request":
            messages.append({"type": "pull_request", "time": when, "url": entry.get("url")})
        elif kind == "error":
            messages.append({"type": "error", "time": when, "code": entry.get("code"), "text": entry.get("detail") or ""})
        elif kind == "session_end":
            messages.append(
                {
                    "type": "end",
                    "time": when,
                    "success": bool(entry.get("success")),
                    "reason": entry.get("abort_reason"),
                    "tokens": entry.get("tokens_total"),
                    "cost_usd": entry.get("cost_usd_total"),
                    "rounds": entry.get("build_rounds"),
                }
            )
    return messages


def legacy_messages(session_dir: Path, state: dict) -> list[dict]:
    """Gespräch für Sessions ohne timeline.jsonl (ältere Läufe): aus Plan-, Review- und Abnahme-Dateien nach Änderungszeit."""
    messages: list[dict] = [{"type": "task", "time": state.get("created_at"), "text": state.get("task") or ""}]
    files: list[tuple[float, str, Path]] = [(p.stat().st_mtime, "plan", p) for p in plan_files(session_dir)]
    for kind, pattern in (("review", "REVIEW_round*.md"), ("inspection", "INSPECTION_round*.md")):
        files += [(p.stat().st_mtime, kind, p) for p in session_dir.glob(pattern)]
    for mtime, kind, path in sorted(files, key=lambda item: (item[0], item[2].name)):
        when = datetime.datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
        text = session_file_text(session_dir, path.name)
        if kind == "plan":
            messages.append({"type": "plan", "time": when, "file": path.name, "version": plan_version(path), "text": text})
            continue
        parsed = parse_review(text)
        approved, reason = review_decision(parsed)
        number = re.sub(r"\D", "", path.stem)
        messages.append(
            {
                "type": kind,
                "time": when,
                "file": path.name,
                "round": int(number) if number else None,
                "approved": approved,
                "reason": reason,
                "findings": len(parsed["findings"]),
                "text": text,
            }
        )
    if state.get("phase") == "completed" or state.get("abort_reason"):
        messages.append(
            {
                "type": "end",
                "time": state.get("updated_at"),
                "success": state.get("phase") == "completed",
                "reason": state.get("abort_reason"),
                "tokens": (state.get("metrics") or {}).get("total_tokens"),
                "rounds": state.get("last_iteration"),
            }
        )
    return messages


def chat_messages(session_dir: Path) -> list[dict]:
    """Das Gespräch einer Session: aus dem Verlauf, bei älteren Sessions ohne Verlauf aus ihren Dateien."""
    entries = read_timeline(session_dir)
    if entries:
        return timeline_messages(session_dir, entries)
    return legacy_messages(session_dir, watch.read_state(session_dir))


# ==========================================
# Loop-Prozesse des Chats
# ==========================================
@dataclasses.dataclass
class ChatRun:
    """Ein vom Chat gestarteter Loop-Prozess."""

    run_id: str
    proc: subprocess.Popen
    project: Path
    log_path: Path
    task: str
    session: str | None = None
    answered: str | None = None
    stop_at: float | None = None
    lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)

    @property
    def alive(self) -> bool:
        """Ob der Prozess noch läuft."""
        return self.proc.poll() is None

    def output_tail(self) -> str:
        """Ende der Konsolenausgabe des Laufs, geschwärzt."""
        try:
            with open(self.log_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - CHAT_OUTPUT_TAIL))
                return mask_secrets(f.read().decode("utf-8", "replace"))
        except OSError:
            return ""


def chat_log_path(project: Path) -> Path:
    """Konsolen-Log eines Chat-Laufs. Liegt als Datei in sessions/, damit .dual-loop nur diesen Unterordner hat."""
    sessions = project / ".dual-loop" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return sessions / f"{stamp}_{secrets.token_hex(2)}_chat.log"


def start_options(data: dict) -> list[str]:
    """Flags für einen neuen Lauf aus dem Formular der Seite. Nur bekannte Werte; freie Zusatzoptionen kommen
    als eigene Argumente dazu (nie über eine Shell)."""
    args: list[str] = []
    strategy = data.get("strategy")
    if strategy in CHAT_STRATEGIES:
        args += ["--strategy", strategy]
    template = data.get("template")
    if template in CHAT_TEMPLATES:
        args += ["--template", template]
    proof = data.get("proof")
    if isinstance(proof, str) and proof.strip():
        args += ["--proof", proof.strip()[:500]]
    for key, flag in (("yolo", "--yolo"), ("plan_auto", "--plan-auto"), ("ask", "--ask"), ("merge", "--merge")):
        if data.get(key) is True:
            args.append(flag)
    extra = data.get("extra")
    if isinstance(extra, str) and extra.strip():
        args += shlex.split(extra.strip()[:2000])
    return args


def launch_loop(project: Path, loop_args: list[str], task: str, session: str | None = None) -> ChatRun:
    """Loop als eigenen Prozess starten: eigene Prozessgruppe, stdin als Leitung für die Antworten, Ausgabe ins Log."""
    log_path = chat_log_path(project)
    run_id = secrets.token_hex(8)
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200) | getattr(
            subprocess, "CREATE_NO_WINDOW", 0x08000000
        )
    else:
        kwargs["start_new_session"] = True
    env = {
        **os.environ,
        CHAT_CHILD_ENV: run_id,
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "CLAUDEGRAVITY_NO_BROWSER": "1",
    }
    with open(log_path, "w", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            loop_entry() + loop_args,
            cwd=str(project),
            stdin=subprocess.PIPE,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            encoding="utf-8",
            **kwargs,
        )
    return ChatRun(run_id=run_id, proc=proc, project=project, log_path=log_path, task=task, session=session)


def attach_session(run: ChatRun) -> None:
    """Die Session finden, die der gestartete Prozess angelegt hat: Ihre live.json trägt die Kennung des Chat-Laufs."""
    if run.session:
        return
    for session_dir in watch.list_sessions(run.project)[: watch.SESSION_LIST_LIMIT]:
        if watch.read_live(session_dir).get("chat") == run.run_id:
            run.session = session_dir.name
            return


def send_answer(run: ChatRun, value: str, question_id: str | None) -> bool:
    """Antwort als eine Zeile an den Loop schicken. Jede Rückfrage (erkennbar an ihrer Kennung) bekommt höchstens eine Antwort."""
    line = value.replace("\r", "").strip("\n").replace("\n", ANSWER_NEWLINE)[:CHAT_ANSWER_LIMIT]
    with run.lock:
        if not run.alive or run.proc.stdin is None or (question_id and run.answered == question_id):
            return False
        try:
            run.proc.stdin.write(line + "\n")
            run.proc.stdin.flush()
        except (OSError, ValueError):
            return False
        run.answered = question_id
    return True


def signal_run(run: ChatRun, force: bool = False) -> None:
    """Lauf samt seiner KI-CLIs beenden: zuerst SIGTERM an die Prozessgruppe (der Loop sichert seinen Stand),
    mit `force` hart. Unter Windows gibt es nur den harten Weg über taskkill."""
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(run.proc.pid), "/T", "/F"], capture_output=True, check=False, timeout=15)
        else:
            os.killpg(run.proc.pid, signal.SIGKILL if force else signal.SIGTERM)


def stop_run(run: ChatRun) -> bool:
    """Stopp aus der Seite: beim ersten Mal sanft, ein zweiter Stopp nach der Schonfrist hart."""
    if not run.alive:
        return False
    force = run.stop_at is not None and time.monotonic() - run.stop_at >= CHAT_STOP_GRACE
    if run.stop_at is None:
        run.stop_at = time.monotonic()
    signal_run(run, force=force)
    return True


# ==========================================
# Stand für die Seite
# ==========================================
def chat_setup() -> dict:
    """Erkannte KI-CLIs und Endpunkte mit Anmeldestatus (dauert einige Sekunden, läuft daher im Hintergrund)."""
    rows = []
    for key, agent in detect_installed_agents().items():
        if agent.local or agent.binary in ENDPOINT_BINARIES:
            ready, status = True, "lokal"
        else:
            ready, status = check_cli_auth(agent.binary)
        rows.append({"key": key, "name": agent.name, "local": bool(agent.local), "ready": bool(ready), "status": tr(status)})
    return {"agents": rows, "checked": datetime.datetime.now().isoformat(timespec="seconds")}


def project_info(project: Path) -> dict:
    """Angaben zum Projektordner für das Startformular: Name, Git, geratener Prüfbefehl."""
    return {
        "path": str(project),
        "name": project.name or str(project),
        "git": is_git_repo(project),
        "proof": suggest_proof_command(project),
        "home": project == Path.home(),
    }


def chat_session_payload(project: Path, session_dir: Path, after: int, run: ChatRun | None) -> dict:
    """Eine Session für die Seite: Stand wie in der Live-Ansicht, dazu die Nachrichten ab `after` und die offene Rückfrage."""
    snapshot = watch.session_snapshot(project, session_dir)
    messages = chat_messages(session_dir)
    owned = bool(run and run.alive)
    waiting = snapshot.get("waiting") if snapshot.get("running") else None
    if waiting and run and run.answered == waiting.get("id"):
        waiting = None  # schon beantwortet, der Loop hat die Zeile nur noch nicht gelesen
    snapshot.update(
        {
            "messages": messages[max(0, after) :],
            "total": len(messages),
            "question": waiting,
            "owned": owned,
            "stopping": bool(run and run.alive and run.stop_at is not None),
            "can_resume": not snapshot.get("running") and snapshot.get("phase") != "completed" and not snapshot.get("done"),
        }
    )
    return snapshot


# ==========================================
# HTTP-Server
# ==========================================
class ChatServer(http.server.ThreadingHTTPServer):
    """Server der Chat-Oberfläche; nur 127.0.0.1, Zugriff nur mit Token. Verwaltet die gestarteten Loop-Prozesse."""

    daemon_threads = True

    def __init__(self, project: Path, port: int):
        self.project = project
        self.token = secrets.token_urlsafe(18)
        self.runs: list[ChatRun] = []
        self.lock = threading.Lock()
        self.setup: dict | None = None
        self.setup_time = 0.0
        self.setup_busy = False
        self.info_cache: dict[str, tuple[float, dict]] = {}
        super().__init__(("127.0.0.1", port), ChatHandler)

    @property
    def url(self) -> str:
        """Adresse der Seite samt Token."""
        return f"http://127.0.0.1:{self.server_address[1]}/?t={self.token}"

    def refresh_setup(self, force: bool = False) -> None:
        """Erkennung der KI-CLIs im Hintergrund anstoßen, wenn sie fehlt oder veraltet ist."""
        with self.lock:
            fresh = self.setup is not None and time.monotonic() - self.setup_time < CHAT_SETUP_TTL
            if self.setup_busy or (fresh and not force):
                return
            self.setup_busy = True

        def work() -> None:
            data = None
            with contextlib.suppress(Exception):
                data = chat_setup()
            with self.lock:
                if data is not None:
                    self.setup, self.setup_time = data, time.monotonic()
                self.setup_busy = False

        threading.Thread(target=work, name="claudegravity-chat-setup", daemon=True).start()

    def info(self, project: Path) -> dict:
        """project_info() mit kurzem Zwischenspeicher (die Seite fragt alle anderthalb Sekunden)."""
        key = str(project)
        cached = self.info_cache.get(key)
        if cached and time.monotonic() - cached[0] < 15:
            return cached[1]
        data = project_info(project)
        self.info_cache[key] = (time.monotonic(), data)
        return data

    def run_for(self, project: Path, session: str | None) -> ChatRun | None:
        """Der Chat-Lauf zu einer Session (der jüngste), falls dieser Server ihn gestartet hat."""
        if not session:
            return None
        with self.lock:
            runs = list(self.runs)
        for run in reversed(runs):
            attach_session(run)
            if run.project == project and run.session == session:
                return run
        return None

    def pending(self, project: Path) -> dict | None:
        """Der jüngste Lauf des Projekts: noch ohne Session (startet oder ist vorher gescheitert) oder gerade zugeordnet."""
        with self.lock:
            runs = [r for r in self.runs if r.project == project]
        if not runs:
            return None
        run = runs[-1]
        attach_session(run)
        if run.session:
            return {"run": run.run_id, "session": run.session}
        alive = run.alive
        return {
            "run": run.run_id,
            "session": None,
            "task": task_preview(run.task, 300),
            "alive": alive,
            "code": None if alive else run.proc.returncode,
            "output": "" if alive else run.output_tail()[-6000:],
        }

    def start(self, project: Path, loop_args: list[str], task: str, session: str | None = None) -> ChatRun:
        """Neuen Loop-Prozess starten und merken; beendete Läufe ohne Session werden dabei vergessen."""
        run = launch_loop(project, loop_args, task, session)
        with self.lock:
            self.runs = [r for r in self.runs if r.alive or r.session] + [run]
        remember_project(project)
        return run

    def state(self, project: Path, wanted: str | None, after: int) -> dict:
        """Antwort von /api/state: Projekt, erkannte KIs, Sessions und die gewählte Session mit neuen Nachrichten."""
        self.refresh_setup()
        sessions = watch.list_sessions(project)[: watch.SESSION_LIST_LIMIT]
        chosen = next((s for s in sessions if s.name == wanted), None)
        return {
            "lang": SETTINGS.lang,
            "version": __version__,
            "now": datetime.datetime.now().isoformat(timespec="seconds"),
            "project": self.info(project),
            "default_project": str(self.project),
            "recent": recent_projects(),
            "setup": self.setup,
            "strategies": list(CHAT_STRATEGIES),
            "templates": list(CHAT_TEMPLATES),
            "sessions": [watch.session_summary(s) for s in sessions],
            "session": chat_session_payload(project, chosen, after, self.run_for(project, chosen.name)) if chosen else None,
            "pending": self.pending(project),
        }

    def stop_all(self) -> int:
        """Beim Beenden des Chats alle noch laufenden Loop-Prozesse anhalten (sie sichern ihren Stand). Liefert die Anzahl."""
        with self.lock:
            running = [r for r in self.runs if r.alive]
        for run in running:
            signal_run(run)
        deadline = time.monotonic() + CHAT_STOP_GRACE
        while any(r.alive for r in running) and time.monotonic() < deadline:
            time.sleep(0.1)
        for run in running:
            if run.alive:
                signal_run(run, force=True)
        return len(running)


class ChatHandler(watch.WatchHandler):
    """GET / (Seite), /api/state, /api/diff, /api/output, /api/dirs; POST /api/start, /api/answer, /api/stop, /api/resume."""

    server: ChatServer

    def _fail(self, status: int, message: str) -> None:
        self._send(
            status, json.dumps({"ok": False, "error": message}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"
        )

    def _project(self, raw: str | None) -> Path | None:
        project = resolve_project(raw, self.server.project)
        if project is None:
            self._fail(400, tr("Projektordner nicht gefunden."))
        return project

    def do_GET(self):  # noqa: N802 - Name aus BaseHTTPRequestHandler
        """Seite und lesende API; ohne passenden Host-Kopf oder Token 403."""
        parts = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parts.query)
        if not self._allowed(query):
            self._send(403, b"forbidden", "text/plain; charset=utf-8")
            return

        def arg(name: str) -> str | None:
            return (query.get(name) or [None])[0]

        if parts.path == "/":
            self._send(200, CHAT_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parts.path == "/api/dirs":
            self._json(list_directories(arg("path")))
            return
        project = self._project(arg("project"))
        if project is None:
            return
        wanted = arg("session")
        if parts.path == "/api/state":
            after = arg("after") or "0"
            self._json(self.server.state(project, wanted, int(after) if after.isdigit() else 0))
        elif parts.path == "/api/diff":
            session = next((s for s in watch.list_sessions(project) if s.name == wanted), None)
            text, cut = watch.session_diff(project, session) if session else ("", False)
            self._json({"diff": text, "truncated": cut})
        elif parts.path == "/api/output":
            run = self.server.run_for(project, wanted)
            self._json({"output": run.output_tail() if run else "", "owned": run is not None})
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def _post_allowed(self, query: dict) -> bool:
        """Schreibende Aufrufe: Token und Host wie beim Lesen, dazu JSON als Inhalt und (falls gesendet) die eigene Herkunft.
        Eine fremde Seite kann so weder ein Formular hierher schicken noch den Token erraten."""
        if not self._allowed(query):
            return False
        port = self.server.server_address[1]
        origin = (self.headers.get("Origin") or "").strip().lower()
        if origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
            return False
        return (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() == "application/json"

    def _body(self) -> dict | None:
        length = self.headers.get("Content-Length") or ""
        if not length.isdigit() or int(length) > CHAT_BODY_LIMIT:
            return None
        try:
            data = json.loads(self.rfile.read(int(length)).decode("utf-8"))
        except (ValueError, OSError):
            return None
        return data if isinstance(data, dict) else None

    def do_POST(self):  # noqa: N802 - Name aus BaseHTTPRequestHandler
        """Schreibende API: Lauf starten, Rückfrage beantworten, anhalten, fortsetzen."""
        parts = urllib.parse.urlsplit(self.path)
        if not self._post_allowed(urllib.parse.parse_qs(parts.query)):
            self._send(403, b"forbidden", "text/plain; charset=utf-8")
            return
        data = self._body()
        if data is None:
            self._fail(400, tr("Ungültige Anfrage."))
            return
        project = self._project(data.get("project") if isinstance(data.get("project"), str) else None)
        if project is None:
            return
        session = data.get("session") if isinstance(data.get("session"), str) else None
        server = self.server
        if parts.path == "/api/project":
            remember_project(project)
            self._json({"ok": True, "project": server.info(project)})
        elif parts.path == "/api/start":
            task = data.get("task") if isinstance(data.get("task"), str) else ""
            task = task.strip()[:CHAT_TASK_LIMIT]
            if not task:
                self._fail(400, tr("Die Aufgabe fehlt."))
                return
            try:
                options = start_options(data)
            except ValueError as exc:
                self._fail(400, tr(f"Zusatzoptionen unlesbar: {exc}"))
                return
            lang = ["--lang", SETTINGS.lang] if SETTINGS.lang != "de" else []
            # Die Aufgabe steht nach "--", damit ein Text mit führendem Bindestrich nie als Option gelesen wird
            run = server.start(project, ["-p", str(project), "--no-guide", *lang, *options, "--", task], task)
            self._json({"ok": True, "run": run.run_id})
        elif parts.path == "/api/resume":
            session_dir = next((s for s in watch.list_sessions(project) if s.name == session), None)
            if session_dir is None:
                self._fail(404, tr("Sitzung nicht gefunden."))
                return
            if watch.session_summary(session_dir)["running"]:
                self._fail(409, tr("Diese Sitzung läuft noch."))
                return
            lang = ["--lang", SETTINGS.lang] if SETTINGS.lang != "de" else []
            task = str(watch.read_state(session_dir).get("task") or "")
            run = server.start(project, ["-p", str(project), "--session", session_dir.name, "--no-guide", *lang], task, session_dir.name)
            self._json({"ok": True, "run": run.run_id})
        elif parts.path in ("/api/answer", "/api/stop"):
            run = server.run_for(project, session)
            if run is None or not run.alive:
                self._fail(409, tr("Dieser Lauf wird nicht von diesem Chat gesteuert oder ist schon beendet."))
            elif parts.path == "/api/stop":
                self._json({"ok": stop_run(run)})
            else:
                value = data.get("value") if isinstance(data.get("value"), str) else None
                waiting = watch.read_live(project / ".dual-loop" / "sessions" / str(run.session)).get("waiting") or {}
                if value is None or not waiting:
                    self._fail(409, tr("Der Lauf wartet gerade auf keine Antwort."))
                else:
                    self._json({"ok": send_answer(run, value, waiting.get("id") or waiting.get("since"))})
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")


def start_chat_server(project: Path, port: int = CHAT_PORT) -> ChatServer:
    """Server im Hintergrund-Thread starten; ist der Port belegt, nimmt er einen freien."""
    try:
        server = ChatServer(project, port)
    except OSError:
        server = ChatServer(project, 0)
    threading.Thread(target=server.serve_forever, name="claudegravity-chat", daemon=True).start()
    server.refresh_setup()
    return server


def run_chat(project: Path, port: int = CHAT_PORT) -> None:
    """`claudegravity chat`: Chat-Oberfläche für das Projekt, bis Strg+C. Laufende Läufe werden beim Beenden angehalten."""
    server = start_chat_server(project, port)
    say(f"💬 Chat: {server.url}")
    say(f"   Projekt: {project} · beenden mit Strg+C")
    if not watch.can_open_browser():
        say("   Öffne die Adresse im Browser dieses Rechners.")
    watch.open_browser(server.url)
    try:
        while not SETTINGS.stop_requested:
            time.sleep(0.3)
    finally:
        stopped = server.stop_all()
        if stopped:
            say(f"⏹️ {stopped} laufende(r) Lauf/Läufe angehalten. Im Chat mit „Fortsetzen“ oder mit 'claudegravity -c' geht es weiter.")
        server.shutdown()
        server.server_close()
