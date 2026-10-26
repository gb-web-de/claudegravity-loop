"""Live-Ansicht im Browser (`claudegravity watch`, `--watch`) und Live-Stand des laufenden Loops.

Der Lauf schreibt `live.json` in den Session-Ordner (Prozess, aktueller Aufruf, offene Rückfrage) und meldet über
notify.py, wenn er auf dich wartet oder fertig ist. Die Seite liest state.json, live.json, LOG.md und den Diff des
Arbeitsbereichs. Der Server hört nur auf 127.0.0.1, verlangt einen Zufallstoken in der URL und prüft den Host-Kopf
(gegen DNS-Rebinding). Nur Standardbibliothek.
"""

import contextlib
import dataclasses
import datetime
import hmac
import http.server
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

from . import notify
from .common import SETTINGS, WAIT_HOOKS, say, tr
from .errors import LAST_ERROR
from .session import EVENT_HOOKS, task_preview

LIVE_FILE = "live.json"
DEFAULT_PORT = 8765
SESSION_LIST_LIMIT = 30
LOG_TAIL_LINES = 80
DIFF_LIMIT = 300_000
REPORT_LIMIT = 20_000


@dataclasses.dataclass
class LiveState:
    """Was der laufende Prozess über sich in live.json schreibt."""

    session_dir: Path | None = None
    task: str = ""
    started: str = ""
    activity: dict | None = None
    waiting: dict | None = None
    pull_request: str | None = None
    url: str | None = None
    ended: bool = False


LIVE = LiveState()
_LOCK = threading.Lock()
_WAIT_TIMER: threading.Timer | None = None
_HOOKS_INSTALLED = False


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


# ==========================================
# Live-Stand des laufenden Prozesses
# ==========================================
def write_live() -> None:
    """live.json atomar schreiben (für die Live-Ansicht, auch aus einem anderen Prozess)."""
    if LIVE.session_dir is None:
        return
    data = {
        "pid": os.getpid(),
        "task": task_preview(LIVE.task, 300),
        "started": LIVE.started,
        "activity": LIVE.activity,
        "waiting": LIVE.waiting,
        "pull_request": LIVE.pull_request,
        "url": LIVE.url,
        "ended": LIVE.ended,
        "updated": _now(),
    }
    target = LIVE.session_dir / LIVE_FILE
    tmp = target.with_suffix(".tmp")
    with contextlib.suppress(OSError):
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, target)


def bind(session_dir: Path, task: str) -> None:
    """Den Lauf an seine Session binden: live.json anlegen, Ereignisse und Rückfragen mitverfolgen."""
    global _HOOKS_INSTALLED
    with _LOCK:
        LIVE.session_dir, LIVE.task, LIVE.started, LIVE.ended = session_dir, task, _now(), False
        LIVE.activity = LIVE.waiting = LIVE.pull_request = None
        if not _HOOKS_INSTALLED:
            EVENT_HOOKS.append(on_event)
            WAIT_HOOKS.append(on_wait)
            _HOOKS_INSTALLED = True
        write_live()


def on_event(session_dir: Path | None, event: str, fields: dict) -> None:
    """Ereignis aus log_event(): aktueller Aufruf, Pull Request, Ende des Laufs (mit Benachrichtigung)."""
    if session_dir is None or session_dir != LIVE.session_dir:
        return
    already = True
    with _LOCK:
        if event == "call_start":
            LIVE.activity = {"kind": "call", "role": fields.get("role"), "agent": fields.get("agent"), "since": _now()}
        elif event == "proof_start":
            LIVE.activity = {"kind": "proof", "command": fields.get("command"), "since": _now()}
        elif event in ("call", "proof"):
            LIVE.activity = None
        elif event == "pull_request":
            LIVE.pull_request = fields.get("url")
        elif event == "session_end":
            already = LIVE.ended
            LIVE.activity, LIVE.ended = None, True
        else:
            return
        write_live()
    if event == "session_end" and not already:
        notify_end(bool(fields.get("success")), fields.get("abort_reason"))


