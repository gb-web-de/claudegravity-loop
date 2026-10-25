"""Tests für den Kandidaten-Modus (--candidates): Aufteilung, Auswahl und ein ganzer Lauf mit Fake-Server."""

import http.server
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "smoke"))

import loop  # noqa: E402
import run_smoke  # noqa: E402
from claudegravity import candidates as cand  # noqa: E402

GOOD = "```filepath: src/calc.py\ndef add(a, b):\n    return a + b\n```"
BAD = "```filepath: src/calc.py\ndef add(a, b):\n    return a - b\n```"


class ParseTest(unittest.TestCase):
    def test_names_are_unique_and_models_kept(self):
        got = [(c.name, c.binary, c.model) for c in cand.parse_candidates("claude, codex=gpt-5,ollama=qwen3-coder:30b,claude")]
        self.assertEqual(
            got,
            [
                ("claude", "claude", None),
                ("codex-gpt-5", "codex", "gpt-5"),
                ("ollama-qwen3-coder-30b", "ollama", "qwen3-coder:30b"),
                ("claude-2", "claude", None),
            ],
        )

    def test_winner_line(self):
        names = ["claude", "codex"]
        self.assertEqual(cand.parse_winner("Text\nWINNER: `codex`\nVERDICT: APPROVED", names), "codex")
        self.assertEqual(cand.parse_winner("**Gewinner:** claude", names), "claude")
        self.assertIsNone(cand.parse_winner("WINNER: gemini", names))
        self.assertIsNone(cand.parse_winner("kein Urteil", names))

    def test_fallback_prefers_clean_then_small(self):
        a = cand.Candidate("a", "x", diff="x" * 50, findings=["Testdatei gelöscht: t.py"])
        b = cand.Candidate("b", "x", diff="x" * 500)
        c = cand.Candidate("c", "x", diff="x" * 100)
        self.assertEqual(cand.fallback_winner([a, b, c]).name, "c")

    def test_child_state_starts_build_fresh(self):
        state = {"phase": "build", "task": "t", "builder_model": "opus", "worktree": {"path": "/x"}, "last_iteration": 4, "strategy": "eco"}
        child = cand.child_state(state, cand.Candidate("codex-gpt-5", "codex", "gpt-5"))
        self.assertEqual(child["builder_model"], "gpt-5")
        self.assertNotIn("worktree", child)
        self.assertEqual((child["last_iteration"], child["inspect"], child["strategy"], child["user_approved"]), (0, False, "eco", True))

    def test_child_command_keeps_key_out_of_argv(self):
        args = loop.cli.build_parser(True).parse_args(["x", "--api-key", "geheim", "--bauer-endpoint", "http://h/v1", "-m", "3"])
        c = cand.Candidate("bauer_ep-a", "bauer_ep", "a", work_dir=Path("/wt"))
        cmd = cand.child_command(args, c, "make test")
        self.assertNotIn("geheim", cmd)
        self.assertEqual(cand.child_env(args)["CLAUDEGRAVITY_API_KEY"], "geheim")
        for part in (
            ["-c", "-p", str(Path("/wt"))],
            ["--bauer-model", "a"],
            ["--proof", "make test"],
            ["-m", "3"],
            ["--bauer-endpoint", "http://h/v1"],
        ):
            self.assertTrue(any(cmd[i : i + len(part)] == part for i in range(len(cmd))), part)


def answer(prompt: str, model: str) -> str:
    if "Mehrere Bauleiter" in prompt:
        return "WINNER: bauer_ep-gut\n\nBEFUNDE:\n- keine\nVERDICT: APPROVED"
    if "leitende Software-Architekt" in prompt:
        return "# Plan\n\n1. add in src/calc.py\n"
    if "Führe den genehmigten Plan" in prompt or "Rückmeldung" in prompt:
        import re

        done = re.search(r"unter: '([^']+)'", prompt)
        body = GOOD if model == "gut" else BAD
        return body + (f"\n\n```filepath: {done.group(1)}\nfertig\n```" if done else "")
    return "BEFUNDE:\n- keine\nVERDICT: APPROVED"


@unittest.skipUnless(shutil.which("git"), "git fehlt")
class CandidatesRunTest(unittest.TestCase):
    def test_two_candidates_good_one_wins(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                out = answer(req["messages"][-1]["content"], req.get("model", ""))
                body = json.dumps(
                    {"choices": [{"message": {"content": out}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_port}/v1"
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            (tmp / "leer").mkdir()
            project = tmp / "projekt"
            (project / "tests").mkdir(parents=True)
            (project / "tests" / "test_calc.py").write_text(
                "import sys, unittest\nsys.path.insert(0, 'src')\n\n\nclass T(unittest.TestCase):\n"
                "    def test_add(self):\n        from calc import add\n        self.assertEqual(add(1, 2), 3)\n"
            )
            (project / ".gitignore").write_text(".dual-loop/\nlogs/\n")
            env = run_smoke.smoke_env(tmp)
            env["PATH"] = str(tmp / "leer") + (";" if sys.platform == "win32" else ":") + str(Path(shutil.which("git")).parent)
            git = ["git", "-c", "user.name=t", "-c", "user.email=t@localhost"]
            for c in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "start"]):
                subprocess.run(git + c, cwd=project, check=True, capture_output=True)
            cmd = [
                sys.executable, str(ROOT / "loop.py"), "Addition", "-p", str(project), "-d", "0", "--plan-auto", "--no-guide", "--yolo",
                "--architekt-endpoint", url, "--architekt", "architekt_ep", "--architekt-model", "planer",
                "--pruefstatiker-endpoint", url, "--pruefstatiker", "pruefstatiker_ep", "--pruefstatiker-model", "pruefer",
                "--bauer-endpoint", url, "--etappen", "aus", "-m", "1",
                "--candidates", "bauer_ep=gut,bauer_ep=schlecht",
                "--proof", f'"{sys.executable}" -m unittest discover -s tests',
            ]  # fmt: skip
            res = subprocess.run(cmd, input="", capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
            session = sorted((project / ".dual-loop" / "sessions").glob("*"))[-1]
            state = json.loads((session / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["phase"], "completed", res.stdout[-3000:] + res.stderr[-2000:])
            self.assertEqual(state["candidate_winner"], "bauer_ep-gut")
            results = {r["name"]: r for r in state["candidate_results"]}
            self.assertTrue(results["bauer_ep-gut"]["proof_ok"])
            self.assertFalse(results["bauer_ep-schlecht"]["proof_ok"])
            branch = results["bauer_ep-gut"]["branch"]
            shown = subprocess.run(["git", "show", f"{branch}:src/calc.py"], cwd=project, capture_output=True, text=True)
            self.assertIn("return a + b", shown.stdout)
            listed = subprocess.run(["git", "ls-tree", "-r", "--name-only", branch], cwd=project, capture_output=True, text=True)
            self.assertNotIn(".dual-loop", listed.stdout)
            self.assertTrue((session / ".done").exists())
            self.assertTrue((session / "candidates" / "bauer_ep-gut" / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
