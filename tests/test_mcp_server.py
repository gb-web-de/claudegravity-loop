"""Unit-Tests für mcp_server.py (nur Standardbibliothek: python -m unittest discover -s tests)."""

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import mcp_server  # noqa: E402

HOSTILE_TASK = 'Fix it" ; touch /tmp/pwned ; echo "'


class OptimizerTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(mcp_server, "detect_installed_agents", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_complexity_analysis(self):
        self.assertEqual(mcp_server.analyze_task_complexity("Fix typo in README")["complexity"], "niedrig")
        self.assertEqual(mcp_server.analyze_task_complexity("Datenbank-Migration planen")["complexity"], "hoch")
        self.assertEqual(mcp_server.analyze_task_complexity("Neue Seite bauen")["complexity"], "mittel")

    def test_all_priorities_produce_a_command(self):
        for prio in ["auto", "best-code", "eco", "lowest-cost", "local-free", "balanced"]:
            with self.subTest(priority=prio):
                opt = mcp_server.optimize_claudegravity_command("Neue Seite bauen", priority=prio)
                self.assertTrue(opt["recommended_command"].startswith("claudegravity "))
                self.assertEqual(opt["loop_args"][0], "Neue Seite bauen")
                self.assertIn("bauleiter", opt["roles"])

    def test_hostile_task_stays_one_argument(self):
        opt = mcp_server.optimize_claudegravity_command(HOSTILE_TASK, project_path="/tmp/my project")
        self.assertEqual(shlex.split(opt["recommended_command"])[1], HOSTILE_TASK)
        self.assertEqual(opt["loop_args"][0], HOSTILE_TASK)
        self.assertIn("/tmp/my project", opt["loop_args"])

    def test_markdown_contains_all_shells(self):
        opt = mcp_server.optimize_claudegravity_command("Neue Seite bauen")
        md = mcp_server.format_optimization_markdown(opt)
        for marker in ["```bash", "```cmd", "```powershell", "claudegravity.bat", "claudegravity.ps1"]:
            self.assertIn(marker, md)

    def test_powershell_quoting(self):
        self.assertEqual(mcp_server.format_shell_command(["x", "it's"], "powershell"), "x 'it''s'")

    def test_background_run_never_uses_shell(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mcp_server.subprocess, "Popen") as popen:
            popen.return_value.pid = 4242
            res = mcp_server.handle_tool_call("claudegravity_run", {"task": HOSTILE_TASK, "project_path": tmp, "background": True})
            logs = list((Path(tmp) / ".dual-loop" / "sessions").glob("*_background.log"))
        self.assertFalse(res["isError"])
        argv = popen.call_args.args[0]
        self.assertIsInstance(argv, list)
        self.assertNotIn("shell", popen.call_args.kwargs)
        self.assertEqual(argv[1], str(ROOT / "loop.py"))
        self.assertEqual(argv[2], HOSTILE_TASK)
        # Ausgabe landet im Log statt in /dev/null, und die Antwort nennt das Status-Tool.
        self.assertEqual(len(logs), 1)
        self.assertIsNot(popen.call_args.kwargs["stdout"], subprocess.DEVNULL)
        self.assertIn("claudegravity_status", res["content"][0]["text"])

    def test_status_without_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = mcp_server.handle_tool_call("claudegravity_status", {"project_path": tmp})
        self.assertFalse(res["isError"])
        self.assertIn("Keine Session", res["content"][0]["text"])

    def test_status_reports_session_and_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            sessions = Path(tmp) / ".dual-loop" / "sessions"
            sess = sessions / "20261023_100000_csv"
            sess.mkdir(parents=True)
            (sess / "state.json").write_text(
                json.dumps(
                    {
                        "task": "CSV-Export",
                        "phase": "build",
                        "last_iteration": 2,
                        "stages": ["a", "b", "c"],
                        "stage_index": 1,
                        "metrics": {"total_tokens": 12345, "cost_usd": 0.5},
                        "abort_reason": "Budget: 10k erreicht",
                        "updated_at": "2026-10-23T10:05:00",
                    }
                ),
                encoding="utf-8",
            )
            (sess / "LOG.md").write_text("Zeile 1\nZeile 2\nZeile 3\n", encoding="utf-8")
            (sessions / "20261023_100000_background.log").write_text("gestartet\n", encoding="utf-8")
            text = mcp_server.handle_tool_call("claudegravity_status", {"project_path": tmp, "log_lines": 2})["content"][0]["text"]
        for part in ("CSV-Export", "build", "Etappe 2/3", "12.345", "0.50 USD", "Budget: 10k erreicht", "Zeile 3", "gestartet"):
            self.assertIn(part, text)
        self.assertNotIn("Zeile 1", text)

    def test_status_missing_project_is_error(self):
        self.assertTrue(mcp_server.handle_tool_call("claudegravity_status", {"project_path": "/nicht/da/xyz"})["isError"])

    def test_unknown_tool_is_error(self):
        self.assertTrue(mcp_server.handle_tool_call("nope", {})["isError"])

    def test_missing_task_is_error(self):
        self.assertTrue(mcp_server.handle_tool_call("claudegravity_run", {"background": True})["isError"])


class BackgroundRunTest(unittest.TestCase):
    """Hintergrundlauf für Desktop-Apps: PID-Datei, kein -i, Status und Abbruch."""

    def setUp(self):
        patcher = mock.patch.object(mcp_server, "detect_installed_agents", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(mcp_server.BACKGROUND_PROCS.clear)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)

    def start(self, popen, **extra):
        popen.return_value.pid = 4242
        args = {"task": "Migration der Datenbank", "project_path": str(self.project), "background": True, **extra}
        return mcp_server.handle_tool_call("claudegravity_run", args)

    def test_background_writes_info_and_drops_ask_mode(self):
        with mock.patch.object(mcp_server.subprocess, "Popen") as popen:
            popen.return_value.poll.return_value = None
            res = self.start(popen, ask_mode=True)
        self.assertFalse(res["isError"])
        argv = popen.call_args.args[0]
        self.assertNotIn("-i", argv)
        self.assertIn("--plan-auto", argv)
        # -p ist absolut, damit cwd und -p nicht doppelt aufgelöst werden
        self.assertEqual(argv[argv.index("-p") + 1], str(self.project.resolve()))
        info = mcp_server.latest_background_run(self.project)
        self.assertEqual(info["pid"], 4242)
        if sys.platform == "win32":
            self.assertTrue(popen.call_args.kwargs["creationflags"])
        else:
            self.assertTrue(popen.call_args.kwargs["start_new_session"])

    def test_status_shows_running_then_finished(self):
        with mock.patch.object(mcp_server.subprocess, "Popen") as popen:
            popen.return_value.poll.return_value = None
            self.start(popen)
            status = mcp_server.handle_tool_call("claudegravity_status", {"project_path": str(self.project)})["content"][0]["text"]
            self.assertIn("läuft noch", status)
            # Zweiter Start, solange der erste läuft, wird abgelehnt
            self.assertTrue(self.start(popen)["isError"])
            popen.return_value.poll.return_value = 3
            status = mcp_server.handle_tool_call("claudegravity_status", {"project_path": str(self.project)})["content"][0]["text"]
        self.assertIn("Exit-Code 3", status)

    def test_stop_only_kills_running_recorded_run(self):
        res = mcp_server.handle_tool_call("claudegravity_stop", {"project_path": str(self.project)})
        self.assertTrue(res["isError"])
        with mock.patch.object(mcp_server.subprocess, "Popen") as popen:
            popen.return_value.poll.return_value = None
            self.start(popen)
        kill = "run" if sys.platform == "win32" else "killpg"
        target = mcp_server.subprocess if sys.platform == "win32" else mcp_server.os
        with mock.patch.object(target, kill) as killer:
            res = mcp_server.handle_tool_call("claudegravity_stop", {"project_path": str(self.project)})
        self.assertFalse(res["isError"])
        killer.assert_called_once()
        if sys.platform != "win32":
            self.assertEqual(killer.call_args.args, (4242, mcp_server.signal.SIGTERM))

    def test_foreground_run_returns_command_with_server_python(self):
        res = mcp_server.handle_tool_call("claudegravity_run", {"task": HOSTILE_TASK, "project_path": str(self.project)})
        text = res["content"][0]["text"]
        self.assertIn(str(ROOT / "loop.py"), text)
        self.assertIn("powershell" if sys.platform == "win32" else "bash", text)


class DesktopEnvironmentTest(unittest.TestCase):
    """Desktop-Apps starten den Server mit kleinem PATH und cwd / bzw. Home."""

    def test_extend_search_path_adds_existing_dirs_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".local" / "bin").mkdir(parents=True)
            if sys.platform != "win32":
                (home / ".nvm" / "versions" / "node" / "v22.1.0" / "bin").mkdir(parents=True)
            env = {"PATH": os.pathsep.join(["/usr/bin", "/bin"])}
            with mock.patch.dict(os.environ, {"APPDATA": str(home / "x"), "LOCALAPPDATA": str(home / "y")}):
                added = mcp_server.extend_search_path(env, home)
                self.assertIn(str(home / ".local" / "bin"), added)
                self.assertIn(str(home / ".local" / "bin"), env["PATH"].split(os.pathsep))
                self.assertEqual(mcp_server.extend_search_path(env, home), [])
            if sys.platform != "win32":
                self.assertIn(str(home / ".nvm" / "versions" / "node" / "v22.1.0" / "bin"), added)

    def test_relative_project_in_root_cwd_is_rejected(self):
        root = Path(Path.cwd().anchor)
        with mock.patch.object(mcp_server.Path, "cwd", return_value=root), mock.patch.dict(os.environ, {mcp_server.PROJECT_ENV: ""}):
            path, error = mcp_server.resolve_project_dir(".")
        self.assertIsNone(path)
        self.assertIn(mcp_server.PROJECT_ENV, error)

    def test_project_env_and_tilde(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {mcp_server.PROJECT_ENV: tmp}):
            self.assertEqual(mcp_server.resolve_project_dir(None), (Path(tmp).resolve(), None))
            self.assertEqual(mcp_server.resolve_project_dir(tmp), (Path(tmp).resolve(), None))
        path, error = mcp_server.resolve_project_dir("~")
        self.assertEqual(path, Path.home().resolve())


