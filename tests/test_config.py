"""Tests für die Konfigurationsschichten CLI > Session > Umgebung > Projekt-Profil > globales Profil > Standard."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402


class ConfigLayerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "projekt"
        (self.project / ".dual-loop").mkdir(parents=True)
        self.global_path = self.root / "config" / "profile.json"
        self.global_path.parent.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path: Path, data):
        path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")

    def resolve(self, argv, env=None, project=None, global_=None):
        if project is not None:
            self.write(loop.project_profile_path(self.project), project)
        if global_ is not None:
            self.write(self.global_path, global_)
        parser = loop.build_parser()
        full = list(argv) + ["-p", str(self.project)]
        args = parser.parse_args(full)
        report = loop.apply_config_layers(parser, args, full, env=env or {}, global_path=self.global_path)
        return args, report

    def test_defaults_without_profiles(self):
        args, report = self.resolve([])
        self.assertIsNone(args.strategy)
        self.assertEqual(args.max_rounds, 2)
        self.assertTrue(args.worktree)
        self.assertEqual(set(report["sources"].values()), {"default"})
        self.assertEqual(report["conflicts"], [])

    def test_order_cli_env_project_global(self):
        global_ = {"strategy": "best-code", "proof": "make test", "max_rounds": 4, "builder_model": "g"}
        project = {"strategy": "hybrid", "proof": "pytest", "builder_model": "p"}
        env = {"CLAUDEGRAVITY_STRATEGY": "eco", "CLAUDEGRAVITY_BUILDER_MODEL": "e"}
        args, report = self.resolve(["--bauer-model", "c"], env=env, project=project, global_=global_)
        self.assertEqual((args.builder_model, report["sources"]["builder_model"]), ("c", "cli"))
        self.assertEqual((args.strategy, report["sources"]["strategy"]), ("eco", "env"))
        self.assertEqual((args.proof, report["sources"]["proof"]), ("pytest", "project"))
        self.assertEqual((args.max_rounds, report["sources"]["max_rounds"]), (4, "global"))
        self.assertTrue(any(c.startswith("strategy:") and "Projekt-Profil 'hybrid'" in c for c in report["conflicts"]))
        self.assertTrue(any(c.startswith("builder_model:") and "Kommandozeile 'c'" in c for c in report["conflicts"]))

    def test_cli_value_equal_to_default_still_wins(self):
        args, report = self.resolve(["--max-rounds", "2"], project={"max_rounds": 5})
        self.assertEqual(args.max_rounds, 2)
        self.assertEqual(report["sources"]["max_rounds"], "cli")

    def test_flag_aliases_and_booleans(self):
        args, report = self.resolve([], project={"bauer-model": "qwen", "etappen": "aus", "worktree": False, "merge": "ja"})
        self.assertEqual(args.builder_model, "qwen")
        self.assertEqual(args.etappen, "aus")
        self.assertFalse(args.worktree)
        self.assertTrue(args.merge)
        self.assertEqual(report["warnings"], [])

    def test_invalid_entries_are_ignored_with_warning(self):
        project = {"strategy": "teuer", "max_rounds": "viele", "gibtsnicht": 1, "no_worktree": True, "_kommentar": "x"}
        args, report = self.resolve([], project=project)
        self.assertIsNone(args.strategy)
        self.assertEqual(args.max_rounds, 2)
        self.assertTrue(args.worktree)
        self.assertEqual(len(report["warnings"]), 4)

    def test_secrets_and_rights_not_from_project_profile(self):
        args, report = self.resolve([], project={"api_key": "geheim", "yolo": True})
        self.assertFalse(args.yolo)
        self.assertIsNone(args.api_key)
        self.assertEqual(len(report["warnings"]), 2)
        args, _ = self.resolve([], global_={"yolo": True}, project={})
        self.assertTrue(args.yolo)

    def test_broken_profile_is_ignored(self):
        args, report = self.resolve([], project="{kaputt")
        self.assertIsNone(args.strategy)
        self.assertIn("nicht lesbar", report["warnings"][0])

    def test_env_values_are_typed(self):
        env = {"CLAUDEGRAVITY_MAX_ITERATIONS": "7", "CLAUDEGRAVITY_AUTO_SWITCH": "on", "CLAUDEGRAVITY_DELAY": "kurz"}
        args, report = self.resolve([], env=env)
        self.assertEqual(args.max_iterations, 7)
        self.assertTrue(args.auto_switch)
        self.assertEqual(args.delay, 3)
        self.assertIn("CLAUDEGRAVITY_DELAY", report["warnings"][0])

    def test_resume_keeps_session_strategy(self):
        session = self.project / ".dual-loop" / "sessions" / "20260101_000000_x"
        session.mkdir(parents=True)
        self.write(session / "state.json", {"strategy": "hybrid", "builder_model": "s", "proof": "pytest"})
        args, report = self.resolve(["-c", "--bauer-model", "c"], env={"CLAUDEGRAVITY_STRATEGY": "eco"}, project={"proof": "make"})
        self.assertEqual((args.strategy, report["sources"]["strategy"]), ("hybrid", "session"))
        self.assertEqual(args.builder_model, "c")
        self.assertEqual(args.proof, "pytest")
        args, report = self.resolve([], env={"CLAUDEGRAVITY_STRATEGY": "eco"})
        self.assertEqual(args.strategy, "eco")

    def test_global_profile_path(self):
        self.assertEqual(loop.global_profile_path({"CLAUDEGRAVITY_CONFIG_DIR": "/x"}), Path("/x") / "profile.json")
        if os.name != "nt":
            self.assertEqual(loop.global_profile_path({"XDG_CONFIG_HOME": "/cfg"}), Path("/cfg/claudegravity/profile.json"))

    def test_project_profile_is_protected_from_model_writes(self):
        self.assertIsNone(loop.resolve_project_target(self.project, ".dual-loop/profile.json"))

    def test_print_effective_config_cli(self):
        self.write(loop.project_profile_path(self.project), {"strategy": "hybrid"})
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDEGRAVITY_")}
        env["CLAUDEGRAVITY_CONFIG_DIR"] = str(self.global_path.parent)
        env["CLAUDEGRAVITY_STRATEGY"] = "eco"
        env["PYTHONIOENCODING"] = "utf-8"
        res = subprocess.run(
            [sys.executable, str(ROOT / "loop.py"), "--print-effective-config", "-p", str(self.project)],
            capture_output=True, text=True, encoding="utf-8", timeout=60, env=env,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertRegex(res.stdout, r'strategy\s+= "eco"\s+\[Umgebung\]\s+⚠️ Konflikt')
        self.assertIn("Projekt-Profil 'hybrid'", res.stdout)
        self.assertFalse((self.project / ".dual-loop" / "sessions").exists())


if __name__ == "__main__":
    unittest.main()
