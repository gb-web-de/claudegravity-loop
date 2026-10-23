"""Tests für Review-Urteil, Rollenrechte, Abnahme und Token-Sparen (python -m unittest discover -s tests)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402
import mcp_server  # noqa: E402


def agent(binary: str, model: str | None = None) -> loop.AgentCLI:
    return loop.AgentCLI(binary, binary, lambda *a: ("", {}), model=model)


class VerdictTest(unittest.TestCase):
    def decide(self, text: str) -> bool:
        return loop.review_decision(loop.parse_review(text))[0]

    def test_echoed_template_is_no_approval(self):
        echo = "Antworte strukturiert mit:\nVERDICT: APPROVED (oder VERDICT: REVISE)\nKRITIK:\n- Race Condition"
        self.assertFalse(self.decide(echo))

    def test_verdict_inside_sentence_is_ignored(self):
        self.assertFalse(self.decide("Ich gebe kein VERDICT: APPROVED, weil Tests fehlen."))

    def test_last_verdict_line_wins(self):
        self.assertFalse(self.decide("VERDICT: APPROVED\n...nach erneutem Lesen:\nVERDICT: REVISE"))
        self.assertTrue(self.decide("BEFUNDE:\n- keine\n**VERDICT: APPROVED**"))

    def test_approved_with_material_finding_is_revise(self):
        text = "BEFUNDE:\n- [HOCH] loop.py: Pfad ungeprüft -> prüfen\nVERDICT: APPROVED"
        approved, reason = loop.review_decision(loop.parse_review(text))
        self.assertFalse(approved)
        self.assertIn("HOCH/MITTEL", reason)

    def test_only_low_findings_count_as_approval(self):
        self.assertTrue(self.decide("BEFUNDE:\n- [NIEDRIG] README: Tippfehler -> korrigieren\nVERDICT: REVISE"))

    def test_missing_or_blocked_verdict_never_approves(self):
        self.assertFalse(self.decide(""))
        self.assertFalse(self.decide("Sieht gut aus."))
        self.assertFalse(self.decide("BEFUNDE:\n- keine\nVERDICT: BLOCKED"))

    def test_findings_digest_keeps_only_findings(self):
        text = "Lange Einleitung\nBEFUNDE:\n- [MITTEL] a.py: x -> y\n- [low] b.py: z\nVERDICT: REVISE"
        self.assertEqual(loop.findings_digest(text), "- [MITTEL] a.py: x -> y\n- [NIEDRIG] b.py: z")


class RoleRightsTest(unittest.TestCase):
    def test_reviewer_and_planner_never_get_write_flags(self):
        for role in ("planner", "reviewer"):
            flags = loop.role_flags("claude", role, write_allowed=True)
            self.assertNotIn("--dangerously-skip-permissions", flags)
            self.assertIn("dontAsk", flags)
        self.assertEqual(loop.role_flags("codex", "reviewer", True), ["-s", "read-only"])
        self.assertNotIn("-y", loop.role_flags("gemini", "reviewer", True))

    def test_builder_writes_only_after_approval(self):
        self.assertEqual(loop.role_flags("claude", "builder", False), [])
        self.assertIn("--dangerously-skip-permissions", loop.role_flags("claude", "builder", True))

    def test_switch_never_lands_on_counter_role(self):
        agents = {k: agent(k) for k in ("claude", "agy", "codex")}
        self.assertEqual(loop.get_alternative_agent(agents["claude"], agents).binary, "agy")
        self.assertEqual(loop.get_alternative_agent(agents["claude"], agents, {"agy"}).binary, "codex")
        self.assertIsNone(loop.get_alternative_agent(agents["claude"], agents, {"agy", "codex"}))


class CodexTest(unittest.TestCase):
    def test_args_pass_model_effort_and_read_prompt_from_stdin(self):
        args = loop.build_codex_args(["-s", "workspace-write", "--model", "gpt-x", "--effort", "max"])
        self.assertEqual(args[:3], ["exec", "-s", "workspace-write"])
        self.assertIn("gpt-x", args)
        self.assertIn('model_reasoning_effort="xhigh"', args)
        self.assertEqual(args[-1], "-")
        self.assertEqual(loop.build_codex_args(None)[2], "read-only")

    def test_parses_jsonl_events(self):
        raw = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "t"}),
                json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Plan"}}),
                json.dumps({"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 3}}),
            ]
        )
        text, usage, error = loop.parse_codex_events(raw)
        self.assertEqual((text, usage["input_tokens"], error), ("Plan", 7, None))


class AcceptanceHelpersTest(unittest.TestCase):
    def test_inspector_is_never_the_builder(self):
        builder = agent("claude")
        agents = {"claude": builder, "gemini": agent("gemini")}
        self.assertEqual(loop.pick_inspector(builder, [agent("claude"), None], agents).binary, "gemini")
        self.assertIsNone(loop.pick_inspector(builder, [], {"claude": builder}))

    def test_same_provider_with_other_model_may_inspect(self):
        self.assertFalse(loop.same_identity(agent("endpoint", "qwen"), agent("endpoint", "llama")))
        self.assertTrue(loop.same_identity(agent("claude", "opus"), agent("claude", loop.DEFAULT_MODEL_LABEL)))

    def test_run_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok, _ = loop.run_proof(f'"{sys.executable}" -c "print(1)"', Path(tmp))
            self.assertTrue(ok)
            ok, out = loop.run_proof(f'"{sys.executable}" -c "import sys; print(\'rot\'); sys.exit(3)"', Path(tmp))
            self.assertFalse(ok)
            self.assertIn("Exit-Code 3", out)
            self.assertIn("rot", out)

    @unittest.skipUnless(shutil.which("git"), "git nicht installiert")
    def test_changes_include_new_files_but_not_loop_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for cmd in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
                subprocess.run(["git", *cmd], cwd=tmp, check=True)
            (repo / "a.txt").write_text("alt\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=tmp, check=True)
            subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp, check=True)
            base = loop.git_head(repo)
            (repo / "a.txt").write_text("neu\n", encoding="utf-8")
            (repo / "b.py").write_text("print('b')\n", encoding="utf-8")
            (repo / ".dual-loop" / "sessions").mkdir(parents=True)
            (repo / ".dual-loop" / "sessions" / "x.md").write_text("intern", encoding="utf-8")
            changes = loop.collect_build_changes(repo, base)
            self.assertIn("+neu", changes)
            self.assertIn("--- b.py ---", changes)
            self.assertNotIn("intern", changes)
            self.assertIn("gekürzt", loop.collect_build_changes(repo, base, limit=20))


class PlanFilesTest(unittest.TestCase):
    def test_next_plan_file_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for name in ("PLAN_v1.md", "PLAN_v2.md", "PLAN_v3_manual.md"):
                (d / name).write_text("x", encoding="utf-8")
            self.assertEqual(loop.next_plan_file(d).name, "PLAN_v4.md")

    def test_plan_diff_is_smaller_than_plan(self):
        old = "\n".join(f"Zeile {i}" for i in range(200))
        new = old.replace("Zeile 100", "Zeile 100 geändert")
        self.assertLess(len(loop.plan_diff(old, new)), len(new))


class ContextTest(unittest.TestCase):
    def test_loads_claude_and_agents_md_and_filters_knowledge(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "CLAUDE.md").write_text("Regel A", encoding="utf-8")
            (p / "AGENTS.md").write_text("Regel B", encoding="utf-8")
            (p / "knowledge").mkdir()
            (p / "knowledge" / "datenbank.md").write_text("Migrationen immer rückwärtskompatibel", encoding="utf-8")
            (p / "knowledge" / "design.md").write_text("Farben und Schriften", encoding="utf-8")
            ctx = loop.load_project_context(p, "Datenbank Migration ergänzen")
            self.assertIn("Regel A", ctx)
            self.assertIn("Regel B", ctx)
            self.assertIn("rückwärtskompatibel", ctx)
            self.assertNotIn("Farben", ctx)
            self.assertIn("design.md", ctx)

    def test_identical_rule_files_load_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "CLAUDE.md").write_text("Gleiche Regel", encoding="utf-8")
            (p / "AGENTS.md").write_text("Gleiche Regel", encoding="utf-8")
            self.assertEqual(loop.load_project_context(p).count("Gleiche Regel"), 1)


class McpDefaultsTest(unittest.TestCase):
    def test_run_tool_does_not_default_to_yolo(self):
        run_tool = next(t for t in mcp_server.MCP_TOOLS if t["name"] == "claudegravity_run")
        self.assertFalse(run_tool["inputSchema"]["properties"]["yolo"]["default"])

    def test_proof_reaches_loop_args(self):
        from unittest import mock

        with mock.patch.object(mcp_server, "detect_installed_agents", return_value={}):
            opt = mcp_server.optimize_claudegravity_command("Neue Seite bauen", proof="python -m unittest")
        self.assertEqual(opt["loop_args"][-2:], ["--proof", "python -m unittest"])


FAKE_CLAUDE = r"""
import json, os, pathlib, re, sys
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"bin": "claude", "argv": sys.argv[1:], "prompt": prompt}) + "\n")
if "Führe den genehmigten Plan" in prompt or "Weiter in deiner Bau-Sitzung" in prompt:
    pathlib.Path("hallo.txt").write_text("hallo\n", encoding="utf-8")
    done = pathlib.Path(re.search(r"unter:? '([^']+)'", prompt).group(1))
    done.write_text("fertig\n", encoding="utf-8")
    out = "gebaut"
