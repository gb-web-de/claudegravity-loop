"""GitHub: Issue als Aufgabe (--from-issue), Pull Request (--open-pr), GitHub Action und ein ganzer Lauf mit Fake-API."""

import contextlib
import http.server
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "smoke"))
sys.path.insert(0, str(ROOT / "tools"))

import loop  # noqa: E402
import github_action  # noqa: E402
import run_smoke  # noqa: E402
from claudegravity import common, github  # noqa: E402

HAS_GIT = shutil.which("git") is not None
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
ISSUE = {
    "number": 12,
    "title": "Addition fehlt",
    "body": "Bitte add(a, b) in src/calc.py mit Test.",
    "html_url": "https://github.com/o/r/issues/12",
    "state": "open",
    "labels": [{"name": "claudegravity"}],
    "user": {"login": "gordon81"},
}
COMMENTS = [{"user": {"login": "x"}, "body": "Gern auch mit Docstring."}]


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, env=dict(os.environ, **GIT_ENV), check=True)


def done(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class FakeGitHub:
    """Kleiner Ersatz für api.github.com: Issue 12 in o/r, Kommentare, Pull Requests anlegen."""

    def __init__(self, pull_status: int = 201):
        self.calls: list[tuple] = []
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def send(self, code, data):
                body = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                fake.calls.append(("GET", self.path, self.headers.get("Authorization")))
                if self.path == "/repos/o/r/issues/12":
                    return self.send(200, ISSUE)
                if self.path.startswith("/repos/o/r/issues/12/comments"):
                    return self.send(200, COMMENTS)
                if self.path.startswith("/repos/o/r/pulls?"):
                    return self.send(200, [{"html_url": "https://github.com/o/r/pull/9"}])
                self.send(404, {"message": "Not Found"})

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.calls.append(("POST", self.path, data))
                if pull_status == 201:
                    return self.send(201, {"html_url": "https://github.com/o/r/pull/13"})
                self.send(pull_status, {"message": "A pull request already exists"})

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class RefTest(unittest.TestCase):
    def test_issue_refs(self):
        self.assertEqual(github.parse_issue_ref("12"), (None, 12))
        self.assertEqual(github.parse_issue_ref("#12"), (None, 12))
        self.assertEqual(github.parse_issue_ref("gb-web-de/claudegravity-loop#7"), ("gb-web-de/claudegravity-loop", 7))
        self.assertEqual(github.parse_issue_ref("https://github.com/o/r/issues/5#issuecomment-1"), ("o/r", 5))
        for bad in ("", "abc", "o/r", "12a", "https://example.com/x"):
            with self.assertRaises(ValueError):
                github.parse_issue_ref(bad)

    def test_remote_slugs(self):
        self.assertEqual(github.slug_from_remote("https://github.com/o/r.git"), "o/r")
        self.assertEqual(github.slug_from_remote("git@github.com:gb-web-de/claudegravity-loop.git\n"), "gb-web-de/claudegravity-loop")
        self.assertEqual(github.slug_from_remote("ssh://git@github.com/o/r"), "o/r")
        self.assertIsNone(github.slug_from_remote("https://gitlab.com/o/r.git"))

    def test_gh_can_be_switched_off(self):
        with mock.patch.dict(os.environ, {"CLAUDEGRAVITY_GH": "off"}):
            self.assertIsNone(github.gh_path())
            self.assertIsNone(github.run_gh(["--version"], ROOT))
        with mock.patch.dict(os.environ, {"CLAUDEGRAVITY_GH": "/opt/gh"}):
            self.assertEqual(github.gh_path(), "/opt/gh")


class IssueTest(unittest.TestCase):
    def issue(self, **over):
        base = github._issue_from_rest(ISSUE, COMMENTS, "o/r")
        base.update(over)
        return base

    def test_task_text(self):
        text = github.issue_task(self.issue(), "Bitte mit Typen")
        self.assertTrue(text.startswith("GitHub-Issue #12 (o/r): Addition fehlt\nhttps://github.com/o/r/issues/12"))
        for part in ("Bitte add(a, b)", "Labels: claudegravity", "- @x: Gern auch mit Docstring.", "Zusätzlicher Auftrag: Bitte mit Typen"):
            self.assertIn(part, text)
        self.assertTrue(text.endswith(github.ISSUE_NOTE))

    def test_task_preview_for_status_lines(self):
        self.assertEqual(loop.task_preview("kurz"), "kurz")
        self.assertEqual(loop.task_preview(github.issue_task(self.issue())), "GitHub-Issue #12 (o/r): Addition fehlt …")
        self.assertEqual(len(loop.task_preview("x" * 500)), 160)

    def test_task_text_is_limited(self):
        text = github.issue_task(self.issue(body="x" * 50000, comments=[{"author": "a", "body": "y" * 5000}] * 30), limit=3000)
        self.assertLess(len(text), 3000 + len(github.ISSUE_NOTE) + 50)
        self.assertIn("(… gekürzt)", text)

    def test_fetch_with_gh(self):
        gh_json = {
            "number": 12,
            "title": "T",
            "body": "B",
            "url": "https://github.com/o/r/issues/12",
            "state": "OPEN",
            "labels": [{"name": "bug"}],
            "author": {"login": "a"},
            "comments": [{"author": {"login": "b"}, "body": "C"}],
        }
        with (
            mock.patch.object(github, "repo_slug", return_value=None),
            mock.patch.object(github, "run_gh", return_value=done(json.dumps(gh_json))) as gh,
        ):
            issue = github.fetch_issue(ROOT, "#12")
        self.assertEqual(gh.call_args.args[0][:3], ["issue", "view", "12"])
        self.assertNotIn("--repo", gh.call_args.args[0])
        self.assertEqual(
            (issue["repo"], issue["state"], issue["labels"], issue["comments"]), ("o/r", "open", ["bug"], [{"author": "b", "body": "C"}])
        )

    def test_fetch_falls_back_to_api(self):
        fake = FakeGitHub()
        self.addCleanup(fake.close)
        env = {"GITHUB_API_URL": fake.url, "GH_TOKEN": "geheim-token", "CLAUDEGRAVITY_GH": "off"}
        with mock.patch.dict(os.environ, env):
            issue = github.fetch_issue(ROOT, "o/r#12")
        self.assertEqual((issue["title"], issue["url"], issue["author"]), ("Addition fehlt", ISSUE["html_url"], "gordon81"))
        self.assertEqual(issue["comments"], [{"author": "x", "body": "Gern auch mit Docstring."}])
        self.assertEqual(fake.calls[0], ("GET", "/repos/o/r/issues/12", "Bearer geheim-token"))

    def test_fetch_error_has_code_and_no_token(self):
        fake = FakeGitHub()
        self.addCleanup(fake.close)
        err = io.StringIO()
        env = {"GITHUB_API_URL": fake.url, "GH_TOKEN": "ghp_abcdefghijklmnopqrstuvwxyz0123456789", "CLAUDEGRAVITY_GH": "off"}
        with mock.patch.dict(os.environ, env), contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            github.fetch_issue(ROOT, "o/r#99")
        self.assertIn("CG-1601", err.getvalue())
        self.assertIn("HTTP 404", err.getvalue())
        self.assertNotIn("ghp_abcdef", err.getvalue())

    def test_bad_reference(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            github.fetch_issue(ROOT, "kein-issue")
        self.assertIn("CG-1601", err.getvalue())


class PullRequestTextTest(unittest.TestCase):
    def body(self, **kw):
        args = dict(
            task="Aufgabe",
            issue={"number": 12, "repo": "o/r"},
            roles=[("Architekt", "Claude Code"), ("Bauleiter", "Codex")],
            proof="pytest -q",
            kpi_lines=["* **Ergebnis:** erfolgreich"],
            plan_text="# Plan\n1. Schritt",
            session_id="s1",
            target_repo="o/r",
        )
        args.update(kw)
        return github.pull_request_body(**args)

    def test_body(self):
        body = self.body()
        self.assertTrue(body.startswith("Closes #12\n"))
        for part in (
            "* **Architekt:** Claude Code",
            "* **Bauleiter:** Codex",
            "`pytest -q`",
            "* **Ergebnis:** erfolgreich",
            "# Plan\n1. Schritt",
        ):
            self.assertIn(part, body)
        self.assertIn("Closes o/r#12", self.body(target_repo="fork/r"))
        self.assertIn("**Aufgabe:**", self.body(issue=None))
        self.assertIn("keiner", self.body(proof=None))

    def test_body_in_english(self):
        old = common.SETTINGS.lang
        common.SETTINGS.lang = "en"
        try:
            body = self.body()
        finally:
            common.SETTINGS.lang = old
        for part in (
            "## Summary",
            "* **Architect:** Claude Code",
            "* **Builder:** Codex",
            "run by the loop itself and green",
            "Approved plan",
        ):
            self.assertIn(part, body)

    def test_title(self):
        self.assertEqual(github.pull_request_title("egal", {"title": "Addition fehlt"}), "Addition fehlt")
        self.assertEqual(github.pull_request_title("\n" + "x" * 100, None), "x" * 71 + "…")


class CreatePullRequestTest(unittest.TestCase):
    def test_gh_creates_or_finds_existing(self):
        ok = done("https://github.com/o/r/pull/3\n")
        exists = done("", 1, 'a pull request for branch "b" into branch "main" already exists:\nhttps://github.com/o/r/pull/2\n')
        with mock.patch.object(github, "gh_path", return_value="gh"), mock.patch.object(github, "run_gh", side_effect=[ok, exists]) as gh:
            self.assertEqual(github.create_pull_request(ROOT, "o/r", "main", "b", "T", "B", draft=True), "https://github.com/o/r/pull/3")
            self.assertEqual(github.create_pull_request(ROOT, "o/r", "main", "b", "T", "B"), "https://github.com/o/r/pull/2")
        first = gh.call_args_list[0].args[0]
        self.assertEqual(first[:2], ["pr", "create"])
        self.assertIn("--draft", first)
        self.assertNotIn("--draft", gh.call_args_list[1].args[0])

    def test_api_existing_pull_request(self):
        fake = FakeGitHub(pull_status=422)
        self.addCleanup(fake.close)
        with mock.patch.dict(os.environ, {"GITHUB_API_URL": fake.url, "GH_TOKEN": "t", "CLAUDEGRAVITY_GH": "off"}):
            self.assertEqual(github.create_pull_request(ROOT, "o/r", "main", "b", "T", "B"), "https://github.com/o/r/pull/9")

    def test_without_gh_and_token(self):
        env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
        env["CLAUDEGRAVITY_GH"] = "off"
        with mock.patch.dict(os.environ, env, clear=True), self.assertRaises(RuntimeError) as ctx:
            github.create_pull_request(ROOT, "o/r", "main", "b", "T", "B")
        self.assertIn("gh nicht installiert", str(ctx.exception))
        self.assertIn("GH_TOKEN", str(ctx.exception))


@unittest.skipUnless(HAS_GIT, "git fehlt")
class OpenPullRequestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        patcher = mock.patch.dict(os.environ, GIT_ENV)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.project = self.tmp / "projekt"
        self.project.mkdir()
        git(self.project, "init", "-q", "-b", "main")
        (self.project / ".gitignore").write_text(".dual-loop/\n")
        git(self.project, "add", "-A")
        git(self.project, "commit", "-qm", "start")
        self.origin = self.tmp / "origin.git"
        git(self.tmp, "init", "-q", "--bare", str(self.origin))
        git(self.project, "remote", "add", "origin", str(self.origin))
        git(self.project, "push", "-q", "origin", "main")
        self.session = self.project / ".dual-loop" / "sessions" / "s1"
        self.session.mkdir(parents=True)
        self.state = {"issue": {"number": 12, "repo": "o/r"}}

    def worktree(self, change: bool = True) -> dict:
        wt = loop.acquire_worktree(self.project, self.session, self.state)
        if change:
            (wt / "neu.txt").write_text("neu\n")
        loop.release_worktree(self.project, self.session, self.state, "Aufgabe")
        return self.state["worktree"]

    def test_push_and_record(self):
        (self.session / ".done").write_text("fertig\n")
        out = io.StringIO()
        url = "https://github.com/o/r/pull/13"
        with mock.patch.object(github, "create_pull_request", return_value=url) as create, contextlib.redirect_stdout(out):
            self.assertEqual(github.open_pull_request(self.project, self.session, self.state, self.worktree(), "T", "B", draft=True), url)
        self.assertEqual(create.call_args.args[1:4], ("o/r", "main", "loop/s1"))
        self.assertIn("loop/s1", git(self.origin, "branch").stdout)
        self.assertEqual(self.state["pull_request"], {"url": url, "branch": "loop/s1", "base": "main", "draft": True})
        self.assertIn(f"Pull Request: {url}", (self.session / ".done").read_text())
        self.assertIn(url, (self.session / "LOG.md").read_text())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(github.open_pull_request(self.project, self.session, self.state, self.state["worktree"], "T", "B"), url)
        self.assertEqual(create.call_count, 1)

    def test_no_commits_no_pull_request(self):
        with mock.patch.object(github, "create_pull_request") as create, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertIsNone(github.open_pull_request(self.project, self.session, self.state, self.worktree(change=False), "T", "B"))
        create.assert_not_called()
        self.assertIn("keine neuen Commits", out.getvalue())

    def test_without_worktree_or_after_merge(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertIsNone(github.open_pull_request(self.project, self.session, self.state, {"enabled": False}, "T", "B"))
            self.assertIsNone(github.open_pull_request(self.project, self.session, self.state, {"branch": "x", "merged": True}, "T", "B"))
        self.assertIn("--no-worktree", out.getvalue())
        self.assertIn("schon gemerged", out.getvalue())


class CliTest(unittest.TestCase):
    def test_flags_and_layers(self):
        args = loop.build_parser(True).parse_args(["--issue", "#3", "--pr-entwurf"])
        self.assertEqual((args.from_issue, args.open_pr, args.pr_draft), ("#3", False, True))
        self.assertIn("from_issue", loop.CONFIG_EXCLUDED)
        self.assertTrue({"open_pr", "pr_draft"} <= loop.PROJECT_PROFILE_FORBIDDEN)

    def test_dry_run_command_keeps_issue_reference(self):
        args = loop.build_parser(True).parse_args(["--from-issue", "o/r#12", "--open-pr"])
        args.issue_extra = ""
        cmd = loop.dry_run_command(args, "GitHub-Issue #12 … langer Text", "balanced")
        self.assertEqual(cmd[:3], ["claudegravity", "--from-issue", "o/r#12"])
        self.assertIn("--open-pr", cmd)
        self.assertNotIn("GitHub-Issue #12 … langer Text", cmd)

    def test_candidate_children_never_open_pull_requests(self):
        from claudegravity import candidates

        self.assertTrue({"open_pr", "pr_draft", "pull_request"} <= set(candidates.CHILD_STATE_DROP))


class ActionTest(unittest.TestCase):
    def test_argv(self):
        env = {
            "CG_ISSUE": "12",
            "CG_PROOF": "pytest -q",
            "CG_DRAFT": "true",
            "CG_LANG": "en",
            "CG_ARGS": '--architekt claude --strategy "best-code"',
        }
        argv = github_action.action_argv(env)
        self.assertEqual(argv[1:5], ["-m", "claudegravity", "--from-issue", "12"])
        for part in ("--plan-auto", "--yolo", "--pr-draft"):
            self.assertIn(part, argv)
        self.assertNotIn("--open-pr", argv)
        self.assertEqual(argv[-4:], ["--architekt", "claude", "--strategy", "best-code"])
        self.assertIn("--open-pr", github_action.action_argv({"CG_ISSUE": "5"}))
        with self.assertRaises(SystemExit):
            github_action.action_argv({"CG_ISSUE": " "})

    def test_comment_command(self):
        self.assertEqual(github_action.comment_command("o/r#12", "x"), ["gh", "issue", "comment", "12", "--body", "x", "--repo", "o/r"])
        self.assertEqual(github_action.comment_command("12", "x")[:4], ["gh", "issue", "comment", "12"])

    def test_outputs_and_summary(self):
        result = {
            "session": "s1",
            "success": False,
            "abort_reason": "Rundenlimit erreicht",
            "pull_request": "",
            "issue": {"number": 12, "title": "T", "url": "u"},
            "report": "Bericht",
        }
        with tempfile.TemporaryDirectory() as tmp:
            env = {"GITHUB_OUTPUT": str(Path(tmp) / "out"), "GITHUB_STEP_SUMMARY": str(Path(tmp) / "sum"), "CG_LANG": "en"}
            github_action.write_outputs(result, env)
            self.assertEqual((Path(tmp) / "out").read_text(), "pull-request=\nsuccess=false\nsession=s1\n")
            summary = (Path(tmp) / "sum").read_text()
        for part in ("[#12 T](u)", "❌ not completed", "Rundenlimit erreicht", "<summary>Report</summary>"):
            self.assertIn(part, summary)
        env = {"GITHUB_SERVER_URL": "https://github.com", "GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": "7"}
        self.assertIn("https://github.com/o/r/actions/runs/7", github_action.comment_text(result, env))
        self.assertIn("pull/1", github_action.comment_text(dict(result, pull_request="https://github.com/o/r/pull/1"), env))

    def test_action_yml_matches_script(self):
        text = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertIn("using: composite", text)
        self.assertIn('python "$GITHUB_ACTION_PATH/tools/github_action.py"', text)
        script = (ROOT / "tools" / "github_action.py").read_text(encoding="utf-8")
        # CG_CLI braucht nur der npm-Schritt
        for var in set(re.findall(r"\b(CG_[A-Z]+):", text)) - {"CG_CLI"}:
            self.assertIn(var, script, var)
        # Eingaben gehen nur über die Umgebung in Skripte, nie direkt in eine Shell-Zeile
        for line in text.splitlines():
            if line.strip().startswith("run:"):
                self.assertNotIn("${{", line, line)


@unittest.skipUnless(HAS_GIT, "git fehlt")
class IssueToPullRequestRunTest(unittest.TestCase):
    """Ganzer Lauf: Issue über die (Fake-)API lesen, mit Fake-Modellen im Git-Workspace bauen, Branch pushen, PR öffnen."""

    def test_run(self):
        fake = FakeGitHub()
        self.addCleanup(fake.close)
        server, url = run_smoke.start_server()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            project = tmp / "projekt"
            (project / "tests").mkdir(parents=True)
            (project / "tests" / "test_vorhanden.py").write_text(
                "import unittest\n\nclass V(unittest.TestCase):\n    def test_ok(self):\n        pass\n", encoding="utf-8"
            )
            (project / ".gitignore").write_text(".dual-loop/\n", encoding="utf-8")
            with mock.patch.dict(os.environ, GIT_ENV):
                git(project, "init", "-q", "-b", "main")
                git(project, "add", "-A")
                git(project, "commit", "-qm", "start")
                origin = tmp / "origin.git"
                git(tmp, "init", "-q", "--bare", str(origin))
                git(project, "remote", "add", "origin", str(origin))
                git(project, "push", "-q", "origin", "main")
            cmd = [
                c
                for c in run_smoke.smoke_command(project, url, "balanced", ["--from-issue", "o/r#12", "--open-pr"])
                if c not in ("--no-worktree", "Addition mit Test")
            ]
            env = run_smoke.smoke_env(tmp)
            env.update(GIT_ENV, PATH=os.environ.get("PATH", ""), CLAUDEGRAVITY_GH="off", GITHUB_API_URL=fake.url, GH_TOKEN="test-token")
            res = subprocess.run(cmd, input="", capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
            session = sorted((project / ".dual-loop" / "sessions").glob("*"))[-1]
            state = json.loads((session / "state.json").read_text(encoding="utf-8"))
            branches = git(origin, "branch").stdout
        self.assertEqual(res.returncode, 0, res.stdout[-3000:] + res.stderr[-2000:])
        self.assertEqual(state["phase"], "completed", res.stdout[-3000:])
        self.assertIn("issue-12_Addition_fehlt", session.name)
        self.assertEqual(state["issue"]["number"], 12)
        self.assertEqual(state["pull_request"]["url"], "https://github.com/o/r/pull/13")
        self.assertIn(state["pull_request"]["branch"], branches)
        posts = [c for c in fake.calls if c[0] == "POST"]
        self.assertEqual(len(posts), 1)
        payload = posts[0][2]
        self.assertEqual((payload["title"], payload["base"], payload["draft"]), ("Addition fehlt", "main", False))
        self.assertTrue(payload["body"].startswith("Closes #12"))
        self.assertNotIn("test-token", res.stdout + res.stderr)


class DoneMarkerTest(unittest.TestCase):
    """Endpunkt-Bauleiter im Git-Workspace: der Session-Ordner liegt außerhalb, die Fertigmeldung schreibt der Loop selbst."""

    def test_done_block_goes_to_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "sitzung"
            session.mkdir()
            answer = f"```filepath: src/a.py\nx = 1\n```\n\n```filepath: {session / '.done'}\n# Aufgabe abgeschlossen\n```"
            rest, found = loop.take_done_block(answer, session)
            self.assertTrue(found)
            self.assertEqual((session / ".done").read_text(), "# Aufgabe abgeschlossen\n")
            self.assertIn("src/a.py", rest)
            self.assertNotIn(".done", rest)
            self.assertEqual(loop.take_done_block("```filepath: src/b.py\ny\n```", session), ("```filepath: src/b.py\ny\n```", False))


if __name__ == "__main__":
    unittest.main()
