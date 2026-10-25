"""Tests für den Testwächter: geschönte Tests seit dem Basis-Commit erkennen."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402

ORIGINAL = """import unittest


class T(unittest.TestCase):
    def test_a(self):
        self.assertEqual(1, 1)

    def test_b(self):
        self.assertTrue(True)
"""


@unittest.skipUnless(shutil.which("git"), "git fehlt")
class TestGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "tests").mkdir()
        (self.tmp / "tests" / "test_x.py").write_text(ORIGINAL)
        (self.tmp / "tests" / "test_y.py").write_text(ORIGINAL)
        (self.tmp / "app.py").write_text("x = 1\n")
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@localhost"]
        for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "start"]):
            subprocess.run(git + cmd, cwd=self.tmp, check=True, capture_output=True)
        self.base = loop.git_head(self.tmp)

    def findings(self):
        return loop.test_integrity_findings(self.tmp, self.base)

    def test_clean_change_has_no_findings(self):
        (self.tmp / "app.py").write_text("x = 2\n")
        (self.tmp / "tests" / "test_x.py").write_text(ORIGINAL + "\n    def test_c(self):\n        self.assertEqual(2, 2)\n")
        self.assertEqual(self.findings(), [])

    def test_skip_marker_is_found(self):
        (self.tmp / "tests" / "test_x.py").write_text(ORIGINAL.replace("    def test_a", "    @unittest.skip('später')\n    def test_a"))
        self.assertEqual(self.findings(), ["tests/test_x.py: 1 neue(r) Skip-/Only-Marker"])

    def test_removed_case_and_deleted_file_are_found(self):
        (self.tmp / "tests" / "test_x.py").write_text(ORIGINAL.split("    def test_b")[0])
        (self.tmp / "tests" / "test_y.py").unlink()
        found = self.findings()
        self.assertIn("Testdatei gelöscht: tests/test_y.py", found)
        self.assertIn("tests/test_x.py: 1 Testfall/Testfälle weniger", found)
        self.assertIn("tests/test_x.py: 1 Prüfung(en) weniger", found)

    def test_weakened_assertion_is_found(self):
        (self.tmp / "tests" / "test_x.py").write_text(ORIGINAL.replace("        self.assertEqual(1, 1)\n", "        pass\n"))
        self.assertEqual(self.findings(), ["tests/test_x.py: 1 Prüfung(en) weniger"])

    def test_js_only_and_no_base(self):
        self.assertEqual(loop.test_integrity_findings(self.tmp, None), [])
        self.assertTrue(loop.build.SKIP_MARKER.search("describe.only('x', () => {})"))
        self.assertTrue(loop.build.SKIP_MARKER.search("    $this->markTestSkipped('kaputt');"))
        self.assertTrue(loop.build.TEST_PATH.search("src/app.spec.ts"))
        self.assertFalse(loop.build.TEST_PATH.search("src/contest.py"))

    def test_note_names_findings(self):
        note = loop.format_test_findings(["Testdatei gelöscht: tests/test_y.py"])
        self.assertIn("Testwächter", note)
        self.assertIn("- Testdatei gelöscht: tests/test_y.py", note)


if __name__ == "__main__":
    unittest.main()
