"""Tests für das Fortsetzen der Bauleiter-Sitzung über Bau-Runden (Token-Schonung)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402


def make_ctx(tmp: Path) -> "loop.BuildContext":
    session_dir = tmp / "session"
    session_dir.mkdir()
    return loop.BuildContext(
        work_path=tmp,
        session_dir=session_dir,
        session_log=tmp / "loop.log",
        state={},
        metrics=loop.SessionMetrics(),
        agents={},
        auto_switch=False,
        inspector=None,
        written_so_far=[],
    )


class ResumeFlagsTest(unittest.TestCase):
    def test_only_cli_builders_with_session(self):
        claude = loop.AgentCLI("Claude Code", "claude", None)
        self.assertEqual(loop.builder_resume_flags(claude), [])
        claude.session_id = "abc"
        self.assertEqual(loop.builder_resume_flags(claude), ["--resume", "abc"])
        self.assertEqual(loop.builder_resume_flags(claude, enabled=False), [])
        gemini = loop.AgentCLI("Gemini CLI", "gemini", None)
        gemini.session_id = "x"
        self.assertEqual(loop.builder_resume_flags(gemini), [])

    def test_codex_resume_args_and_thread_id(self):
        args = loop.build_codex_args(["-s", "workspace-write", "--resume", "t-1"])
        self.assertEqual(args[:4], ["exec", "-s", "workspace-write", "--json"])
        self.assertEqual(args[-3:], ["resume", "t-1", "-"])
        self.assertNotIn("resume", loop.build_codex_args(["-s", "workspace-write"]))
        raw = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "t-9"}),
                json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}}),
            ]
        )
        self.assertEqual(loop.codex_thread_id(raw), "t-9")
        self.assertIsNone(loop.codex_thread_id("kein json"))


class ResumePromptTest(unittest.TestCase):
    def test_short_prompt_skips_task_and_plan(self):
        full = loop.compose_build_prompt("GEHEIME AUFGABE", Path("plan.md"), "make test", "Test rot", False, plan_text="PLAN")
        short = loop.compose_build_prompt(
            "GEHEIME AUFGABE", Path("plan.md"), "make test", "Test rot", False, rel_done_path=Path("s/.done"), resumed=True
        )
        self.assertIn("GEHEIME AUFGABE", full)
        self.assertNotIn("GEHEIME AUFGABE", short)
        self.assertIn("Test rot", short)
        self.assertIn("s/.done", short)
        self.assertLess(len(short), len(full))

    def test_short_stage_prompt(self):
        short = loop.compose_build_prompt(
            "Aufgabe", Path("plan.md"), "make test", "", False, stage=("Etappe 2/3", "API bauen", "- [x] Modell"), resumed=True
        )
        self.assertIn("JETZT NUR ETAPPE 2/3: API bauen", short)
        self.assertIn("KEINE Fertigmeldung", short)
        self.assertNotIn("Aufgabe", short.split("\n")[1:])

    def test_endpoint_never_gets_short_prompt(self):
        prompt = loop.compose_build_prompt("Aufgabe", Path("plan.md"), None, "", True, plan_text="PLAN", resumed=True)
        self.assertIn("--- GENEHMIGTER PLAN ---", prompt)


class RunBuildCallTest(unittest.TestCase):
    def test_resumed_call_uses_short_prompt(self):
        builder = loop.AgentCLI("Claude Code", "claude", None)
        builder.session_id = "s1"
        calls = []

        def fake_run(agent, prompt, flags, **kw):
            calls.append((prompt, list(flags)))
            return "ok", agent, flags

        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(Path(tmp))
            with mock.patch.object(loop.build, "safe_agent_run", side_effect=fake_run):
                _, _, flags, _ = loop.run_build_call(ctx, builder, ["-x"], "KURZ", False, "w", "l", "h", full_prompt="LANG")
        self.assertEqual(calls, [("KURZ", ["-x", "--resume", "s1"])])
        self.assertEqual(flags, ["-x"])
        self.assertEqual(ctx.metrics.counters.get("builder_resumed"), 1)
        self.assertEqual(ctx.state["builder_session"], {"binary": "claude", "id": "s1"})

    def test_failed_resume_falls_back_to_full_prompt(self):
        builder = loop.AgentCLI("Claude Code", "claude", None)
        builder.session_id = "alt"
        calls = []

        def fake_run(agent, prompt, flags, **kw):
            calls.append((prompt, list(flags)))
            if "--resume" in flags:
                raise RuntimeError("No conversation found")
            return "ok", agent, flags

        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(Path(tmp))
            with mock.patch.object(loop.build, "safe_agent_run", side_effect=fake_run):
                res, _, flags, _ = loop.run_build_call(ctx, builder, ["-x"], "KURZ", False, "w", "l", "h", full_prompt="LANG")
        self.assertEqual(res, "ok")
        self.assertEqual(calls[-1], ("LANG", ["-x"]))
        self.assertEqual(flags, ["-x"])
        self.assertNotIn("builder_resumed", ctx.metrics.counters)

    def test_switched_builder_gets_full_prompt(self):
        builder = loop.AgentCLI("Claude Code", "claude", None)
        builder.session_id = "s1"
        other = loop.AgentCLI("Codex", "codex", None)
        calls = []

        def fake_run(agent, prompt, flags, **kw):
            calls.append((agent.binary, prompt))
            if agent is builder:
                return "ok", other, ["-s", "workspace-write"]
            return "ok", agent, flags

        with tempfile.TemporaryDirectory() as tmp:
            ctx = make_ctx(Path(tmp))
            with mock.patch.object(loop.build, "safe_agent_run", side_effect=fake_run):
                _, new_builder, flags, _ = loop.run_build_call(ctx, builder, ["-x"], "KURZ", False, "w", "l", "h", full_prompt="LANG")
        self.assertIs(new_builder, other)
        self.assertEqual(calls, [("claude", "KURZ"), ("codex", "LANG")])
        self.assertEqual(flags, ["-s", "workspace-write"])


if __name__ == "__main__":
    unittest.main()
