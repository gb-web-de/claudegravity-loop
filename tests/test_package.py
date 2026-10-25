"""Paketaufteilung: loop.py bietet die Namen weiter an, und Module importieren nur Module vor sich."""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402
from claudegravity import cli, common, runner  # noqa: E402

ORDER = [
    "i18n",
    "common",
    "safety",
    "errors",
    "metrics",
    "backends",
    "session",
    "budget",
    "runner",
    "planning",
    "roles",
    "build",
    "config",
    "wizard",
    "phases",
    "candidates",
    "cli",
]


class PackageTest(unittest.TestCase):
    def test_loop_reexports_module_names(self):
        self.assertIs(loop.main, cli.main)
        self.assertIs(loop.SETTINGS, common.SETTINGS)
        self.assertIs(loop.safe_agent_run, runner.safe_agent_run)

    def test_modules_import_only_earlier_modules(self):
        files = {p.stem for p in (ROOT / "claudegravity").glob("*.py") if p.stem != "__init__"}
        self.assertEqual(files, set(ORDER))
        for pos, name in enumerate(ORDER):
            tree = ast.parse((ROOT / "claudegravity" / f"{name}.py").read_text(encoding="utf-8"))
            # Nur Importe, die beim Laden laufen; `if TYPE_CHECKING:` darf für Annotationen in beide Richtungen zeigen.
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                    self.assertLess(ORDER.index(node.module), pos, f"{name} importiert {node.module}")

    def test_public_functions_have_docstrings(self):
        missing = []
        for path in sorted((ROOT / "claudegravity").glob("*.py")) + [ROOT / "mcp_server.py"]:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
            nodes += [m for c in tree.body if isinstance(c, ast.ClassDef) for m in c.body if isinstance(m, ast.FunctionDef)]
            missing += [f"{path.name}:{n.name}" for n in nodes if not n.name.startswith("_") and not ast.get_docstring(n)]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
