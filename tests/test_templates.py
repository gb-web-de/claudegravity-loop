"""Tests für Aufgaben-Vorlagen (--template) und ihre Anpassung über Profile."""

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


class TemplateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "projekt"
        (self.project / ".dual-loop").mkdir(parents=True)
        self.global_path = self.root / "cfg" / "profile.json"
        self.global_path.parent.mkdir()
        self.addCleanup(self.tmp.cleanup)

    def resolve(self, argv, env=None, project=None, global_=None):
        if project is not None:
            loop.project_profile_path(self.project).write_text(json.dumps(project), encoding="utf-8")
        if global_ is not None:
            self.global_path.write_text(json.dumps(global_), encoding="utf-8")
        parser = loop.build_parser()
        full = list(argv) + ["-p", str(self.project)]
        args = parser.parse_args(full)
        return args, loop.apply_config_layers(parser, args, full, env=env or {}, global_path=self.global_path)

    def test_builtin_bugfix(self):
        args, report = self.resolve(["--template", "bugfix"])
        self.assertEqual((args.strategy, args.etappen, args.max_iterations), ("eco", "aus", 5))
        self.assertEqual(report["sources"]["strategy"], "template")
        self.assertEqual(report["template"]["requires"], ["proof"])
        self.assertIn("Test", report["template"]["hint"])

    def test_cli_beats_template_and_template_beats_profile(self):
        args, report = self.resolve(
            ["--vorlage", "bugfix", "-m", "9"], project={"strategy": "hybrid", "max_rounds": 4}, env={"CLAUDEGRAVITY_ETAPPEN": "an"}
        )
        self.assertEqual(args.max_iterations, 9)
        self.assertEqual(args.strategy, "eco")
        self.assertEqual(args.etappen, "aus")
        self.assertEqual(args.max_rounds, 4)
        self.assertTrue(any(c.startswith("strategy:") for c in report["conflicts"]))

    def test_profiles_adjust_and_add_templates(self):
        global_ = {"templates": {"bugfix": {"max_iterations": 8}, "typo3": {"strategy": "hybrid", "proof": "vendor/bin/phpunit"}}}
        project = {"templates": {"bugfix": {"max_iterations": 3}}}
        args, report = self.resolve(["--template", "bugfix"], project=project, global_=global_)
        self.assertEqual((args.max_iterations, args.strategy), (3, "eco"))
        self.assertEqual(report["template"]["origin"], "Projekt-Profil")
        args, report = self.resolve(["--template", "typo3"], project={}, global_=global_)
        self.assertEqual((args.strategy, args.proof), ("hybrid", "vendor/bin/phpunit"))
        self.assertEqual(report["warnings"], [])

    def test_default_template_from_profile(self):
        args, report = self.resolve([], project={"template": "refactor"})
        self.assertEqual((args.reviewer_effort, args.max_rounds), ("high", 3))

    def test_unknown_template_and_forbidden_keys(self):
        _, report = self.resolve(["--template", "quatsch"])
        self.assertIsNone(report["template"])
        self.assertTrue(any("Unbekannte Vorlage" in w for w in report["warnings"]))
        args, report = self.resolve(["--template", "x"], project={"templates": {"x": {"yolo": True, "template": "y"}}})
        self.assertFalse(args.yolo)
        self.assertEqual(len(report["warnings"]), 2)

    def test_template_requires_proof_on_command_line(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDEGRAVITY_")}
        env.update(PATH=str(self.root), CLAUDEGRAVITY_CONFIG_DIR=str(self.global_path.parent), PYTHONIOENCODING="utf-8")
        cmd = [
            sys.executable,
            str(ROOT / "loop.py"),
            "--dry-run",
            "Fix",
            "--template",
            "refactor",
            "-p",
            str(self.project),
            "--endpoint",
            "http://127.0.0.1:9/v1",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("braucht einen Prüfbefehl", res.stdout + res.stderr)
        (self.project / "package.json").write_text("{}", encoding="utf-8")
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("npm test", res.stdout)


if __name__ == "__main__":
    unittest.main()
