"""Tests für das strukturierte Ereignis-Log events.jsonl (--log-format json)."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent / "smoke"))

import loop  # noqa: E402
import run_smoke  # noqa: E402


class LogEventTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, loop.SETTINGS, "log_format", loop.SETTINGS.log_format)

    def test_text_format_writes_nothing(self):
        loop.SETTINGS.log_format = "text"
        with tempfile.TemporaryDirectory() as tmp:
            loop.log_event(Path(tmp), "call", role="builder")
            loop.append_log(Path(tmp), "Hallo")
            self.assertFalse((Path(tmp) / "events.jsonl").exists())

    def test_json_lines_masked_and_without_none(self):
        loop.SETTINGS.log_format = "json"
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "20261023_x"
            session.mkdir()
            loop.log_event(session, "call", role="builder", model=None, tokens=12)
            loop.append_log(session, "Schlüssel sk-ant-api03-" + "a" * 40)
            events = [json.loads(line) for line in (session / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([e["event"] for e in events], ["call", "log"])
            self.assertEqual(events[0]["session"], "20261023_x")
            self.assertNotIn("model", events[0])
            self.assertEqual(events[0]["tokens"], 12)
            self.assertNotIn("a" * 40, events[1]["message"])


class EventsEndToEndTest(unittest.TestCase):
    def test_smoke_run_writes_events(self):
        server, url = run_smoke.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp_name:
                tmp = Path(tmp_name)
                project = tmp / "projekt"
                (project / "tests").mkdir(parents=True)
                (tmp / "leer").mkdir()
                cmd = run_smoke.smoke_command(project, url, "balanced") + ["--log-format", "json"]
                res = subprocess.run(cmd, input="", capture_output=True, text=True, encoding="utf-8",
                                     timeout=120, env=run_smoke.smoke_env(tmp))
                session = next((project / ".dual-loop" / "sessions").iterdir())
                events = [json.loads(line) for line in (session / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(res.returncode, 0, res.stdout[-2000:])
        kinds = [e["event"] for e in events]
        calls = [e for e in events if e["event"] == "call"]
        self.assertEqual([c["role"] for c in calls], ["planner", "reviewer", "builder", "inspector"])
        self.assertEqual(calls[2]["iteration"], 1)
        self.assertEqual(calls[2]["tokens"], 120)
        self.assertIn("proof", kinds)
        self.assertIn("log", kinds)
        end = events[-1]
        self.assertEqual((end["event"], end["success"], end["phase"]), ("session_end", True, "completed"))


if __name__ == "__main__":
    unittest.main()
