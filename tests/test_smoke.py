"""Smoke-Matrix lokal: dieselben Läufe wie der CI-Job `smoke` (balanced und local-free mit Fake-Server)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "smoke"))

import run_smoke  # noqa: E402


class SmokeTest(unittest.TestCase):
    def check(self, strategy: str, stage_count: int):
        summary = run_smoke.run_smoke(strategy)
        self.assertTrue(summary["ok"], summary["stdout"][-3000:] + summary["stderr"][-2000:])
        self.assertEqual(summary["kpi"]["strategy"], strategy)
        self.assertEqual(summary["kpi"]["stages"], stage_count)
        self.assertEqual(summary["kpi"]["proof_red"], 0)

    def test_balanced(self):
        self.check("balanced", 0)

    def test_local_free_in_stages(self):
        self.check("local-free", 2)


if __name__ == "__main__":
    unittest.main()
