"""Unit-Tests für loop.py (nur Standardbibliothek: python -m unittest discover -s tests)."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402


class RateLimitParsingTest(unittest.TestCase):
    def test_detects_rate_limit_messages(self):
        self.assertTrue(loop.is_rate_limit("Error: You hit your session limit, resets 3pm"))
        self.assertTrue(loop.is_rate_limit("429 Too Many Requests"))
        self.assertTrue(loop.is_rate_limit("RESOURCE_EXHAUSTED: quota"))
        self.assertFalse(loop.is_rate_limit("SyntaxError in line 3"))

    def test_extracts_reset_time(self):
        self.assertEqual(loop.extract_reset_time("limit reached, resets in 2 hours"), "2 hours")
        self.assertEqual(loop.extract_reset_time("please try again in 30s"), "30s")
        self.assertIsNone(loop.extract_reset_time("no hint here"))

    def test_parses_durations(self):
        self.assertEqual(loop.parse_reset_seconds("2 hours"), 7200)
        self.assertEqual(loop.parse_reset_seconds("15 min"), 900)
        self.assertEqual(loop.parse_reset_seconds("30s"), 30)
        self.assertIsNone(loop.parse_reset_seconds(None))
        self.assertIsNone(loop.parse_reset_seconds("irgendwann"))

    def test_parses_clock_time_in_the_future(self):
        secs = loop.parse_reset_seconds("23:59:59")
        self.assertIsNotNone(secs)
        self.assertGreater(secs, 0)
        self.assertLessEqual(secs, 24 * 3600)


class HelperTest(unittest.TestCase):
    def test_extract_flag_value(self):
        flags = ["--model", "opus", "--effort=high"]
        self.assertEqual(loop.extract_flag_value(flags, "--model"), "opus")
        self.assertEqual(loop.extract_flag_value(flags, "--effort"), "high")
        self.assertIsNone(loop.extract_flag_value(flags, "--missing"))
        self.assertIsNone(loop.extract_flag_value(None, "--model"))

    def test_normalize_endpoint_url(self):
        self.assertEqual(loop.normalize_endpoint_url("http://localhost:11434"), "http://localhost:11434/v1/chat/completions")
        self.assertEqual(loop.normalize_endpoint_url("https://ai.example/v1/"), "https://ai.example/v1/chat/completions")
        self.assertEqual(loop.normalize_endpoint_url("https://x/v1/chat/completions"), "https://x/v1/chat/completions")

    def test_sanitize_filename(self):
        self.assertEqual(loop.sanitize_filename("Baue eine REST-API!"), "Baue_eine_REST-API")
        self.assertEqual(loop.sanitize_filename("???"), "task")
        self.assertLessEqual(len(loop.sanitize_filename("x" * 100)), 30)

    def test_extract_questions(self):
        text = "Plan...\n## OFFENE FRAGEN\n1. Welche Datenbank?\n## Nächster Abschnitt\n"
        self.assertIn("Welche Datenbank?", loop.extract_questions(text))
        self.assertIsNone(loop.extract_questions("Nur ein Plan ohne Fragen."))

    def test_session_metrics_roundtrip(self):
        m = loop.SessionMetrics()
        m.add("claude", input_tokens=100, output_tokens=50, cost_usd=0.01, role="planner", model="opus")
        m.add("claude", input_tokens=10, output_tokens=5, role="planner")
        restored = loop.SessionMetrics.from_dict(m.to_dict())
        self.assertEqual(restored.total_tokens, 165)
        self.assertEqual(restored.by_agent["planner [claude]"]["model"], "opus")
        self.assertIn("165", loop.format_metrics_report(restored).replace(".", "").replace(",", ""))


class ApplyCodeBlocksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.project = self.base / "project"
        self.project.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def apply(self, text):
        with mock.patch("builtins.print"):
            return loop.apply_code_blocks(self.project, text)

    def test_writes_files_inside_project(self):
        text = (
            "```filepath: src/app.py\nprint('hi')\n```\n"
            "### Datei: `docs/readme.md`\n```markdown\n# Doku\n```\n"
        )
        self.assertEqual(self.apply(text), ["src/app.py", "docs/readme.md"])
        self.assertEqual((self.project / "src/app.py").read_text(encoding="utf-8"), "print('hi')\n")
        self.assertEqual((self.project / "docs/readme.md").read_text(encoding="utf-8"), "# Doku\n")

    def test_blocks_parent_traversal(self):
        written = self.apply("```filepath: ../outside.txt\npwned\n```\n```file: a/../../b.txt\nx\n```\n")
        self.assertEqual(written, [])
        self.assertFalse((self.base / "outside.txt").exists())
        self.assertFalse((self.base / "b.txt").exists())

    def test_blocks_absolute_paths(self):
        target = self.base / "abs.txt"
        written = self.apply(f"```filepath: {target.as_posix()}\npwned\n```\n")
        self.assertEqual(written, [])
        self.assertFalse(target.exists())

    def test_blocks_windows_drive_and_backslash_traversal(self):
        written = self.apply("```filepath: C:/Windows/evil.txt\nx\n```\n```filepath: ..\\evil.txt\nx\n```\n")
        self.assertEqual(written, [])
        self.assertFalse((self.base / "evil.txt").exists())

    def test_blocks_git_directory(self):
        written = self.apply("```filepath: .git/hooks/pre-commit\n#!/bin/sh\n```\n")
        self.assertEqual(written, [])
        self.assertFalse((self.project / ".git").exists())

    @unittest.skipIf(sys.platform == "win32", "Symlinks benötigen unter Windows Sonderrechte")
    def test_blocks_symlink_escape(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.project / "link").symlink_to(outside, target_is_directory=True)
        written = self.apply("```filepath: link/evil.txt\nx\n```\n")
        self.assertEqual(written, [])
        self.assertFalse((outside / "evil.txt").exists())


class WindowsCommandTest(unittest.TestCase):
    NPM_SHIM = (
        '@ECHO off\r\nGOTO start\r\n:find_dp0\r\nSET dp0=%~dp0\r\nEXIT /b\r\n:start\r\nSETLOCAL\r\nCALL :find_dp0\r\n'
        'IF EXIST "%dp0%\\node.exe" (\r\n  SET "_prog=%dp0%\\node.exe"\r\n) ELSE (\r\n  SET "_prog=node"\r\n)\r\n'
        'endLocal & goto #_undefined_# 2>NUL || title %COMSPEC% & "%_prog%"  '
        '"%dp0%\\node_modules\\@anthropic-ai\\claude-code\\cli.js" %*\r\n'
    )

    def test_unwraps_npm_shim_to_node_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            shim = Path(tmp) / "claude.cmd"
            shim.write_text(self.NPM_SHIM, encoding="utf-8")
            (Path(tmp) / "node.exe").write_text("", encoding="utf-8")
            argv = loop.unwrap_npm_cmd_shim(shim)
        self.assertEqual(argv[0], str(Path(tmp) / "node.exe"))
        self.assertTrue(argv[1].replace("\\", "/").endswith("node_modules/@anthropic-ai/claude-code/cli.js"))

    def test_unknown_batch_file_is_not_unwrapped(self):
        with tempfile.TemporaryDirectory() as tmp:
            bat = Path(tmp) / "tool.bat"
            bat.write_text("@echo off\r\npython tool.py %*\r\n", encoding="utf-8")
            self.assertIsNone(loop.unwrap_npm_cmd_shim(bat))

    def test_quote_cmd_arg_neutralises_metacharacters(self):
        self.assertEqual(loop.quote_cmd_arg('a & b'), '"a & b"')
        self.assertEqual(loop.quote_cmd_arg('say "hi"'), '"say ""hi"""')
        self.assertEqual(loop.quote_cmd_arg("%PATH%"), '"%%cd:~,%PATH%%cd:~,%"')
        self.assertEqual(loop.quote_cmd_arg("C:\\dir\\"), '"C:\\dir\\\\"')
        with self.assertRaises(ValueError):
            loop.quote_cmd_arg("zeile1\nzeile2")

    def test_non_windows_never_uses_shell(self):
        with mock.patch.object(loop.sys, "platform", "linux"):
            cmd, shell = loop.build_cli_command("claude", ["-p", "a & b\nc"])
        self.assertFalse(shell)
        self.assertEqual(cmd[1:], ["-p", "a & b\nc"])

    def test_windows_shim_runs_without_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            shim = Path(tmp) / "claude.cmd"
            shim.write_text(self.NPM_SHIM, encoding="utf-8")
            (Path(tmp) / "node.exe").write_text("", encoding="utf-8")
            with mock.patch.object(loop.sys, "platform", "win32"), \
                 mock.patch.object(loop.shutil, "which", return_value=str(shim)):
                cmd, shell = loop.build_cli_command("claude", ["-p", "Zeile 1\nZeile 2 & mehr"])
        self.assertFalse(shell)
        self.assertEqual(cmd[-2:], ["-p", "Zeile 1\nZeile 2 & mehr"])


