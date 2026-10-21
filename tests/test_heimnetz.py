"""Tests für Heimnetz-Endpunkte, Pfadschutz und Datenschutzschild. Ausführen: python3 -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import loop  # noqa: E402
import mcp_server  # noqa: E402


class PrivateEndpointTest(unittest.TestCase):
    def test_local_and_lan(self):
        for url in [
            "http://localhost:11434/v1",
            "http://127.0.0.1:1234",
            "http://192.168.1.50:11434/v1",
            "http://10.0.0.5/v1",
            "http://172.20.1.1:8000",
            "http://nas:4100/v1",
            "http://server.local:11434",
            "http://nas.fritz.box:11434",
            "http://[::1]:11434",
        ]:
            self.assertTrue(loop.is_private_endpoint(url), url)

    def test_internet(self):
        for url in ["https://api.openai.com/v1", "https://example.de/v1", "http://8.8.8.8", "http://172.32.0.1"]:
            self.assertFalse(loop.is_private_endpoint(url), url)

    def test_timeout_depends_on_endpoint(self):
        with mock.patch.object(loop, "ENDPOINT_TIMEOUT", None):
            self.assertEqual(loop.endpoint_timeout("http://192.168.1.50:11434"), loop.LOCAL_TIMEOUT)
            self.assertEqual(loop.endpoint_timeout("https://api.openai.com/v1"), loop.CLOUD_TIMEOUT)
        with mock.patch.object(loop, "ENDPOINT_TIMEOUT", 42):
            self.assertEqual(loop.endpoint_timeout("http://localhost:11434"), 42)
        self.assertGreater(loop.LOCAL_TIMEOUT, loop.CLOUD_TIMEOUT)


class OllamaHostTest(unittest.TestCase):
    def check(self, value, expected):
        env = {} if value is None else {"OLLAMA_HOST": value}
        with mock.patch.dict(os.environ, env, clear=False):
            if value is None:
                os.environ.pop("OLLAMA_HOST", None)
            self.assertEqual(loop.ollama_base_url(), expected)
            self.assertEqual(mcp_server.ollama_base_url(), expected)

    def test_variants(self):
        self.check(None, "http://localhost:11434")
        self.check("0.0.0.0:11434", "http://localhost:11434")
        self.check("192.168.1.50", "http://192.168.1.50:11434")
        self.check("http://nas:11500", "http://nas:11500")
        self.check("https://ki.example.de", "https://ki.example.de:11434")


class ShieldTest(unittest.TestCase):
    def test_redacts_secrets(self):
        cases = {
            "Anthropic-Key": "key sk-ant-" + "a" * 30,
            "GitHub-Token": "ghp_" + "A" * 36,
            "Passwort/Token": "DB_PASSWORD=hunter2geheim",
            "Zugangsdaten in URL": "mysql://admin:supergeheim@db.example.de/app",
            "IBAN": "Überweise an DE89 3704 0044 0532 0130 00 bitte",
            "Kreditkartennummer": "Karte 4111 1111 1111 1111",
            "privater Schlüssel": "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----",
        }
        for label, text in cases.items():
            redacted, found = loop.redact_secrets(text)
            self.assertIn(label, found, text)
            self.assertIn("[GESCHWÄRZT", redacted)

    def test_keeps_normal_text(self):
        text = ("Baue ein Login mit password_hash(). api_key = ${API_KEY}. Bestellnummer 1234 5678 9012 3456.\n"
                "token = create_token(user_id2)\napi_key = os.environ[\"API_KEY_2\"]\nsecret: str = load_secret()")
        redacted, found = loop.redact_secrets(text)
        self.assertEqual(found, [])
        self.assertEqual(redacted, text)

    def test_agent_redacts_only_for_cloud(self):
        seen = []
        run_fn = lambda binary, prompt, cwd, flags: (seen.append(prompt) or "ok", {})
        secret = "token=abcdef123456"
        with mock.patch.object(loop, "SHIELD_ENABLED", True):
            loop.AgentCLI("Cloud", "claude", run_fn).run(secret)
            loop.AgentCLI("Pi", "ollama", run_fn, local=True).run(secret)
        self.assertNotIn("abcdef123456", seen[0])
        self.assertEqual(seen[1], secret)
        with mock.patch.object(loop, "SHIELD_ENABLED", False):
            loop.AgentCLI("Cloud", "claude", run_fn).run(secret)
        self.assertEqual(seen[2], secret)


class ApplyCodeBlocksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "projekt"
        self.project.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def block(self, path, content="x\n"):
        return f"```filepath: {path}\n{content}```\n"

    def test_writes_inside_project(self):
        written = loop.apply_code_blocks(self.project, self.block("src/app.py", "print(1)\n")
                                         + self.block(".dual-loop/sessions/s1/.done"))
        self.assertEqual(written, ["src/app.py", ".dual-loop/sessions/s1/.done"])
        self.assertEqual((self.project / "src/app.py").read_text(), "print(1)\n")

    def test_blocks_escape_and_secrets(self):
        evil = "".join(self.block(p) for p in [
            "../ausserhalb.txt", "src/../../ausserhalb2.txt", str(self.root / "abs.txt"),
            "~/.bashrc", ".env", "config/.env.local", ".ssh/authorized_keys", ".git/config", "certs/server.key",
        ])
        with mock.patch("builtins.print"):
            written = loop.apply_code_blocks(self.project, evil)
        self.assertEqual(written, [])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["projekt"])
        self.assertEqual(list(self.project.iterdir()), [])

    def test_allows_env_example(self):
        self.assertEqual(loop.apply_code_blocks(self.project, self.block(".env.example")), [".env.example"])

    def test_header_pattern_is_checked_too(self):
        text = "### Datei: ../boese.py\n```python\nx = 1\n```\n"
        with mock.patch("builtins.print"):
            self.assertEqual(loop.apply_code_blocks(self.project, text), [])
        self.assertFalse((self.root / "boese.py").exists())


class KnowledgeTest(unittest.TestCase):
    def test_skips_secret_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            k = Path(tmp) / "knowledge"
            k.mkdir()
            (k / "api.md").write_text("Regeln")
            (k / ".env").write_text("SECRET=1")
            ctx = loop.load_project_context(Path(tmp))
        self.assertIn("api.md", ctx)
        self.assertNotIn(".env", ctx)


if __name__ == "__main__":
    unittest.main()
