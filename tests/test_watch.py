"""Live-Ansicht (claudegravity watch, --watch) und Benachrichtigungen (--notify)."""

import contextlib
import http.server
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "smoke"))

import loop  # noqa: E402
import run_smoke  # noqa: E402
from claudegravity import common, notify, session, watch  # noqa: E402

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@contextlib.contextmanager
def settings(**values):
    old = {k: getattr(common.SETTINGS, k) for k in values}
    for k, v in values.items():
        setattr(common.SETTINGS, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(common.SETTINGS, k, v)


@contextlib.contextmanager
def fresh_live():
    """LIVE-Zustand und Hooks nach dem Test zurücksetzen."""
    saved = watch.LIVE
    watch.LIVE = watch.LiveState()
    try:
        yield watch.LIVE
    finally:
        if watch._WAIT_TIMER is not None:
            watch._WAIT_TIMER.cancel()
        watch.LIVE = saved


class Collector:
    """Kleiner HTTP-Server, der POST-Bodys sammelt (für ntfy und Webhooks)."""

    def __init__(self):
        received = self.received = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                received.append((self.path, dict(self.headers), json.loads(body)))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class ChannelTest(unittest.TestCase):
    def test_parse_channels(self):
        found, problems = notify.parse_channels(
            "desktop, bell,ntfy:mein-thema,ntfy:https://ntfy.example.org/team_1,webhook:https://hooks.example/x/y"
        )
        self.assertEqual(
            found,
            [
                ("desktop", ""),
                ("bell", ""),
                ("ntfy", "https://ntfy.sh/mein-thema"),
                ("ntfy", "https://ntfy.example.org/team_1"),
                ("webhook", "https://hooks.example/x/y"),
            ],
        )
        self.assertEqual(problems, [])
        found, problems = notify.parse_channels("ntfy:../böse,webhook:file:///etc/passwd,sms")
        self.assertEqual(found, [])
        self.assertEqual(len(problems), 3)
        for off in ("", "aus", "off", None):
            self.assertEqual(notify.parse_channels(off), ([], []))

    def test_redact_hides_topic_and_webhook_path(self):
        shown = notify.redact("desktop,ntfy:geheimes-thema,webhook:https://hooks.slack.com/services/T0/B0/XYZ")
        self.assertEqual(shown, "desktop,ntfy:ge…,webhook:https://hooks.slack.com/…")
        self.assertNotIn("XYZ", shown)

    def test_desktop_command_never_puts_text_into_a_script(self):
        text = '"; do shell script "rm -rf ~" --'
        with mock.patch.object(notify.sys, "platform", "darwin"):
            cmd, env = notify.desktop_command("ClaudeGravity", text)
        self.assertEqual(cmd[0], "osascript")
        self.assertEqual(cmd[-1], text)
        self.assertTrue(all(text not in part for part in cmd[:-1]))
        with mock.patch.object(notify.sys, "platform", "linux"), mock.patch.object(notify.os, "name", "nt"):
            cmd, env = notify.desktop_command("ClaudeGravity", text)
        self.assertEqual(env["CG_NOTIFY_TEXT"], text)
        self.assertTrue(all(text not in part for part in cmd))
        with (
            mock.patch.object(notify.sys, "platform", "linux"),
            mock.patch.object(notify.os, "name", "posix"),
            mock.patch.object(notify.shutil, "which", return_value=None),
        ):
            self.assertIsNone(notify.desktop_command("t", "m"))

    def test_ntfy_and_webhook_payloads(self):
        hub = Collector()
        try:
            spec = f"ntfy:{hub.url}/mein-thema,webhook:{hub.url}/hook"
            with (
                settings(notify=spec),
                mock.patch.dict(os.environ, {"CLAUDEGRAVITY_NTFY_TOKEN": "tk_123"}),
                mock.patch.object(notify.urllib.request, "urlopen", NO_PROXY.open),
            ):
                sent = notify.send("✅ Fertig mit sk-ant-api03-" + "a" * 40, "success", "https://github.com/o/r/pull/1")
        finally:
            hub.close()
        self.assertEqual(sent, 2)
        (p1, h1, ntfy_body), (p2, _h2, hook_body) = sorted(hub.received, key=lambda r: r[0])
        self.assertEqual(p1, "/")
        self.assertEqual(ntfy_body["topic"], "mein-thema")
        self.assertEqual(ntfy_body["click"], "https://github.com/o/r/pull/1")
        self.assertEqual(h1.get("Authorization"), "Bearer tk_123")
        self.assertNotIn("a" * 40, ntfy_body["message"])
        self.assertEqual(p2, "/hook")
        self.assertIn("Fertig", hook_body["text"])
        self.assertEqual(hook_body["content"], hook_body["text"])
        self.assertEqual(hook_body["event"], "success")

    def test_failed_delivery_warns_once_and_never_raises(self):
        out = io.StringIO()
        notify._WARNED.clear()
        with settings(notify="webhook:http://127.0.0.1:9/x"), contextlib.redirect_stdout(out):
            self.assertEqual(notify.send("a"), 0)
            self.assertEqual(notify.send("b"), 0)
        self.assertEqual(out.getvalue().count("fehlgeschlagen"), 1)
        self.assertNotIn("/x", out.getvalue())


class LiveStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.session = Path(self.tmp.name) / "s1"
        self.session.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def live(self) -> dict:
        return json.loads((self.session / watch.LIVE_FILE).read_text(encoding="utf-8"))

    def test_events_update_live_file_and_notify_at_the_end(self):
        sent = []
        with fresh_live(), settings(notify="bell"), mock.patch.object(notify, "send", side_effect=lambda *a, **k: sent.append(a)):
            watch.bind(self.session, "Addition mit Test")
            self.assertEqual(self.live()["pid"], os.getpid())
            session.log_event(self.session, "call_start", role="builder", agent="claude")
            self.assertEqual(self.live()["activity"]["role"], "builder")
            session.log_event(self.session, "call", role="builder", agent="claude")
            self.assertIsNone(self.live()["activity"])
            session.log_event(Path(self.tmp.name) / "fremd", "call_start", role="planner", agent="x")
            self.assertIsNone(self.live()["activity"])
            session.log_event(self.session, "pull_request", url="https://github.com/o/r/pull/7")
            session.log_event(self.session, "session_end", success=True)
            session.log_event(self.session, "session_end", success=True)
        self.assertTrue(self.live()["ended"])
        self.assertEqual(len(sent), 1)
        self.assertIn("Addition mit Test", sent[0][0])
        self.assertIn("pull/7", sent[0][0])
        self.assertEqual(sent[0][2], "https://github.com/o/r/pull/7")

    def test_waiting_prompt_is_shown_and_notified(self):
        sent = threading.Event()
        with (
            fresh_live(),
            settings(notify="bell"),
            mock.patch.dict(os.environ, {"CLAUDEGRAVITY_NOTIFY_WAIT": "0"}),
            mock.patch.object(notify, "send", side_effect=lambda *a, **k: sent.set()),
        ):
            watch.bind(self.session, "Aufgabe")
            seen = {}

            def fake_input(prompt):
                seen.update(self.live()["waiting"] or {})
                self.assertTrue(sent.wait(5))
                return "j"

            with mock.patch("builtins.input", side_effect=fake_input):
                self.assertEqual(common.ask("Plan freigeben? [J/n]: "), "j")
        self.assertIn("Plan freigeben", seen.get("prompt", ""))
        self.assertIsNone(self.live()["waiting"])

    def test_failure_after_fail_is_notified(self):
        sent = []
        with fresh_live(), settings(notify="bell"), mock.patch.object(notify, "send", side_effect=lambda *a, **k: sent.append(a)):
            watch.bind(self.session, "Aufgabe")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                loop.fail("CG-1701", "docker ist nicht installiert")
            watch.notify_failure()
            watch.notify_failure()
        self.assertEqual(len(sent), 1)
        self.assertIn("CG-1701", sent[0][0])


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env={**os.environ, **GIT_ENV})


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "proj"
        self.project.mkdir()
        git(self.project, "init", "-q")
        (self.project / "a.py").write_text("x = 1\n", encoding="utf-8")
        git(self.project, "add", "-A")
        git(self.project, "commit", "-qm", "start")
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.project, capture_output=True, text=True).stdout.strip()
        (self.project / "a.py").write_text("x = 2\ny = 3\n", encoding="utf-8")
        (self.project / "neu.py").write_text("z = 1\n", encoding="utf-8")
        sessions = self.project / ".dual-loop" / "sessions"
        self.old, self.new = sessions / "20261026_010000_alt", sessions / "20261026_020000_neu"
        for s in (self.old, self.new):
            s.mkdir(parents=True)
        (self.project / ".gitignore").write_text(".dual-loop/\n", encoding="utf-8")
        state = {
            "task": "Zahl erhöhen <script>alert(1)</script>",
            "phase": "build",
            "last_iteration": 2,
            "max_iterations": 10,
            "build_base": base,
            "worktree": {"enabled": False},
            "metrics": {
                "total_tokens": 1234,
                "cost_usd": 0.5,
                "by_agent": {"x": {"role": "🔨 Bauleiter", "agent_name": "claude", "calls": 2, "total_tokens": 1000}},
            },
        }
        (self.new / "state.json").write_text(json.dumps(state), encoding="utf-8")
        (self.new / "LOG.md").write_text("- [01:00:00] Runde 2\n", encoding="utf-8")
        (self.new / watch.LIVE_FILE).write_text(
            json.dumps(
                {"pid": os.getpid(), "activity": {"kind": "call", "role": "builder", "agent": "claude", "since": "2026-10-26T02:00:00"}}
            ),
            encoding="utf-8",
        )
        (self.old / "state.json").write_text(json.dumps({"task": "Alt", "phase": "completed"}), encoding="utf-8")
        (self.old / ".done").write_text("fertig", encoding="utf-8")
        self.server = watch.start_server(self.project, 0)
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def get(self, path: str, host: str | None = None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers={"Host": host} if host else {})
        try:
            with NO_PROXY.open(req, timeout=10) as res:
                return res.status, res.headers, res.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers, ""

    def test_token_and_host_are_required(self):
        t = self.server.token
        self.assertEqual(self.get("/")[0], 403)
        self.assertEqual(self.get("/?t=falsch")[0], 403)
        self.assertEqual(self.get(f"/?t={t}", host=f"evil.example:{self.port}")[0], 403)
        status, headers, body = self.get(f"/?t={t}")
        self.assertEqual(status, 200)
        self.assertIn("ClaudeGravity Live", body)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.get(f"/nix?t={t}")[0], 404)
        self.assertTrue(self.server.url.startswith(f"http://127.0.0.1:{self.port}/?t="))

    def test_status_shows_newest_session_with_files(self):
        status, _h, body = self.get(f"/api/status?t={self.server.token}")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual([s["name"] for s in data["sessions"]], [self.new.name, self.old.name])
        s = data["session"]
        self.assertEqual((s["name"], s["phase"], s["iteration"], s["tokens"]), (self.new.name, "build", 2, 1234))
        self.assertTrue(s["running"])
        self.assertEqual(s["activity"]["agent"], "claude")
        files = {f["path"]: f for f in s["files"]}
        self.assertEqual((files["a.py"]["added"], files["a.py"]["removed"]), (2, 1))
        self.assertTrue(files["neu.py"]["new"])
        self.assertNotIn(".gitignore", "".join(p for p in files if p.startswith(".dual-loop")))
        self.assertEqual(s["log"], ["- [01:00:00] Runde 2"])
        old = json.loads(self.get(f"/api/status?t={self.server.token}&session={self.old.name}")[2])["session"]
        self.assertTrue(old["done"])
        self.assertEqual(old["report"], "fertig")

    def test_diff_only_for_known_sessions(self):
        t = self.server.token
        data = json.loads(self.get(f"/api/diff?t={t}&session={self.new.name}")[2])
        self.assertIn("+x = 2", data["diff"])
        self.assertIn("neu.py", data["diff"])
        for bad in ("../../..", "..%2F..%2Fetc", ""):
            self.assertEqual(json.loads(self.get(f"/api/diff?t={t}&session={bad}")[2])["diff"], "")


