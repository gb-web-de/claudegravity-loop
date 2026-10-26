"""Repo-Karte für Rollen ohne Dateizugriff: Dateiliste, Symbole je Sprache, Sortierung, Grenze und Einbau in Prompts."""

import contextlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402
from claudegravity import common, repomap  # noqa: E402


@contextlib.contextmanager
def mode(value: str):
    old = common.SETTINGS.repo_map
    common.SETTINGS.repo_map = value
    try:
        yield
    finally:
        common.SETTINGS.repo_map = old


def write(base: Path, rel: str, text: str) -> None:
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class SymbolTest(unittest.TestCase):
    def test_python_functions_and_classes(self):
        src = "def add(a, b=1, *rest, key=None, **kw):\n    pass\n\nclass Calc:\n    def __init__(self):\n        pass\n    def sub(self, x):\n        pass\n"
        self.assertEqual(repomap.python_symbols(src), ["def add(a, b, *rest, key, **kw)", "class Calc [sub]"])

    def test_python_syntax_error_falls_back(self):
        self.assertEqual(repomap.python_symbols("def ok():\n    pass\ndef kaputt(:\n"), ["def ok", "def kaputt"])

    def test_other_languages(self):
        js = "export default class Cart {}\nexport async function total(items) {}\nexport const sum = (a) => a\ntype Item = {}\n"
        self.assertEqual(repomap.file_symbols("src/cart.ts", js), ["class Cart", "function total", "const sum", "type Item"])
        php = "<?php\nfinal class Flyer\n{\n    public static function render(): string {}\n}\n"
        self.assertEqual(repomap.file_symbols("Classes/Flyer.php", php), ["class Flyer", "function render"])
        go = "package x\nfunc (s *Server) Start() {}\ntype Server struct {}\n"
        self.assertEqual(repomap.file_symbols("main.go", go), ["func Start", "type Server"])
        self.assertEqual(repomap.file_symbols("README.md", "# Titel"), [])


class MapTest(unittest.TestCase):
    def make_project(self, tmp: Path, git: bool) -> Path:
        project = tmp / "p"
        write(project, "src/stats.py", "def median(values):\n    pass\n")
        write(project, "src/other.py", "def unrelated():\n    pass\n")
        write(project, "tests/test_stats.py", "def test_median():\n    pass\n")
        write(project, ".env", "TOKEN=geheim\n")
        write(project, "node_modules/lib/index.js", "function hidden() {}\n")
        write(project, "logo.png", "nicht wirklich ein Bild")
        write(project, "build/out.py", "def generated():\n    pass\n")
        if git:
            write(project, ".gitignore", "build/\n")
            subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        return project

    def test_files_skip_secrets_dependencies_and_binaries(self):
        for git in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                files = repomap.list_project_files(self.make_project(Path(tmp), git))
            self.assertIn("src/stats.py", files, git)
            for hidden in (".env", "node_modules/lib/index.js", "logo.png", "build/out.py"):
                self.assertNotIn(hidden, files, (git, hidden))

    def test_map_sorts_by_task_and_shows_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = repomap.repo_map(self.make_project(Path(tmp), False), "Fix den Fehler in `src/stats.py` beim median")
        lines = text.splitlines()
        self.assertEqual(lines[0], "src/stats.py: def median(values)")
        self.assertIn("tests/test_stats.py: def test_median()", lines)
        self.assertNotIn("geheim", text)

    def test_limit_and_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            for i in range(80):
                write(project, f"pkg/modul_{i:02d}.py", f"def funktion_{i}(a, b):\n    pass\n")
            text = repomap.repo_map(project, "", limit=500)
        self.assertLessEqual(len(text), 500)
        self.assertRegex(text.splitlines()[-1], r"^\(… \d+ weitere Dateien ausgelassen\)$")

    def test_empty_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(repomap.repo_map(Path(tmp)), "")
        self.assertEqual(repomap.repo_map_block(""), "")


class UseTest(unittest.TestCase):
    def test_modes(self):
        with mode("auto"):
            self.assertTrue(repomap.wants_repo_map("bauer_ep"))
            self.assertFalse(repomap.wants_repo_map("claude"))
        with mode("an"):
            self.assertTrue(repomap.wants_repo_map("claude"))
        with mode("aus"):
            self.assertFalse(repomap.wants_repo_map("ollama"))

    def test_flag_sets_mode(self):
        with mode("auto"):
            args = loop.build_parser().parse_args(["x", "--repo-map", "off"])
            loop.apply_runtime_settings(args)
            self.assertEqual(common.SETTINGS.repo_map, "aus")

    def test_build_prompt_carries_map_before_changing_part(self):
        for stage in (None, ("Etappe 1/2", "Funktion bauen", "- (noch keine)")):
            prompt = loop.compose_build_prompt(
                "Aufgabe", Path("PLAN_v1.md"), None, "Rückmeldung", True, plan_text="Plan", stage=stage, repo_map="src/a.py: def f()"
            )
            self.assertIn("--- REPO-KARTE", prompt)
            self.assertLess(prompt.index("REPO-KARTE"), prompt.index("Rückmeldung"))
        resumed = loop.compose_build_prompt("A", Path("P.md"), None, "", False, repo_map="src/a.py", resumed=True)
        self.assertNotIn("REPO-KARTE", resumed)


if __name__ == "__main__":
    unittest.main()