def notify_end(success: bool, reason: str | None = None) -> None:
    """Meldung am Ende des Laufs: fertig (mit Pull Request) oder ohne Abschluss (mit Grund)."""
    task = task_preview(LIVE.task, 120)
    if success:
        message = tr(f"✅ Fertig: {task}") + (" · " + tr(f"Pull Request: {LIVE.pull_request}") if LIVE.pull_request else "")
        notify.send(message, "success", LIVE.pull_request or LIVE.url)
    else:
        message = tr(f"🛑 Beendet ohne Abschluss: {task}") + (f" · {tr(reason)}" if reason else "")
        notify.send(message, "failure", LIVE.url)


def notify_failure() -> None:
    """Der Lauf endet mit einem Fehlercode (sys.exit), ohne dass ein Ende gemeldet wurde."""
    if LIVE.session_dir is None or LIVE.ended:
        return
    with _LOCK:
        LIVE.ended, LIVE.activity = True, None
        write_live()
    code, detail = LAST_ERROR.get("code"), LAST_ERROR.get("detail")
    message = tr(f"🛑 Fehler {code or 'CG-1999'}: {task_preview(LIVE.task, 80)}") + (f" · {detail}" if detail else "")
    notify.send(message, "error", LIVE.url)


def on_wait(prompt: str, waiting: bool) -> None:
    """Rückfrage im Terminal: in live.json vermerken und nach einer Weile ohne Antwort benachrichtigen."""
    global _WAIT_TIMER
    if LIVE.session_dir is None:
        return
    with _LOCK:
        if _WAIT_TIMER is not None:
            _WAIT_TIMER.cancel()
            _WAIT_TIMER = None
        LIVE.waiting = {"prompt": task_preview(prompt.strip(), 300), "since": _now()} if waiting else None
        write_live()
        if waiting and notify.active():
            message = tr(f"⏳ Wartet auf dich: {task_preview(prompt.strip(), 160)}")
            _WAIT_TIMER = threading.Timer(notify.wait_delay(), notify.send, args=(message, "waiting", LIVE.url))
            _WAIT_TIMER.daemon = True
            _WAIT_TIMER.start()


# ==========================================
# Stand einer Session lesen (auch aus einem anderen Prozess)
# ==========================================
def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_state(session_dir: Path) -> dict:
    """state.json (oder .bak) ohne Ausgaben lesen."""
    return _read_json(session_dir / "state.json") or _read_json(session_dir / "state.json.bak")


