"""Tests für das Benchmark-Pack (tools/benchmark): Aufgaben sind anfangs rot, Musterlösung grün, Ablauf im Fake-Modus."""

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "benchmark"))

import benchmark  # noqa: E402


def run_tests(folder: Path) -> int:
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=folder, capture_output=True, timeout=60
    ).returncode


class TaskPackTest(unittest.TestCase):
    def test_every_task_starts_red_and_solution_is_green(self):
        self.assertGreaterEqual(len(benchmark.list_tasks()), 3)
        for task in benchmark.list_tasks():
            with self.subTest(task=task), tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp) / "p"
                benchmark.prepare_project(task, work, git=False)
                self.assertNotEqual(run_tests(work), 0, f"{task}: Tests sind schon ohne Lösung grün")
                shutil.copytree(benchmark.TASKS_DIR / task / "solution", work, dirs_exist_ok=True)
                self.assertEqual(run_tests(work), 0, f"{task}: Musterlösung besteht die Tests nicht")


class FakeRunTest(unittest.TestCase):
    def run_main(self, args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = benchmark.main(args)
        return code, out.getvalue()

    def test_fake_run_writes_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_main(["--fake", "--tasks", "median-bug", "--strategies", "balanced,local-free", "--out", tmp])
            self.assertEqual(code, 0, out)
            results = json.loads((Path(tmp) / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [(r["strategy"], r["success"], r["build_rounds"]) for r in results], [("balanced", True, 1), ("local-free", True, 1)]
            )
            self.assertIn("| balanced | 1/1 |", (Path(tmp) / "results.md").read_text(encoding="utf-8"))
            self.assertTrue((Path(tmp) / "median-bug-balanced.log").exists())

    def test_failing_builder_is_reported(self):
        with unittest.mock.patch.object(
            benchmark, "fake_answer", lambda prompt, solution: "VERDICT: APPROVED" if "Führe" not in prompt else "keine Ahnung"
        ):
            code, out = self.run_main(["--fake", "--tasks", "fizzbuzz", "--", "-m", "1"])
        self.assertEqual(code, 1)
        self.assertIn("❌ Rundenlimit erreicht (1 Bau-Runden)", out)

    def test_weakened_tests_do_not_count(self):
        cheat = (
            "```filepath: tests/test_stats.py\nimport unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n```"
        )

        def answer(prompt, solution):
            if "Führe den genehmigten Plan" in prompt:
                done = benchmark.re.search(r"unter: '([^']+)'", prompt)
                return cheat + f"\n\n```filepath: {done.group(1)}\nfertig\n```"
            return original(prompt, solution)

        original = benchmark.fake_answer
        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch.object(benchmark, "fake_answer", answer):
            code, out = self.run_main(["--fake", "--tasks", "median-bug", "--out", tmp])
            results = json.loads((Path(tmp) / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 1, out)
        self.assertEqual((results[0]["loop_success"], results[0]["original_tests"], results[0]["success"]), (True, False, False))
        self.assertIn("Original-Tests rot", out)

    def test_baseline_runs_single_cli_and_checks_original_tests(self):
        def solve(binary, prompt, cwd=None, flags=None):
            shutil.copytree(benchmark.TASKS_DIR / "median-bug" / "solution", cwd, dirs_exist_ok=True)
            return "fertig", {"input_tokens": 10, "output_tokens": 5}

        agents = {"fake": benchmark.loop.AgentCLI("Fake", "fake", solve)}
        with tempfile.TemporaryDirectory() as tmp:
            result = benchmark.run_baseline("median-bug", "fake", Path(tmp), 60, agents)
        self.assertEqual((result["strategy"], result["success"], result["tokens_total"]), ("allein:fake", True, 15))

    def test_repeat_and_summary_quote(self):
        code, out = self.run_main(["--fake", "--tasks", "fizzbuzz", "--repeat", "2"])
        self.assertEqual(code, 0, out)
        self.assertIn("| balanced | 2/2 | 100 % |", out)

    def test_unknown_task(self):
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()), unittest.mock.patch("sys.stderr", io.StringIO()):
            benchmark.main(["--tasks", "gibtsnicht"])


if __name__ == "__main__":
    unittest.main()
