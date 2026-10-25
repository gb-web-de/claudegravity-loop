"""Tests für die Plugin-Manifeste (Claude Code, Codex, Copilot, Cursor, Antigravity, Gemini CLI)."""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_NAME = "claudegravity"
sys.path.insert(0, str(ROOT))

import claudegravity  # noqa: E402

# Manifest mit MCP-Server → Variable für den Plugin-Ordner, die der Client einsetzt
MCP_FILES = {
    ".claude-plugin/plugin.json": "${CLAUDE_PLUGIN_ROOT}/",
    "mcp.json": "${PLUGIN_ROOT}/",
    "mcp_config.json": "${PLUGIN_ROOT}/",
    ".cursor-plugin/mcp.json": "${CURSOR_PLUGIN_ROOT}/",
    "gemini-extension.json": "${extensionPath}${/}",
}

VERSIONED = [".claude-plugin/plugin.json", ".cursor-plugin/plugin.json", "gemini-extension.json"]


def read_json(relative: str) -> dict:
    """Liest eine JSON-Datei relativ zum Repository."""
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class PluginManifestTest(unittest.TestCase):
    def test_all_manifests_name_the_plugin(self):
        for relative in [".claude-plugin/plugin.json", ".cursor-plugin/plugin.json", "plugin.json", "gemini-extension.json"]:
            with self.subTest(manifest=relative):
                self.assertEqual(read_json(relative)["name"], PLUGIN_NAME)

    def test_versions_match(self):
        versions = {relative: read_json(relative)["version"] for relative in VERSIONED}
        versions["marketplace"] = read_json(".claude-plugin/marketplace.json")["plugins"][0]["version"]
        versions["paket"] = claudegravity.__version__
        versions["mcp_server"] = re.search(r'SERVER_VERSION = "([^"]+)"', (ROOT / "mcp_server.py").read_text(encoding="utf-8")).group(1)
        self.assertEqual(len(set(versions.values())), 1, versions)

    def test_antigravity_manifest_only_allowed_keys(self):
        # Antigravity verbietet weitere Felder in plugin.json (additionalProperties: false)
        self.assertLessEqual(set(read_json("plugin.json")), {"$schema", "name", "description"})

    def test_marketplaces_point_to_repo_root(self):
        claude = read_json(".claude-plugin/marketplace.json")
        cursor = read_json(".cursor-plugin/marketplace.json")
        self.assertEqual(claude["plugins"][0]["name"], PLUGIN_NAME)
        self.assertEqual(cursor["plugins"][0]["name"], PLUGIN_NAME)
        self.assertEqual((ROOT / claude["plugins"][0]["source"]).resolve(), ROOT)
        self.assertEqual((ROOT / cursor["plugins"][0]["source"]).resolve(), ROOT)

    def test_mcp_entries_start_bundled_server(self):
        for relative, root_var in MCP_FILES.items():
            with self.subTest(manifest=relative):
                server = read_json(relative)["mcpServers"][PLUGIN_NAME]
                self.assertEqual(server["args"], [f"{root_var}mcp_server.py"])
                self.assertEqual(server["env"]["PYTHONIOENCODING"], "utf-8")
                self.assertTrue(server["command"].startswith("python"))
        self.assertTrue((ROOT / "mcp_server.py").is_file())

    def test_host_matches_loop_backend(self):
        hosts = {
            ".claude-plugin/plugin.json": "claude",
            "mcp_config.json": "agy",
            "gemini-extension.json": "gemini",
        }
        for relative, host in hosts.items():
            with self.subTest(manifest=relative):
                self.assertEqual(read_json(relative)["mcpServers"][PLUGIN_NAME]["env"]["CLAUDEGRAVITY_HOST"], host)

    def test_agent_plugins_mcp_declares_type(self):
        data = read_json("mcp.json")
        self.assertIn("agent-plugins.org", data["$schema"])
        self.assertEqual(data["mcpServers"][PLUGIN_NAME]["type"], "stdio")

    def test_cursor_paths_exist(self):
        manifest = read_json(".cursor-plugin/plugin.json")
        for key in ("skills", "commands", "mcpServers"):
            with self.subTest(key=key):
                self.assertTrue((ROOT / manifest[key]).exists(), manifest[key])

    def test_skill_is_bundled(self):
        self.assertTrue((ROOT / "skills" / PLUGIN_NAME / "SKILL.md").is_file())


