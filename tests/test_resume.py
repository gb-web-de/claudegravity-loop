"""Robustheit beim Fortsetzen: atomarer Sitzungsstand, beschädigte Dateien, Absturz mitten im Bau."""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402


class StateFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_roundtrip_and_backup(self):
        loop.save_session_state(self.dir, {"phase": "plan"})
        loop.save_session_state(self.dir, {"phase": "build"})
        self.assertEqual(loop.load_session_state(self.dir)["phase"], "build")
        self.assertEqual(json.loads((self.dir / "state.json.bak").read_text(encoding="utf-8"))["phase"], "plan")
        self.assertFalse((self.dir / "state.json.tmp").exists())

    def test_crash_during_write_keeps_old_state(self):
        loop.save_session_state(self.dir, {"phase": "plan", "rounds_completed": 1})
        with mock.patch.object(loop.os, "replace", side_effect=OSError("Strom weg")), self.assertRaises(OSError):
            loop.save_session_state(self.dir, {"phase": "build"})
        self.assertEqual(loop.load_session_state(self.dir), json.loads((self.dir / "state.json").read_text(encoding="utf-8")))
        self.assertEqual(loop.load_session_state(self.dir)["phase"], "plan")

    def test_corrupt_state_falls_back_to_backup(self):
        loop.save_session_state(self.dir, {"phase": "plan"})
        loop.save_session_state(self.dir, {"phase": "build"})
        (self.dir / "state.json").write_text('{"phase": "bu', encoding="utf-8")
        self.assertEqual(loop.load_session_state(self.dir)["phase"], "plan")
        (self.dir / "state.json.bak").write_text("[]", encoding="utf-8")
        self.assertEqual(loop.load_session_state(self.dir), {})


FAKE_CLAUDE = r'''
import json, os, pathlib, re, signal, sys
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"bin": "claude", "build": "Führe den genehmigten Plan" in prompt}) + "\n")
if "Führe den genehmigten Plan" in prompt:
    pathlib.Path("hallo.txt").write_text("hallo\n", encoding="utf-8")
    if os.environ.get("FAKE_CRASH") == "vor-done":
        os.kill(os.getppid(), signal.SIGKILL)  # harter Absturz des Loops mitten im Bau
        sys.exit(0)
    done = pathlib.Path(re.search(r"unter: '([^']+)'", prompt).group(1))
    done.write_text("fertig\n", encoding="utf-8")
    if os.environ.get("FAKE_CRASH") == "nach-done":
        os.kill(os.getppid(), signal.SIGKILL)  # Bau fertig, Loop stürzt vor der Abnahme ab
        sys.exit(0)
    out = "gebaut"
else:
    out = "# Plan\n- hallo.txt anlegen\n"
print(json.dumps({"result": out, "session_id": "s1", "usage": {"input_tokens": 9, "output_tokens": 4}}))
'''

FAKE_GEMINI = r'''
import json, os, sys
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"bin": "gemini", "inspection": "unabhängige Abnahme" in prompt}) + "\n")
print("BEFUNDE:\n- keine\nVERDICT: APPROVED")
'''


@unittest.skipIf(sys.platform == "win32", "Fake-CLIs als Shebang-Skripte und SIGKILL nur unter Unix")
class CrashResumeTest(unittest.TestCase):
    def test_crash_during_build_repeats_only_that_round(self):
        self.crash_and_resume("vor-done", expected_builds=2)

    def test_crash_after_done_goes_straight_to_acceptance(self):
        self.crash_and_resume("nach-done", expected_builds=1)

    def crash_and_resume(self, crash: str, expected_builds: int):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bindir, project = tmp / "bin", tmp / "proj"
            bindir.mkdir()
            project.mkdir()
            for name, body in (("claude", FAKE_CLAUDE), ("gemini", FAKE_GEMINI)):
                script = bindir / name
                script.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body), encoding="utf-8")
                script.chmod(0o755)
            log = tmp / "calls.jsonl"
            env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDEGRAVITY_") and k not in ("OPENAI_BASE_URL", "AI_ENDPOINT")}
            env.update(PATH=str(bindir), FAKE_LOG=str(log), CLAUDEGRAVITY_CONFIG_DIR=str(tmp), PYTHONIOENCODING="utf-8")
            base = [sys.executable, str(ROOT / "loop.py"), "-p", str(project), "--planner", "claude", "--reviewer", "gemini",
                    "--yolo", "-d", "0", "-m", "3", "--no-worktree"]

            crashed = subprocess.run(base + ["Lege hallo.txt an"], input="1\n", capture_output=True, text=True,
                                     encoding="utf-8", timeout=120, env=dict(env, FAKE_CRASH=crash))
            self.assertLess(crashed.returncode, 0, crashed.stdout[-2000:])  # durch SIGKILL beendet
            session = next((project / ".dual-loop" / "sessions").iterdir())
            state = loop.load_session_state(session)
            self.assertTrue(state.get("plan_approved"))
            self.assertNotEqual(state.get("phase"), "completed")
            self.assertFalse(list(session.glob("state.json.tmp")))

            resumed = subprocess.run(base + ["-c"], input="", capture_output=True, text=True,
                                     encoding="utf-8", timeout=120, env=env)
            self.assertEqual(resumed.returncode, 0, resumed.stdout[-3000:] + resumed.stderr[-2000:])
            calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            plans = [c for c in calls if c["bin"] == "claude" and not c["build"]]
            reviews = [c for c in calls if c["bin"] == "gemini" and not c["inspection"]]
            builds = [c for c in calls if c.get("build")]
            self.assertEqual(len(plans), 1, "Plan wurde nach dem Absturz neu erstellt")
            self.assertEqual(len(reviews), 1, "Review wurde nach dem Absturz wiederholt")
            self.assertEqual(len(builds), expected_builds)
            self.assertEqual(len([c for c in calls if c.get("inspection")]), 1)
            state = loop.load_session_state(session)
            self.assertEqual(state["phase"], "completed")
            self.assertTrue((session / ".done").exists())
            self.assertEqual(len(list(session.glob("PLAN_v*.md"))), 1)


if __name__ == "__main__":
    unittest.main()
