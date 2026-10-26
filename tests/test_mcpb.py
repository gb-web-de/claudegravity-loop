"""Claude-Desktop-Erweiterung (.mcpb): Manifest, Bundle-Inhalt und Start wie in Claude Desktop."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_mcpb  # noqa: E402
import mcp_server  # noqa: E402

MANIFEST = json.loads((ROOT / "mcpb" / "manifest.json").read_text(encoding="utf-8"))


def substitute(value: str, dirname: Path, user_config: dict) -> str:
    """Platzhalter ersetzen wie Claude Desktop; nicht gesetzte Einstellungen bleiben als Platzhalter stehen."""
    value = value.replace("${__dirname}", str(dirname))
    for key, setting in user_config.items():
        value = value.replace("${user_config." + key + "}", setting)
    return value


class ManifestTest(unittest.TestCase):
    def test_manifest_matches_package_and_tools(self):
        self.assertEqual(build_mcpb.manifest_problems(MANIFEST), [])
        self.assertEqual(MANIFEST["manifest_version"], "0.3")
        self.assertEqual(MANIFEST["server"]["entry_point"], "mcp_server.py")

    def test_every_setting_is_used_and_declared(self):
        env = MANIFEST["server"]["mcp_config"]["env"]
        used = {v[len("${user_config.") : -1] for v in env.values() if v.startswith("${user_config.")}
        self.assertEqual(used, set(MANIFEST["user_config"]))
        self.assertTrue(MANIFEST["user_config"]["api_key"]["sensitive"])
        self.assertEqual(MANIFEST["server"]["mcp_config"]["platform_overrides"]["win32"]["command"], "py")

    def test_drift_is_reported(self):
        changed = dict(MANIFEST, version="0.0.1", tools=MANIFEST["tools"][:-1])
        self.assertEqual(len(build_mcpb.manifest_problems(changed)), 2)


class BundleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bundle_contents_are_complete_and_reproducible(self):
        first = build_mcpb.build(self.out / "a")
        second = build_mcpb.build(self.out / "b")
        self.assertEqual(first.read_bytes(), second.read_bytes())
        names = zipfile.ZipFile(first).namelist()
        for required in (
            "manifest.json",
            "icon.png",
            "launch.sh",
            "mcp_server.py",
            "loop.py",
            "claudegravity/cli.py",
            "claudegravity/watch.py",
        ):
            self.assertIn(required, names)
        self.assertFalse([n for n in names if "__pycache__" in n or n.startswith(("tests/", ".dual-loop"))])
        self.assertEqual(first.name, f"claudegravity-{mcp_server.SERVER_VERSION}.mcpb")

    @unittest.skipIf(os.name == "nt", "launch.sh läuft unter macOS und Linux")
    def test_bundle_starts_like_claude_desktop(self):
        bundle = build_mcpb.build(self.out / "dist")
        target = self.out / "Application Support" / "Claude Extensions" / "claudegravity"
        zipfile.ZipFile(bundle).extractall(target)
        config = MANIFEST["server"]["mcp_config"]
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "claude-ai", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "claudegravity_info", "arguments": {}}},
        ]
        python_dir = str(Path(sys.executable).parent)
        cases = {
            # Pfad zum Python aus den Einstellungen
            "python gesetzt": {"python": sys.executable, "notify": "desktop", "lang": "auto"},
            # Einstellungen leer: Platzhalter bleiben stehen, das Skript sucht selbst ein Python
            "python gesucht": {},
        }
        for label, user_config in cases.items():
            with self.subTest(label):
                env = {k: substitute(v, target, user_config) for k, v in config["env"].items()}
                env.update(HOME=self.tmp.name, PATH=f"/usr/bin:/bin:{python_dir}")
                cmd = [config["command"]] + [substitute(a, target, user_config) for a in config["args"]]
                res = subprocess.run(
                    cmd,
                    input="\n".join(json.dumps(r) for r in requests) + "\n",
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env=env,
                    cwd="/",
                    timeout=120,
                )
                responses = {r.get("id"): r for r in (json.loads(line) for line in res.stdout.splitlines() if line.strip())}
                self.assertIn(2, responses, res.stderr[-2000:])
                self.assertEqual(len(responses[2]["result"]["tools"]), len(MANIFEST["tools"]))
                info = responses[3]["result"]["content"][0]["text"]
                self.assertFalse(responses[3]["result"].get("isError"), info)
                self.assertNotIn("${user_config", info)


class EnvTest(unittest.TestCase):
    def test_placeholders_and_empty_settings_are_dropped(self):
        env = {"CLAUDEGRAVITY_ENDPOINT": "${user_config.endpoint}", "CLAUDEGRAVITY_NOTIFY": "", "CLAUDEGRAVITY_LANG": "en", "OTHER": ""}
        self.assertEqual(sorted(mcp_server.drop_unset_settings(env)), ["CLAUDEGRAVITY_ENDPOINT", "CLAUDEGRAVITY_NOTIFY"])
        self.assertEqual(env, {"CLAUDEGRAVITY_LANG": "en", "OTHER": ""})


if __name__ == "__main__":
    unittest.main()
