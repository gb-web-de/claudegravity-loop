"""Tests für die Statuszeile nach jedem KI-Aufruf und den Abbruchgrund (#4 Live-Fortschritt)."""

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

ORIGINAL = run_smoke.answer


def metrics(tokens=0, usd=0.0):
    m = loop.SessionMetrics()
    if tokens:
        m.add("Claude Code", tokens, 0, cost_usd=usd, role="🔨 Bauleiter")
    return m


class FormatProgressTest(unittest.TestCase):
    def test_builder_with_stage_proof_and_budget(self):
        state = {"last_iteration": 3, "iteration_limit": 8, "stages": ["a", "b", "c"], "stage_index": 1,
                 "stage_mode_active": True, "proof": "make test"}
        lines = loop.format_progress("builder", "Claude Code", state, metrics(40_000, 0.25), 75, 12_000,
                                     loop.Budget(max_total="100k"))
        self.assertEqual(lines[0], "📍 Bau-Runde 3/8 · Etappe 2/3 · 🔨 Bauleiter Claude Code fertig nach 1 min 15 s · "
                                   "+12k Tokens (gesamt 40k Tokens, 0.25 USD gemeldet)")
        self.assertEqual(lines[1], "   Weiter: Prüfbefehl `make test` · Budget 40% von 100k Tokens")

    def test_plan_roles_and_inspection(self):
        planner = loop.format_progress("planner", "Codex", {"rounds_completed": 1}, metrics(500), 4, 500)
        self.assertIn("Plan-Runde 2 · 🏗️ Architekt Codex fertig nach 4 s", planner[0])
        self.assertNotIn("USD", planner[0])
        self.assertEqual(planner[1], "   Weiter: Prüfstatiker prüft den Plan")
        reviewer = loop.format_progress("reviewer", "Prüfstatiker Endpoint (http://x/v1)", {}, None, 1, 0)
        self.assertIn("🧐 Prüfstatiker Endpoint (http://x/v1)", reviewer[0])
        self.assertIn("Freigabe oder Überarbeitung", reviewer[1])
        inspection = loop.format_progress("inspector", "Gemini", {"inspection_rounds": 2}, metrics(10), 2, 10)
        self.assertIn("Abnahme-Runde 2", inspection[0])

    def test_builder_without_proof_or_stages(self):
        lines = loop.format_progress("builder", "Ollama", {"last_iteration": 1, "max_iterations": 10}, metrics(), 0, 0)
        self.assertTrue(lines[0].startswith("📍 Bau-Runde 1/10 · 🔨 Bauleiter Ollama"))
        self.assertIn("Fertigmeldung prüfen", lines[1])


class AbortReasonEndToEndTest(unittest.TestCase):
    def run_loop(self, extra, answer):
        server, url = run_smoke.start_server()
        try:
            with tempfile.TemporaryDirectory() as tmp_name, unittest.mock.patch.object(run_smoke, "answer", answer):
                tmp = Path(tmp_name)
                project = tmp / "projekt"
                (project / "tests").mkdir(parents=True)
                (tmp / "leer").mkdir()
                cmd = run_smoke.smoke_command(project, url, "balanced") + extra
                res = subprocess.run(cmd, input="", capture_output=True, text=True, encoding="utf-8",
                                     timeout=120, env=run_smoke.smoke_env(tmp))
                session = sorted((project / ".dual-loop" / "sessions").glob("*"))[-1]
                state = json.loads((session / "state.json").read_text(encoding="utf-8"))
                audit = (session / "AUDIT.md").read_text(encoding="utf-8") if (session / "AUDIT.md").exists() else ""
                return res.stdout, state, audit
        finally:
            server.shutdown()
            server.server_close()

    def test_round_limit_names_reason(self):
        def lazy_builder(prompt):
            if "Führe den genehmigten Plan" in prompt:
                return "Ich bin noch nicht fertig."
            return ORIGINAL(prompt)
        out, state, audit = self.run_loop(["-m", "2", "--no-inspect"], lazy_builder)
        self.assertIn("📍 Bau-Runde 2/2 · 🔨 Bauleiter", out)
        self.assertIn("⏹️ Abbruchgrund: Rundenlimit erreicht (2 Bau-Runden)", out)
        self.assertEqual(state["abort_reason"], "Rundenlimit erreicht (2 Bau-Runden)")
        self.assertIn("* **Abbruchgrund:** Rundenlimit erreicht (2 Bau-Runden)", audit)

    def test_no_progress_flag(self):
        out, state, _ = self.run_loop(["--no-progress"], ORIGINAL)
        self.assertEqual(state["phase"], "completed")
        self.assertNotIn("📍", out)
        self.assertNotIn("Abbruchgrund", out)


if __name__ == "__main__":
    unittest.main()
