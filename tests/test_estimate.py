"""Tests für die Kostenschätzung vorab im Trockenlauf (aus Kennzahlen früherer Sessions)."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402


def write_session(project: Path, name: str, strategy: str, builds: int, tokens: int,
                  usd: float = 0.0, done: bool = True, rework: int = 0) -> None:
    session = project / ".dual-loop" / "sessions" / name
    session.mkdir(parents=True)
    metrics = loop.SessionMetrics()
    for _ in range(builds):
        metrics.add("Claude Code" if usd else "Ollama", tokens // builds, 0,
                    cost_usd=usd / builds, role="🔨 Bauleiter")
    metrics.counters["proof_red"] = rework
    state = {"phase": "completed" if done else "build", "strategy": strategy, "created_at": "2026-10-23T10:00:00"}
    target = session / (".done" if done else "AUDIT.md")
    target.write_text("# Fertig\n" + loop.format_metrics_report(metrics, state), encoding="utf-8")


class HistoryTest(unittest.TestCase):
    def test_reads_done_and_audit_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_session(project, "20261020_a", "balanced", 2, 20_000)
            write_session(project, "20261021_b", "balanced", 4, 40_000, done=False)
            (project / ".dual-loop" / "sessions" / "20261022_leer").mkdir()
            history = loop.collect_kpi_history(project)
            self.assertEqual([k["build_rounds"] for k in history], [4, 2])
            self.assertEqual([k["success"] for k in history], [False, True])

    def test_broken_or_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.assertEqual(loop.collect_kpi_history(project), [])
            session = project / ".dual-loop" / "sessions" / "x"
            session.mkdir(parents=True)
            (session / ".done").write_text("### 📈 Kennzahlen (ClaudeGravity KPI v1)\n```json\n{kaputt}\n```\n", encoding="utf-8")
            self.assertEqual(loop.collect_kpi_history(project), [])

    def test_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            for i in range(5):
                write_session(project, f"2026102{i}_s", "eco", 1, 1000)
            self.assertEqual(len(loop.collect_kpi_history(project, limit=3)), 3)


class EstimateTest(unittest.TestCase):
    def test_heuristic_without_history(self):
        est = loop.estimate_run([], "balanced", 10)
        self.assertEqual(est["source"], "heuristik")
        self.assertEqual(est["rounds"], (1, 3, 10))
        self.assertIsNone(est["cost_usd"])
        lines = "\n".join(loop.format_estimate(est, []))
        self.assertIn("Faustregel", lines)
        self.assertNotIn("USD:", lines)

    def test_spread_from_same_strategy(self):
        history = [
            {"version": 1, "strategy": "balanced", "build_rounds": 2, "tokens_total": 20_000, "cost_usd_task": 0.2, "success": True, "rework_rate": 0.0},
            {"version": 1, "strategy": "balanced", "build_rounds": 6, "tokens_total": 90_000, "cost_usd_task": 0.9, "success": False, "rework_rate": 0.5},
            {"version": 1, "strategy": "balanced", "build_rounds": 3, "tokens_total": 30_000, "cost_usd_task": 0.0, "success": True, "rework_rate": 0.33},
            {"version": 1, "strategy": "local-free", "build_rounds": 9, "tokens_total": 500_000, "success": True},
        ]
        est = loop.estimate_run(history, "balanced", 5)
        self.assertTrue(est["strategy_match"])
        self.assertEqual(est["sessions"], 3)
        self.assertEqual(est["rounds"], (2, 3, 5))  # auf --max-iterations gekappt
        self.assertEqual(est["tokens"], (20_000, 30_000, 90_000))
        self.assertEqual(est["cost_usd"], (0.2, 0.55, 0.9))  # nur Sessions mit gemeldeten Kosten
        self.assertEqual(est["cost_sessions"], 2)
        self.assertAlmostEqual(est["success_rate"], 2 / 3)

    def test_falls_back_to_all_strategies(self):
        history = [{"version": 1, "strategy": "eco", "build_rounds": 2, "tokens_total": 5_000, "success": True}]
        est = loop.estimate_run(history, "balanced", 10)
        self.assertFalse(est["strategy_match"])
        self.assertIsNone(est["cost_usd"])
        text = "\n".join(loop.format_estimate(est, []))
        self.assertIn("alle Strategien", text)
        self.assertIn("keine gemeldet", text)


class HintTest(unittest.TestCase):
    def est(self, tokens=None, usd=None, rework=None):
        return {"tokens": tokens, "cost_usd": usd, "rework_rate": rework}

    def test_budget_too_small(self):
        hints = loop.estimate_hints(self.est(tokens=(1, 2, 200_000)), "balanced", loop.Budget(max_total="100k"), False, None)
        self.assertTrue(any("reicht --budget-max 100k Tokens nicht" in h for h in hints))

    def test_suggests_budget_and_local(self):
        hints = loop.estimate_hints(self.est(tokens=(1, 2, 3), usd=(0.1, 0.2, 1.0)), "balanced", None, True, None)
        self.assertTrue(any("--budget-max 1.20 USD" in h for h in hints))
        self.assertTrue(any("hybrid oder local-free" in h for h in hints))
        hints = loop.estimate_hints(self.est(usd=(0.1, 0.2, 1.0)), "local-free", None, True, None)
        self.assertFalse(any("local-free" in h for h in hints))

    def test_rework(self):
        hints = loop.estimate_hints(self.est(rework=0.6), "balanced", None, False, None)
        self.assertTrue(any("--proof" in h for h in hints))
        self.assertEqual(loop.estimate_hints(self.est(rework=0.2), "balanced", None, False, None), [])


class DryRunTest(unittest.TestCase):
    def test_dry_run_shows_estimate_from_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "p"
            project.mkdir()
            write_session(project, "20261020_a", "balanced", 2, 20_000, usd=0.4)
            write_session(project, "20261021_b", "balanced", 4, 60_000, usd=1.0)
            env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDEGRAVITY_")}
            env.update(CLAUDEGRAVITY_CONFIG_DIR=str(Path(tmp) / "cfg"), PYTHONIOENCODING="utf-8")
            res = subprocess.run([sys.executable, str(ROOT / "loop.py"), "Aufgabe", "-p", str(project),
                                  "--dry-run", "--strategy", "balanced", "--endpoint", "http://127.0.0.1:9/v1"],
                                 capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)
            out = res.stdout
            self.assertEqual(res.returncode, 0, res.stderr[-2000:])
            self.assertIn("Kostenschätzung vorab", out)
            self.assertIn("2 frühere Session(s) mit gleicher Strategie", out)
            self.assertIn("Kosten        : günstig 0.40 USD · erwartet 0.70 USD · ungünstig 1.00 USD", out)


if __name__ == "__main__":
    unittest.main()
