"""Tests für Suchen/Ersetzen-Blöcke von Endpunkt-Bauleitern (statt ganzer Dateien)."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402


def edit(path: str, *pairs: tuple[str, str], marker: tuple[str, str] = ("SUCHEN", "ERSETZEN")) -> str:
    body = "".join(f"<<<<<<< {marker[0]}\n{old}=======\n{new}>>>>>>> {marker[1]}\n" for old, new in pairs)
    return f"```edit: {path}\n{body}```"


class ApplyEditBlocksTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "src").mkdir()
        self.file = self.root / "src" / "calc.py"
        self.file.write_text("def add(a, b):\n    return a - b\n\n\ndef sub(a, b):\n    return a - b\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_applies_several_pairs(self):
        text = "Erklärung\n" + edit(
            "src/calc.py",
            ("def add(a, b):\n    return a - b\n", "def add(a, b):\n    return a + b\n"),
            ("def sub(a, b):\n", "def sub(a: int, b: int):\n"),
        )
        changed, errors = loop.apply_edit_blocks(self.root, text)
        self.assertEqual((changed, errors), (["src/calc.py"], []))
        content = self.file.read_text(encoding="utf-8")
        self.assertIn("return a + b", content)
        self.assertIn("def sub(a: int, b: int):\n    return a - b", content)

    def test_english_markers(self):
        text = edit("src/calc.py", ("return a - b\n\n\n", "return a + b\n\n\n"), marker=("SEARCH", "REPLACE"))
        changed, errors = loop.apply_edit_blocks(self.root, text)
        self.assertEqual((changed, errors), (["src/calc.py"], []))

    def test_missing_or_ambiguous_search_leaves_file_unchanged(self):
        before = self.file.read_text(encoding="utf-8")
        text = edit("src/calc.py", ("def add(a, b):\n", "def add(x, y):\n"), ("gibt es nicht\n", "x\n"))
        changed, errors = loop.apply_edit_blocks(self.root, text)
        self.assertEqual(changed, [])
        self.assertIn("nicht gefunden", errors[0])
        changed, errors = loop.apply_edit_blocks(self.root, edit("src/calc.py", ("return a - b\n", "return 0\n")))
        self.assertIn("2-mal gefunden", errors[0])
        self.assertEqual(self.file.read_text(encoding="utf-8"), before)

    def test_new_file_must_come_as_filepath_block(self):
        changed, errors = loop.apply_edit_blocks(self.root, edit("src/neu.py", ("a\n", "b\n")))
        self.assertEqual(changed, [])
        self.assertIn("filepath", errors[0])

    def test_blocked_paths(self):
        (self.root / ".env").write_text("TOKEN=1\n", encoding="utf-8")
        blocked = []
        for path in (".env", "../aussen.py", "/etc/passwd", ".git/config"):
            changed, _ = loop.apply_edit_blocks(self.root, edit(path, ("TOKEN=1\n", "TOKEN=2\n")), on_blocked=blocked.append)
            self.assertEqual(changed, [])
        self.assertEqual(len(blocked), 4)
        self.assertEqual((self.root / ".env").read_text(encoding="utf-8"), "TOKEN=1\n")

    def test_build_call_reports_failed_edits(self):
        ctx = loop.BuildContext(
            work_path=self.root,
            session_dir=self.root,
            session_log=self.root / "loop.log",
            state={},
            metrics=loop.SessionMetrics(),
            agents={},
            auto_switch=False,
            inspector=None,
            written_so_far=[],
        )
        answer = edit("src/calc.py", ("return a - b\n\n\n", "return a + b\n\n\n")) + "\n" + edit("src/calc.py", ("fehlt\n", "x\n"))
        builder = loop.AgentCLI("Intranet", "endpoint", None)
        with mock.patch.object(loop.build, "safe_agent_run", return_value=(answer, builder, [])):
            _, _, _, written = loop.run_build_call(ctx, builder, [], "p", True, "w", "l", "h")
        self.assertEqual(written, ["src/calc.py"])
        self.assertEqual(ctx.written_so_far, ["src/calc.py"])
        self.assertEqual(len(ctx.edit_errors), 1)
        self.assertIn("NICHT angewendet", loop.edit_errors_note(ctx.edit_errors))
        self.assertEqual(loop.edit_errors_note([]), "")


if __name__ == "__main__":
    unittest.main()