class ConfigTest(unittest.TestCase):
    def test_flags_dry_run_and_profile(self):
        parsed = loop.load_cli_config(["x", "--watch", "--watch-port", "9000", "--notify", "desktop,webhook:https://hooks.example/geheim"])
        args = parsed[1]
        self.assertTrue(args.watch)
        cmd = loop.dry_run_command(args, "x", "balanced")
        self.assertIn("--watch", cmd)
        self.assertEqual(cmd[cmd.index("--watch-port") + 1], "9000")
        self.assertEqual(cmd[cmd.index("--notify") + 1], "desktop,webhook:https://hooks.example/…")
        self.assertIn("notify", loop.PROJECT_PROFILE_FORBIDDEN)

    def test_candidates_do_not_notify(self):
        from claudegravity import candidates

        args = loop.load_cli_config(["x"])[1]
        with mock.patch.dict(os.environ, {"CLAUDEGRAVITY_NOTIFY": "desktop", "CLAUDEGRAVITY_WATCH": "1"}):
            env = candidates.child_env(args)
        self.assertEqual((env["CLAUDEGRAVITY_NOTIFY"], env["CLAUDEGRAVITY_WATCH"]), ("aus", "false"))

    def test_watch_subcommand(self):
        argv = ["claudegravity", "watch", "-p", tempfile.gettempdir(), "--watch-port", "0"]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(watch, "run_watch") as run_watch,
            mock.patch.object(loop.cli, "setup_agents") as agents,
        ):
            loop.main()
        run_watch.assert_called_once_with(Path(tempfile.gettempdir()).resolve(), 0)
        agents.assert_not_called()


