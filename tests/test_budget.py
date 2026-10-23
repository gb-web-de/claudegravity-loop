"""Tests für harte und weiche Budget-Grenzen (--budget-max, --budget-warn, --budget-roles)."""

import json
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent / "smoke"))

import loop  # noqa: E402
import run_smoke  # noqa: E402


def metrics_with(builder_tokens=0, inspector_usd=0.0, planner_tokens=0):
    m = loop.SessionMetrics()
    if planner_tokens:
        m.add("Codex", planner_tokens, 0, role="🏗️ Architekt")
    if builder_tokens:
        m.add("Ollama", builder_tokens, 0, role="🔨 Bauleiter")
    if inspector_usd:
        m.add("Claude Code", 10, 0, cost_usd=inspector_usd, role="🔎 Abnahme")
    return m


class ParseTest(unittest.TestCase):
    def test_units(self):
        self.assertEqual(loop.parse_budget("500k"), ("tokens", 500_000))
        self.assertEqual(loop.parse_budget("1.5M"), ("tokens", 1_500_000))
        self.assertEqual(loop.parse_budget("80000 tokens"), ("tokens", 80_000))
        self.assertEqual(loop.parse_budget("2.50usd"), ("usd", 2.5))
        self.assertEqual(loop.parse_budget("$2,50"), ("usd", 2.5))
        for bad in ("viel", "0", "-5k", "usd"):
            with self.assertRaises(ValueError):
                loop.parse_budget(bad)

    def test_roles(self):
        b = loop.Budget(roles="bauleiter=300k, Abnahme=0.50usd")
        self.assertEqual(b.roles, {"builder": ("tokens", 300_000), "inspector": ("usd", 0.5)})
        for bad in ("koch=1k", "bauleiter"):
            with self.assertRaises(ValueError):
                loop.Budget(roles=bad)
        self.assertFalse(loop.Budget().active)


class CheckTest(unittest.TestCase):
    def test_soft_then_hard(self):
        b = loop.Budget(max_total="10k")
        self.assertEqual(b.check(metrics_with(builder_tokens=7_000)), [])
        warnings = b.check(metrics_with(builder_tokens=8_500))
        self.assertEqual(len(warnings), 1)
        self.assertIn("80 %", warnings[0])
        self.assertEqual(b.check(metrics_with(builder_tokens=9_000)), [])  # nur einmal warnen
        with self.assertRaises(loop.BudgetExceeded) as ctx:
            b.check(metrics_with(builder_tokens=10_000))
        self.assertIn("Gesamtbudget 10k Tokens", str(ctx.exception))

    def test_explicit_warn_and_usd_only_counts_reported_costs(self):
        b = loop.Budget(max_total="1usd", warn_total="0.20usd")
        self.assertEqual(b.check(metrics_with(builder_tokens=5_000_000)), [])  # lokale Tokens kosten nichts
        self.assertEqual(len(b.check(metrics_with(inspector_usd=0.25))), 1)
        with self.assertRaises(loop.BudgetExceeded):
            b.check(metrics_with(inspector_usd=1.0))

    def test_role_limit(self):
        b = loop.Budget(roles="bauleiter=1k")
        self.assertEqual(b.check(metrics_with(planner_tokens=50_000)), [])
        with self.assertRaises(loop.BudgetExceeded) as ctx:
            b.check(metrics_with(builder_tokens=1_000))
        self.assertIn("Bauleiter", str(ctx.exception))

    def test_safe_agent_run_stops_after_the_call(self):
        calls = []
        agent = loop.AgentCLI("Ollama", "ollama", lambda *a: (calls.append(1) or "ok", {"total_tokens": 850}), local=True)
        metrics = loop.SessionMetrics()
        agent.metrics_tracker = metrics
        agent.role = "🔨 Bauleiter"
        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch.object(loop.SETTINGS, "budget", loop.Budget(max_total="1k")):
            loop.safe_agent_run(agent, "p", Path(tmp), [], {}, Path(tmp), {}, False, role="builder", metrics_tracker=metrics)
            with self.assertRaises(loop.BudgetExceeded):
                loop.safe_agent_run(agent, "p", Path(tmp), [], {}, Path(tmp), {}, False, role="builder", metrics_tracker=metrics)
            self.assertIn("Budget-Warnung", (Path(tmp) / "LOG.md").read_text(encoding="utf-8"))
        self.assertEqual(len(calls), 2)


class BudgetRunTest(unittest.TestCase):
    def test_hard_budget_ends_run_with_report(self):
        server, url = run_smoke.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                project = tmp / "projekt"
                (project / "tests").mkdir(parents=True)
                (tmp / "leer").mkdir()
                cmd = run_smoke.smoke_command(project, url, "local-free") + ["--budget-max", "300"]
                res = subprocess.run(
                    cmd, input="", capture_output=True, text=True, encoding="utf-8", timeout=120, env=run_smoke.smoke_env(tmp)
                )
                self.assertEqual(res.returncode, 3, res.stdout[-2000:] + res.stderr)
                self.assertIn("[CG-1404]", res.stderr)
                session = next((project / ".dual-loop" / "sessions").iterdir())
                state = json.loads((session / "state.json").read_text(encoding="utf-8"))
                self.assertIn("Gesamtbudget 300 Tokens", state["abort_reason"])
                audit = (session / "AUDIT.md").read_text(encoding="utf-8")
                self.assertIn("Abbruchgrund:** Budget", audit)
                self.assertFalse((session / ".done").exists())
                bad = subprocess.run(
                    run_smoke.smoke_command(project, url, "balanced") + ["--budget-max", "viel"],
                    input="",
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=60,
                    env=run_smoke.smoke_env(tmp),
                )
                self.assertEqual(bad.returncode, 1)
                self.assertIn("[CG-1103]", bad.stderr)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
