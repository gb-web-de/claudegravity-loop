"""Tests für die adaptive Eskalation eines lokalen Bauleiters auf eine Cloud-CLI (#7)."""

import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402


def agent(name, binary, local):
    return loop.AgentCLI(name, binary, lambda *a, **k: "", local=local)


AGENTS = {
    "ollama": agent("Ollama", "ollama", True),
    "claude": agent("Claude Code", "claude", False),
    "gemini": agent("Gemini CLI", "gemini", False),
    "endpoint": agent("Intranet", "endpoint", False),
}


class ChooseTest(unittest.TestCase):
    def test_off_or_cloud_builder(self):
        self.assertEqual(loop.choose_escalation(AGENTS["ollama"], AGENTS, None)[0], None)
        key, why = loop.choose_escalation(AGENTS["claude"], AGENTS, "auto", write_allowed=True)
        self.assertIsNone(key)
        self.assertIn("kein lokales Modell", why)

    def test_auto_prefers_planner_and_skips_inspector(self):
        choose = loop.choose_escalation
        self.assertEqual(choose(AGENTS["ollama"], AGENTS, "auto", prefer="gemini", write_allowed=True)[0], "gemini")
        self.assertEqual(
            choose(AGENTS["ollama"], AGENTS, "auto", inspector=AGENTS["claude"], prefer="claude", write_allowed=True)[0], "gemini"
        )

    def test_without_write_rights_only_endpoints(self):
        key, _ = loop.choose_escalation(AGENTS["ollama"], AGENTS, "auto", prefer="claude", write_allowed=False)
        self.assertEqual(key, "endpoint")
        key, why = loop.choose_escalation(AGENTS["ollama"], AGENTS, "claude", write_allowed=False)
        self.assertIsNone(key)
        self.assertIn("Schreibrechte", why)

    def test_explicit_target_checks(self):
        choose = loop.choose_escalation
        self.assertEqual(choose(AGENTS["ollama"], AGENTS, "claude", write_allowed=True), ("claude", ""))
        self.assertIn("nicht verfügbar", choose(AGENTS["ollama"], AGENTS, "codex", write_allowed=True)[1])
        self.assertIn("selbst lokal", choose(AGENTS["ollama"], AGENTS, "ollama", write_allowed=True)[1])
        self.assertIn("Abnahme", choose(AGENTS["ollama"], AGENTS, "claude", inspector=AGENTS["claude"], write_allowed=True)[1])
        only_local = {"ollama": AGENTS["ollama"]}
        self.assertIn("kein Cloud-Anbieter", choose(AGENTS["ollama"], only_local, "auto", write_allowed=True)[1])

    def test_kpi_block_names_escalation(self):
        state = {
            "phase": "completed",
            "strategy": "local-free",
            "escalation": {
                "from": "Ollama",
                "to": "Claude Code",
                "iteration": 3,
                "reason": "2 erfolglose Bau-Runden in Folge (zuletzt: Prüfbefehl rot)",
            },
        }
        block = loop.format_kpi_block(loop.build_kpis(state, loop.SessionMetrics()))
        self.assertIn("* **Eskalation:** Bau-Runde 3: Ollama → Claude Code (2 erfolglose Bau-Runden in Folge", block)


FAKE_CLAUDE = r"""
import json, os, pathlib, re, sys
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"bin": "claude", "argv": sys.argv[1:], "prompt": prompt}) + "\n")
if "Führe den genehmigten Plan" in prompt:
    pathlib.Path("hallo.txt").write_text("hallo\n", encoding="utf-8")
    pathlib.Path(re.search(r"unter: '([^']+)'", prompt).group(1)).write_text("fertig\n", encoding="utf-8")
    out = "gebaut"
else:
    out = "# Plan\n- hallo.txt anlegen\n"
print(json.dumps({"result": out, "session_id": "s1", "usage": {"input_tokens": 9, "output_tokens": 4}}))
"""

FAKE_GEMINI = r"""
import sys
sys.stdin.read()
print("BEFUNDE:\n- keine\nVERDICT: APPROVED")
"""


@unittest.skipIf(sys.platform == "win32", "Fake-CLIs als Shebang-Skripte nur unter Unix")
class EscalationEndToEndTest(unittest.TestCase):
    def setUp(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                body = json.dumps(
                    {
                        "choices": [{"message": {"content": "Ich weiß nicht weiter."}}],
                        "usage": {"prompt_tokens": 50, "completion_tokens": 5},
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def run_loop(self, extra):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        bindir, project = tmp / "bin", tmp / "proj"
        bindir.mkdir()
        project.mkdir()
        for name, body in (("claude", FAKE_CLAUDE), ("gemini", FAKE_GEMINI)):
            script = bindir / name
            script.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body), encoding="utf-8")
            script.chmod(0o755)
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("CLAUDEGRAVITY_") and k not in ("OPENAI_BASE_URL", "AI_ENDPOINT", "OLLAMA_HOST")
        }
        env.update(
            PATH=str(bindir), FAKE_LOG=str(tmp / "calls.jsonl"), CLAUDEGRAVITY_CONFIG_DIR=str(tmp / "cfg"), OLLAMA_HOST="127.0.0.1:9"
        )
        url = f"http://127.0.0.1:{self.server.server_port}/v1"
        proof = f'"{sys.executable}" -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'hallo.txt\').exists() else 1)"'
        res = subprocess.run(
            [
                sys.executable,
                str(ROOT / "loop.py"),
                "Lege hallo.txt an",
                "-p",
                str(project),
                "--no-worktree",
                "--planner",
                "claude",
                "--reviewer",
                "gemini",
                "--abnahme",
                "gemini",
                "--bauer-endpoint",
                url,
                "--bauer",
                "bauer_ep",
                "--bauer-model",
                "klein",
                "--proof",
                proof,
                "--plan-auto",
                "--no-guide",
                "--etappen",
                "aus",
                "-d",
                "0",
                "-m",
                "5",
                *extra,
            ],
            input="",
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            env=env,
        )
        session = next((project / ".dual-loop" / "sessions").iterdir())
        state = json.loads((session / "state.json").read_text(encoding="utf-8"))
        return res, state, session

    def test_local_builder_escalates_after_two_red_rounds(self):
        res, state, session = self.run_loop(["--yolo", "--escalate", "auto"])
        self.assertEqual(state["phase"], "completed", res.stdout[-3000:])
        esc = state["escalation"]
        self.assertEqual((esc["to"], esc["iteration"]), ("Claude Code", 2))
        self.assertIn("Prüfbefehl rot", esc["reason"])
        self.assertIn("⬆️ Eskalation:", res.stdout)
        done = (session / ".done").read_text(encoding="utf-8")
        self.assertIn("* **Eskalation:** Bau-Runde 2:", done)
        self.assertIn("Eskalation Bauleiter", (session / "LOG.md").read_text(encoding="utf-8"))

    def test_without_flag_no_escalation(self):
        res, state, _ = self.run_loop(["--yolo", "-m", "3"])
        self.assertNotIn("escalation", state)
        self.assertEqual(state["abort_reason"], "Rundenlimit erreicht (3 Bau-Runden)")

    def test_without_write_rights_refuses_cli(self):
        res, state, _ = self.run_loop(["--escalate", "claude", "-m", "3"])
        self.assertNotIn("escalation", state)
        self.assertIn("Eskalation nicht möglich: Claude Code bräuchte Schreibrechte", res.stdout)


if __name__ == "__main__":
    unittest.main()
