"""Tests für den Kennzahlen-Block (KPI) in .done."""

import datetime
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402


def sample_metrics() -> loop.SessionMetrics:
    m = loop.SessionMetrics()
    m.add("Claude Code", 100, 50, cost_usd=0.10, role="🏗️ Architekt (Planung & Entwurf)")
    m.add("Antigravity", 80, 20, role="🧐 Prüfstatiker (Prüfung & Review)")
    for _ in range(3):
        m.add("Ollama", 500, 400, role="🔨 Bauleiter (Bau & Umsetzung)")
    m.add("Claude Code", 60, 10, cost_usd=0.05, role="🔎 Abnahme")
    m.add("Claude Code", 60, 10, cost_usd=0.04, role="🔎 Abnahme")
    m.count("proof_red")
    m.count("proof_green")
    m.count("inspection_rejected")
    return m


class KpiTest(unittest.TestCase):
    def test_build_kpis(self):
        state = {"phase": "completed", "strategy": "hybrid", "rounds_completed": 2,
                 "created_at": "2026-10-23T10:00:00", "stages": ["a", "b"]}
        kpi = loop.build_kpis(state, sample_metrics(), now=datetime.datetime(2026, 10, 23, 10, 12, 30))
        self.assertTrue(kpi["success"])
        self.assertEqual(kpi["duration_s"], 750)
        self.assertEqual((kpi["build_rounds"], kpi["build_rounds_to_success"], kpi["inspection_rounds"]), (3, 3, 2))
        self.assertEqual((kpi["proof_runs"], kpi["proof_red"], kpi["inspection_rejected"]), (2, 1, 1))
        self.assertEqual((kpi["rework_rounds"], kpi["rework_rate"]), (2, 0.67))
        self.assertAlmostEqual(kpi["cost_usd_task"], 0.19)
        self.assertAlmostEqual(kpi["cost_usd_inspection"], 0.09)
        self.assertEqual(kpi["cost_reported_by"], ["Claude Code"])
        self.assertEqual(kpi["stages"], 2)

    def test_rework_never_exceeds_extra_rounds(self):
        m = loop.SessionMetrics()
        m.add("Ollama", 1, 1, role="🔨 Bauleiter")
        for _ in range(4):
            m.count("proof_red")
        kpi = loop.build_kpis({"phase": "build"}, m)
        self.assertEqual((kpi["rework_rounds"], kpi["build_rounds_to_success"], kpi["duration_s"]), (0, None, None))

    def test_block_format_is_parseable(self):
        state = {"phase": "completed", "strategy": "eco"}
        report = loop.format_metrics_report(sample_metrics(), state)
        self.assertTrue(report.index("Kennzahlen") < report.index("ClaudeGravity Audit"))
        self.assertIn("Kosten je Aufgabe:** 0.1900 USD", report)
        kpi = json.loads(report.split("```json\n", 1)[1].split("\n```", 1)[0])
        self.assertEqual(kpi["version"], 1)
        self.assertNotIn("Kennzahlen", loop.format_metrics_report(sample_metrics()))

    def test_no_reported_costs(self):
        m = loop.SessionMetrics()
        m.add("Antigravity", 5, 5, role="🔨 Bauleiter")
        block = loop.format_kpi_block(loop.build_kpis({"phase": "completed"}, m))
        self.assertIn("kein Anbieter", block)

    def test_counters_roundtrip(self):
        m = sample_metrics()
        again = loop.SessionMetrics.from_dict(json.loads(json.dumps(m.to_dict())))
        self.assertEqual(again.counters, m.counters)
        self.assertEqual(loop.build_kpis({}, again)["build_rounds"], 3)


if __name__ == "__main__":
    unittest.main()
