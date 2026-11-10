"""Chat-Oberfläche (claudegravity chat): Verlauf als Gespräch, Server-Schutz, Start, Antwort, Stopp und Fortsetzen."""

import json
import os
import shlex
import subprocess
import sys
import tempfile
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
from claudegravity import chat, chatpage, common, watch  # noqa: E402

NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def write_timeline(session_dir: Path, entries: list[dict]) -> None:
    lines = [json.dumps({"time": "2026-01-01T10:00:00", **e}, ensure_ascii=False) for e in entries]
    (session_dir / watch.TIMELINE_FILE).write_text("\n".join(lines) + "\n{halb geschrieben", encoding="utf-8")


class MessagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.session = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_timeline_becomes_a_conversation(self):
        (self.session / "PLAN_v1.md").write_text("# Plan\n1. Schritt\napi_key=sk-abcdefghijklmnopqrstuvwxyz123456", encoding="utf-8")
        (self.session / "REVIEW_round1.md").write_text("BEFUNDE:\n- keine\nVERDICT: APPROVED", encoding="utf-8")
        plan_question = {
            "type": "question",
            "kind": "plan",
            "prompt": "Auswahl",
            "choices": [{"value": "1", "label": "Plan freigeben und bauen"}],
        }
        write_timeline(
            self.session,
            [
                {"type": "start", "task": "Addiere"},
                {"type": "roles", "strategy": "balanced", "planner": "Claude", "reviewer": "Codex", "builder": "Claude"},
                {"type": "call", "role": "planner", "tokens": 120, "duration_s": 2, "model": "opus"},
                {"type": "plan", "file": "PLAN_v1.md", "agent": "Claude", "source": "draft"},
                {"type": "review", "file": "REVIEW_round1.md", "round": 1, "approved": True, "findings": 0},
                {"type": "question", "kind": "questions", "prompt": "Antwort", "detail": "Welche Sprache?"},
                {"type": "answer", "answer": "Python"},
                plan_question,
                {"type": "answer", "answer": "Bitte mit Subtraktion"},
                plan_question,
                {"type": "answer", "answer": "1"},
                {"type": "question", "kind": "permission", "prompt": "Erlauben? [J/n]"},
                {"type": "answer", "answer": None, "cancelled": True},
                {"type": "build_round", "iteration": 1, "agent": "Claude", "files": ["src/a.py"], "summary": "fertig"},
                {"type": "proof", "ok": False, "command": "pytest", "output": "1 failed"},
                {"type": "log", "message": "Prüfbefehl `pytest` rot"},
                {"type": "log", "message": "Testwächter: nichts auffällig"},
                {"type": "start", "task": "Addiere", "resumed": True},
                {"type": "session_end", "success": True, "tokens_total": 500, "build_rounds": 1},
            ],
        )
        messages = chat.chat_messages(self.session)
        self.assertEqual(
            [m["type"] for m in messages],
            ["task", "roles", "plan", "review", "ask", "answer", "answer", "answer", "build", "proof", "notice", "resumed", "end"],
        )
        plan = messages[2]
        self.assertEqual((plan["version"], plan["source"], plan["stats"]["tokens"]), (1, "draft", 120))
        self.assertIn("1. Schritt", plan["text"])
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz123456", plan["text"])
        self.assertTrue(messages[3]["approved"])
        self.assertEqual(messages[4]["text"], "Welche Sprache?")
        self.assertEqual((messages[6]["value"], messages[6]["label"]), ("Bitte mit Subtraktion", None))
        self.assertEqual((messages[7]["value"], messages[7]["label"], messages[7]["kind"]), ("1", "Plan freigeben und bauen", "plan"))
        self.assertEqual(messages[9]["output"], "1 failed")
        self.assertEqual(messages[10]["text"], "Testwächter: nichts auffällig")
        self.assertTrue(messages[-1]["success"])

    def test_file_names_from_the_timeline_cannot_leave_the_session(self):
        secret = self.session.parent / "geheim.md"
        secret.write_text("geheim", encoding="utf-8")
        try:
            for name in ("../geheim.md", str(secret), ".done", "", None, 7):
                self.assertEqual(chat.session_file_text(self.session, name), "", name)
        finally:
            secret.unlink()

    def test_old_sessions_without_timeline_are_built_from_their_files(self):
        (self.session / "PLAN_v1.md").write_text("# Plan alt", encoding="utf-8")
        (self.session / "REVIEW_round1.md").write_text("BEFUNDE:\n- [HOCH] Test fehlt\nVERDICT: REVISE", encoding="utf-8")
        os.utime(self.session / "PLAN_v1.md", (1_700_000_000, 1_700_000_000))
        os.utime(self.session / "REVIEW_round1.md", (1_700_000_100, 1_700_000_100))
        state = {"task": "Alt", "phase": "review", "abort_reason": "Abgebrochen (Strg+C)", "created_at": "2026-01-01T10:00:00"}
        (self.session / "state.json").write_text(json.dumps(state), encoding="utf-8")
        messages = chat.chat_messages(self.session)
        self.assertEqual([m["type"] for m in messages], ["task", "plan", "review", "end"])
        self.assertFalse(messages[2]["approved"])
        self.assertEqual(messages[2]["round"], 1)
        self.assertFalse(messages[3]["success"])


