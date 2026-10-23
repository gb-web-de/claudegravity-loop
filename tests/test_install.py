"""Tests für install.py: Server-Eintrag mit optionalem Standardprojekt."""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import install  # noqa: E402


class ServerEntryTest(unittest.TestCase):
    def test_entry_uses_absolute_python_and_optional_project(self):
        entry = install.server_entry()
        self.assertTrue(Path(entry["command"]).is_absolute())
        self.assertEqual(entry["args"], [str(ROOT / "mcp_server.py")])
        self.assertNotIn("CLAUDEGRAVITY_PROJECT", entry["env"])
        with mock.patch.object(install, "PROJECT_DIR", ROOT):
            self.assertEqual(install.server_entry()["env"]["CLAUDEGRAVITY_PROJECT"], str(ROOT))

    def test_host_is_set_per_client(self):
        self.assertEqual(install.server_entry(host="agy")["env"]["CLAUDEGRAVITY_HOST"], "agy")
        self.assertNotIn("CLAUDEGRAVITY_HOST", install.server_entry()["env"])


if __name__ == "__main__":
    unittest.main()
