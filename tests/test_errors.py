"""Tests für Fehlercodes (CG-1xxx), Lösungshinweise und Doku-Verweise."""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402


class ErrorCodeTest(unittest.TestCase):
    def test_classification(self):
        cases = {
            "Verbindungsfehler zu http://pi:11434/v1: [Errno 111] Connection refused": "CG-1201",
            "Zeitüberschreitung nach 900 s bei http://localhost:11434/v1.": "CG-1202",
            "API-Fehler an https://x/v1: HTTP 401 (Unauthorized): ": "CG-1203",
            "API-Fehler an http://localhost:11434/v1: HTTP 404 (Not Found): model 'qwen' not found": "CG-1204",
            "Leere Antwort vom Endpunkt x: {}": "CG-1205",
            "Claude Fehler: something odd": "CG-1206",
            "Agent-CLI 'ollama' ist nicht verfügbar.": "CG-1002",
            "ganz etwas anderes": "CG-1999",
        }
        for text, code in cases.items():
            self.assertEqual(loop.classify_error(text), code, text)

    def test_format_masks_and_links(self):
        out = loop.format_error("CG-1203", "Token ghp_" + "A" * 36 + " abgelehnt")
        self.assertIn("[CG-1203]", out)
        self.assertNotIn("A" * 36, out)
        self.assertIn("docs/de/fehlerbehebung.md#cg-1203", out)

    def test_every_code_is_documented_in_both_languages(self):
        for lang in ("de", "en"):
            doc = (ROOT / "docs" / lang / "fehlerbehebung.md").read_text(encoding="utf-8")
            anchors = set(re.findall(r'<a id="(cg-\d{4})"></a>', doc))
            self.assertEqual(anchors, {c.lower() for c in loop.ERROR_CODES}, lang)

    def test_unexpected_error_shows_code_not_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDEGRAVITY_")}
            env.update(PATH=tmp, CLAUDEGRAVITY_CONFIG_DIR=tmp, PYTHONIOENCODING="utf-8")
            res = subprocess.run(
                [sys.executable, str(ROOT / "loop.py"), "x", "-p", str(Path(tmp) / "fehlt"), "--endpoint", "http://127.0.0.1:9/v1"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=60,
                env=env,
            )
        self.assertEqual(res.returncode, 1)
        self.assertIn("[CG-1003]", res.stderr)
        self.assertNotIn("Traceback", res.stderr)


if __name__ == "__main__":
    unittest.main()
