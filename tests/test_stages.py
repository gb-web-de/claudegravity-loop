"""Tests für Etappen-Modus, Strategie hybrid und automatische Ollama-Modellwahl (nur Standardbibliothek)."""

import argparse
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402
import mcp_server  # noqa: E402

GB = 1024 ** 3
MODELS = [
    {"name": "qwen3-coder:30b", "size": 19 * GB},
    {"name": "gpt-oss:20b", "size": 14 * GB},
    {"name": "qwen3:30b", "size": 19 * GB},
    {"name": "llama3.3:70b", "size": 43 * GB},
    {"name": "nomic-embed-text:latest", "size": GB // 3},
]


def make_args(**overrides) -> argparse.Namespace:
    base = dict(
        resume=False, strategy="balanced", planner=None, reviewer=None, builder=None, inspector=None,
        planner_model=None, reviewer_model=None, builder_model=None, inspector_model=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def fake_agents(*keys: str) -> dict:
    return {k: loop.AgentCLI(k, "ollama" if k == "ollama-cli" else k, None) for k in keys}


class ParseStagesTest(unittest.TestCase):
    def test_reads_numbered_list_under_heading(self):
        plan = (
            "# Plan\nText\n\n## Etappen\n1. Parser in `src/a.py`\n2. Tests in tests/test_a.py\n"
            "   mit Randfall\n\n## Risiken\n1. keine\n"
        )
        self.assertEqual(loop.parse_stages(plan), ["Parser in `src/a.py`", "Tests in tests/test_a.py mit Randfall"])

    def test_accepts_numbered_heading_and_english(self):
        self.assertEqual(loop.parse_stages("### 5. Stages\n1) one\n2) two"), ["one", "two"])

    def test_last_section_wins_and_missing_section_is_empty(self):
        self.assertEqual(loop.parse_stages("## Etappen\n1. alt\n## Etappen\n1. neu\n2. zwei"), ["neu", "zwei"])
        self.assertEqual(loop.parse_stages("# Plan\n1. Schritt ohne Abschnitt"), [])

    def test_stages_wanted(self):
        self.assertTrue(loop.stages_wanted("auto", "ollama"))
        self.assertFalse(loop.stages_wanted("auto", "codex"))
        self.assertTrue(loop.stages_wanted("an", "codex"))
        self.assertFalse(loop.stages_wanted("aus", "ollama"))

    def test_planning_directive_mentions_stages_only_when_on(self):
        with mock.patch.object(loop, "STAGE_PLANNING", False):
            self.assertNotIn("## Etappen", loop.planning_directive())
        with mock.patch.object(loop, "STAGE_PLANNING", True):
            self.assertIn("## Etappen", loop.planning_directive())


class StageFileContextTest(unittest.TestCase):
    def test_includes_existing_files_and_skips_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "src").mkdir()
            (work / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
            (work / ".env").write_text("TOKEN=geheim\n", encoding="utf-8")
            ctx = loop.stage_file_context(work, "Ändere src/a.py und .env und fehlt.py", extra=["src/a.py"])
        self.assertIn("```filepath: src/a.py\nx = 1", ctx)
        self.assertEqual(ctx.count("src/a.py"), 1)
        self.assertNotIn("geheim", ctx)
        self.assertNotIn("fehlt.py", ctx)

    def test_respects_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "a.txt").write_text("a" * 500, encoding="utf-8")
            (work / "b.txt").write_text("b" * 500, encoding="utf-8")
            ctx = loop.stage_file_context(work, "a.txt b.txt", limit=600)
        self.assertIn("a.txt", ctx)
        self.assertNotIn("b" * 500, ctx)


class OllamaModelPickTest(unittest.TestCase):
    def test_prefers_role_families_and_skips_embeddings_and_huge_models(self):
        self.assertEqual(loop.pick_ollama_model(MODELS, "builder"), "qwen3-coder:30b")
        self.assertEqual(loop.pick_ollama_model(MODELS, "reviewer"), "gpt-oss:20b")
        self.assertEqual(loop.pick_ollama_model(MODELS, "planner"), "qwen3:30b")
        self.assertEqual(loop.pick_ollama_model(MODELS, "reviewer", {"gpt-oss:20b"}), "qwen3:30b")
        only_big = [{"name": "llama3.3:70b", "size": 43 * GB}, {"name": "nomic-embed-text", "size": 1}]
        self.assertEqual(loop.pick_ollama_model(only_big, "builder"), "llama3.3:70b")
        self.assertIsNone(loop.pick_ollama_model([], "builder"))

    def test_lists_models_from_api_tags(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps({"models": [{"name": "qwen3-coder:30b", "size": 5}]}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            models = loop.list_ollama_models(f"http://127.0.0.1:{server.server_port}")
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(models, [{"name": "qwen3-coder:30b", "size": 5}])
        self.assertEqual(loop.list_ollama_models("http://127.0.0.1:9", timeout=0.2), [])


class AutoRolesTest(unittest.TestCase):
    def test_hybrid_fills_roles_and_models(self):
        args = make_args(strategy="hybrid")
        notes = loop.apply_auto_roles(args, fake_agents("codex", "ollama-cli", "ollama"), models=MODELS)
        self.assertEqual((args.planner, args.reviewer, args.builder, args.inspector), ("codex", "ollama", "ollama", "codex"))
        self.assertEqual(args.builder_model, "qwen3-coder:30b")
        self.assertEqual(args.reviewer_model, "gpt-oss:20b")
        self.assertIsNone(args.planner_model)
        self.assertTrue(any("hybrid" in n for n in notes))

    def test_explicit_choices_win(self):
        args = make_args(strategy="hybrid", planner="claude", builder_model="qwen2.5-coder:14b")
        loop.apply_auto_roles(args, fake_agents("codex", "claude", "ollama"), models=MODELS)
        self.assertEqual(args.planner, "claude")
        self.assertEqual(args.builder_model, "qwen2.5-coder:14b")

    def test_variant_b_planner_and_reviewer_differ(self):
        args = make_args(planner="ollama", reviewer="ollama", builder="ollama")
        loop.apply_auto_roles(args, fake_agents("ollama"), models=MODELS)
        self.assertEqual(args.builder_model, "qwen3-coder:30b")
        self.assertNotEqual(args.planner_model, args.reviewer_model)

    def test_hybrid_without_local_model_only_warns(self):
        args = make_args(strategy="hybrid")
        notes = loop.apply_auto_roles(args, fake_agents("codex"), models=[])
        self.assertIsNone(args.builder)
        self.assertTrue(any("lokales Modell" in n for n in notes))

    def test_resume_keeps_state(self):
        args = make_args(strategy="hybrid", resume=True)
        self.assertEqual(loop.apply_auto_roles(args, fake_agents("codex", "ollama"), models=MODELS), [])
        self.assertIsNone(args.planner)


class DryRunCommandTest(unittest.TestCase):
    def test_contains_every_role_flag(self):
        args = argparse.Namespace(
            endpoint=None, architekt_endpoint=None, pruefstatiker_endpoint=None, bauer_endpoint=None,
            planner="codex", planner_model=None, planner_effort="high",
            reviewer="ollama", reviewer_model="gpt-oss:20b", reviewer_effort=None,
            builder="ollama", builder_model="qwen3-coder:30b", builder_effort=None,
            inspector="codex", inspector_model=None, inspector_effort=None, effort=None,
            proof="python -m unittest", etappen="an", swap=False, ask=False, yolo=False, approve_plan=True,
            auto_switch=False, merge=True, inspect=True, max_iterations=None, project=".",
            escalate="auto", escalate_after=3,
        )
        cmd = loop.dry_run_command(args, "CSV-Export", "hybrid")
        joined = " ".join(cmd)
        for part in ["--strategy hybrid", "--architekt codex", "--architekt-effort high", "--pruefstatiker ollama",
                     "--pruefstatiker-model gpt-oss:20b", "--bauer ollama", "--bauer-model qwen3-coder:30b",
                     "--abnahme codex", "--etappen an", "--plan-auto", "--merge", "--escalate auto", "--escalate-after 3"]:
            self.assertIn(part, joined)
        self.assertEqual(cmd[1], "CSV-Export")


class McpRolesTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            mcp_server, "detect_installed_agents",
            return_value={"codex": "Codex CLI", "ollama-cli": "Ollama CLI", "ollama": "Ollama"},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_hybrid_priority(self):
        opt = mcp_server.optimize_claudegravity_command("CSV", priority="hybrid", proof="python -m unittest")
        self.assertIn("--strategy", opt["loop_args"])
        self.assertIn("hybrid", opt["loop_args"])
        self.assertEqual(opt["roles"]["architekt"]["cli"], "codex")
        self.assertEqual(opt["roles"]["bauleiter"]["cli"], "ollama")
        self.assertEqual(opt["roles"]["abnahme"]["cli"], "codex")

    def test_roles_are_passed_through(self):
        opt = mcp_server.optimize_claudegravity_command(
            "CSV", roles={"architekt": "ollama", "pruefstatiker": "codex", "bauer": "ollama", "bauer_model": "qwen3-coder:30b"},
            stages="an", approve_plan=True,
        )
        args = opt["loop_args"]
        for flag, value in [("--architekt", "ollama"), ("--pruefstatiker", "codex"), ("--bauer", "ollama"),
                            ("--bauer-model", "qwen3-coder:30b"), ("--etappen", "an")]:
            self.assertEqual(args[args.index(flag) + 1], value)
        self.assertIn("--plan-auto", args)

    def test_no_foreign_model_names_for_codex(self):
        opt = mcp_server.optimize_claudegravity_command("CSV", priority="lowest-cost")
        self.assertNotIn("gemini", " ".join(opt["loop_args"]))
        self.assertEqual(opt["roles"]["architekt"]["model"], "CLI-Default")

    def test_background_has_no_stdin_and_approves_plan(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mcp_server.subprocess, "Popen") as popen:
            popen.return_value.pid = 1
            mcp_server.handle_tool_call("claudegravity_run", {"task": "CSV", "project_path": tmp, "background": True})
        self.assertIs(popen.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertIn("--plan-auto", popen.call_args.args[0])

    def test_schema_lists_role_parameters(self):
        props = {t["name"]: t["inputSchema"]["properties"] for t in mcp_server.MCP_TOOLS}
        for name in ("claudegravity_optimize", "claudegravity_run"):
            for key in ("architekt", "bauer_model", "abnahme", "stages", "approve_plan"):
                self.assertIn(key, props[name])
            self.assertIn("hybrid", props[name]["priority"]["enum"])


class BuildPromptTest(unittest.TestCase):
    def test_stage_prompt_names_only_the_current_stage(self):
        prompt = loop.compose_build_prompt(
            "CSV-Export", Path("PLAN_v1.md"), "make test", "Test x rot", endpoint=True,
            plan_text="# Plan", file_ctx="```filepath: a.py\n```", stage=("Etappe 2/3", "Export", "- [x] Parser"),
        )
        for part in ("JETZT NUR ETAPPE 2/3: Export", "- [x] Parser", "`make test`", "Test x rot",
                     "--- GENEHMIGTER PLAN ---", "BETROFFENEN DATEIEN", "FORMAT FÜR DATEI-ÄNDERUNGEN"):
            self.assertIn(part, prompt)
        self.assertIn("KEINE Fertigmeldung", prompt)

    def test_full_plan_prompt_asks_for_done_marker(self):
        prompt = loop.compose_build_prompt("CSV-Export", Path("PLAN_v1.md"), None, "", endpoint=False,
                                           rel_done_path=Path("sess/.done"))
        self.assertTrue(prompt.startswith("Führe den genehmigten Plan (PLAN_v1.md)"))
        self.assertIn("'sess/.done'", prompt)
        self.assertNotIn("GENEHMIGTER PLAN ---", prompt)
        self.assertNotIn("Prüfbefehl", prompt)

    def test_endpoint_full_plan_prompt_carries_plan_and_done_block(self):
        prompt = loop.compose_build_prompt("CSV-Export", Path("PLAN_v1.md"), "make test", "", endpoint=True,
                                           plan_text="# Plan", rel_done_path=Path("sess/.done"))
        self.assertIn("--- GENEHMIGTER PLAN ---\n# Plan", prompt)
        self.assertTrue(prompt.endswith("```filepath: sess/.done\n# Aufgabe abgeschlossen\n```"))


class StageLoopEndToEndTest(unittest.TestCase):
    """Ganzer Lauf mit drei lokalen Fake-Endpunkten: Plan mit Etappen, Bau Etappe für Etappe, Abnahme."""

    def test_builds_stage_by_stage(self):
        prompts: list[str] = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                prompt = req["messages"][-1]["content"]
                prompts.append(prompt)
                if "leitende Software-Architekt" in prompt:
                    out = "# Plan\n\n## Etappen\n1. Funktion in src/calc.py\n2. Test in tests/test_calc.py\n"
                elif "ETAPPE 1/2" in prompt:
                    out = "```filepath: src/calc.py\ndef add(a, b):\n    return a + b\n```"
                elif "ETAPPE 2/2" in prompt:
                    out = (
                        "```filepath: tests/test_calc.py\nimport sys, unittest\nsys.path.insert(0, 'src')\n"
                        "from calc import add\n\nclass T(unittest.TestCase):\n    def test_add(self):\n"
                        "        self.assertEqual(add(1, 2), 3)\n```"
                    )
                else:
                    out = "BEFUNDE:\n- keine\nVERDICT: APPROVED"
                body = json.dumps({"choices": [{"message": {"content": out}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_port}/v1"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp)
                (project / "tests").mkdir()
                (project / "tests" / "test_smoke.py").write_text(
                    "import unittest\n\nclass S(unittest.TestCase):\n    def test_ok(self):\n        pass\n", encoding="utf-8"
                )
                env = {k: v for k, v in os.environ.items()
                       if not k.startswith("CLAUDEGRAVITY_") and k not in ("OPENAI_BASE_URL", "AI_ENDPOINT", "OLLAMA_HOST")}
                env["CLAUDEGRAVITY_CONFIG_DIR"] = os.devnull  # kein globales Profil des Nutzers
                env["PATH"] = tmp
                env["OLLAMA_HOST"] = "127.0.0.1:9"
                env["PYTHONIOENCODING"] = "utf-8"
                res = subprocess.run(
                    [sys.executable, str(ROOT / "loop.py"), "Addition mit Test", "-p", tmp, "--no-worktree", "-d", "0",
                     "--architekt-endpoint", url, "--architekt", "architekt_ep",
                     "--pruefstatiker-endpoint", url, "--pruefstatiker", "pruefstatiker_ep", "--pruefstatiker-model", "pruefer",
                     "--bauer-endpoint", url, "--bauer", "bauer_ep", "--bauer-model", "bauer",
                     "--abnahme", "pruefstatiker_ep", "--plan-auto",
                     "--proof", f"{sys.executable} -m unittest discover -s tests"],
                    input="", capture_output=True, text=True, encoding="utf-8", timeout=120, env=env,
                )
                out = res.stdout
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertIn("Etappe 1/2 erledigt", out)
                self.assertIn("Etappe 2/2 erledigt", out)
                self.assertIn("Abnahme erteilt", out)
                self.assertTrue((project / "src" / "calc.py").exists())
                self.assertTrue(list((project / ".dual-loop" / "sessions").glob("*/.done")))
        finally:
            server.shutdown()
            server.server_close()
        plan_prompt = next(p for p in prompts if "leitende Software-Architekt" in p)
        self.assertIn("## Etappen", plan_prompt)
        stage2 = next(p for p in prompts if "ETAPPE 2/2" in p)
        self.assertIn("```filepath: src/calc.py", stage2)


if __name__ == "__main__":
    unittest.main()
