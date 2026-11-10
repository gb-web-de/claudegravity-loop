"""Freigabe-Menü des Plans, Rückfragen und Fortsetzen: Änderungswunsch in Worten, erneutes Review, Abbruch, --session."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "smoke"))

import loop  # noqa: E402,F401
import run_smoke  # noqa: E402
from claudegravity import common, planning, session  # noqa: E402


def run_loop(
    stdin: str, extra: list[str] | None = None, project: Path | None = None, tmp: Path | None = None, url: str = ""
) -> subprocess.CompletedProcess:
    """Lauf mit dem Fake-Endpunkt aus dem Smoke-Test, mit Freigabe-Menü und vorgegebenen Eingaben."""
    command = run_smoke.smoke_command(project, url, "balanced", extra)
    command.remove("--plan-auto")
    return subprocess.run(
        command,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        env=run_smoke.smoke_env(tmp),
    )


class HelperTest(unittest.TestCase):
    def test_plans_are_ordered_by_version_not_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ("PLAN_v1.md", "PLAN_v2.md", "PLAN_v10.md", "PLAN_v9_manual.md"):
                (folder / name).write_text("x", encoding="utf-8")
            self.assertEqual([p.name for p in session.plan_files(folder)], ["PLAN_v1.md", "PLAN_v2.md", "PLAN_v9_manual.md", "PLAN_v10.md"])
            self.assertEqual(session.next_plan_file(folder).name, "PLAN_v11.md")
        self.assertEqual(session.plan_version(Path("PLAN_v4_manual.md")), 4)
        self.assertEqual(session.plan_version(Path("NOTIZ.md")), 0)

    def test_empty_plans_are_not_usable(self):
        self.assertFalse(session.is_usable_plan("  \n"))
        self.assertTrue(session.is_usable_plan("# Plan\n1. Schritt"))
        agent = mock.Mock()
        agent.name = "Claude"
        with mock.patch.object(common.SETTINGS, "stop_requested", True):
            self.assertFalse(planning.plan_delivered("", agent))
        with mock.patch.object(common.SETTINGS, "stop_requested", False):
            self.assertTrue(planning.plan_delivered("# Plan", agent))
            with self.assertRaises(RuntimeError):
                planning.plan_delivered(" ", agent)

    def test_find_session_takes_only_folder_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            loop_dir = Path(tmp) / ".dual-loop"
            for name in ("20260101_000000_alt", "20260102_000000_neu"):
                (loop_dir / "sessions" / name).mkdir(parents=True)
            self.assertEqual(session.find_session(loop_dir, None).name, "20260102_000000_neu")
            self.assertEqual(session.find_session(loop_dir, "20260101_000000_alt").name, "20260101_000000_alt")
            for bad in ("fehlt", "..", "../sessions/20260101_000000_alt", str(loop_dir / "sessions" / "20260101_000000_alt")):
                self.assertIsNone(session.find_session(loop_dir, bad), bad)

    def test_two_runs_in_the_same_second_get_their_own_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            sessions = Path(tmp) / ".dual-loop" / "sessions"
            names = [session.create_session_dir(sessions, "20260101_000000_x").name for _ in range(3)]
        self.assertEqual(names, ["20260101_000000_x", "20260101_000000_x_2", "20260101_000000_x_3"])

    def test_typed_sentences_count_as_feedback(self):
        for text in ("Bitte ohne Datenbank", "mit Tests", "kürzerbitte"):
            self.assertTrue(planning.is_feedback_text(text), text)
        for text in ("1", "x", "nein", ""):
            self.assertFalse(planning.is_feedback_text(text), text)

    def test_editor_comes_from_the_environment_or_the_system(self):
        path = Path("PLAN_v1.md")
        with mock.patch.dict(os.environ, {"EDITOR": "code --wait"}, clear=False):
            os.environ.pop("VISUAL", None)
            self.assertEqual(planning.editor_command(path), ["code", "--wait", "PLAN_v1.md"])
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(planning.sys, "platform", "darwin"):
                self.assertEqual(planning.editor_command(path), ["open", "-t", "PLAN_v1.md"])
            with mock.patch.object(planning.sys, "platform", "linux"), mock.patch.object(planning.os, "name", "posix"):
                with mock.patch.object(planning.shutil, "which", return_value=None):
                    self.assertIsNone(planning.editor_command(path))
                with mock.patch.object(planning.shutil, "which", return_value="/usr/bin/xdg-open"):
                    self.assertEqual(planning.editor_command(path), ["xdg-open", "PLAN_v1.md"])

    def test_missing_editor_is_a_hint_not_a_crash(self):
        out = io.StringIO()
        with mock.patch.object(planning, "editor_command", return_value=["gibt-es-nicht-xyz", "PLAN_v1.md"]), redirect_stdout(out):
            self.assertFalse(planning.open_in_editor(Path("PLAN_v1.md")))
        self.assertIn("PLAN_v1.md", out.getvalue())


class AskTest(unittest.TestCase):
    def test_hooks_get_choices_and_the_answer(self):
        seen = []
        hook = lambda prompt, waiting, question=None: seen.append((waiting, question))  # noqa: E731
        common.WAIT_HOOKS.append(hook)
        try:
            with mock.patch("builtins.input", return_value="n"):
                self.assertEqual(common.ask("Erlauben? [J/n] ", kind="permission"), "n")
            with mock.patch("builtins.input", side_effect=EOFError), self.assertRaises(EOFError):
                common.ask("Auswahl: ", choices=[("1", "Abbrechen")], kind="plan", free_text=True)
        finally:
            common.WAIT_HOOKS.remove(hook)
        opened, closed, opened2, closed2 = seen
        self.assertEqual(
            opened,
            (
                True,
                {
                    "kind": "permission",
                    "choices": [{"value": "j", "label": "Ja"}, {"value": "n", "label": "Nein"}],
                    "detail": "",
                    "text": False,
                },
            ),
        )
        self.assertEqual(closed, (False, {"kind": "permission", "answer": "n"}))
        self.assertTrue(opened2[1]["text"])
        self.assertEqual(closed2, (False, {"kind": "plan", "answer": None}))

    def test_ctrl_c_leaves_an_open_question_at_once(self):
        def interrupted(_prompt):
            common.sigint_handler(None, None)
            return "nie erreicht"

        out = io.StringIO()
        try:
            with mock.patch("builtins.input", side_effect=interrupted), redirect_stdout(out), self.assertRaises(KeyboardInterrupt):
                common.ask("Auswahl: ")
            self.assertFalse(common._ASKING)
            with redirect_stdout(out):
                common.sigint_handler(None, None)  # außerhalb einer Rückfrage nur vormerken
            self.assertTrue(common.SETTINGS.stop_requested)
        finally:
            common.SETTINGS.stop_requested = False


class PlanMenuRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_dir.name)
        self.project = self.tmp / "projekt"
        self.project.mkdir()
        (self.tmp / "leer").mkdir()
        self.server, self.url = run_smoke.start_server()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp_dir.cleanup()

    def sessions(self) -> list[Path]:
        return sorted(p for p in (self.project / ".dual-loop" / "sessions").iterdir() if p.is_dir())

    def events(self, folder: Path) -> list[dict]:
        return [json.loads(line) for line in (folder / "timeline.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_typed_feedback_is_planned_and_reviewed_again(self):
        res = run_loop("Bitte auch eine Subtraktion einplanen\n1\n", project=self.project, tmp=self.tmp, url=self.url)
        self.assertEqual(res.returncode, 0, res.stdout[-3000:] + res.stderr[-2000:])
        folder = self.sessions()[-1]
        self.assertTrue((folder / "PLAN_v2.md").exists())
        self.assertTrue((folder / "REVIEW_round2.md").exists(), "geänderter Plan muss neu geprüft werden")
        state = json.loads((folder / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["approved_plan_file"], "PLAN_v2.md")
        self.assertEqual(state["phase"], "completed")
        self.assertEqual((state["planner_binary"], state["builder_binary"]), ("architekt_ep", "bauer_ep"))
        self.assertNotIn("Schreibrechte ()", res.stdout)
        timeline = [json.loads(line)["type"] for line in (folder / "timeline.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(timeline.count("plan"), 2)
        self.assertEqual(timeline.count("review"), 2)
        self.assertEqual(timeline[-1], "session_end")

    def test_quitting_at_the_menu_ends_cleanly_and_a_named_session_resumes(self):
        first = run_loop("5\n", project=self.project, tmp=self.tmp, url=self.url)
        self.assertEqual(first.returncode, 0, first.stdout[-3000:] + first.stderr[-2000:])
        self.assertIn("claudegravity -c", first.stdout)
        old = self.sessions()[-1]
        end = [e for e in self.events(old) if e.get("type") == "session_end"]
        self.assertEqual(len(end), 1)
        self.assertFalse(end[0].get("success"))
        self.assertFalse(list(old.glob("PLAN_v2*")))

        # Eine zweite Sitzung; danach die erste gezielt fortsetzen, ohne die Endpunkte noch einmal anzugeben
        second = run_loop("5\n", project=self.project, tmp=self.tmp, url=self.url)
        self.assertEqual(second.returncode, 0, second.stdout[-2000:])
        self.assertEqual(len(self.sessions()), 2)
        command = [sys.executable, str(ROOT / "loop.py"), "-p", str(self.project), "--session", old.name, "--no-guide"]
        resumed = subprocess.run(
            command,
            input="j\n1\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            env=run_smoke.smoke_env(self.tmp),
        )
        self.assertEqual(resumed.returncode, 0, resumed.stdout[-3000:] + resumed.stderr[-2000:])
        self.assertEqual(json.loads((old / "state.json").read_text(encoding="utf-8"))["phase"], "completed")
        self.assertEqual(len(self.sessions()), 2)
        missing = subprocess.run(
            command[:-3] + ["--session", "gibt_es_nicht", "--no-guide"],
            input="",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env=run_smoke.smoke_env(self.tmp),
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertEqual(len(self.sessions()), 2)


if __name__ == "__main__":
    unittest.main()
