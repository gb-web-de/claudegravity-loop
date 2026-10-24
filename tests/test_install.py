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


class SkillInstallTest(unittest.TestCase):
    def test_skill_targets_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            targets = install.skill_targets(Path(tmp))
            self.assertIn("claude", targets)
            self.assertIn("antigravity", targets)
            self.assertIn("codex", targets)
            for _, _, target in targets.values():
                self.assertEqual(target.name, "claudegravity")

    def test_install_and_uninstall_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_home = Path(tmp) / "home"
            fake_home.mkdir()
            source = Path(tmp) / "source"
            source.mkdir()
            (source / "SKILL.md").write_text("# ClaudeGravity Skill", encoding="utf-8")
            target = fake_home / ".claude" / "skills" / "claudegravity"

            self.assertFalse(install.is_skill_installed(target, source))
            with mock.patch.object(install, "say"):
                self.assertTrue(install.install_skill(target, source))
                self.assertTrue(install.is_skill_installed(target, source))
                self.assertTrue((target / "SKILL.md").is_file())

                # Erneuter Aufruf ist idempotent
                self.assertTrue(install.install_skill(target, source))

                # Deinstallation
                self.assertTrue(install.uninstall_skill(target))
                self.assertFalse(install.is_skill_installed(target, source))
                self.assertFalse(target.exists())


class ClaudeCommandsInstallTest(unittest.TestCase):
    def test_claude_command_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            pairs = install.claude_command_targets(Path(tmp))
            self.assertEqual(len(pairs), 3)
            names = [src.name for src, _ in pairs]
            self.assertEqual(names, ["loop_optimize.md", "loop_run.md", "loop_status.md"])
            for src, dst in pairs:
                self.assertEqual(dst.parent, Path(tmp) / ".claude" / "commands")
                self.assertEqual(dst.name, src.name)

    def test_install_and_uninstall_claude_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_home = Path(tmp)
            with mock.patch.object(install, "say"):
                self.assertTrue(install.install_claude_commands(fake_home))
                pairs = install.claude_command_targets(fake_home)
                for src, dst in pairs:
                    self.assertTrue(install.is_claude_command_installed(dst, src))
                    self.assertTrue(dst.is_file())

                # Idempotent
                self.assertTrue(install.install_claude_commands(fake_home))

                # Deinstallation
                self.assertTrue(install.uninstall_claude_commands(fake_home))
                for src, dst in pairs:
                    self.assertFalse(dst.exists())


if __name__ == "__main__":
    unittest.main()