class HostClientTest(unittest.TestCase):
    """Der aufrufende Client (Codex, Antigravity, Claude) führt den Loop; Ollama prüft und baut."""

    AGENTS = {"codex": "Codex CLI", "claude": "Claude Code", "agy": "Antigravity", "ollama": "Ollama"}

    def setUp(self):
        patcher = mock.patch.object(mcp_server, "detect_installed_agents", return_value=dict(self.AGENTS))
        patcher.start()
        self.addCleanup(patcher.stop)
        env = mock.patch.dict(os.environ, {mcp_server.HOST_ENV: ""})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(mcp_server.HOST_CLIENT.clear)

    def optimize(self, client, **kwargs):
        mcp_server.HOST_CLIENT.clear()
        mcp_server.HOST_CLIENT["name"] = client
        return mcp_server.optimize_claudegravity_command("CSV-Export bauen", **kwargs)

    def test_client_names_map_to_backends(self):
        for name, key in (
            ("codex-mcp-client", "codex"),
            ("Codex Desktop", "codex"),
            ("Antigravity", "agy"),
            ("gemini-cli-mcp-client", "gemini"),
            ("claude-ai", "claude"),
            ("claude-code", "claude"),
            ("cursor-vscode", None),
        ):
            with self.subTest(name=name):
                self.assertEqual(mcp_server.host_backend(name), key)
        with mock.patch.dict(os.environ, {mcp_server.HOST_ENV: "aus"}):
            self.assertIsNone(mcp_server.host_backend("codex"))

    def test_auto_with_ollama_is_hybrid_led_by_host(self):
        for client, key in (("Antigravity", "agy"), ("claude-ai", "claude"), ("codex-mcp-client", "codex")):
            with self.subTest(client=client):
                opt = self.optimize(client)
                self.assertEqual(opt["priority"], "hybrid")
                self.assertEqual(opt["roles"]["architekt"]["cli"], key)
                self.assertEqual(opt["roles"]["bauleiter"]["cli"], "ollama")
                self.assertEqual(opt["roles"]["pruefstatiker"]["cli"], "ollama")
                self.assertTrue(opt["host"]["leads"])
                if key != "codex":
                    self.assertIn(key, opt["loop_args"][opt["loop_args"].index("--architekt") + 1])

    def test_host_never_reviews_itself(self):
        opt = self.optimize("Antigravity", priority="balanced")
        self.assertEqual(opt["roles"]["architekt"]["cli"], "agy")
        self.assertNotEqual(opt["roles"]["pruefstatiker"]["cli"], "agy")

    def test_explicit_role_wins_and_missing_cli_is_reported(self):
        mcp_server.HOST_CLIENT["name"] = "codex-mcp-client"
        opt = mcp_server.optimize_claudegravity_command("x", roles={"architekt": "claude"})
        self.assertEqual(opt["roles"]["architekt"]["cli"], "claude")
        with mock.patch.object(mcp_server, "detect_installed_agents", return_value={"claude": "Claude Code"}):
            opt = self.optimize("Antigravity")
        self.assertFalse(opt["host"]["leads"])
        self.assertIn("nicht im PATH", mcp_server.format_optimization_markdown(opt))

    def test_initialize_remembers_client(self):
        mcp_server.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "codex-mcp-client", "version": "1.0"}}}
        )
        self.assertEqual(mcp_server.HOST_CLIENT["name"], "codex-mcp-client")
        self.assertEqual(mcp_server.host_backend(), "codex")


