"""Unit-Tests für mcp_server.py (nur Standardbibliothek: python -m unittest discover -s tests)."""

import json
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
        for prio in ["best-code", "eco", "lowest-cost", "local-free", "balanced"]:
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
        self.assertEqual(names, {"claudegravity_optimize", "claudegravity_run", "claudegravity_status", "claudegravity_info"})
        self.assertFalse(by_id[3]["result"]["isError"])
        self.assertEqual(by_id[4]["error"]["code"], -32601)
        self.assertEqual(by_id[None]["error"]["code"], -32700)
        self.assertEqual(len(responses), 5)


if __name__ == "__main__":
    unittest.main()
