"""Tests für Secrets-Hygiene (Maskierung, Warnungen) und Rechte-Audit (blockierte und unerlaubte Schreibzugriffe)."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402

GH_TOKEN = "ghp_" + "A" * 36


def agent_with(run_fn, name="Fake", binary="fake", local=False):
    return loop.AgentCLI(name, binary, run_fn, local=local)


class SecretsHygieneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.session = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_log_lines_are_masked(self):
        loop.append_log(self.session, f"Fehler bei https://user:geheim123@host/v1 mit {GH_TOKEN}")
        log = (self.session / "LOG.md").read_text(encoding="utf-8")
        self.assertNotIn(GH_TOKEN, log)
        self.assertNotIn("geheim123", log)
        self.assertIn("GESCHWÄRZT", log)

    def test_secret_in_output_is_reported(self):
        metrics = loop.SessionMetrics()
        agent = agent_with(lambda b, p, c, f: (f"Nutze {GH_TOKEN} für den Push", {}))
        res, _, _ = loop.safe_agent_run(agent, "p", self.session, [], {}, self.session, {}, False,
                                        role="planner", metrics_tracker=metrics)
        self.assertIn(GH_TOKEN, res)  # Antwort selbst bleibt unverändert
        self.assertEqual(metrics.audit_events, {"secret_in_output": 1})
        events = [json.loads(l) for l in (self.session / "audit-events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(events[0]["kind"], "secret_in_output")
        self.assertIn("GitHub-Token", events[0]["detail"])
        self.assertNotIn(GH_TOKEN, (self.session / "LOG.md").read_text(encoding="utf-8"))
        report = loop.format_metrics_report(metrics)
        self.assertIn("Mögliche Zugangsdaten in Modellantwort: 1", report)
        self.assertEqual(loop.SessionMetrics.from_dict(metrics.to_dict()).audit_events, metrics.audit_events)


class PermissionAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_blocked_writes_are_reported(self):
        blocked = []
        text = "```filepath: ../draussen.txt\nx\n```\n```filepath: .env\nKEY=1\n```\n```filepath: ok.txt\nok\n```\n"
        written = loop.apply_code_blocks(self.root, text, on_blocked=blocked.append)
        self.assertEqual(written, ["ok.txt"])
        self.assertEqual(blocked, ["../draussen.txt", ".env"])

    @unittest.skipUnless(shutil.which("git"), "git fehlt")
    def test_write_by_readonly_role_is_detected(self):
        project = self.root / "p"
        project.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        (project / "a.txt").write_text("a", encoding="utf-8")
        session = project / ".dual-loop" / "sessions" / "s"
        session.mkdir(parents=True)
        metrics = loop.SessionMetrics()

        def sneaky(binary, prompt, cwd, flags):
            (cwd / "b.txt").write_text("b", encoding="utf-8")
            return "Plan", {}

        loop.safe_agent_run(agent_with(sneaky), "p", project, [], {}, session, {}, False,
                            role="reviewer", metrics_tracker=metrics)
        self.assertEqual(metrics.audit_events, {"readonly_changed": 1})
        self.assertIn("b.txt", (session / "LOG.md").read_text(encoding="utf-8"))

        # Bauleiter darf schreiben; Änderungen im Session-Ordner zählen nie
        loop.safe_agent_run(agent_with(sneaky), "p", project, [], {}, session, {}, False,
                            role="builder", metrics_tracker=metrics)

        def session_only(binary, prompt, cwd, flags):
            (session / "notiz.md").write_text("n", encoding="utf-8")
            return "ok", {}

        loop.safe_agent_run(agent_with(session_only), "p", project, [], {}, session, {}, False,
                            role="inspector", metrics_tracker=metrics)
        self.assertEqual(metrics.audit_events, {"readonly_changed": 1})

    def test_fingerprint_without_git(self):
        self.assertEqual(loop.fingerprint_changes(None, {"a": 1}), [])
        self.assertEqual(loop.fingerprint_changes({"a": 1}, {"a": 2, "b": 1}), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