class MessageHandlingTest(unittest.TestCase):
    def test_notifications_never_get_a_response(self):
        for method in ("notifications/initialized", "notifications/cancelled", "unbekannt/notification"):
            self.assertIsNone(mcp_server.handle_message({"jsonrpc": "2.0", "method": method}))

    def test_protocol_version_negotiation(self):
        for requested, expected in (("2025-06-18", "2025-06-18"), ("2024-11-05", "2024-11-05"), ("1999-01-01", "2025-06-18")):
            res = mcp_server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": requested}})
            self.assertEqual(res["result"]["protocolVersion"], expected)
        self.assertIn("project_path", res["result"]["instructions"])

    def test_empty_lists_and_annotations(self):
        self.assertEqual(mcp_server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "prompts/list"})["result"], {"prompts": []})
        self.assertEqual(mcp_server.handle_message({"jsonrpc": "2.0", "id": 3, "method": "resources/list"})["result"], {"resources": []})
        tools = {t["name"]: t for t in mcp_server.MCP_TOOLS}
        self.assertTrue(tools["claudegravity_status"]["annotations"]["readOnlyHint"])
        self.assertFalse(tools["claudegravity_run"]["annotations"]["readOnlyHint"])

    def test_internal_error_keeps_request_id(self):
        with mock.patch.object(mcp_server, "handle_tool_call", side_effect=RuntimeError("kaputt")):
            res = mcp_server.handle_message({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "x"}})
        self.assertEqual((res["id"], res["error"]["code"]), (7, -32603))


class StdioProtocolTest(unittest.TestCase):
    def test_initialize_list_and_call(self):
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "claudegravity_optimize", "arguments": {"task": "Fix typo"}},
            },
            {"jsonrpc": "2.0", "id": 4, "method": "does/not/exist"},
            {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 3}},
        ]
        stdin = "\n".join(json.dumps(r) for r in requests) + "\nkein json\n"
        res = subprocess.run(
            [sys.executable, str(ROOT / "mcp_server.py")],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        responses = [json.loads(line) for line in res.stdout.splitlines() if line.strip()]
        by_id = {r["id"]: r for r in responses}

        self.assertEqual(by_id[1]["result"]["serverInfo"]["name"], mcp_server.SERVER_NAME)
        names = {t["name"] for t in by_id[2]["result"]["tools"]}
        self.assertEqual(
            names, {"claudegravity_optimize", "claudegravity_run", "claudegravity_status", "claudegravity_stop", "claudegravity_info"}
        )
        self.assertFalse(by_id[3]["result"]["isError"])
        self.assertEqual(by_id[4]["error"]["code"], -32601)
        self.assertEqual(by_id[None]["error"]["code"], -32700)
        self.assertEqual(len(responses), 5)


if __name__ == "__main__":
    unittest.main()
