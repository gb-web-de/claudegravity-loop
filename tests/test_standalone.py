"""Eigenständiges Programm aus dem Release: Aufrufverteilung, Selbststart, Installer im Programm-Modus, Archive, Release."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import build_standalone  # noqa: E402
import install  # noqa: E402
import loop  # noqa: E402
import mcp_server  # noqa: E402
import release  # noqa: E402
import standalone  # noqa: E402
from claudegravity import __version__  # noqa: E402
from claudegravity import candidates as cand  # noqa: E402


def frozen(executable: Path):
    """Laufzeit wie im PyInstaller-Programm vortäuschen."""
    return [mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(sys, "executable", str(executable))]


class RouteTest(unittest.TestCase):
    def test_subcommands_and_program_names(self):
        self.assertEqual(standalone.route(["claudegravity", "Aufgabe", "-p", "x"]), ("loop", ["Aufgabe", "-p", "x"]))
        self.assertEqual(standalone.route(["/opt/bin/claudegravity", "mcp", "--info"]), ("mcp", ["--info"]))
        self.assertEqual(standalone.route(["claudegravity.exe", "install", "--dry-run"]), ("install", ["--dry-run"]))
        self.assertEqual(standalone.route(["/home/a/.local/bin/claudegravity-mcp"]), ("mcp", []))
        self.assertEqual(standalone.route(["claudegravity-loop", "watch"]), ("loop", ["watch"]))
        # Nur das erste Argument zählt: eine Aufgabe, die "mcp" enthält, bleibt eine Aufgabe
        self.assertEqual(standalone.route(["claudegravity", "MCP-Server reparieren", "mcp"]), ("loop", ["MCP-Server reparieren", "mcp"]))


class SelfStartTest(unittest.TestCase):
    def test_program_starts_itself_for_background_runs_and_candidates(self):
        program = Path("/opt/claudegravity/claudegravity")
        with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(sys, "executable", str(program)):
            self.assertEqual(mcp_server.loop_launch_argv(["Aufgabe", "-p", "x"]), [str(program), "Aufgabe", "-p", "x"])
            args = loop.cli.build_parser(True).parse_args(["x"])
            cmd = cand.child_command(args, cand.Candidate("codex", "codex", None, work_dir=Path("/wt")), None)
            self.assertEqual(cmd[:2], [str(program), "-c"])
        self.assertNotEqual(mcp_server.loop_launch_argv(["x"])[0:1], [str(program)])


class InstallerProgramModeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.download = base / "download" / "claudegravity"
        self.download.parent.mkdir()
        self.download.write_bytes(b"programm-1")
        self.home = base / "home"
        for name in (".codex", ".cursor"):
            (self.home / name).mkdir(parents=True)
        self.bin = base / "bin"
        self.patches = [
            *frozen(self.download),
            mock.patch.object(install, "HOME", self.home),
            mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(base / "share"), "LOCALAPPDATA": str(base / "local"), "PATH": str(base)}),
            mock.patch.object(install, "SKILL_SOURCE", install.SKILL_SOURCE),
            mock.patch.object(install, "COMMANDS_DIR", install.COMMANDS_DIR),
            mock.patch.object(install, "PROGRAM", None),
            mock.patch.object(install, "DRY_RUN", False),
            mock.patch.object(install, "say"),
            mock.patch("builtins.print"),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tmp.cleanup()

    def run_installer(self, *extra: str) -> int:
        argv = ["claudegravity install", "--no-path", "--only", "codex,cursor", "--bin-dir", str(self.bin), *extra]
        with mock.patch.object(sys, "argv", argv):
            return install.main()

    def test_install_copies_program_and_registers_it_as_server(self):
        self.assertEqual(self.run_installer(), 0)
        program = self.bin.resolve() / install.program_name()
        self.assertEqual(program.read_bytes(), b"programm-1")
        cursor = json.loads((self.home / ".cursor" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["claudegravity"]
        self.assertEqual((cursor["command"], cursor["args"]), (str(program), ["mcp"]))
        codex = (self.home / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertIn(f"command = {json.dumps(str(program))}", codex)
        self.assertIn('args = ["mcp"]', codex)
        share = install.share_dir_default()
        self.assertTrue((share / "skills" / "claudegravity" / "SKILL.md").is_file())
        self.assertTrue((self.home / ".codex" / "skills" / "claudegravity" / "SKILL.md").is_file())
        if install.IS_WINDOWS:
            self.assertIn(" mcp %*", (self.bin / "claudegravity-mcp.cmd").read_text(encoding="utf-8"))
        else:
            self.assertEqual((self.bin / "claudegravity-mcp").resolve(), program)
            self.assertEqual((self.bin / "claudegravity-loop").resolve(), program)

        # Update: ein neues Programm ersetzt das alte, die Einträge bleiben gleich
        self.download.write_bytes(b"programm-2")
        self.assertEqual(self.run_installer(), 0)
        self.assertEqual(program.read_bytes(), b"programm-2")

        self.assertEqual(self.run_installer("--uninstall"), 0)
        self.assertFalse(program.exists())
        self.assertFalse(share.exists())
        self.assertNotIn("claudegravity", (self.home / ".codex" / "config.toml").read_text(encoding="utf-8"))
        self.assertNotIn("claudegravity", json.loads((self.home / ".cursor" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"])

    def test_dry_run_changes_nothing(self):
        self.assertEqual(self.run_installer("--dry-run"), 0)
        self.assertFalse(self.bin.exists())
        self.assertFalse(install.share_dir_default().exists())
        self.assertFalse((self.home / ".cursor" / "mcp.json").exists())


class ArchiveTest(unittest.TestCase):
    def test_target_names(self):
        self.assertEqual(build_standalone.target_name("Linux", "aarch64"), "linux-arm64")
        self.assertEqual(build_standalone.target_name("Darwin", "arm64"), "macos-arm64")
        self.assertEqual(build_standalone.target_name("Windows", "AMD64"), "windows-x86_64")
        with self.assertRaises(SystemExit):
            build_standalone.target_name("SunOS", "sparc")

    def test_pyinstaller_bundles_data_and_entry(self):
        args = build_standalone.pyinstaller_args(Path("/w"))
        self.assertEqual(args[-1], str(ROOT / "tools" / "standalone.py"))
        self.assertIn(f"{ROOT / 'skills'}{os.pathsep}skills", args)
        self.assertIn("--onefile", args)

    def test_archives_hold_program_and_readme_in_one_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "bin"
            binary.write_bytes(b"\x7fELF")
            archive = build_standalone.package(binary, "linux-arm64", Path(tmp) / "dist")
            self.assertEqual(archive.name, "claudegravity-linux-arm64.tar.gz")
            with tarfile.open(archive) as tf:
                self.assertEqual(sorted(tf.getnames()), ["claudegravity/README.txt", "claudegravity/claudegravity"])
                self.assertEqual(tf.getmember("claudegravity/claudegravity").mode, 0o755)
                self.assertIn(__version__, tf.extractfile("claudegravity/README.txt").read().decode("utf-8"))
            archive = build_standalone.package(binary, "windows-x86_64", Path(tmp) / "dist")
            self.assertEqual(sorted(zipfile.ZipFile(archive).namelist()), ["claudegravity/README.txt", "claudegravity/claudegravity.exe"])


class ReleaseTest(unittest.TestCase):
    def test_changelog_section(self):
        text = "# Log\n\n## [Unveröffentlicht]\n\n## [2.0.0] – 2027-01-01\n\n### Neu\n- A\n\n## [1.0.0]\n\n- B\n"
        self.assertEqual(release.changelog_section(text, "2.0.0"), "### Neu\n- A")
        self.assertEqual(release.changelog_section(text, "1.0.0"), "- B")
        self.assertEqual(release.changelog_section(text, "3.0.0"), "")

    def test_tag_must_match_version(self):
        release.check_tag(f"v{__version__}")
        with self.assertRaises(SystemExit):
            release.check_tag("v0.0.1")

    def test_installers_carry_one_placeholder(self):
        for name in release.INSTALLERS:
            text = (ROOT / "tools" / "release" / name).read_text(encoding="utf-8")
            self.assertEqual(text.count(release.TAG_PLACEHOLDER), 1, name)
            self.assertIn('version="${CLAUDEGRAVITY_VERSION:-$release_tag}"' if name.endswith(".sh") else "$Version = $releaseTag", text)
        with self.assertRaises(SystemExit):
            release.stamp_installer("echo", "v1")

    @unittest.skipUnless(shutil.which("sh"), "sh fehlt")
    def test_shell_installer_parses(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(ROOT / "tools" / "release" / "claudegravity-install.sh")]).returncode, 0)

    def test_prepare_writes_installers_checksums_and_notes(self):
        tag = f"v{__version__}"
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            dist.mkdir()
            for name in ("claudegravity-linux-x86_64.tar.gz", "claudegravity-macos-arm64.tar.gz", "claudegravity.mcpb"):
                (dist / name).write_bytes(name.encode())
            (dist / f"claudegravity_loop-{__version__}-py3-none-any.whl").write_bytes(b"whl")
            notes_file = Path(tmp) / "notes.md"
            assets = release.prepare(tag, dist, notes_file)
            self.assertIn("SHA256SUMS", assets)
            self.assertIn("claudegravity-install.ps1", assets)
            installer = (dist / "claudegravity-install.sh").read_text(encoding="utf-8")
            self.assertIn(f'release_tag="{tag}"', installer)
            sums = dict(reversed(line.split("  ")) for line in (dist / "SHA256SUMS").read_text(encoding="utf-8").splitlines())
            self.assertEqual(sums["claudegravity.mcpb"], hashlib.sha256(b"claudegravity.mcpb").hexdigest())
            self.assertEqual(set(sums), set(assets) - {"SHA256SUMS"})
            notes = notes_file.read_text(encoding="utf-8")
            self.assertIn(f"releases/download/{tag}/claudegravity-install.sh \\| sh`", notes)
            # Nur Systeme mit Programm im Release stehen in der Tabelle
            self.assertIn("| macOS (Apple Silicon), Linux (x64) |", notes)
            self.assertIn(f"pipx install https://github.com/gb-web-de/claudegravity-loop/releases/download/{tag}/claudegravity_loop", notes)


if __name__ == "__main__":
    unittest.main()
