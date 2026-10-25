"""Git-Workspace pro Session: Freigeben und Neuanlegen auch nach halb gescheitertem Aufräumen."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402

HAS_GIT = shutil.which("git") is not None


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, env=env, check=True)


@unittest.skipUnless(HAS_GIT, "git fehlt")
class WorktreeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = self.tmp / "projekt"
        self.project.mkdir()
        git(self.project, "init", "-q")
        (self.project / ".gitignore").write_text(".dual-loop/\ncache/\n")
        (self.project / "a.txt").write_text("a\n")
        git(self.project, "add", "-A")
        git(self.project, "commit", "-qm", "start")
        self.session = self.project / ".dual-loop" / "sessions" / "s1"
        self.session.mkdir(parents=True)
        self.state: dict = {}
        p = mock.patch.dict(
            os.environ, {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        )
        p.start()
        self.addCleanup(p.stop)

    def branch_files(self, branch: str) -> str:
        return git(self.project, "ls-tree", "-r", "--name-only", branch).stdout

    def test_release_commits_and_removes_even_with_ignored_files(self):
        wt = loop.acquire_worktree(self.project, self.session, self.state)
        (wt / "b.txt").write_text("b\n")
        (wt / "cache").mkdir()
        (wt / "cache" / "x.pyc").write_text("x")
        self.assertTrue(loop.release_worktree(self.project, self.session, self.state, "Aufgabe"))
        self.assertFalse(wt.exists())
        self.assertIn("b.txt", self.branch_files("loop/s1"))
        self.assertTrue(self.state["worktree"]["released"])

    def test_release_after_git_admin_data_vanished(self):
        # Zustand aus dem Fehlerbild: Verwaltungsdaten unter .git/worktrees/ weg, Ordner noch da
        wt = loop.acquire_worktree(self.project, self.session, self.state)
        (wt / "b.txt").write_text("b\n")
        git(wt, "add", "-A")
        git(wt, "commit", "-qm", "bau")
        shutil.rmtree(self.project / ".git" / "worktrees" / wt.name)
        self.assertFalse(loop.worktree_is_valid(wt))
        self.assertTrue(loop.release_worktree(self.project, self.session, self.state, "Aufgabe"))
        self.assertFalse(wt.exists())
        self.assertIn("b.txt", self.branch_files("loop/s1"))

    def test_acquire_recreates_broken_worktree(self):
        wt = loop.acquire_worktree(self.project, self.session, self.state)
        shutil.rmtree(self.project / ".git" / "worktrees" / wt.name)
        again = loop.acquire_worktree(self.project, self.session, self.state)
        self.assertEqual(again, wt)
        self.assertTrue(loop.worktree_is_valid(again))

    def test_uncommitted_changes_are_never_forced_away(self):
        wt = loop.acquire_worktree(self.project, self.session, self.state)
        (wt / "b.txt").write_text("b\n")
        # Commit scheitern lassen: git add wird übersprungen, dann bleibt b.txt offen
        calls = []

        def fake_git(repo, *args):
            calls.append(args)
            if args[:1] in (("add",), ("commit",), ("-c",)):
                return subprocess.CompletedProcess(args, 1, "", "kaputt")
            return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)

        with mock.patch.object(loop.session, "_git", side_effect=fake_git):
            self.assertFalse(loop.release_worktree(self.project, self.session, self.state, "Aufgabe"))
        self.assertTrue((wt / "b.txt").exists())
        self.assertNotIn(("worktree", "remove", "--force", str(wt)), calls)

    @unittest.skipIf(os.name == "nt", "chmod-Rechte unter Windows anders")
    def test_remove_tree_handles_read_only_entries(self):
        d = self.tmp / "ro"
        (d / "sub").mkdir(parents=True)
        f = d / "sub" / "f.txt"
        f.write_text("x")
        os.chmod(f, 0o444)
        os.chmod(d / "sub", 0o555)
        self.assertEqual(loop.remove_tree(d), [])
        self.assertFalse(d.exists())

    def test_foreign_files_are_reported_and_session_still_released(self):
        wt = loop.acquire_worktree(self.project, self.session, self.state)
        (wt / "b.txt").write_text("b\n")
        failed = subprocess.CompletedProcess([], 1, "", "Keine Berechtigung")
        real_git = loop.session._git

        def fake_git(repo, *args):
            if args[:2] == ("worktree", "remove"):
                return failed
            return real_git(repo, *args)

        out = []
        with (
            mock.patch.object(loop.session, "_git", side_effect=fake_git),
            mock.patch.object(loop.session, "remove_tree", return_value=[str(wt / "root.pyc")]),
            mock.patch.object(loop.session, "say", side_effect=lambda m, **k: out.append(m)),
        ):
            self.assertTrue(loop.release_worktree(self.project, self.session, self.state, "Aufgabe"))
        self.assertTrue(self.state["worktree"]["released"])
        self.assertIn("b.txt", self.branch_files("loop/s1"))
        self.assertTrue(any("root.pyc" in m for m in out))
        self.assertTrue(any("rm -rf" in m or "rmdir" in m for m in out))


if __name__ == "__main__":
    unittest.main()