else:
    out = "# Plan\n- hallo.txt anlegen\n"
print(json.dumps({"result": out, "session_id": "s1", "usage": {"input_tokens": 9, "output_tokens": 4},
                  "modelUsage": {"fake-opus": {}}}))
"""

FAKE_GEMINI = r"""
import json, os, pathlib, sys
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"bin": "gemini", "argv": sys.argv[1:], "prompt": prompt}) + "\n")
if "unabhängige Abnahme" in prompt:
    counter = pathlib.Path(os.environ["FAKE_LOG"] + ".abnahme")
    n = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(n + 1))
    if n == 0:
        print("BEFUNDE:\n- [HOCH] hallo.txt: Test fehlt -> Test ergänzen\nVERDICT: REVISE")
        sys.exit(0)
print("BEFUNDE:\n- keine\nVERDICT: APPROVED")
"""


@unittest.skipIf(sys.platform == "win32", "Fake-CLIs als Shebang-Skripte nur unter Unix")
class EndToEndTest(unittest.TestCase):
    """Ganzer Ablauf mit Fake-CLIs: Plan, Review, Bau, abgelehnte und erteilte Abnahme."""

    def test_builder_cannot_finish_without_independent_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bindir, project = tmp / "bin", tmp / "proj"
            bindir.mkdir()
            project.mkdir()
            for name, body in (("claude", FAKE_CLAUDE), ("gemini", FAKE_GEMINI)):
                script = bindir / name
                script.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body), encoding="utf-8")
                script.chmod(0o755)
            log = tmp / "calls.jsonl"
            env = {
                k: v for k, v in os.environ.items() if not k.startswith("CLAUDEGRAVITY_") and k not in ("OPENAI_BASE_URL", "AI_ENDPOINT")
            }
            env["CLAUDEGRAVITY_CONFIG_DIR"] = os.devnull  # kein globales Profil des Nutzers
            env.update(PATH=str(bindir), FAKE_LOG=str(log))
            proof = f'"{sys.executable}" -c "import pathlib,sys; sys.exit(0 if pathlib.Path(\'hallo.txt\').exists() else 1)"'
            task = "Lege hallo.txt an"
            res = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "loop.py"),
                    task,
                    "-p",
                    str(project),
                    "--planner",
                    "claude",
                    "--reviewer",
                    "gemini",
                    "--yolo",
                    "--proof",
                    proof,
                    "-d",
                    "0",
                    "-m",
                    "5",
                ],
                input="1\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
                env=env,
            )
            self.assertEqual(res.returncode, 0, res.stdout[-3000:] + res.stderr[-3000:])
            calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            session = next((project / ".dual-loop" / "sessions").iterdir())

            self.assertTrue((session / ".done").exists())
            self.assertTrue((session / "INSPECTION_round1.md").exists())
            self.assertTrue((session / "INSPECTION_round2.md").exists())
            state = json.loads((session / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["phase"], "completed")
            self.assertTrue(state["approved_plan_sha256"])

            done = (session / ".done").read_text(encoding="utf-8")
            self.assertIn("Kennzahlen (ClaudeGravity KPI v1)", done)
            kpi = json.loads(done.split("```json\n", 1)[1].split("\n```", 1)[0])
            self.assertTrue(kpi["success"])
            self.assertEqual((kpi["build_rounds"], kpi["inspection_rounds"], kpi["inspection_rejected"]), (2, 2, 1))
            self.assertEqual((kpi["rework_rounds"], kpi["rework_rate"]), (1, 0.5))

            builds = [
                c
                for c in calls
                if c["bin"] == "claude" and ("Führe den genehmigten Plan" in c["prompt"] or "Weiter in deiner" in c["prompt"])
            ]
            self.assertEqual(len(builds), 2)
            self.assertIn("Test fehlt", builds[1]["prompt"])
            self.assertIn("--dangerously-skip-permissions", builds[0]["argv"])
            # Runde 2 setzt die Bauleiter-Sitzung fort und schickt weder Aufgabe noch Plan erneut
            self.assertNotIn("--resume", builds[0]["argv"])
            self.assertEqual(builds[1]["argv"][builds[1]["argv"].index("--resume") + 1], "s1")
            self.assertIn("--dangerously-skip-permissions", builds[1]["argv"])
            self.assertNotIn(task, builds[1]["prompt"])
            self.assertEqual(kpi.get("builder_resumed", state["metrics"]["counters"].get("builder_resumed")), 1)

            plan_calls = [c for c in calls if c["bin"] == "claude" and c not in builds]
            self.assertTrue(plan_calls)
            for c in plan_calls:
                self.assertNotIn("--dangerously-skip-permissions", c["argv"])
                self.assertIn("dontAsk", c["argv"])
            for c in calls:
                self.assertNotIn(task, " ".join(c["argv"]), "Prompt darf nicht in der Kommandozeile stehen")
            log_md = (session / "LOG.md").read_text(encoding="utf-8")
            self.assertIn("angefordert `CLI-Default`, gemeldet `fake-opus`", log_md)


FAKE_PLANNER_GEMINI = r"""
import json, os, pathlib, re, sys
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"bin": "gemini", "argv": sys.argv[1:], "prompt": prompt}) + "\n")
body = "\n".join(f"Schritt {i}: Detail {i}" for i in range(60))
if "Führe den genehmigten Plan" in prompt:
    pathlib.Path(re.search(r"unter: '([^']+)'", prompt).group(1)).write_text("fertig\n", encoding="utf-8")
    print("gebaut")