class OptionsTest(unittest.TestCase):
    def test_start_options_take_only_known_values(self):
        data = {
            "strategy": "eco",
            "template": "bugfix",
            "proof": " pytest -q ",
            "yolo": True,
            "plan_auto": "ja",
            "ask": True,
            "merge": False,
            "extra": "--builder codex --max-iterations 3 --proof 'a b'",
        }
        self.assertEqual(
            chat.start_options(data),
            ["--strategy", "eco", "--template", "bugfix", "--proof", "pytest -q", "--yolo", "--ask"]
            + ["--builder", "codex", "--max-iterations", "3", "--proof", "a b"],
        )
        self.assertEqual(chat.start_options({"strategy": "; rm -rf /", "template": 3, "proof": None}), [])

    def test_task_can_never_become_an_option(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(chat, "launch_loop") as launch:
            server = chat.ChatServer(Path(tmp), 0)
            try:
                with mock.patch.object(chat, "remember_project"):
                    server.start(Path(tmp), ["-p", tmp, "--no-guide", "--", "--yolo --merge"], "--yolo --merge")
            finally:
                server.server_close()
        args = launch.call_args[0][1]
        self.assertEqual(args[args.index("--") + 1 :], ["--yolo --merge"])

    def test_project_must_be_an_existing_absolute_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            self.assertEqual(chat.resolve_project(None, base), base)
            self.assertEqual(chat.resolve_project(str(base), Path("/")), base)
            self.assertIsNone(chat.resolve_project("relativ/ordner", base))
            self.assertIsNone(chat.resolve_project(str(base / "fehlt"), base))
            (base / "sub").mkdir()
            (base / ".versteckt").mkdir()
            listing = chat.list_directories(str(base))
            self.assertEqual((listing["path"], listing["dirs"]), (str(base), ["sub"]))

    def test_recent_projects_are_remembered_next_to_the_profile(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CLAUDEGRAVITY_CONFIG_DIR": str(Path(tmp) / "config")}):
            first, second = Path(tmp) / "a", Path(tmp) / "b"
            first.mkdir()
            second.mkdir()
            chat.remember_project(first)
            chat.remember_project(second)
            chat.remember_project(first)
            self.assertEqual(chat.recent_projects(), [str(first), str(second)])
            second.rmdir()
            self.assertEqual(chat.recent_projects(), [str(first)])

    def test_answers_keep_their_line_breaks(self):
        with mock.patch("builtins.input", return_value="eins" + common.ANSWER_NEWLINE + "zwei"):
            self.assertEqual(common.ask("Antwort: "), "eins\nzwei")

    def test_chat_subcommand(self):
        argv = ["claudegravity", "chat", "-p", tempfile.gettempdir(), "--chat-port", "0"]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(chat, "run_chat") as run_chat,
            mock.patch.object(loop.cli, "setup_agents") as agents,
        ):
            loop.main()
        run_chat.assert_called_once_with(Path(tempfile.gettempdir()).resolve(), 0)
        agents.assert_not_called()

    def test_page_shows_model_text_only_as_text(self):
        page = chatpage.CHAT_PAGE
        self.assertNotIn("innerHTML", page)
        self.assertNotIn("document.write", page)
        self.assertNotIn("eval(", page)
        for lang in ("de:", "en:"):
            self.assertIn(lang, page)


class ServerTestCase(unittest.TestCase):
    """Chat-Server auf einem Projekt mit dem Fake-Endpunkt aus dem Smoke-Test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.project = (tmp / "projekt").resolve()
        self.project.mkdir()
        (tmp / "leer").mkdir()
        self.endpoint, self.endpoint_url = run_smoke.start_server()
        env = {**run_smoke.smoke_env(tmp), "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}
        self.env = mock.patch.dict(os.environ, env, clear=True)
        self.env.start()
        with mock.patch.object(chat, "chat_setup", return_value={"agents": [], "checked": ""}):
            self.server = chat.start_chat_server(self.project, 0)
        self.port = self.server.server_address[1]
        command = run_smoke.smoke_command(self.project, self.endpoint_url, "balanced")
        self.loop_options = [a for a in command[command.index("--no-guide") + 1 :]] + ["--no-worktree", "-d", "0"]

    def tearDown(self):
        self.server.stop_all()
        for run in self.server.runs:
            with_timeout = time.monotonic() + 15
            while run.alive and time.monotonic() < with_timeout:
                time.sleep(0.1)
            if run.alive:
                chat.signal_run(run, force=True)
            if run.proc.stdin:
                run.proc.stdin.close()
            run.proc.wait(timeout=15)
        self.server.shutdown()
        self.server.server_close()
        self.endpoint.shutdown()
        self.endpoint.server_close()
        self.env.stop()
        self.tmp.cleanup()

    def request(self, path: str, body: dict | None = None, headers: dict | None = None, token: bool = True):
        sep = "&" if "?" in path else "?"
        url = f"http://127.0.0.1:{self.port}{path}" + (f"{sep}t={self.server.token}" if token else "")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        head = {"Content-Type": "application/json"} if body is not None else {}
        req = urllib.request.Request(url, data=data, headers={**head, **(headers or {})})
        try:
            with NO_PROXY.open(req, timeout=20) as res:
                text = res.read().decode("utf-8")
                return res.status, res.headers, json.loads(text) if text.startswith("{") else text
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8")
            return exc.code, exc.headers, json.loads(text) if text.startswith("{") else text

    def state(self, session: str | None = None) -> dict:
        path = "/api/state" + (f"?session={session}" if session else "")
        return self.request(path)[2]

    def wait_for(self, check, timeout: float = 60.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = check()
            if value:
                return value
            time.sleep(0.15)
        logs = "\n".join(run.output_tail()[-3000:] for run in self.server.runs)
        self.fail(f"Zeit abgelaufen. Konsolen-Ausgabe:\n{logs}")

    def start(self, task: str = "Addition mit Test", extra: list[str] | None = None) -> str:
        """Lauf über die API starten; liefert den Namen der Session, sobald sie angelegt ist."""
        body = {"task": task, "extra": shlex.join(self.loop_options + (extra or [])), "yolo": True}
        status, _h, data = self.request("/api/start", body)
        self.assertEqual(status, 200, data)
        return self.wait_for(lambda: (self.state().get("pending") or {}).get("session"))

    def question(self, session: str, kind: str) -> dict:
        def check():
            question = (self.state(session).get("session") or {}).get("question")
            return question if question and question.get("kind") == kind else None

        return self.wait_for(check)


class ServerSecurityTest(ServerTestCase):
    def test_token_host_and_content_type_are_required(self):
        self.assertEqual(self.request("/", token=False)[0], 403)
        self.assertEqual(self.request("/api/state", token=False)[0], 403)
        self.assertEqual(self.request("/api/state", headers={"Host": f"evil.example:{self.port}"})[0], 403)
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("ClaudeGravity Chat", body)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("/nix")[0], 404)

        body = {"task": "x"}
        self.assertEqual(self.request("/api/start", body, token=False)[0], 403)
        self.assertEqual(self.request("/api/start", body, headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("/api/start", body, headers={"Content-Type": "text/plain"})[0], 403)
        self.assertEqual(self.request("/api/start", body, headers={"Content-Type": "application/x-www-form-urlencoded"})[0], 403)
        self.assertEqual(self.server.runs, [])

    def test_bad_requests_start_nothing(self):
        self.assertEqual(self.request("/api/start", {"task": "   "})[0], 400)
        self.assertEqual(self.request("/api/start", {"task": "x", "project": "relativ"})[0], 400)
        self.assertEqual(self.request("/api/resume", {"session": "../.."})[0], 404)
        self.assertEqual(self.request("/api/answer", {"session": "fehlt", "value": "1"})[0], 409)
        self.assertEqual(self.request("/api/stop", {"session": "fehlt"})[0], 409)
        self.assertEqual(self.request("/api/state?project=relativ")[0], 400)
        self.assertEqual(self.server.runs, [])

    def test_state_without_sessions(self):
        data = self.state()
        self.assertEqual((data["sessions"], data["session"], data["pending"]), ([], None, None))
        self.assertEqual(data["project"]["path"], str(self.project))
        self.assertIn("balanced", data["strategies"])

    def test_failed_start_reports_the_console_output(self):
        status, _h, data = self.request("/api/start", {"task": "Ohne KI"})
        self.assertEqual(status, 200, data)
        pending = self.wait_for(lambda: (lambda p: p if p and not p["alive"] else None)(self.state().get("pending")))
        self.assertIsNone(pending["session"])
        self.assertNotEqual(pending["code"], 0)
        self.assertIn("CG-1001", pending["output"])


class ChatRunTest(ServerTestCase):
    def test_plan_feedback_approval_and_build(self):
        session = self.start()
        question = self.question(session, "plan")
        self.assertEqual(question["choices"][0], {"value": "1", "label": "Plan freigeben und bauen"})
        self.assertTrue(question["text"])
        payload = self.state(session)["session"]
        self.assertTrue(payload["owned"] and payload["running"])
        self.assertEqual([m["type"] for m in payload["messages"]][:4], ["task", "roles", "plan", "review"])

        # Änderungswunsch in Worten (mit Zeilenumbruch): neuer Plan, neues Review, wieder die Freigabe-Frage
        asked = question["id"]
        self.assertEqual(self.request("/api/answer", {"session": session, "value": "Bitte auch Subtraktion.\nKurz halten."})[0], 200)
        self.wait_for(
            lambda: (lambda q: q if q and q.get("kind") == "plan" and q["id"] != asked else None)(
                self.state(session)["session"]["question"]
            )
        )
        messages = self.state(session)["session"]["messages"]
        self.assertEqual([m["type"] for m in messages][4:], ["answer", "plan", "review"], [m["type"] for m in messages])
        self.assertEqual(messages[4]["value"], "Bitte auch Subtraktion.\nKurz halten.")
        self.assertEqual((messages[5]["version"], messages[5]["source"]), (2, "feedback"))
        self.assertEqual(messages[6]["round"], 2)

        # Nur neue Nachrichten ab `after`
        newer = self.request(f"/api/state?session={session}&after=6")[2]["session"]
        self.assertEqual((len(newer["messages"]), newer["total"]), (1, 7))

        self.assertEqual(self.request("/api/answer", {"session": session, "value": "1"})[0], 200)
        done = self.wait_for(
            lambda: (lambda s: s if s["phase"] == "completed" and not s["running"] else None)(self.state(session)["session"])
        )
        types = [m["type"] for m in done["messages"]]
        self.assertEqual(types[7:], ["answer", "build", "proof", "inspection", "end"], types)
        self.assertEqual(done["messages"][7]["label"], "Plan freigeben und bauen")
        self.assertTrue(done["messages"][-1]["success"])
        self.assertFalse(done["can_resume"])
        self.assertIsNone(done["question"])
        self.assertIn("src/calc.py", done["messages"][8]["files"])
        self.assertTrue((self.project / "src" / "calc.py").exists())
        output = self.request(f"/api/output?session={session}")[2]
        self.assertTrue(output["owned"])
        self.assertIn("ClaudeGravity Loop", output["output"])
        # Nach dem Ende nimmt der Lauf keine Antwort mehr an
        self.assertEqual(self.request("/api/answer", {"session": session, "value": "1"})[0], 409)

    @unittest.skipIf(sys.platform == "win32", "Unter Windows beendet Stopp den Lauf hart (taskkill)")
    def test_stop_and_resume_keep_the_cast(self):
        session = self.start()
        self.question(session, "plan")
        self.assertEqual(self.request("/api/stop", {"session": session})[0], 200)
        stopped = self.wait_for(lambda: (lambda s: s if not s["running"] else None)(self.state(session)["session"]))
        self.assertTrue(stopped["can_resume"])
        self.assertIn("Strg+C", stopped["abort_reason"])
        self.assertEqual(stopped["messages"][-1]["type"], "end")

        # Fortsetzen: dieselbe Session, dieselben Rollen und Endpunkte (ohne die Flags noch einmal anzugeben)
        self.assertEqual(self.request("/api/resume", {"session": session})[0], 200)
        self.assertEqual(self.request("/api/resume", {"session": session})[0] in (200, 409), True)
        question = self.question(session, "plan")
        self.assertTrue(self.state(session)["session"]["owned"])
        self.assertEqual(self.request("/api/answer", {"session": session, "value": "1", "project": str(self.project)})[0], 200)
        self.assertIsNotNone(question)
        done = self.wait_for(
            lambda: (lambda s: s if s["phase"] == "completed" and not s["running"] else None)(self.state(session)["session"])
        )
        types = [m["type"] for m in done["messages"]]
        self.assertIn("resumed", types)
        self.assertEqual(types[-1], "end")
        self.assertEqual(len(self.state()["sessions"]), 1)


class DiffTest(unittest.TestCase):
    def test_new_files_show_their_content_but_no_secrets_or_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            env = {**os.environ, **GIT_ENV}
            (project / "alt.py").write_text("a = 1\n", encoding="utf-8")
            for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "init"]):
                subprocess.run(cmd, cwd=project, env=env, check=True, capture_output=True)
            base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True).stdout.strip()
            session = project / ".dual-loop" / "sessions" / "20260101_000000_x"
            session.mkdir(parents=True)
            (session / "state.json").write_text(json.dumps({"build_base": base, "worktree": {"enabled": False}}), encoding="utf-8")
            (project / "alt.py").write_text("a = 2\n", encoding="utf-8")
            (project / "neu mit leer.py").write_text("def neu():\n    return 1\n", encoding="utf-8")
            (project / ".env").write_text("TOKEN=streng-geheim-123456\n", encoding="utf-8")
            (project / "bild.bin").write_bytes(b"\x00\x01\x02")
            (project / "__pycache__").mkdir()
            (project / "__pycache__" / "x.cpython-313.pyc").write_bytes(b"\x00")
            (project / "logs").mkdir()
            (project / "logs" / "loop_20260101_000000_x.log").write_text("log", encoding="utf-8")
            text, cut = watch.session_diff(project, session)
            paths = [c["path"] for c in watch.file_changes(project, watch.read_state(session))]
        self.assertFalse(cut)
        self.assertIn("+a = 2", text)
        self.assertIn("+++ b/neu mit leer.py", text)
        self.assertIn("+def neu():", text)
        self.assertIn("a/.env", text)
        self.assertNotIn("streng-geheim", text)
        self.assertIn("a/bild.bin", text)
        self.assertNotIn("pycache", text)
        self.assertNotIn("logs/loop_", text)
        self.assertEqual(sorted(paths), [".env", "alt.py", "bild.bin", "neu mit leer.py"])


if __name__ == "__main__":
    unittest.main()