class SmokeTest(unittest.TestCase):
    def test_full_run_with_watch_and_webhook(self):
        hub = Collector()
        try:
            env_extra = {"CLAUDEGRAVITY_NO_BROWSER": "1", "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}
            result = run_smoke_with_env(["--watch", "--watch-port", "0", "--notify", f"webhook:{hub.url}/hook"], env_extra)
            deadline = time.monotonic() + 5
            while not hub.received and time.monotonic() < deadline:
                time.sleep(0.1)
        finally:
            hub.close()
        self.assertEqual(result["returncode"], 0, result.get("stdout", "")[-2000:])
        self.assertIn("Live-Ansicht      : http://127.0.0.1:", result["stdout"])
        self.assertIn("Benachrichtigung  : webhook:http://127.0.0.1", result["stdout"])
        self.assertEqual(len(hub.received), 1)
        self.assertEqual(hub.received[0][2]["event"], "success")
        self.assertIn("Addition mit Test", hub.received[0][2]["message"])
        live = json.loads(result["live"])
        self.assertTrue(live["ended"])
        self.assertTrue(live["url"].startswith("http://127.0.0.1:"))


def run_smoke_with_env(extra: list[str], env_extra: dict) -> dict:
    """Ganzer Lauf mit dem Fake-Server aus run_smoke, mit zusätzlichen Optionen und Umgebung."""
    server, url = run_smoke.start_server()
    try:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            project = tmp / "projekt"
            project.mkdir()
            (tmp / "leer").mkdir()
            env = {**run_smoke.smoke_env(tmp), **env_extra}
            res = subprocess.run(
                run_smoke.smoke_command(project, url, "balanced", extra),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                stdin=subprocess.DEVNULL,
            )
            sessions = sorted((project / ".dual-loop" / "sessions").iterdir())
            live = (sessions[-1] / watch.LIVE_FILE).read_text(encoding="utf-8") if sessions else "{}"
            return {"returncode": res.returncode, "stdout": res.stdout + res.stderr, "live": live}
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    unittest.main()
