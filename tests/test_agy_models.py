"""Modellnamen und Effort für die Antigravity CLI (agy ab 1.4): keine Platzhalter im Aufruf, neues Namensformat."""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402

AGY_ERROR = """error: invalid model selection (--model "gemini-3.8-flash (CLI-Default)" --effort ""): model gemini-3.8-flash (CLI-Default) is not recognized as a known model or custom model in settings
Available models:
  Gemini 4 Argon (Medium)
  Gemini 4 Argon (High)
  Gemini 4 Argon (Low)
  Gemini 3.8 Flash (High)
  Gemini 3.8 Flash (Medium)
  Gemini 3.8 Flash (Low)
  Claude Opus 5.5 (Medium)
  GPT-OSS 120B (Medium)
"""
AVAILABLE = loop.parse_agy_available_models(AGY_ERROR)


class ModelFlagsTest(unittest.TestCase):
    def test_placeholders_never_reach_the_cli(self):
        for model in (None, "", "CLI-Default", "gemini-3.8-flash (CLI-Default)", "gemini-4-argon (Standard)"):
            for effort in (None, "", "high (CLI Default)", "high (7 thinking tokens)"):
                with self.subTest(model=model, effort=effort):
                    self.assertEqual(loop.model_flags("agy", model, effort), [])

    def test_agy_gets_new_model_names_with_effort(self):
        self.assertEqual(loop.model_flags("agy", "gemini-3.8-flash", "low"), ["--model", "Gemini 3.8 Flash (Low)"])
        self.assertEqual(loop.model_flags("agy", "gemini-4-argon", None), ["--model", "Gemini 4 Argon (Medium)"])
        self.assertEqual(loop.model_flags("agy", "gemini-4-argon", "max"), ["--model", "Gemini 4 Argon (High)"])
        self.assertEqual(loop.model_flags("agy", "Claude Opus 5.5 (High)", "low"), ["--model", "Claude Opus 5.5 (High)"])
        self.assertEqual(loop.agy_model_name("gpt-oss-120b"), "GPT-OSS 120B (Medium)")
        self.assertEqual(loop.model_flags("agy", None, "high"), ["--effort", "high"])

    def test_other_clis_keep_their_names(self):
        self.assertEqual(loop.model_flags("codex", "gpt-5", "high"), ["--model", "gpt-5", "--effort", "high"])
        self.assertEqual(loop.model_flags("claude", "sonnet", "high"), ["--model", "sonnet"])

    def test_reported_model_does_not_become_the_requested_one(self):
        agent = loop.AgentCLI(
            "Antigravity", "agy", lambda *a: ("ok", {"model": "gemini-3.8-flash (CLI-Default)", "effort": "high (7 thinking tokens)"})
        )
        agent.model, agent.effort = loop.DEFAULT_MODEL_LABEL, None
        agent.run("Prompt")
        self.assertEqual(agent.model, loop.DEFAULT_MODEL_LABEL)
        self.assertIsNone(agent.effort)


class AgyModelListTest(unittest.TestCase):
    def setUp(self):
        loop.backends._AGY_AVAILABLE_MODELS.clear()
        self.addCleanup(loop.backends._AGY_AVAILABLE_MODELS.clear)
        p = mock.patch.object(loop.backends, "build_cli_command", side_effect=lambda b, a: ([b] + list(a), False))
        p.start()
        self.addCleanup(p.stop)

    def test_parse_and_match(self):
        self.assertEqual(len(AVAILABLE), 8)
        self.assertEqual(loop.match_agy_model("gemini-3.8-flash (CLI-Default)", None, AVAILABLE), "Gemini 3.8 Flash (Medium)")
        self.assertEqual(loop.match_agy_model("gemini-3.8-flash", "low", AVAILABLE), "Gemini 3.8 Flash (Low)")
        self.assertEqual(loop.match_agy_model("Gemini 4 Argon (High)", None, AVAILABLE), "Gemini 4 Argon (High)")
        self.assertEqual(loop.match_agy_model("claude-opus-5-5", None, AVAILABLE), "Claude Opus 5.5 (Medium)")
        self.assertIsNone(loop.match_agy_model("unbekannt", None, AVAILABLE))

    def test_unknown_model_is_retried_with_name_from_agy(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            if len(calls) == 1:
                return subprocess.CompletedProcess(cmd, 1, "", AGY_ERROR)
            return subprocess.CompletedProcess(cmd, 0, '{"response": "ok"}', "")

        with mock.patch.object(loop.subprocess, "run", side_effect=fake_run):
            text, metrics = loop._exec_agy("agy", "Prompt", None, ["--model", "gemini-3.8-flash", "--effort", "low"])
            self.assertEqual(text, "ok")
            self.assertEqual(calls[1][calls[1].index("--model") + 1], "Gemini 3.8 Flash (Low)")
            self.assertNotIn("--effort", calls[1])
            self.assertEqual(metrics["model"], "Gemini 3.8 Flash (Low)")
            # Der nächste Aufruf nutzt die gemerkte Liste direkt
            loop._exec_agy("agy", "Prompt", None, ["--model", "gemini-4-argon"])
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[2][calls[2].index("--model") + 1], "Gemini 4 Argon (Medium)")

    def test_no_match_falls_back_to_cli_default(self):
        results = [subprocess.CompletedProcess([], 1, "", AGY_ERROR), subprocess.CompletedProcess([], 0, '{"response": "ok"}', "")]
        with mock.patch.object(loop.subprocess, "run", side_effect=results) as run:
            loop._exec_agy("agy", "Prompt", None, ["--model", "gibts-nicht", "--effort", "high"])
        retry = run.call_args_list[1].args[0]
        self.assertNotIn("--model", retry)
        self.assertNotIn("--effort", retry)

    def test_other_errors_are_not_retried(self):
        failed = subprocess.CompletedProcess([], 1, "", "not logged in")
        with mock.patch.object(loop.subprocess, "run", return_value=failed) as run, self.assertRaises(RuntimeError):
            loop._exec_agy("agy", "Prompt", None, ["--model", "gemini-4-argon"])
        self.assertEqual(run.call_count, 1)

    def test_empty_response_asks_once_in_same_conversation(self):
        empty = '{"conversation_id": "c-1", "status": "SUCCESS", "response": "", "usage": {"input_tokens": 10, "output_tokens": 2}}'
        filled = '{"conversation_id": "c-1", "status": "SUCCESS", "response": "VERDICT: APPROVED", "usage": {"input_tokens": 5, "output_tokens": 3}}'
        results = [subprocess.CompletedProcess([], 0, empty, ""), subprocess.CompletedProcess([], 0, filled, "")]
        with mock.patch.object(loop.subprocess, "run", side_effect=results) as run:
            text, metrics = loop._exec_agy("agy", "Prompt", None, ["--mode", "plan"])
        self.assertEqual(text, "VERDICT: APPROVED")
        self.assertEqual((metrics["input_tokens"], metrics["output_tokens"]), (15, 5))
        followup = run.call_args_list[1].args[0]
        self.assertEqual(followup[followup.index("--conversation") + 1], "c-1")
        self.assertIn("plan", followup)

    def test_empty_response_stays_empty_after_one_followup(self):
        empty = '{"conversation_id": "c-1", "status": "SUCCESS", "response": ""}'
        results = [subprocess.CompletedProcess([], 0, empty, ""), subprocess.CompletedProcess([], 0, empty, "")]
        with mock.patch.object(loop.subprocess, "run", side_effect=results) as run:
            text, _ = loop._exec_agy("agy", "Prompt", None, [])
        self.assertEqual(text, "")
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
