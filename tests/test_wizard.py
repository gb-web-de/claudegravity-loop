"""Tests für `claudegravity init`, den geführten Erstlauf und die Warnungen bei riskanten Einstellungen."""

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


def fake(name, local=False):
    return loop.AgentCLI(name, name, lambda *a: ("", {}), local=local)


CLOUD_AND_LOCAL = {"codex": fake("Codex"), "ollama": fake("Ollama", local=True)}


def scripted(*answers):
    it = iter(answers)
    return lambda prompt: next(it)


class WizardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "projekt"
        self.project.mkdir()
        self.global_path = self.root / "cfg" / "profile.json"
        self.addCleanup(self.tmp.cleanup)

    def test_proof_suggestions(self):
        self.assertIsNone(loop.suggest_proof_command(self.project))
        (self.project / "tests").mkdir()
        self.assertEqual(loop.suggest_proof_command(self.project), "python3 -m unittest discover -s tests")
        (self.project / "package.json").write_text("{}", encoding="utf-8")
        self.assertEqual(loop.suggest_proof_command(self.project), "npm test")
        (self.project / "composer.json").write_text("{}", encoding="utf-8")
        self.assertEqual(loop.suggest_proof_command(self.project), "vendor/bin/phpunit")

    def test_strategy_for_goal(self):
        self.assertEqual(loop.strategy_for_goal("guenstig", CLOUD_AND_LOCAL)[0], "hybrid")
        self.assertEqual(loop.strategy_for_goal("guenstig", {"ollama": fake("Ollama", True)})[0], "local-free")
        self.assertEqual(loop.strategy_for_goal("guenstig", {"claude": fake("Claude")})[0], "eco")
        self.assertEqual(loop.strategy_for_goal("qualitaet", CLOUD_AND_LOCAL)[0], "best-code")
        self.assertEqual(loop.strategy_for_goal("schnell", CLOUD_AND_LOCAL)[0], "balanced")

    def test_wizard_writes_project_profile_with_defaults(self):
        (self.project / "tests").mkdir()
        target = loop.run_setup_wizard(self.project, CLOUD_AND_LOCAL, input_fn=scripted("", "", ""), global_path=self.global_path)
        self.assertEqual(target, loop.project_profile_path(self.project))
        data = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual((data["strategy"], data["proof"], data["etappen"]),
                         ("hybrid", "python3 -m unittest discover -s tests", "auto"))
        self.assertFalse(self.global_path.exists())

    def test_wizard_global_and_merge(self):
        self.global_path.parent.mkdir()
        self.global_path.write_text(json.dumps({"bauer-model": "qwen", "strategy": "eco"}), encoding="utf-8")
        target = loop.run_setup_wizard(self.project, {"claude": fake("Claude"), "agy": fake("Antigravity")},
                                       input_fn=scripted("x", "3", "-", "2"), global_path=self.global_path)
        data = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual((data["strategy"], data["bauer-model"]), ("best-code", "qwen"))
        self.assertNotIn("proof", data)

    def test_wizard_without_agents(self):
        self.assertIsNone(loop.run_setup_wizard(self.project, {}, input_fn=scripted(), global_path=self.global_path))

    def test_wizard_profile_is_valid_config(self):
        loop.run_setup_wizard(self.project, CLOUD_AND_LOCAL, input_fn=scripted("1", "make test", "1"), global_path=self.global_path)
        parser = loop.build_parser()
        argv = ["-p", str(self.project)]
        args = parser.parse_args(argv)
        report = loop.apply_config_layers(parser, args, argv, env={}, global_path=self.global_path)
        self.assertEqual(report["warnings"], [])
        self.assertEqual((args.strategy, args.proof), ("balanced", "make test"))

    def test_broken_profile_is_not_overwritten(self):
        path = loop.project_profile_path(self.project)
        path.parent.mkdir(parents=True)
        path.write_text("{kaputt", encoding="utf-8")
        with self.assertRaises(ValueError):
            loop.write_profile(path, {"strategy": "eco"})
        self.assertEqual(path.read_text(encoding="utf-8"), "{kaputt")

    def test_first_run_guide(self):
        self.assertEqual(loop.first_run_guide(None, input_fn=scripted("")), "dry-run")
        self.assertEqual(loop.first_run_guide(None, input_fn=scripted("2")), "init")
        self.assertEqual(loop.first_run_guide(None, input_fn=scripted("4")), "quiet")

    def test_init_from_command_line(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDEGRAVITY_")}
        env.update(PATH=str(self.root), CLAUDEGRAVITY_CONFIG_DIR=str(self.global_path.parent), PYTHONIOENCODING="utf-8")
        res = subprocess.run(
            [sys.executable, str(ROOT / "loop.py"), "init", "-p", str(self.project), "--endpoint", "http://127.0.0.1:9/v1"],
            input="\nmake test\n\n", capture_output=True, text=True, encoding="utf-8", timeout=60, env=env,
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("Profil gespeichert", res.stdout)
        data = json.loads(loop.project_profile_path(self.project).read_text(encoding="utf-8"))
        self.assertEqual((data["strategy"], data["proof"]), ("local-free", "make test"))
        self.assertFalse((self.project / ".dual-loop" / "sessions").exists())


class UnsafeConfigTest(unittest.TestCase):
    def args(self, *argv):
        return loop.build_parser().parse_args(list(argv))

    def test_warnings(self):
        p = Path(".")
        self.assertTrue(any("ohne Git" in w for w in loop.unsafe_config_warnings(self.args("x", "--yolo"), p, False)))
        self.assertTrue(any("--no-worktree" in w for w in loop.unsafe_config_warnings(self.args("x", "--yolo", "--no-worktree"), p, True)))
        self.assertTrue(any("--no-inspect" in w for w in loop.unsafe_config_warnings(self.args("x", "--no-inspect", "--proof", "t"), p, True)))
        warn = loop.unsafe_config_warnings(self.args("x", "--endpoint", "http://ki.example.com/v1", "--api-key", "k", "--proof", "t"), p, True)
        self.assertTrue(any("unverschlüsselt" in w for w in warn))
        self.assertEqual(loop.unsafe_config_warnings(self.args("x", "--proof", "t"), p, True), [])


if __name__ == "__main__":
    unittest.main()
