#!/usr/bin/env python3
"""Smoke-Lauf ohne KI-Abos: ein Fake-Server spielt alle Rollen über die OpenAI-kompatible API.

Aufruf:  python tests/smoke/run_smoke.py --strategy balanced|local-free --out smoke-artifacts/<name>
Ergebnis: Exit-Code 0, wenn die Session abgeschlossen ist; im Ausgabeordner liegen stdout, Session-Ordner,
Bau-Logs und summary.json (Kennzahlen aus der .done). Läuft unter Linux, macOS und Windows.
"""

import argparse
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CALC = "```filepath: src/calc.py\ndef add(a, b):\n    return a + b\n```"
TEST = (
    "```filepath: tests/test_calc.py\nimport sys, unittest\nsys.path.insert(0, 'src')\n"
    "from calc import add\n\nclass T(unittest.TestCase):\n    def test_add(self):\n"
    "        self.assertEqual(add(1, 2), 3)\n```"
)


def answer(prompt: str) -> str:
    """Antwort des Fake-Modells je nach Rolle, erkannt am Prompt."""
    if "leitende Software-Architekt" in prompt:
        return "# Plan\n\n1. Funktion add in src/calc.py\n2. Test in tests/test_calc.py\n\n## Etappen\n1. Funktion in src/calc.py\n2. Test in tests/test_calc.py\n"
    if "ETAPPE 1/2" in prompt:
        return CALC
    if "ETAPPE 2/2" in prompt:
        return TEST
    if "Führe den genehmigten Plan" in prompt:
        # Endpunkt-Bauleiter melden "fertig", indem sie die .done-Datei als Block schreiben
        done = re.search(r"unter: '([^']+)'", prompt)
        return CALC + "\n\n" + TEST + (f"\n\n```filepath: {done.group(1)}\nfertig\n```" if done else "")
    return "BEFUNDE:\n- keine\nVERDICT: APPROVED"


def start_server() -> tuple[http.server.HTTPServer, str]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = answer(req["messages"][-1]["content"])
            body = json.dumps({"choices": [{"message": {"content": out}}],
                               "usage": {"prompt_tokens": 100, "completion_tokens": 20}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/v1"


def smoke_command(project: Path, url: str, strategy: str) -> list[str]:
    cmd = [
        sys.executable, str(ROOT / "loop.py"), "Addition mit Test", "-p", str(project), "--no-worktree", "-d", "0",
        "--strategy", strategy, "--plan-auto", "--no-guide",
        "--architekt-endpoint", url, "--architekt", "architekt_ep", "--architekt-model", "planer",
        "--pruefstatiker-endpoint", url, "--pruefstatiker", "pruefstatiker_ep", "--pruefstatiker-model", "pruefer",
        "--bauer-endpoint", url, "--bauer", "bauer_ep", "--bauer-model", "bauer",
        "--abnahme", "pruefstatiker_ep",
        "--proof", f'"{sys.executable}" -m unittest discover -s tests',
    ]
    # balanced: ganzer Plan in einer Runde; local-free: Etappen wie bei lokalen Bauleitern üblich
    cmd += ["--etappen", "aus" if strategy == "balanced" else "auto"]
    return cmd


def smoke_env(tmp: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("CLAUDEGRAVITY_") and k not in ("OPENAI_BASE_URL", "AI_ENDPOINT", "OLLAMA_HOST")}
    env.update(PATH=str(tmp / "leer"), OLLAMA_HOST="127.0.0.1:9", PYTHONIOENCODING="utf-8",
               CLAUDEGRAVITY_CONFIG_DIR=str(tmp / "config"))
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return env


def read_kpi(done: Path) -> dict | None:
    text = done.read_text(encoding="utf-8") if done.exists() else ""
    if "```json\n" not in text:
        return None
    return json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])


def run_smoke(strategy: str, out_dir: Path | None = None) -> dict:
    server, url = start_server()
    try:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            project = tmp / "projekt"
            (project / "tests").mkdir(parents=True)
            # Ab Python 3.12 ist ein Testlauf ohne Tests rot; das Projekt hat daher schon einen Test
            (project / "tests" / "test_vorhanden.py").write_text(
                "import unittest\n\nclass Vorhanden(unittest.TestCase):\n    def test_ok(self):\n        pass\n", encoding="utf-8")
            (tmp / "leer").mkdir()
            res = subprocess.run(smoke_command(project, url, strategy), input="", capture_output=True, text=True,
                                 encoding="utf-8", timeout=300, env=smoke_env(tmp))
            sessions = sorted((project / ".dual-loop" / "sessions").glob("*"))
            session = sessions[-1] if sessions else None
            state = json.loads((session / "state.json").read_text(encoding="utf-8")) if session else {}
            kpi = read_kpi(session / ".done") if session else None
            summary = {
                "strategy": strategy,
                "platform": sys.platform,
                "python": sys.version.split()[0],
                "returncode": res.returncode,
                "phase": state.get("phase"),
                "files": sorted(p.relative_to(project).as_posix() for p in (project / "src").rglob("*.py")) if (project / "src").exists() else [],
                "kpi": kpi,
                "ok": res.returncode == 0 and state.get("phase") == "completed" and bool(kpi and kpi.get("success")),
            }
            if out_dir:
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "stdout.txt").write_text(res.stdout, encoding="utf-8")
                (out_dir / "stderr.txt").write_text(res.stderr, encoding="utf-8")
                if session:
                    shutil.copytree(session, out_dir / "session", dirs_exist_ok=True)
                if (project / "logs").exists():
                    shutil.copytree(project / "logs", out_dir / "logs", dirs_exist_ok=True)
                (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
            summary["stdout"] = res.stdout
            summary["stderr"] = res.stderr
            return summary
    finally:
        server.shutdown()
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strategy", default="balanced", choices=["balanced", "local-free"])
    parser.add_argument("--out", default=None, help="Ordner für Logs und Berichte (Artefakte)")
    args = parser.parse_args()
    summary = run_smoke(args.strategy, Path(args.out) if args.out else None)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("stdout", "stderr")}, indent=2, ensure_ascii=False))
    if not summary["ok"]:
        print(summary["stdout"][-4000:])
        print(summary["stderr"][-2000:], file=sys.stderr)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
