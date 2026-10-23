"""Tests für install.py: Server-Eintrag mit optionalem Standardprojekt."""

import json
import sys
import tempfile
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


class AntigravityTest(unittest.TestCase):
    def test_writes_config_file_keeps_other_servers_and_cleans_old_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            gemini = Path(tmp)
            (gemini / "config").mkdir()
            (gemini / "antigravity").mkdir()
            new_file = gemini / "config" / "mcp_config.json"
            old_file = gemini / "antigravity" / "mcp_config.json"
            new_file.write_text(json.dumps({"mcpServers": {"sentry": {"serverUrl": "https://x"}}}), encoding="utf-8")
            old_file.write_text(json.dumps({"mcpServers": {"claudegravity": {"command": "python3"}}}), encoding="utf-8")
            install_fn, uninstall_fn, status_fn = install.antigravity_client(gemini)
            with mock.patch.object(install, "say"):
                self.assertTrue(install_fn())
                servers = json.loads(new_file.read_text(encoding="utf-8"))["mcpServers"]
                self.assertEqual(set(servers), {"sentry", "claudegravity"})
                self.assertEqual(servers["claudegravity"]["env"]["CLAUDEGRAVITY_HOST"], "agy")
                self.assertNotIn("claudegravity", json.loads(old_file.read_text(encoding="utf-8"))["mcpServers"])
                self.assertTrue(status_fn())
                self.assertTrue(uninstall_fn())
            self.assertEqual(set(json.loads(new_file.read_text(encoding="utf-8"))["mcpServers"]), {"sentry"})


if __name__ == "__main__":
    unittest.main()