elif "Befunde zum Plan" in prompt:
    print("# Plan\n" + body + "\nSchritt 61: Test ergänzt\n## Stellungnahme zu den Befunden\n- übernommen")
else:
    print("# Plan\n" + body)
"""

FAKE_REVIEWER_CLAUDE = r"""
import json, os, sys
prompt = sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"bin": "claude", "argv": sys.argv[1:], "prompt": prompt}) + "\n")
if os.environ.get("FAKE_RESUME_FAIL") and "--resume" in sys.argv:
    print("No conversation found with session ID", file=sys.stderr)
    sys.exit(1)
if ("Änderungen gegenüber der von dir geprüften Fassung" in prompt or "unabhängige Abnahme" in prompt
        or "Schritt 61" in prompt):
    out = "BEFUNDE:\n- keine\nVERDICT: APPROVED"
else:
    out = "BEFUNDE:\n- [MITTEL] Plan: Test fehlt -> ergänzen\nVERDICT: REVISE"
print(json.dumps({"result": out, "session_id": "rev-1", "usage": {}}))
"""


@unittest.skipIf(sys.platform == "win32", "Fake-CLIs als Shebang-Skripte nur unter Unix")
class ReviewResumeTest(unittest.TestCase):
    def run_loop(self, **extra_env):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        bindir, project = tmp / "bin", tmp / "proj"
        bindir.mkdir()
        project.mkdir()
        for name, body in (("claude", FAKE_REVIEWER_CLAUDE), ("gemini", FAKE_PLANNER_GEMINI)):
            script = bindir / name
            script.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body), encoding="utf-8")
            script.chmod(0o755)
        log = tmp / "calls.jsonl"
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDEGRAVITY_") and k not in ("OPENAI_BASE_URL", "AI_ENDPOINT")}
        env["CLAUDEGRAVITY_CONFIG_DIR"] = os.devnull  # kein globales Profil des Nutzers
        env.update(PATH=str(bindir), FAKE_LOG=str(log), **extra_env)
        res = subprocess.run(
            [
                sys.executable,
                str(ROOT / "loop.py"),
                "Plane etwas",
                "-p",
                str(project),
                "--planner",
                "gemini",
                "--reviewer",
                "claude",
                "--yolo",
                "-d",
                "0",
                "-m",
                "2",
            ],
            input="1\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            env=env,
        )
        self.assertEqual(res.returncode, 0, res.stdout[-3000:] + res.stderr[-3000:])
        calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        return calls, project

    def test_second_round_resumes_reviewer_with_diff_only(self):
        calls, project = self.run_loop()
        reviews = [c for c in calls if c["bin"] == "claude"]
        self.assertNotIn("--resume", reviews[0]["argv"])
        self.assertEqual(reviews[1]["argv"][reviews[1]["argv"].index("--resume") + 1], "rev-1")
        self.assertIn("+Schritt 61: Test ergänzt", reviews[1]["prompt"])
        self.assertNotIn("Schritt 30: Detail 30", reviews[1]["prompt"])
        fix_prompt = next(c["prompt"] for c in calls if c["bin"] == "gemini" and "Befunde zum Plan" in c["prompt"])
        self.assertIn("- [MITTEL] Plan: Test fehlt -> ergänzen", fix_prompt)
        self.assertNotIn("--resume", reviews[-1]["argv"], "Die Abnahme startet immer frisch")
        self.assertTrue(any((project / ".dual-loop" / "sessions").glob("*/PLAN_v2.md")))

    def test_failed_resume_falls_back_to_full_plan(self):
        calls, _ = self.run_loop(FAKE_RESUME_FAIL="1")
        reviews = [c for c in calls if c["bin"] == "claude"]
        self.assertIn("--resume", reviews[1]["argv"])
        self.assertNotIn("--resume", reviews[2]["argv"])
        self.assertIn("Schritt 30: Detail 30", reviews[2]["prompt"])


if __name__ == "__main__":
    unittest.main()
