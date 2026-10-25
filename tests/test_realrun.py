"""Tests für tools/realrun.py: Prüfungen mit Attrappen-Backends, Bericht und Exit-Code."""

import datetime
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import loop  # noqa: E402
import realrun  # noqa: E402


def fake_backend(binary, answer, write_probe=False, session="s-1"):
    """Attrappe: merkt sich die Zahl einer Sitzung und schreibt auf Wunsch trotz Lesemodus."""
    memory = {}

    def run_fn(_binary, prompt, cwd=None, flags=None):
        if "Lege im aktuellen Ordner" in prompt and write_probe:
            (Path(cwd) / realrun.PROBE_FILE).write_text("x")
        if "Merke dir" in prompt:
            memory[session] = "4711"
        if "Geheimzahl?" in prompt:
            resumed = "--resume" in (flags or [])
            return (memory.get(session, "?") if resumed else "?"), {"session_id": session}
        return answer, {"session_id": session}

    return loop.AgentCLI(binary, binary, run_fn)


class RealrunChecksTest(unittest.TestCase):
    def run_checks(self, agents):
        with redirect_stdout(io.StringIO()), mock.patch.object(loop, "check_cli_auth", return_value=(True, "bereit")):
            return realrun.run_checks(agents, sorted(agents), full=False, timeout=10, out_dir=None)

    def test_good_backend_passes_all_checks(self):
        results = self.run_checks({"claude": fake_backend("claude", "banane")})
        self.assertEqual([(r["check"], r["ok"]) for r in results], [("antwort", True), ("lesend", True), ("fortsetzen", True)])

    def test_findings_are_reported_not_raised(self):
        def broken(*_a):
            raise RuntimeError("nicht angemeldet")

        agents = {"codex": fake_backend("codex", "falsch", write_probe=True), "gemini": loop.AgentCLI("g", "gemini", broken)}
        results = {(r["backend"], r["check"]): r for r in self.run_checks(agents)}
        self.assertFalse(results[("codex", "antwort")]["ok"])
        self.assertFalse(results[("codex", "lesend")]["ok"])
        self.assertIn("nicht angemeldet", results[("gemini", "antwort")]["detail"])
        self.assertNotIn(("gemini", "fortsetzen"), results)

    def test_not_ready_backend_is_skipped(self):
        with redirect_stdout(io.StringIO()), mock.patch.object(loop, "check_cli_auth", return_value=(False, "nicht angemeldet")):
            results = realrun.run_checks({"agy": fake_backend("agy", "x")}, ["agy"], full=False, timeout=10, out_dir=None)
        self.assertEqual([(r["check"], r["ok"]) for r in results], [("bereit", None)])

    def test_report_counts_and_escapes(self):
        results = [
            {"backend": "claude", "check": "antwort", "ok": True, "detail": "a|b", "seconds": 1.0},
            {"backend": "agy", "check": "bereit", "ok": None, "detail": "aus", "seconds": 0.0},
        ]
        report = realrun.format_report(results, datetime.datetime(2026, 10, 25, 12, 0))
        self.assertIn("1 von 1 Prüfungen bestanden. 1 Backend(s) übersprungen", report)
        self.assertIn("a\\|b", report)
        self.assertIn("| agy | bereit | ⏭ |", report)


if __name__ == "__main__":
    unittest.main()