class PluginCommandTest(unittest.TestCase):
    def test_every_command_has_gemini_twin(self):
        markdown = sorted(path.stem for path in (ROOT / "commands").glob("*.md"))
        toml = sorted(path.stem for path in (ROOT / "commands" / PLUGIN_NAME).glob("*.toml"))
        self.assertEqual(markdown, ["loop_optimize", "loop_run", "loop_status"])
        self.assertEqual(markdown, toml)

    def test_commands_have_description(self):
        for path in (ROOT / "commands").glob("*.md"):
            with self.subTest(command=path.name):
                self.assertRegex(path.read_text(encoding="utf-8"), r"(?m)^description: \S")

    def test_gemini_commands_are_valid_toml(self):
        try:
            import tomllib
        except ImportError:  # Python 3.10
            self.skipTest("tomllib erst ab Python 3.11")
        for path in (ROOT / "commands" / PLUGIN_NAME).glob("*.toml"):
            with self.subTest(command=path.name):
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                self.assertTrue(data["description"])
                self.assertNotIn("$ARGUMENTS", data["prompt"])

    def test_gemini_commands_follow_markdown(self):
        # Die TOML-Befehle sind aus den Markdown-Befehlen abgeleitet und sollen nicht auseinanderlaufen
        for path in (ROOT / "commands").glob("*.md"):
            with self.subTest(command=path.name):
                body = path.read_text(encoding="utf-8").split("---", 2)[2].strip().replace("$ARGUMENTS", "{{args}}")
                twin = (ROOT / "commands" / PLUGIN_NAME / f"{path.stem}.toml").read_text(encoding="utf-8")
                self.assertIn(body, twin)
                self.assertTrue(re.search(r'(?m)^prompt = """$', twin))


class PluginServerStartTest(unittest.TestCase):
    def test_server_answers_initialize_from_plugin_root(self):
        # So startet ein Client den Server aus dem Plugin: python3 <plugin>/mcp_server.py in einem anderen Ordner
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "clientInfo": {"name": "test"}},
        }
        proc = subprocess.run(
            [sys.executable, str(ROOT / "mcp_server.py")],
            input=json.dumps(request) + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(ROOT / "tests"),
            timeout=30,
        )
        answer = json.loads(proc.stdout.splitlines()[0])
        self.assertEqual(answer["result"]["serverInfo"]["name"], "claudegravity-mcp")

    def test_server_lists_tools_after_handshake(self):
        # Minimaler MCP-Handshake ohne Modell-Zugang: initialize, initialized, tools/list
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "clientInfo": {"name": "test"}},
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        proc = subprocess.run(
            [sys.executable, str(ROOT / "mcp_server.py")],
            input="".join(json.dumps(message) + "\n" for message in messages),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        answers = {item["id"]: item for item in map(json.loads, proc.stdout.splitlines()) if "id" in item}
        names = {tool["name"] for tool in answers[2]["result"]["tools"]}
        self.assertEqual(
            names,
            {"claudegravity_optimize", "claudegravity_run", "claudegravity_status", "claudegravity_stop", "claudegravity_info"},
        )


class ManifestParseTest(unittest.TestCase):
    JSON_FILES = [
        "plugin.json",
        "mcp.json",
        "mcp_config.json",
        "gemini-extension.json",
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        ".cursor-plugin/plugin.json",
        ".cursor-plugin/mcp.json",
        ".cursor-plugin/marketplace.json",
    ]

    def test_json_manifests_parse(self):
        for relative in self.JSON_FILES:
            with self.subTest(manifest=relative):
                self.assertIsInstance(read_json(relative), dict)

    def test_vscode_mcp_config_starts_bundled_server(self):
        server = read_json(".vscode/mcp.json")["servers"][PLUGIN_NAME]
        self.assertEqual(server["type"], "stdio")
        self.assertIn("mcp_server.py", server["args"][-1])
        self.assertEqual(server["env"]["PYTHONIOENCODING"], "utf-8")


if __name__ == "__main__":
    unittest.main()