def pid_alive(pid: int | None) -> bool:
    """Ob ein Prozess noch läuft (Linux/macOS über Signal 0, Windows über OpenProcess)."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def list_sessions(project: Path) -> list[Path]:
    """Session-Ordner des Projekts, neueste zuerst."""
    root = project / ".dual-loop" / "sessions"
    if not root.is_dir():
        return []
    return sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None


def diff_source(project: Path, state: dict) -> tuple[Path, list[str], bool] | None:
    """Wo der Diff des Laufs liegt: (Ordner, Revisionsangabe, mit unversionierten Dateien) oder None ohne Git."""
    wt = state.get("worktree") or {}
    base = state.get("build_base")
    if wt.get("path") and not wt.get("released") and Path(wt["path"]).is_dir():
        return Path(wt["path"]), [base or "HEAD"], True
    if wt.get("branch") and wt.get("released"):
        if wt.get("merged"):
            return None
        start = base or wt.get("base_branch") or "HEAD"
        return project, [f"{start}..{wt['branch']}"], False
    if (project / ".git").exists() and base:
        return project, [base], True
    return None


def file_changes(project: Path, state: dict) -> list[dict]:
    """Geänderte Dateien mit hinzugefügten/entfernten Zeilen; ohne Git die vom Loop geschriebenen Dateien."""
    source = diff_source(project, state)
    if source is None:
        return [{"path": p, "added": None, "removed": None} for p in (state.get("written_files") or [])[:200]]
    cwd, rev, untracked = source
    changes: list[dict] = []
    res = _git(cwd, "diff", "--numstat", *rev, "--", ".", ":(exclude).dual-loop")
    for line in (res.stdout if res and res.returncode == 0 else "").splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            added, removed, path = parts
            changes.append(
                {"path": path, "added": int(added) if added.isdigit() else None, "removed": int(removed) if removed.isdigit() else None}
            )
    if untracked:
        res = _git(cwd, "ls-files", "--others", "--exclude-standard", "--", ".", ":(exclude).dual-loop")
        for path in (res.stdout if res and res.returncode == 0 else "").splitlines():
            changes.append({"path": path, "added": None, "removed": None, "new": True})
    return changes[:500]


def session_diff(project: Path, session_dir: Path) -> tuple[str, bool]:
    """Diff des Laufs als Text (begrenzt); neue Dateien erscheinen als Liste. Liefert (Text, gekürzt)."""
    state = read_state(session_dir)
    source = diff_source(project, state)
    if source is None:
        return "", False
    cwd, rev, untracked = source
    res = _git(cwd, "diff", "--no-color", "--no-ext-diff", *rev, "--", ".", ":(exclude).dual-loop")
    text = res.stdout if res and res.returncode == 0 else ""
    if untracked:
        new = _git(cwd, "ls-files", "--others", "--exclude-standard", "--", ".", ":(exclude).dual-loop")
        names = (new.stdout if new and new.returncode == 0 else "").split()
        if names:
            text += "\n" + tr("Neue Dateien (noch nicht im Diff):") + "\n" + "\n".join(f"+ {n}" for n in names) + "\n"
    return text[:DIFF_LIMIT], len(text) > DIFF_LIMIT


def _tail(path: Path, lines: int) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except OSError:
        return []


def session_summary(session_dir: Path) -> dict:
    """Kurzform für die Auswahlliste: Name, Phase, Aufgabe, läuft noch."""
    state, live = read_state(session_dir), _read_json(session_dir / LIVE_FILE)
    return {
        "name": session_dir.name,
        "phase": state.get("phase"),
        "task": task_preview(state.get("task") or "", 80),
        "running": pid_alive(live.get("pid")) and not live.get("ended"),
        "done": (session_dir / ".done").exists(),
    }


def session_snapshot(project: Path, session_dir: Path) -> dict:
    """Alles, was die Live-Ansicht zu einer Session zeigt."""
    state, live = read_state(session_dir), _read_json(session_dir / LIVE_FILE)
    metrics = state.get("metrics") or {}
    roles = [
        {
            "role": v.get("role"),
            "agent": v.get("agent_name"),
            "model": v.get("model"),
            "calls": v.get("calls"),
            "tokens": v.get("total_tokens"),
            "cost_usd": v.get("cost_usd"),
        }
        for v in (metrics.get("by_agent") or {}).values()
        if isinstance(v, dict)
    ]
    report_file = session_dir / (".done" if (session_dir / ".done").exists() else "AUDIT.md")
    try:
        report = report_file.read_text(encoding="utf-8", errors="replace")[:REPORT_LIMIT]
    except OSError:
        report = ""
    stages = state.get("stages") or []
    pull_request = (state.get("pull_request") or {}).get("url") or live.get("pull_request")
    return {
        "name": session_dir.name,
        "task": state.get("task") or live.get("task") or "",
        "phase": state.get("phase"),
        "strategy": state.get("strategy"),
        "iteration": state.get("last_iteration"),
        "max_iterations": state.get("max_iterations") or state.get("iteration_limit"),
        "stage": (int(state.get("stage_index", 0)) + 1) if stages else None,
        "stages": len(stages) or None,
        "tokens": metrics.get("total_tokens", 0),
        "cost_usd": metrics.get("cost_usd", 0),
        "roles": roles,
        "updated_at": state.get("updated_at"),
        "created_at": state.get("created_at"),
        "abort_reason": state.get("abort_reason"),
        "done": (session_dir / ".done").exists(),
        "running": pid_alive(live.get("pid")) and not live.get("ended"),
        "activity": live.get("activity"),
        "waiting": live.get("waiting") if pid_alive(live.get("pid")) else None,
        "pull_request": pull_request if isinstance(pull_request, str) and pull_request.startswith("https://") else None,
        "branch": (state.get("worktree") or {}).get("branch"),
        "proof": state.get("proof"),
        "files": file_changes(project, state),
        "log": _tail(session_dir / "LOG.md", LOG_TAIL_LINES),
        "report": report,
    }


def status_payload(project: Path, wanted: str | None) -> dict:
    """Antwort von /api/status: Sessions zur Auswahl und die gewählte (sonst die neueste) im Detail."""
    sessions = list_sessions(project)[:SESSION_LIST_LIMIT]
    chosen = next((s for s in sessions if s.name == wanted), sessions[0] if sessions else None)
    return {
        "lang": SETTINGS.lang,
        "project": str(project),
        "now": _now(),
        "sessions": [session_summary(s) for s in sessions],
        "session": session_snapshot(project, chosen) if chosen else None,
    }


# ==========================================
# HTTP-Server
# ==========================================
class WatchServer(http.server.ThreadingHTTPServer):
    """Server der Live-Ansicht für ein Projekt; nur 127.0.0.1, Zugriff nur mit Token."""

    daemon_threads = True

    def __init__(self, project: Path, port: int):
        self.project = project
        self.token = secrets.token_urlsafe(18)
        super().__init__(("127.0.0.1", port), WatchHandler)

    @property
    def url(self) -> str:
        """Adresse der Seite samt Token."""
        return f"http://127.0.0.1:{self.server_address[1]}/?t={self.token}"


class WatchHandler(http.server.BaseHTTPRequestHandler):
    """GET / (Seite), /api/status, /api/diff; alles andere 404."""

    server: WatchServer

    def log_message(self, format, *args):  # noqa: A002 - Name aus BaseHTTPRequestHandler
        """Keine Zugriffszeilen im Terminal (der Lauf schreibt dort seine Ausgaben)."""

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: dict) -> None:
        self._send(200, json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8")

    def _allowed(self, query: dict) -> bool:
        port = self.server.server_address[1]
        host = (self.headers.get("Host") or "").strip().lower()
        if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return False
        token = (query.get("t") or [""])[0]
        return hmac.compare_digest(token.encode(), self.server.token.encode())

    def do_GET(self):  # noqa: N802 - Name aus BaseHTTPRequestHandler
        """Seite und API; ohne passenden Host-Kopf oder Token 403."""
        parts = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parts.query)
        if not self._allowed(query):
            self._send(403, b"forbidden", "text/plain; charset=utf-8")
            return
        wanted = (query.get("session") or [None])[0]
        project = self.server.project
        if parts.path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif parts.path == "/api/status":
            self._json(status_payload(project, wanted))
        elif parts.path == "/api/diff":
            session = next((s for s in list_sessions(project) if s.name == wanted), None)
            text, cut = session_diff(project, session) if session else ("", False)
            self._json({"diff": text, "truncated": cut})
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")


def start_server(project: Path, port: int = DEFAULT_PORT) -> WatchServer:
    """Server im Hintergrund-Thread starten; ist der Port belegt, nimmt er einen freien."""
    try:
        server = WatchServer(project, port)
    except OSError:
        server = WatchServer(project, 0)
    threading.Thread(target=server.serve_forever, name="claudegravity-watch", daemon=True).start()
    return server


def can_open_browser() -> bool:
    """Nur mit grafischer Oberfläche: unter Linux ohne Anzeige würde webbrowser einen Text-Browser im Terminal starten."""
    if os.environ.get("CLAUDEGRAVITY_NO_BROWSER"):
        return False
    return sys.platform in ("darwin", "win32") or bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def open_browser(url: str) -> None:
    """Seite im Standard-Browser öffnen, wenn das geht."""
    if can_open_browser():
        with contextlib.suppress(Exception):
            webbrowser.open(url)


def start_for_run(project: Path, port: int = DEFAULT_PORT) -> str:
    """--watch: Live-Ansicht neben dem Lauf; liefert die URL (steht auch im Kopf des Laufs und in live.json)."""
    server = start_server(project, port)
    LIVE.url = server.url
    write_live()
    open_browser(server.url)
    return server.url


def current_url() -> str | None:
    """URL der Live-Ansicht dieses Laufs (mit --watch), sonst None."""
    return LIVE.url


def run_watch(project: Path, port: int = DEFAULT_PORT) -> None:
    """`claudegravity watch`: Live-Ansicht für die Sessions des Projekts, bis Strg+C."""
    server = start_server(project, port)
    say(f"👀 Live-Ansicht: {server.url}")
    say(f"   Projekt: {project} · beenden mit Strg+C")
    if not list_sessions(project):
        say("   Noch keine Session; die Seite zeigt sie, sobald ein Lauf startet.")
    open_browser(server.url)
    try:
        while not SETTINGS.stop_requested:
            time.sleep(0.3)
    finally:
        server.shutdown()
        server.server_close()


PAGE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ClaudeGravity Live</title>
<style>
:root { --bg:#f7f7f5; --card:#ffffff; --fg:#1d1d1b; --muted:#6b6b66; --line:#e3e2dd; --accent:#3d5afe;
  --ok:#1b7f3b; --bad:#b3261e; --warn:#8a5a00; --warnbg:#fff4d6; --add:#e6f4ea; --del:#fdecea; --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
@media (prefers-color-scheme: dark) { :root { --bg:#151514; --card:#1f1f1d; --fg:#ecebe6; --muted:#a3a29b; --line:#33332f;
  --accent:#8c9eff; --ok:#6fcf8f; --bad:#f28b82; --warn:#f6c26b; --warnbg:#3a2f12; --add:#1d3324; --del:#3b1f1d; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1040px; margin: 0 auto; padding: 20px 16px 48px; }
header { display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between; margin-bottom:16px; }
h1 { font-size:18px; margin:0; letter-spacing:.2px; }
h2 { font-size:14px; text-transform:uppercase; letter-spacing:.6px; color:var(--muted); margin:0 0 8px; }
select, button { font:inherit; color:var(--fg); background:var(--card); border:1px solid var(--line); border-radius:8px; padding:6px 10px; max-width:100%; }
button { cursor:pointer; }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; margin-bottom:14px; }
.task { font-size:17px; font-weight:600; margin:0 0 10px; overflow-wrap:anywhere; }
.grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:10px; }
.kv { border:1px solid var(--line); border-radius:10px; padding:8px 10px; }
.kv b { display:block; font-size:12px; color:var(--muted); font-weight:500; }
.kv span { font-size:16px; font-variant-numeric: tabular-nums; overflow-wrap:anywhere; }
.kv.mono span { font: 13.5px/1.4 var(--mono); }
@media (max-width: 560px) { table { font-size:13px; } th, td { padding:5px 4px; } .hide-s { display:none; } }
.badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:13px; border:1px solid var(--line); }
.badge.ok { color:var(--ok); border-color:var(--ok); } .badge.bad { color:var(--bad); border-color:var(--bad); }
.badge.run { color:var(--accent); border-color:var(--accent); }
.banner { border-radius:10px; padding:10px 12px; margin-bottom:12px; background:var(--warnbg); color:var(--warn); font-weight:600; overflow-wrap:anywhere; }
.activity { color:var(--accent); margin:8px 0 0; }
table { width:100%; border-collapse:collapse; font-size:14px; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; overflow-wrap:break-word; }
th { color:var(--muted); font-weight:500; }
td.num, th.num { text-align:right; font-variant-numeric: tabular-nums; white-space:nowrap; }
.plus { color:var(--ok); } .minus { color:var(--bad); }
pre { margin:0; font: 12.5px/1.45 var(--mono); white-space:pre-wrap; overflow-wrap:anywhere; max-height:440px; overflow:auto; }
pre .a { background:var(--add); display:block; } pre .d { background:var(--del); display:block; } pre .h { color:var(--muted); display:block; }
.muted { color:var(--muted); } a { color:var(--accent); }
.scroll { overflow-x:auto; }
.row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.err { color:var(--bad); }
</style>
</head>
<body>
<main>
  <header>
    <h1>ClaudeGravity Live</h1>
    <div class="row"><select id="sessions" aria-label="Session"></select></div>
  </header>
  <p id="error" class="err" hidden></p>
  <p id="empty" class="muted" hidden></p>
  <div id="view" hidden>
    <div id="waiting" class="banner" hidden></div>
    <section class="card">
      <p id="task" class="task"></p>
      <div class="row"><span id="state" class="badge"></span><span id="name" class="muted"></span></div>
      <p id="activity" class="activity" hidden></p>
      <p id="reason" class="err" hidden></p>
      <p id="pr" hidden></p>
    </section>
    <section class="card"><div class="grid" id="facts"></div></section>
    <section class="card"><h2 id="h-roles"></h2><div class="scroll"><table><thead><tr><th id="th-role"></th><th id="th-agent"></th><th class="num hide-s" id="th-calls"></th><th class="num" id="th-tokens"></th><th class="num">USD</th></tr></thead><tbody id="roles"></tbody></table></div></section>
    <section class="card"><div class="row" style="justify-content:space-between"><h2 id="h-files"></h2><button id="diffbtn" type="button"></button></div>
      <table><tbody id="files"></tbody></table><pre id="diff" hidden></pre></section>
    <section class="card"><h2>LOG.md</h2><pre id="log"></pre></section>
    <section class="card" id="report-card" hidden><h2 id="h-report"></h2><pre id="report"></pre></section>
  </div>
</main>
<script>
"use strict";
const L = {
  de: { roles:"Rollen", role:"Rolle", agent:"Anbieter / Modell", calls:"Aufrufe", tokens:"Tokens", files:"Geänderte Dateien",
    showDiff:"Diff zeigen", hideDiff:"Diff ausblenden", report:"Bericht", phase:"Phase", round:"Bau-Runde", stage:"Etappe",
    cost:"Kosten (gemeldet)", updated:"Aktualisiert", strategy:"Strategie", proof:"Prüfbefehl", branch:"Branch",
    running:"läuft", done:"fertig", ended:"beendet", stopped:"nicht aktiv", waiting:"⏳ Wartet auf dich im Terminal: ",
    works:" arbeitet seit ", proofRuns:"🧪 Prüfbefehl läuft seit ", noSessions:"Noch keine Session in diesem Projekt. Die Seite aktualisiert sich von selbst.",
    noFiles:"Noch keine Änderungen.", newFile:"neu", reason:"Abbruchgrund: ", pr:"Pull Request: ", offline:"Keine Verbindung zum Loop (Server beendet?).",
    truncated:"… gekürzt", emptyDiff:"Kein Diff.",
    phases:{plan:"Plan", review:"Review", build:"Bau", inspection_open:"Abnahme offen", stage_open:"Etappe offen", completed:"abgeschlossen", candidates:"Kandidaten"},
    roleNames:{planner:"🏗️ Architekt", reviewer:"🧐 Prüfstatiker", builder:"🔨 Bauleiter", inspector:"🔎 Abnahme"} },
  en: { roles:"Roles", role:"Role", agent:"Provider / model", calls:"Calls", tokens:"Tokens", files:"Changed files",
    showDiff:"Show diff", hideDiff:"Hide diff", report:"Report", phase:"Phase", round:"Build round", stage:"Stage",
    cost:"Cost (reported)", updated:"Updated", strategy:"Strategy", proof:"Proof command", branch:"Branch",
    running:"running", done:"done", ended:"ended", stopped:"not active", waiting:"⏳ Waiting for you in the terminal: ",
    works:" working for ", proofRuns:"🧪 Proof command running for ", noSessions:"No session in this project yet. The page updates by itself.",
    noFiles:"No changes yet.", newFile:"new", reason:"Abort reason: ", pr:"Pull request: ", offline:"No connection to the loop (server stopped?).",
    truncated:"… truncated", emptyDiff:"No diff.",
    phases:{plan:"Plan", review:"Review", build:"Build", inspection_open:"Acceptance open", stage_open:"Stage open", completed:"completed", candidates:"Candidates"},
    roleNames:{planner:"🏗️ Architect", reviewer:"🧐 Reviewer", builder:"🔨 Builder", inspector:"🔎 Acceptance"} }
};
const token = new URLSearchParams(location.search).get("t") || "";
let T = L.de, chosen = null, diffOpen = false, lastNow = null, ticks = 0;
const $ = (id) => document.getElementById(id);
function api(path, extra) {
  const q = new URLSearchParams(Object.assign({ t: token }, extra || {}));
  return fetch(path + "?" + q.toString(), { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
}
function el(tag, text, cls) { const e = document.createElement(tag); if (text !== undefined && text !== null) e.textContent = String(text); if (cls) e.className = cls; return e; }
function num(n) { return (n === null || n === undefined) ? "–" : Number(n).toLocaleString(T === L.de ? "de-DE" : "en-US"); }
function since(iso) {
  if (!iso || !lastNow) return "";
  const s = Math.max(0, Math.round((new Date(lastNow) - new Date(iso)) / 1000));
  const m = Math.floor(s / 60), r = s % 60;
  return m >= 60 ? Math.floor(m / 60) + " h " + (m % 60) + " min" : (m ? m + ":" + String(r).padStart(2, "0") + " min" : s + " s");
}
function fact(label, value, mono) { const d = el("div", null, mono ? "kv mono" : "kv"); d.append(el("b", label), el("span", value)); return d; }
function renderSessions(list) {
  const sel = $("sessions"), keep = chosen;
  sel.replaceChildren(...list.map((s) => { const o = el("option", (s.running ? "● " : "") + s.name); o.value = s.name; return o; }));
  if (keep && list.some((s) => s.name === keep)) sel.value = keep;
}
function render(data) {
  T = L[data.lang] || L.de; document.documentElement.lang = data.lang === "en" ? "en" : "de"; lastNow = data.now;
  $("error").hidden = true;
  renderSessions(data.sessions);
  const s = data.session;
  if (!s) { $("view").hidden = true; $("empty").hidden = false; $("empty").textContent = T.noSessions; return; }
  $("empty").hidden = true; $("view").hidden = false;
  $("task").textContent = s.task;
  $("name").textContent = s.name;
  const st = $("state");
  if (s.running) { st.textContent = T.running + " · " + (T.phases[s.phase] || s.phase || "–"); st.className = "badge run"; }
  else if (s.done || s.phase === "completed") { st.textContent = T.done; st.className = "badge ok"; }
  else { st.textContent = (T.phases[s.phase] || s.phase || "–") + " · " + (s.abort_reason ? T.ended : T.stopped); st.className = s.abort_reason ? "badge bad" : "badge"; }
  $("waiting").hidden = !s.waiting; if (s.waiting) $("waiting").textContent = T.waiting + s.waiting.prompt;
  const a = s.running ? s.activity : null;
  $("activity").hidden = !a;
  if (a) $("activity").textContent = a.kind === "proof" ? T.proofRuns + since(a.since) + " · " + (a.command || "") : ((T.roleNames[a.role] || a.role || "") + " (" + (a.agent || "") + ")" + T.works + since(a.since));
  $("reason").hidden = !s.abort_reason || s.phase === "completed"; if (s.abort_reason) $("reason").textContent = T.reason + s.abort_reason;
  const pr = $("pr"); pr.hidden = !s.pull_request; pr.replaceChildren();
  if (s.pull_request) { const link = el("a", s.pull_request); link.href = s.pull_request; link.target = "_blank"; link.rel = "noopener noreferrer"; pr.append(T.pr, link); }
  const facts = [fact(T.phase, T.phases[s.phase] || s.phase || "–"),
    fact(T.round, s.iteration ? s.iteration + (s.max_iterations ? " / " + s.max_iterations : "") : "–"),
    fact(T.tokens, num(s.tokens)), fact(T.cost, s.cost_usd ? Number(s.cost_usd).toFixed(2) + " USD" : "–")];
  if (s.stages) facts.splice(2, 0, fact(T.stage, s.stage + " / " + s.stages));
  if (s.strategy) facts.push(fact(T.strategy, s.strategy));
  if (s.branch) facts.push(fact(T.branch, s.branch));
  if (s.proof) facts.push(fact(T.proof, s.proof, true));
  facts.push(fact(T.updated, (s.updated_at || "").replace("T", " ").slice(0, 19)));
  $("facts").replaceChildren(...facts);
  $("h-roles").textContent = T.roles; $("th-role").textContent = T.role; $("th-agent").textContent = T.agent; $("th-calls").textContent = T.calls; $("th-tokens").textContent = T.tokens;
  $("roles").replaceChildren(...s.roles.map((r) => { const tr = el("tr"); tr.append(el("td", (r.role || "").replace(/\s*\(.*\)\s*$/, "")), el("td", (r.agent || "") + (r.model ? " · " + r.model : "")), el("td", num(r.calls), "num hide-s"), el("td", num(r.tokens), "num"), el("td", r.cost_usd ? Number(r.cost_usd).toFixed(2) : "–", "num")); return tr; }));
  $("h-files").textContent = T.files + " (" + s.files.length + ")"; $("diffbtn").textContent = diffOpen ? T.hideDiff : T.showDiff;
  $("files").replaceChildren(...(s.files.length ? s.files.map((f) => { const tr = el("tr"); const c = el("td", null, "num");
      if (f.new) c.append(el("span", T.newFile, "plus")); else { c.append(el("span", f.added === null ? "" : "+" + f.added, "plus"), " ", el("span", f.removed === null ? "" : "−" + f.removed, "minus")); }
      tr.append(el("td", f.path), c); return tr; }) : [(() => { const tr = el("tr"); tr.append(el("td", T.noFiles, "muted")); return tr; })()]));
  const log = $("log"), atEnd = log.scrollTop + log.clientHeight >= log.scrollHeight - 8;
  log.textContent = s.log.join("\n"); if (atEnd) log.scrollTop = log.scrollHeight;
  $("report-card").hidden = !s.report; $("h-report").textContent = T.report + (s.done ? " (.done)" : " (AUDIT.md)"); $("report").textContent = s.report;
  if (diffOpen && ++ticks % 5 === 0) loadDiff();
}
function loadDiff() {
  if (!chosen) return;
  api("/api/diff", { session: chosen }).then((d) => {
    const pre = $("diff"); pre.hidden = false;
    const lines = (d.diff || "").split("\n");
    pre.replaceChildren(...(d.diff ? lines.map((line) => el("span", line + "\n", line.startsWith("+") && !line.startsWith("+++") ? "a" : (line.startsWith("-") && !line.startsWith("---") ? "d" : (line.startsWith("@@") || line.startsWith("diff ") ? "h" : "")))) : [el("span", T.emptyDiff, "h")]));
    if (d.truncated) pre.append(el("span", T.truncated, "h"));
  }).catch(() => {});
}
function refresh() {
  api("/api/status", chosen ? { session: chosen } : {}).then((d) => { if (!chosen && d.session) chosen = d.session.name; render(d); })
    .catch(() => { $("error").hidden = false; $("error").textContent = T.offline; });
}
$("sessions").addEventListener("change", (e) => { chosen = e.target.value; diffOpen = false; $("diff").hidden = true; refresh(); });
$("diffbtn").addEventListener("click", () => { diffOpen = !diffOpen; $("diffbtn").textContent = diffOpen ? T.hideDiff : T.showDiff; if (diffOpen) loadDiff(); else $("diff").hidden = true; });
refresh(); setInterval(refresh, 2000);
</script>
</body>
</html>
"""