class CliSmokeTest(unittest.TestCase):
    def run_loop(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "loop.py"), *args],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=60,
        )

    def test_help(self):
        res = self.run_loop("--help")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("--strategy", res.stdout)

    def test_dry_run_prints_roles_without_executing(self):
        # Ein (nicht erreichbarer) Endpunkt reicht als Agent, damit der Test ohne installierte CLIs läuft.
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_loop(
                "--dry-run", "Teste den Trockenlauf", "-p", tmp,
                "--strategy", "local-free", "--endpoint", "http://127.0.0.1:9/v1",
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("Bauleiter", res.stdout)
            self.assertFalse((Path(tmp) / ".dual-loop").exists())

    def test_exits_cleanly_without_any_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items()
                   if k not in ("CLAUDEGRAVITY_ENDPOINT", "OPENAI_BASE_URL", "AI_ENDPOINT")}
            env["PATH"] = tmp
            res = subprocess.run(
                [sys.executable, str(ROOT / "loop.py"), "--dry-run", "x", "-p", tmp],
                capture_output=True, text=True, encoding="utf-8", timeout=60, env=env,
            )
        self.assertEqual(res.returncode, 1)
        self.assertIn("Keine AI-CLI", res.stderr)
        self.assertNotIn("Traceback", res.stderr)


class AgentDescriptionTest(unittest.TestCase):
    def test_describes_provider_model_and_effort(self):
        agent = loop.AgentCLI("Antigravity (agy)", "agy", None, model="gemini-2.5-pro", effort="high")
        self.assertEqual(loop.describe_agent(agent), "Antigravity (agy) (`gemini-2.5-pro`) [Effort: high]")

    def test_marks_effort_ignored_by_other_clis(self):
        self.assertEqual(loop.effort_label("claude", "high"), "high (nur für agy/codex wirksam)")
        self.assertEqual(loop.effort_label("agy", "low"), "low")
        self.assertEqual(loop.effort_label("ollama", "0€ Lokal/Intranet"), "0€ Lokal/Intranet")
        self.assertIsNone(loop.effort_label("claude", None))

    def test_default_model_without_guessed_names(self):
        agent = loop.AgentCLI("Claude Code", "claude", None, model=loop.DEFAULT_MODEL_LABEL)
        self.assertEqual(loop.describe_agent(agent), "Claude Code (`CLI-Default`)")


if __name__ == "__main__":
    unittest.main()
