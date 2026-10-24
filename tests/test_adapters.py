"""Contract-Tests für die Backend-Adapter (CLIs und OpenAI-kompatible Endpunkte).

Vertrag jedes Adapters: (Text: str, Metriken: dict mit int input/output/total_tokens und float cost_usd).
Fehler: Limits als RateLimitError, alles andere als RuntimeError mit lesbarer Meldung; nie ein roher
KeyError/AttributeError/JSONDecodeError und nie ein Hängen ohne Zeitlimit.
"""

import io
import json
import subprocess
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402

CLI_ADAPTERS = {
    "claude": loop._exec_claude,
    "agy": loop._exec_agy,
    "gemini": loop._exec_gemini,
    "codex": loop._exec_codex,
    "copilot": loop._exec_copilot,
    "ollama": loop._exec_ollama_cli,
}


def completed(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


class CliContractTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(loop.backends, "build_cli_command", side_effect=lambda b, a: ([b] + list(a), False))
        p.start()
        self.addCleanup(p.stop)

    def run_adapter(self, name, result=None, side_effect=None, flags=None):
        with mock.patch.object(loop.subprocess, "run", return_value=result, side_effect=side_effect) as run:
            out = CLI_ADAPTERS[name](name, "Prompt", None, flags or [])
        return out, run

    def assert_contract(self, out):
        text, metrics = out
        self.assertIsInstance(text, str)
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            self.assertIsInstance(metrics[key], int, key)
        self.assertIsInstance(metrics["cost_usd"], float)

    def test_plain_or_garbage_output_still_fulfils_contract(self):
        for name in CLI_ADAPTERS:
            for stdout in ("Antwort als Text", "[1, 2]", "null", '{"result": null, "usage": null}', ""):
                with self.subTest(adapter=name, stdout=stdout):
                    self.assert_contract(self.run_adapter(name, completed(stdout))[0])

    def test_structured_output_is_parsed(self):
        claude = json.dumps(
            {
                "result": "ok",
                "usage": {"input_tokens": 3, "cache_read_input_tokens": 2, "output_tokens": 4},
                "total_cost_usd": 0.01,
                "modelUsage": {"claude-x": {}},
                "session_id": "s",
            }
        )
        (text, m), _ = self.run_adapter("claude", completed(claude))
        self.assertEqual(
            (text, m["input_tokens"], m["output_tokens"], m["cost_usd"], m["reported_model"], m["session_id"]),
            ("ok", 5, 4, 0.01, "claude-x", "s"),
        )
        agy = json.dumps({"response": "ok", "usage": {"input_tokens": 1, "output_tokens": 2, "thinking_tokens": 7}})
        (text, m), _ = self.run_adapter("agy", completed(agy))
        self.assertEqual((text, m["total_tokens"]), ("ok", 3))
        self.assertIn("7 thinking", m["effort"])
        codex = "\n".join(
            json.dumps(e)
            for e in (
                {"type": "item.completed", "item": {"type": "agent_message", "text": "fertig"}},
                {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}},
            )
        )
        (text, m), _ = self.run_adapter("codex", completed("Banner\n" + codex))
        self.assertEqual((text, m["total_tokens"]), ("fertig", 15))

    def test_errors_become_runtime_errors(self):
        cases = {
            "claude": completed(json.dumps({"is_error": True, "result": "invalid model"})),
            "agy": completed(json.dumps({"status": "ERROR", "response": "kaputt"})),
            "codex": completed(json.dumps({"type": "turn.failed", "error": {"message": "stream error"}})),
            "gemini": completed("", "Error: not logged in", 1),
        }
        for name, result in cases.items():
            with self.subTest(adapter=name), self.assertRaises(RuntimeError):
                self.run_adapter(name, result)

    def test_rate_limits_become_rate_limit_errors(self):
        cases = {
            "claude": completed(json.dumps({"is_error": True, "result": "You've hit your session limit · resets 5pm"})),
            "agy": completed(json.dumps({"status": "ERROR", "response": "Quota exceeded, try again in 10 minutes"})),
            "codex": completed(json.dumps({"type": "error", "message": "rate limit reached"})),
            "gemini": completed("", "RESOURCE_EXHAUSTED: too many requests", 1),
        }
        for name, result in cases.items():
            with self.subTest(adapter=name), self.assertRaises(loop.RateLimitError):
                self.run_adapter(name, result)

    def test_cli_timeout_is_set_and_reported(self):
        _, run = self.run_adapter("gemini", completed("ok"))
        self.assertEqual(run.call_args.kwargs["timeout"], loop.CLI_TIMEOUT_DEFAULT)
        with mock.patch.dict("os.environ", {"CLAUDEGRAVITY_CLI_TIMEOUT": "0"}):
            _, run = self.run_adapter("gemini", completed("ok"))
        self.assertIsNone(run.call_args.kwargs["timeout"])
        with self.assertRaises(RuntimeError) as ctx:
            self.run_adapter("claude", side_effect=subprocess.TimeoutExpired(["claude"], 5))
        self.assertIn("CLI-Zeitlimit", str(ctx.exception))
        self.assertFalse(loop.is_transient_error(str(ctx.exception)))
        self.assertEqual(loop.classify_error(str(ctx.exception)), "CG-1202")

    def test_prompt_goes_via_stdin_not_argv_where_supported(self):
        for name in ("claude", "gemini", "codex", "ollama"):
            _, run = self.run_adapter(name, completed("ok"))
            self.assertEqual(run.call_args.kwargs["input"], "Prompt", name)
            self.assertNotIn("Prompt", run.call_args.args[0], name)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class EndpointContractTest(unittest.TestCase):
    URL = "http://127.0.0.1:11434/v1"

    def call(self, body=None, side_effect=None, url=None):
        resp = FakeResponse(body.encode("utf-8")) if body is not None else None
        with mock.patch.object(loop.urllib.request, "urlopen", return_value=resp, side_effect=side_effect):
            return loop._exec_openai_api(url or self.URL, "qwen", "Prompt")

    def http_error(self, code, body=""):
        return urllib.error.HTTPError(self.URL, code, "x", {}, io.BytesIO(body.encode()))

    def test_valid_answer(self):
        body = json.dumps({"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 2}})
        text, m = self.call(body)
        self.assertEqual((text, m["total_tokens"], m["cost_usd"]), ("ok", 5, 0.0))

    def test_reported_cost_from_public_endpoint(self):
        body = json.dumps(
            {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.002}}
        )
        _, m = self.call(body, url="https://openrouter.ai/api/v1")
        self.assertEqual(m["cost_usd"], 0.002)

    def test_missing_fields_fulfil_contract(self):
        for body in ('{"choices": [{"message": null}], "usage": null}', '{"choices": [{}]}'):
            text, m = self.call(body)
            self.assertEqual(text, "")
            self.assertIsInstance(m["total_tokens"], int)

    def test_invalid_answers_raise_readable_errors(self):
        for body in ("<html>Proxy error</html>", "[]", '{"choices": []}'):
            with self.subTest(body=body), self.assertRaises(RuntimeError) as ctx:
                self.call(body)
            self.assertEqual(loop.classify_error(str(ctx.exception)), "CG-1205")

    def test_network_errors(self):
        cases = {
            urllib.error.URLError(ConnectionRefusedError("refused")): "CG-1201",
            ConnectionResetError("reset by peer"): "CG-1201",
            TimeoutError(): "CG-1202",
            self.http_error(401): "CG-1203",
            self.http_error(404, '{"error": "model not found"}'): "CG-1204",
        }
        for exc, code in cases.items():
            with self.subTest(exc=type(exc).__name__), self.assertRaises(RuntimeError) as ctx:
                self.call(side_effect=exc)
            self.assertEqual(loop.classify_error(str(ctx.exception)), code)

    def test_server_errors_are_retried_rate_limits_are_not(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.call(side_effect=self.http_error(503, "upstream unavailable"))
        self.assertTrue(loop.is_transient_error(str(ctx.exception)))
        with self.assertRaises(loop.RateLimitError) as ctx:
            self.call(side_effect=self.http_error(429, "rate limit, try again in 30 seconds"))
        self.assertEqual(ctx.exception.reset_seconds, 30)


class CliAuthTest(unittest.TestCase):
    def test_claude_auth_check(self):
        with mock.patch("subprocess.run") as m_run:
            m_run.return_value = completed(stdout='{"loggedIn": true}')
            ok, msg = loop.check_cli_auth("claude")
            self.assertTrue(ok)
            self.assertEqual(msg, "angemeldet")

            m_run.return_value = completed(stdout='{"loggedIn": false}')
            ok, msg = loop.check_cli_auth("claude")
            self.assertFalse(ok)
            self.assertIn("claude login", msg)

    def test_gemini_auth_check(self):
        with mock.patch("subprocess.run") as m_run:
            m_run.return_value = completed(stdout="ok", code=0)
            ok, msg = loop.check_cli_auth("gemini")
            self.assertTrue(ok)
            self.assertEqual(msg, "angemeldet")

            m_run.return_value = completed(stderr="Invalid auth method selected.", code=41)
            ok, msg = loop.check_cli_auth("gemini")
            self.assertFalse(ok)
            self.assertIn("gemini auth login", msg)

    def test_gh_copilot_check(self):
        with mock.patch("subprocess.run") as m_run:
            m_run.return_value = completed(stdout="unknown command copilot", code=1)
            ok, msg = loop.check_cli_auth("gh")
            self.assertFalse(ok)
            self.assertIn("gh extension install", msg)

            m_run.return_value = completed(stdout="gh copilot help", code=0)
            ok, msg = loop.check_cli_auth("gh")
            self.assertTrue(ok)
            self.assertEqual(msg, "bereit")

    def test_copilot_missing_check(self):
        with mock.patch("subprocess.run") as m_run:
            m_run.return_value = completed(stdout="", stderr="GitHub Copilot CLI was not found", code=127)
            ok, msg = loop.check_cli_auth("copilot")
            self.assertFalse(ok)
            self.assertIn("copilot setup", msg)

    def test_timeout_or_missing_binary(self):
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["test"], timeout=2.0)):
            ok, msg = loop.check_cli_auth("gemini")
            self.assertFalse(ok)
            self.assertEqual(msg, "nicht erreichbar")

    def test_get_alternative_agent_require_auth(self):
        agents = {k: loop.AgentCLI(k, k, lambda *a: ("", {})) for k in ("claude", "gemini", "agy")}
        with mock.patch.object(loop.backends, "check_cli_auth", side_effect=lambda b: (True, "angemeldet") if b == "agy" else (False, "unauth")):
            alt = loop.get_alternative_agent(agents["claude"], agents, require_auth=True)
            self.assertIsNotNone(alt)
            self.assertEqual(alt.binary, "agy")


if __name__ == "__main__":
    unittest.main()

