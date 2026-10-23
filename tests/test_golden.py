"""Golden Fixtures: Referenzausgaben zentraler Berichte und Läufe, gegen die jede Änderung geprüft wird.

Weicht eine Ausgabe ab, schlägt der Test fehl und zeigt den Unterschied. Ist die Änderung gewollt:
    UPDATE_GOLDEN=1 python3 -m unittest tests.test_golden
und die geänderten Dateien in tests/golden/ mit committen.
"""

import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = Path(__file__).resolve().parent / "golden"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent / "smoke"))

import loop  # noqa: E402
import run_smoke  # noqa: E402


def normalize(text: str, *paths: Path) -> str:
    """Entfernt, was sich von Lauf zu Lauf ändert: Pfade, Zeiten, Ports, Python-Pfad."""
    for p in paths:
        # Längste zuerst: unter macOS ist /var/... ein Symlink auf /private/var/...
        for variant in sorted({str(p), p.as_posix(), str(p.resolve()), p.resolve().as_posix()}, key=len, reverse=True):
            text = text.replace(variant, "<TMP>")
    # Windows: Pfade unterhalb von <TMP> mit / schreiben
    text = re.sub(r"<TMP>[^\s'\"]*", lambda m: m.group(0).replace("\\", "/"), text)
    text = text.replace(sys.executable, "<PYTHON>")
    text = re.sub(r"127\.0\.0\.1:\d+", "<SERVER>", text)
    text = re.sub(r"\d{8}_\d{6}", "<ZEIT>", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?", "<DATUM>", text)
    text = re.sub(r"\[\d{2}:\d{2}:\d{2}\]", "[<UHR>]", text)
    return text.replace("\r\n", "\n").rstrip() + "\n"


class GoldenTest(unittest.TestCase):
    maxDiff = None

    def check(self, name: str, actual: str):
        path = GOLDEN / name
        if os.environ.get("UPDATE_GOLDEN") or not path.exists():
            path.write_text(actual, encoding="utf-8")
            if not os.environ.get("UPDATE_GOLDEN"):
                self.fail(f"{name} neu angelegt; prüfen und committen")
            return
        self.assertEqual(actual, path.read_text(encoding="utf-8"), f"{name} weicht ab (gewollt? UPDATE_GOLDEN=1)")

    def test_kpi_block(self):
        m = loop.SessionMetrics()
        m.add("Codex", 1200, 300, cost_usd=0.0, role="🏗️ Architekt (Planung & Entwurf)")
        m.add("Ollama", 900, 150, role="🧐 Prüfstatiker (Prüfung & Review)")
        for _ in range(4):
            m.add("Ollama", 3000, 2000, role="🔨 Bauleiter (Bau & Umsetzung)")
        m.add("Claude Code", 800, 100, cost_usd=0.042, role="🔎 Abnahme")
        m.count("proof_red")
        m.count("proof_green")
        m.count("proof_green")
        state = {"phase": "completed", "strategy": "hybrid", "rounds_completed": 2,
                 "created_at": "2026-10-23T10:00:00", "stages": ["a", "b", "c"]}
        kpi = loop.build_kpis(state, m, now=datetime.datetime(2026, 10, 23, 10, 31, 5))
        self.check("kpi_block.md", normalize(loop.format_kpi_block(kpi)))

    def test_error_catalog(self):
        text = "\n\n".join(loop.format_error(code) for code in sorted(loop.ERROR_CODES))
        self.check("error_catalog.txt", normalize(text))

    def test_effective_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            project = tmp / "projekt"
            (project / ".dual-loop").mkdir(parents=True)
            (project / ".dual-loop" / "profile.json").write_text(json.dumps({
                "strategy": "hybrid", "proof": "vendor/bin/phpunit",
                "templates": {"typo3": {"etappen": "an", "hint": "TYPO3-Guidelines"}},
            }), encoding="utf-8")
            gpath = tmp / "cfg" / "profile.json"
            gpath.parent.mkdir()
            gpath.write_text(json.dumps({"max_rounds": 3, "auto_switch": True}), encoding="utf-8")
            parser = loop.build_parser()
            argv = ["--template", "typo3", "--bauer-model", "qwen2.5-coder:7b", "-p", str(project)]
            args = parser.parse_args(argv)
            report = loop.apply_config_layers(parser, args, argv, env={"CLAUDEGRAVITY_STRATEGY": "eco"}, global_path=gpath)
            self.check("effective_config.txt", normalize(loop.format_effective_config(report), tmp))

    @unittest.skipIf(sys.platform == "win32", "Pfad- und Konsolendarstellung unter Windows abweichend")
    def test_dry_run_local_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "leer").mkdir()
            ep = "http://127.0.0.1:9/v1"
            env = {"PATH": str(tmp / "leer"), "OLLAMA_HOST": "127.0.0.1:9", "PYTHONIOENCODING": "utf-8",
                   "CLAUDEGRAVITY_CONFIG_DIR": str(tmp), "HOME": str(tmp)}
            res = subprocess.run(
                [sys.executable, str(ROOT / "loop.py"), "--dry-run", "Addition mit Test", "-p", str(tmp), "--no-guide",
                 "--strategy", "local-free", "--proof", "make test",
                 "--architekt-endpoint", ep, "--architekt", "architekt_ep", "--architekt-model", "planer",
                 "--pruefstatiker-endpoint", ep, "--pruefstatiker", "pruefstatiker_ep", "--pruefstatiker-model", "pruefer",
                 "--bauer-endpoint", ep, "--bauer", "bauer_ep", "--bauer-model", "bauer"],
                capture_output=True, text=True, encoding="utf-8", timeout=60, env=env,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.check("dry_run_local_free.txt", normalize(res.stdout, tmp))

    @unittest.skipIf(sys.platform == "win32", "Pfad- und Konsolendarstellung unter Windows abweichend")
    def test_smoke_session(self):
        with tempfile.TemporaryDirectory() as out:
            out = Path(out)
            summary = run_smoke.run_smoke("local-free", out)
            self.assertTrue(summary["ok"], summary["stdout"][-2000:])
            session = out / "session"
            files = sorted(p.relative_to(session).as_posix() for p in session.rglob("*") if p.is_file())
            kpi = dict(summary["kpi"])
            kpi["duration_s"] = "<DAUER>"
            text = "\n".join([
                "# Dateien im Session-Ordner", *files, "",
                "# LOG.md", (session / "LOG.md").read_text(encoding="utf-8"), "",
                "# Kennzahlen", json.dumps(kpi, indent=2, ensure_ascii=False),
            ])
            text = re.sub(r"/tmp/[^\s`'\"]+/projekt", "<PROJEKT>", text)
            self.check("smoke_session_local_free.txt", normalize(text))


if __name__ == "__main__":
    unittest.main()
