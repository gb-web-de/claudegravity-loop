"""Sandbox (--sandbox docker|podman): Befehle für Container, Konfiguration und echte Läufe mit Docker.

Die echten Läufe brauchen eine laufende Engine und CLAUDEGRAVITY_TEST_SANDBOX=1 (in CI der Job `sandbox`);
das Basis-Image steht in CLAUDEGRAVITY_TEST_SANDBOX_IMAGE (Standard: python:3.12-slim).
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "smoke"))

import loop  # noqa: E402
import run_smoke  # noqa: E402
from claudegravity import common, sandbox  # noqa: E402

BASE_IMAGE = os.environ.get("CLAUDEGRAVITY_TEST_SANDBOX_IMAGE", "python:3.12-slim")
LIVE = os.environ.get("CLAUDEGRAVITY_TEST_SANDBOX") == "1" and shutil.which("docker") is not None and os.name != "nt"
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


@contextlib.contextmanager
def settings(**values):
    old = {k: getattr(common.SETTINGS, k) for k in values}
    for k, v in values.items():
        setattr(common.SETTINGS, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(common.SETTINGS, k, v)


def flag_value(cmd: list[str], flag: str) -> list[str]:
    return [cmd[i + 1] for i, a in enumerate(cmd[:-1]) if a == flag]


class CommandTest(unittest.TestCase):
    def test_engine_choice(self):
        self.assertEqual(sandbox.resolve_engine("aus"), "aus")
        self.assertEqual(sandbox.resolve_engine("off"), "aus")
        self.assertEqual(sandbox.resolve_engine("podman"), "podman")
        with mock.patch.object(sandbox.shutil, "which", side_effect=lambda e: "/bin/podman" if e == "podman" else None):
            self.assertEqual(sandbox.resolve_engine("an"), "podman")

    @unittest.skipIf(os.name == "nt", "Pfade unter Linux/macOS")
    def test_proof_without_network_and_rights(self):
        with tempfile.TemporaryDirectory() as tmp, settings(sandbox="docker", sandbox_image="img:1", sandbox_net=False):
            work = Path(tmp)
            (work / ".git").mkdir()
            cmd = sandbox.proof_command(["python", "-m", "pytest"], work, "n1")
        self.assertEqual(cmd[:3], ["docker", "run", "--rm"])
        self.assertEqual(flag_value(cmd, "--network"), ["none"])
        self.assertIn("ALL", flag_value(cmd, "--cap-drop"))
        self.assertEqual(flag_value(cmd, "--user"), [f"{os.getuid()}:{os.getgid()}"])
        self.assertIn(f"type=bind,src={work},dst={work.as_posix()}", flag_value(cmd, "--mount"))
        self.assertIn(f"type=tmpfs,dst={work.as_posix()}/.git", flag_value(cmd, "--mount"))
        self.assertEqual(cmd[-4:], ["img:1", "python", "-m", "pytest"])
        with settings(sandbox="podman", sandbox_image="img:1", sandbox_net=True):
            cmd = sandbox.proof_command(["make"], Path(tempfile.gettempdir()), "n2")
        self.assertNotIn("--network", cmd)
        self.assertEqual(flag_value(cmd, "--userns"), ["keep-id"])

    @unittest.skipIf(os.name == "nt", "Pfade unter Linux/macOS")
    def test_cli_gets_only_its_own_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            home, work, session = Path(tmp) / "home", Path(tmp) / "wt", Path(tmp) / "sess"
            for d in (home / ".codex", home / ".claude", home / ".ssh", work, session):
                d.mkdir(parents=True)
            env = {"OPENAI_API_KEY": "sk-geheim", "UNRELATED_SECRET": "x"}
            with settings(sandbox="docker", sandbox_image="cg:1"), mock.patch.dict(os.environ, env):
                cmd = sandbox.cli_command("codex", ["exec", "-"], sandbox.Scope(work, session), work, home=home)
        mounts = " ".join(flag_value(cmd, "--mount"))
        self.assertIn(f"src={home / '.codex'},dst={sandbox.CONTAINER_HOME}/.codex", mounts)
        self.assertNotIn(".claude", mounts)
        self.assertNotIn(".ssh", mounts)
        self.assertIn(f"src={session},dst={session.as_posix()}", mounts)
        self.assertIn("OPENAI_API_KEY", flag_value(cmd, "-e"))
        self.assertNotIn("UNRELATED_SECRET", " ".join(cmd))
        self.assertNotIn("sk-geheim", " ".join(cmd))
        self.assertNotIn("--network", cmd)
        self.assertIn("-i", cmd)
        self.assertEqual(cmd[-4:], ["cg:1", "codex", "exec", "-"])

    def test_scope_only_inside_builder_block(self):
        with settings(sandbox="docker"):
            self.assertIsNone(sandbox.current_scope())
            with sandbox.builder_scope(Path("w"), Path("s")):
                expected = None if os.name == "nt" else Path("w")
                self.assertEqual(getattr(sandbox.current_scope(), "work_path", None), expected)
            self.assertIsNone(sandbox.current_scope())
        with settings(sandbox="aus"), sandbox.builder_scope(Path("w"), Path("s")):
            self.assertIsNone(sandbox.current_scope())

    def test_comma_paths_are_rejected(self):
        with self.assertRaises(sandbox.SandboxPathError):
            sandbox._bind(Path("/tmp/a,b"), "/tmp/a,b")

    def test_timeout_removes_container(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            if cmd[1] == "run":
                raise subprocess.TimeoutExpired(cmd, 1)
            return subprocess.CompletedProcess(cmd, 0)

        with mock.patch.object(sandbox.subprocess, "run", side_effect=fake_run), self.assertRaises(subprocess.TimeoutExpired):
            sandbox.run(["docker", "run", "--rm", "--name", "cg-x", "img"], timeout=1)
        self.assertEqual(calls[-1], ["docker", "rm", "-f", "cg-x"])

    def test_missing_engine_fails_with_code(self):
        err = io.StringIO()
        with (
            settings(sandbox="podman"),
            mock.patch.object(sandbox.shutil, "which", return_value=None),
            contextlib.redirect_stderr(err),
            self.assertRaises(SystemExit),
        ):
            sandbox.ensure_ready("claude")
        self.assertIn("CG-1701", err.getvalue())

    def test_missing_proof_program_fails_before_build(self):
        self.assertEqual(sandbox.proof_program("pytest -q"), "pytest")
        self.assertIsNone(sandbox.proof_program("./run-tests.sh"))
        self.assertIsNone(sandbox.proof_program("'offen"))
        checked, err = [], io.StringIO()

        def fake_has(binary):
            checked.append(binary)
            return binary == "claude"

        with (
            settings(sandbox="docker", sandbox_image="cg:1"),
            mock.patch.object(sandbox, "engine_problem", return_value=None),
            mock.patch.object(sandbox, "image_has", side_effect=fake_has),
            contextlib.redirect_stderr(err),
            self.assertRaises(SystemExit),
        ):
            sandbox.ensure_ready("claude", "pytest; rm -rf /")
        # Unter Windows läuft ein CLI-Bauleiter nicht im Container, also wird nur das Programm des Prüfbefehls gesucht
        self.assertEqual(checked, ["pytest;"] if os.name == "nt" else ["claude", "pytest;"])
        self.assertIn("CG-1702", err.getvalue())

    def test_image_check_passes_name_as_argument(self):
        with settings(sandbox="docker", sandbox_image="cg:1"), mock.patch.object(sandbox.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout="/usr/bin/x\n")
            self.assertTrue(sandbox.image_has("x; reboot"))
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[-4:], ["-c", 'command -v "$1"', "sh", "x; reboot"])

    def test_flags_and_config(self):
        parsed = loop.load_cli_config(["x", "--sandbox", "an", "--sandbox-image", "cg:1", "--sandbox-net"])
        args = parsed[1]
        with settings(sandbox="aus", sandbox_image="python:3.12-slim", sandbox_net=False):
            with mock.patch.object(sandbox.shutil, "which", side_effect=lambda e: "/usr/bin/docker" if e == "docker" else None):
                loop.apply_runtime_settings(args)
            self.assertEqual(
                (common.SETTINGS.sandbox, common.SETTINGS.sandbox_image, common.SETTINGS.sandbox_net), ("docker", "cg:1", True)
            )
        self.assertTrue({"sandbox", "sandbox_image", "sandbox_net"} <= loop.PROJECT_PROFILE_FORBIDDEN)
        cmd = loop.dry_run_command(args, "x", "balanced")
        self.assertEqual(cmd[cmd.index("--sandbox") + 1], "an")
        self.assertIn("--sandbox-net", cmd)

    def test_child_inherits_sandbox(self):
        from claudegravity import candidates

        args = loop.build_parser(True).parse_args(["x"])
        with settings(sandbox="docker", sandbox_image="cg:1", sandbox_net=False):
            cmd = candidates.child_command(args, candidates.Candidate("claude", "claude", work_dir=Path("w")), None)
        self.assertEqual(cmd[cmd.index("--sandbox") + 1 : cmd.index("--sandbox") + 4], ["docker", "--sandbox-image", "cg:1"])


FAKE_CLAUDE = textwrap.dedent(
    '''\
    #!/usr/bin/env python3
    """Fake-Claude im Container: schreibt Code und Fertigmeldung selbst, meldet, wo es lief."""
    import json, os, pathlib, re, sys, urllib.request
    prompt = sys.stdin.read()
    pathlib.Path("src").mkdir(exist_ok=True)
    pathlib.Path("src/calc.py").write_text("def add(a, b):\\n    return a + b\\n")
    pathlib.Path("tests/test_calc.py").write_text(
        "import sys, unittest\\nsys.path.insert(0, 'src')\\nfrom calc import add\\n\\n"
        "class T(unittest.TestCase):\\n    def test_add(self):\\n        self.assertEqual(add(1, 2), 3)\\n"
    )
    done = re.search(r"unter: '([^']+)'", prompt)
    if done:
        pathlib.Path(done.group(1)).write_text("fertig\\n")
    seen = {"uid": os.getuid(), "home": os.environ.get("HOME"), "ssh": os.path.exists(os.path.expanduser("~/.ssh")),
            "cwd": os.getcwd(), "in_container": os.path.exists("/.dockerenv")}
    pathlib.Path("sandbox-seen.json").write_text(json.dumps(seen))
    print(json.dumps({"result": "fertig gebaut", "usage": {"input_tokens": 10, "output_tokens": 5}, "session_id": "s1"}))
    '''
)


@unittest.skipUnless(LIVE, "braucht Docker und CLAUDEGRAVITY_TEST_SANDBOX=1")
class LiveSandboxTest(unittest.TestCase):
    """Echte Container: Prüfbefehl ohne Netz, CLI-Bauleiter im Container in einem ganzen Lauf."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        ctx = cls.tmp / "image"
        ctx.mkdir()
        (ctx / "claude").write_text(FAKE_CLAUDE)
        (ctx / "Dockerfile").write_text(f"FROM {BASE_IMAGE}\nCOPY claude /usr/local/bin/claude\nRUN chmod 755 /usr/local/bin/claude\n")
        cls.image = "claudegravity-test-sandbox:latest"
        subprocess.run(["docker", "build", "-q", "-t", cls.image, str(ctx)], check=True, capture_output=True, timeout=600)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_proof_runs_in_container_without_network(self):
        project = Path(tempfile.mkdtemp(dir=self.tmp))
        (project / "tests").mkdir()
        (project / "tests" / "test_n.py").write_text(
            "import os, unittest, urllib.request\n\nclass T(unittest.TestCase):\n"
            "    def test_container(self):\n        self.assertTrue(os.path.exists('/.dockerenv'))\n"
            "        open('aus-container.txt', 'w').close()\n"
            "    def test_no_net(self):\n        with self.assertRaises(OSError):\n"
            "            urllib.request.urlopen('http://1.1.1.1', timeout=3)\n"
        )
        with settings(sandbox="docker", sandbox_image=BASE_IMAGE, sandbox_net=False):
            ok, out = loop.run_proof("python -m unittest discover -s tests", project)
        self.assertTrue(ok, out)
        self.assertEqual((project / "aus-container.txt").stat().st_uid, os.getuid())

    def test_cli_builder_runs_in_container(self):
        server, url = run_smoke.start_server()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        tmp = Path(tempfile.mkdtemp(dir=self.tmp))
        project = tmp / "projekt"
        (project / "tests").mkdir(parents=True)
        (project / "tests" / "test_vorhanden.py").write_text(
            "import unittest\n\nclass V(unittest.TestCase):\n    def test_ok(self):\n        pass\n"
        )
        (project / ".gitignore").write_text(".dual-loop/\nlogs/\n")
        env = dict(os.environ, **GIT_ENV)
        for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-qm", "start"]):
            subprocess.run(["git", *args], cwd=project, env=env, check=True, capture_output=True)
        # Auf dem Rechner liegt eine „claude“, die nie laufen darf: gebaut wird nur im Container
        host_bin = tmp / "bin"
        host_bin.mkdir()
        (host_bin / "claude").write_text(f'#!/bin/sh\n[ "$1" = "-p" ] && touch "{tmp / "HOST_CALLED"}"\nexit 1\n')
        (host_bin / "claude").chmod(0o755)
        cmd = [sys.executable, str(ROOT / "loop.py"), "Addition mit Test", "-p", str(project), "-d", "0", "--plan-auto", "--no-guide"]
        cmd += ["--architekt-endpoint", url, "--architekt", "architekt_ep", "--pruefstatiker-endpoint", url]
        cmd += ["--pruefstatiker", "pruefstatiker_ep", "--abnahme", "pruefstatiker_ep", "--bauer", "claude", "--yolo", "--etappen", "aus"]
        cmd += ["--sandbox", "docker", "--sandbox-image", self.image, "--proof", "python -m unittest discover -s tests"]
        run_env = run_smoke.smoke_env(tmp)
        run_env.update(GIT_ENV, PATH=f"{host_bin}{os.pathsep}{os.environ.get('PATH', '')}")
        res = subprocess.run(cmd, input="", capture_output=True, text=True, encoding="utf-8", timeout=600, env=run_env)
        session = sorted((project / ".dual-loop" / "sessions").glob("*"))[-1]
        state = json.loads((session / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state.get("phase"), "completed", res.stdout[-4000:] + res.stderr[-2000:])
        self.assertFalse((tmp / "HOST_CALLED").exists())
        branch = state["worktree"]["branch"]
        files = subprocess.run(["git", "ls-tree", "-r", "--name-only", branch], cwd=project, capture_output=True, text=True).stdout
        self.assertIn("src/calc.py", files)
        seen = json.loads(
            subprocess.run(["git", "show", f"{branch}:sandbox-seen.json"], cwd=project, capture_output=True, text=True).stdout
        )
        self.assertEqual((seen["uid"], seen["home"], seen["ssh"], seen["in_container"]), (os.getuid(), sandbox.CONTAINER_HOME, False, True))
        self.assertIn("Sandbox", res.stdout)


if __name__ == "__main__":
    unittest.main()
