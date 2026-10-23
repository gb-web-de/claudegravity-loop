"""Tests für automatische Neuversuche mit Backoff und Jitter bei vorübergehenden Fehlern."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402


def flaky_agent(errors, local=False, name="Flaky", binary="flaky"):
    """Agent, der zuerst die übergebenen Fehler wirft und dann 'ok' liefert."""
    calls = []

    def run_fn(binary_, prompt, cwd, flags):
        calls.append(prompt)
        if len(calls) <= len(errors):
            raise errors[len(calls) - 1]
        return "ok", {"total_tokens": 1}

    return loop.AgentCLI(name, binary, run_fn, local=local), calls


class ClassifyTest(unittest.TestCase):
    def test_transient_messages(self):
        for text in (
            "Verbindungsfehler zu http://pi:11434/v1: [Errno 111] Connection refused",
            "API-Fehler an https://x/v1: HTTP 503 (Service Unavailable): ",
            "claude Fehler (Code 1): API Error: 529 Overloaded",
            "codex Fehler: stream error: socket hang up",
            "Zeitüberschreitung nach 180 s bei https://x/v1.",
        ):
            self.assertTrue(loop.is_transient_error(text), text)

    def test_not_transient(self):
        for text in ("API-Fehler an x: HTTP 401 (Unauthorized)", "claude Fehler (Code 1): invalid model", "Leere Antwort vom Endpunkt"):
            self.assertFalse(loop.is_transient_error(text), text)

    def test_local_timeout_is_not_retried(self):
        self.assertFalse(loop.is_transient_error("Zeitüberschreitung nach 900 s bei http://localhost:11434/v1.", local=True))
        self.assertTrue(loop.is_transient_error("Verbindungsfehler zu http://localhost:11434/v1: refused", local=True))

    def test_backoff_grows_with_jitter_and_cap(self):
        self.assertEqual(loop.backoff_delay(1, 5, 60, rng=lambda: 0.0), 2.5)
        self.assertEqual(loop.backoff_delay(1, 5, 60, rng=lambda: 1.0), 5.0)
        self.assertEqual(loop.backoff_delay(3, 5, 60, rng=lambda: 1.0), 20.0)
        self.assertEqual(loop.backoff_delay(10, 5, 60, rng=lambda: 1.0), 60.0)
        self.assertEqual(loop.backoff_delay(10, 5, 60, rng=lambda: 0.0), 30.0)

    def test_policies(self):
        self.assertLess(loop.retry_policy(True)["base"], loop.retry_policy(False)["base"])
        with mock.patch.object(loop, "RETRY_OVERRIDE", 0):
            self.assertEqual(loop.retry_policy(False)["attempts"], 0)


class SafeAgentRunRetryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.session = Path(self.tmp.name)
        self.sleeps = []
        patcher = mock.patch.object(loop, "interruptible_sleep", side_effect=lambda s: self.sleeps.append(s) or True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def run_agent(self, agent, metrics=None):
        return loop.safe_agent_run(
            agent=agent, prompt="p", cwd=self.session, flags=[], agents={}, session_dir=self.session,
            state={}, auto_switch=False, role="builder", metrics_tracker=metrics,
        )

    def test_recovers_after_transient_errors(self):
        agent, calls = flaky_agent([RuntimeError("Verbindungsfehler zu x: reset"), RuntimeError("HTTP 502 (Bad Gateway)")])
        metrics = loop.SessionMetrics()
        text, used, _ = self.run_agent(agent, metrics)
        self.assertEqual((text, used, len(calls), len(self.sleeps)), ("ok", agent, 3, 2))
        self.assertEqual(metrics.retries, {"attempts": 2, "recovered": 1, "exhausted": 0})
        self.assertIn("Neuversuch 2 bei Flaky erfolgreich", (self.session / "LOG.md").read_text(encoding="utf-8"))
        self.assertIn("Automatische Neuversuche:** 2", loop.format_metrics_report(metrics))
        self.assertEqual(loop.SessionMetrics.from_dict(metrics.to_dict()).retries, metrics.retries)

    def test_overload_reported_as_rate_limit_is_retried(self):
        agent, calls = flaky_agent([loop.RateLimitError("claude", "API Error: 529 Overloaded")])
        text, _, _ = self.run_agent(agent)
        self.assertEqual((text, len(calls)), ("ok", 2))

    def test_permanent_error_is_raised_immediately(self):
        agent, calls = flaky_agent([RuntimeError("HTTP 401 (Unauthorized)")])
        with self.assertRaises(RuntimeError):
            self.run_agent(agent)
        self.assertEqual((len(calls), self.sleeps), (1, []))

    def test_rate_limit_with_reset_goes_straight_to_menu(self):
        agent, _ = flaky_agent([loop.RateLimitError("claude", "rate limit, resets in 5 minutes", "5 minutes", 300)])
        with mock.patch.object(loop, "handle_rate_limit", return_value=("wait", agent)) as menu:
            text, _, _ = self.run_agent(agent)
        self.assertEqual(text, "ok")
        self.assertFalse(menu.call_args.args[2].transient)
        self.assertEqual(self.sleeps, [])

    def test_exhausted_retries_offer_menu(self):
        errors = [RuntimeError("HTTP 503 (Service Unavailable)")] * 4
        agent, calls = flaky_agent(errors)
        other, _ = flaky_agent([], name="Andere", binary="other")
        metrics = loop.SessionMetrics()
        with mock.patch.object(loop, "handle_rate_limit", return_value=("switch", other)) as menu:
            text, used, _ = self.run_agent(agent, metrics)
        self.assertEqual((text, used.name, len(calls)), ("ok", "Andere", 4))
        self.assertTrue(menu.call_args.args[2].transient)
        self.assertEqual(metrics.retries["exhausted"], 1)

    def test_retries_can_be_disabled(self):
        agent, _ = flaky_agent([RuntimeError("HTTP 503")])
        with mock.patch.object(loop, "RETRY_OVERRIDE", 0), \
                mock.patch.object(loop, "handle_rate_limit", return_value=("wait", agent)) as menu:
            self.run_agent(agent)
        self.assertEqual(self.sleeps, [])
        self.assertTrue(menu.called)


if __name__ == "__main__":
    unittest.main()
