"""Installation mit pipx/uv/pip: pyproject.toml, Einstiegspunkte und `python -m claudegravity`."""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import claudegravity  # noqa: E402
import mcp_server  # noqa: E402

try:
    import tomllib
except ImportError:  # Python 3.10
    tomllib = None


@unittest.skipIf(tomllib is None, "tomllib erst ab Python 3.11")
class PyprojectTest(unittest.TestCase):
    def setUp(self):
        self.data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_no_runtime_dependencies(self):
        self.assertEqual(self.data["project"]["dependencies"], [])
        self.assertEqual(self.data["project"]["requires-python"], ">=3.10")

    def test_version_comes_from_package(self):
        self.assertEqual(self.data["project"]["dynamic"], ["version"])
        self.assertEqual(self.data["tool"]["setuptools"]["dynamic"]["version"], {"attr": "claudegravity.__version__"})

    def test_scripts_point_to_callables(self):
        scripts = self.data["project"]["scripts"]
        self.assertEqual(set(scripts), {"claudegravity", "claudegravity-loop", "claudegravity-mcp"})
        for target in scripts.values():
            module_name, func = target.split(":")
            module = __import__(module_name, fromlist=[func])
            self.assertTrue(callable(getattr(module, func)), target)

    def test_package_has_no_unlisted_subpackages(self):
        listed = set(self.data["tool"]["setuptools"]["packages"])
        found = {".".join(p.parent.relative_to(ROOT).parts) for p in (ROOT / "claudegravity").rglob("__init__.py")}
        self.assertEqual(found, listed)
        self.assertEqual(self.data["tool"]["setuptools"]["py-modules"], ["mcp_server"])


class ModuleEntryTest(unittest.TestCase):
    def test_python_m_claudegravity(self):
        res = subprocess.run([sys.executable, "-m", "claudegravity", "--version"], capture_output=True, text=True, cwd=ROOT, timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), f"claudegravity {claudegravity.__version__}")

    def test_mcp_server_without_loop_py_uses_module(self):
        self.assertEqual(mcp_server.loop_launch_argv(["x"])[1], str(ROOT / "loop.py"))
        with mock.patch.object(mcp_server, "__file__", str(ROOT / "nirgends" / "mcp_server.py")):
            self.assertEqual(mcp_server.loop_launch_argv(["x"]), [sys.executable, "-m", "claudegravity", "x"])


if __name__ == "__main__":
    unittest.main()
