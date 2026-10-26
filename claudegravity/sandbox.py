"""Sandbox: Prüfbefehl und CLI-Bauleiter in einem Container (Docker oder Podman) statt mit deinen Benutzerrechten.

Im Container sieht der Prozess nur den Arbeitsordner (und beim Bauleiter den Session-Ordner sowie die Anmeldedaten
seiner eigenen CLI), läuft mit deiner Benutzer-ID, ohne Capabilities, mit Grenzen für Prozesse und Speicher.
Der Prüfbefehl hat kein Netz (außer mit --sandbox-net); ein Cloud-CLI-Bauleiter braucht Netz für sein Modell.
Endpunkt-Bauleiter schreiben ohnehin nichts selbst (das macht der Loop), sie laufen nicht im Container.
Nur Standardbibliothek; Prozesse immer mit Argumentlisten.
"""

import contextlib
import dataclasses
import os
import shlex
import shutil
import subprocess
import uuid
from pathlib import Path

from .common import SETTINGS, say, tr
from .errors import fail

SANDBOX_MODES = ("aus", "an", "docker", "podman")
SANDBOX_ENGINES = ("docker", "podman")
DEFAULT_SANDBOX_IMAGE = "python:3.12-slim"
# CLIs, die als Bauleiter selbst Dateien schreiben und deshalb in den Container gehören
SANDBOX_CLIS = ("claude", "codex", "gemini", "copilot", "gh", "agy")
CONTAINER_HOME = "/home/claudegravity"
CONTAINER_WORK = "/work"
# Anmeldedaten je CLI (relativ zum Home-Ordner); nur die der CLI, die gerade baut, kommen in den Container
CREDENTIAL_PATHS = {
    "claude": (".claude", ".claude.json"),
    "codex": (".codex",),
    "gemini": (".gemini",),
    "agy": (".gemini",),
    "copilot": (".copilot", ".config/gh"),
    "gh": (".copilot", ".config/gh"),
}
# Umgebungsvariablen, die in den Container dürfen (nur der Name steht im Befehl, der Wert kommt aus der Umgebung)
PASS_ENV = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "CODEX_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "COPILOT_GITHUB_TOKEN",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "NO_PROXY",
    "https_proxy",
    "http_proxy",
    "no_proxy",
)
LIMITS = ["--pids-limit", "512", "--memory", "4g", "--cpus", "2"]


@dataclasses.dataclass
class Scope:
    """Was ein CLI-Bauleiter im Container sieht: Arbeitsordner und Session-Ordner (beide beschreibbar)."""

    work_path: Path
    session_dir: Path


class SandboxPathError(ValueError):
    """Ein Pfad lässt sich nicht in den Container einbinden (Komma im Pfad)."""


_SCOPE: Scope | None = None


def resolve_engine(mode: str | None) -> str:
    """--sandbox in die Engine übersetzen: aus, docker, podman; `an` nimmt die installierte (Docker vor Podman)."""
    mode = {"on": "an", "off": "aus", None: "aus", "": "aus"}.get(mode, mode)
    if mode == "an":
        return next((e for e in SANDBOX_ENGINES if shutil.which(e)), "docker")
    return mode if mode in SANDBOX_ENGINES else "aus"


def active() -> bool:
    """Ob in diesem Lauf eine Sandbox eingestellt ist."""
    return SETTINGS.sandbox in SANDBOX_ENGINES


def engine_problem(engine: str) -> str | None:
    """Warum die Engine nicht nutzbar ist (nicht installiert, Dienst läuft nicht); None, wenn sie bereit ist."""
    if not shutil.which(engine):
        return f"{engine} ist nicht installiert"
    try:
        res = subprocess.run([engine, "info"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{engine} info: {exc}"
    if res.returncode != 0:
        return f"{engine} info: " + ((res.stderr or res.stdout).strip().splitlines() or ["Fehler"])[-1]
    return None


def image_has(binary: str) -> bool:
    """Ob das Sandbox-Image das Programm enthält (z. B. die CLI des Bauleiters)."""
    # Name als Argument, nicht im Shell-Text: der Prüfbefehl kann aus einem Projekt-Profil stammen
    cmd = [SETTINGS.sandbox, "run", "--rm", "--network", "none", "--entrypoint", "sh", SETTINGS.sandbox_image]
    cmd += ["-c", 'command -v "$1"', "sh", binary]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    except (OSError, subprocess.SubprocessError):
        return False
    return res.returncode == 0 and bool(res.stdout.strip())


def proof_program(proof_cmd: str | None) -> str | None:
    """Programm des Prüfbefehls, wenn es ein bloßer Name ist (z. B. `pytest`); Pfade wie ./test.sh prüft der Loop nicht vorab."""
    try:
        argv = shlex.split(proof_cmd or "")
    except ValueError:
        return None
    return argv[0] if argv and "/" not in argv[0] and "\\" not in argv[0] else None


def ensure_ready(builder_binary: str | None = None, proof_cmd: str | None = None) -> None:
    """Vor dem Bau: Engine bereit (sonst CG-1701), Image enthält die CLI eines CLI-Bauleiters und das Programm
    des Prüfbefehls (sonst CG-1702)."""
    if not active():
        return
    problem = engine_problem(SETTINGS.sandbox)
    if problem:
        fail("CG-1701", problem)
    if builder_binary in SANDBOX_CLIS and cli_sandbox_supported() and not image_has(builder_binary):
        fail("CG-1702", f"`{builder_binary}` (Bauleiter) fehlt in {SETTINGS.sandbox_image}")
    program = proof_program(proof_cmd)
    if program and not image_has(program):
        fail("CG-1702", f"`{program}` (Prüfbefehl) fehlt in {SETTINGS.sandbox_image}")


def cli_sandbox_supported() -> bool:
    """CLI-Bauleiter laufen nur unter Linux und macOS im Container (Pfade werden 1:1 eingebunden)."""
    return os.name != "nt"


def user_flags(engine: str) -> list[str]:
    """Im Container mit deiner Benutzer-ID arbeiten, damit neue Dateien dir gehören (Podman rootless: keep-id)."""
    if os.name == "nt":
        return []
    if engine == "podman":
        return ["--userns", "keep-id"]
    return ["--user", f"{os.getuid()}:{os.getgid()}"]


def _bind(src: Path, dst: str, readonly: bool = False) -> list[str]:
    text = str(src)
    if "," in text or "," in dst:
        raise SandboxPathError(f"Pfad mit Komma kann nicht in die Sandbox eingebunden werden: {text}")
    return ["--mount", f"type=bind,src={text},dst={dst}" + (",readonly" if readonly else "")]


def _container_path(path: Path) -> str:
    """Pfad im Container: unter Linux und macOS derselbe, unter Windows /work."""
    return CONTAINER_WORK if os.name == "nt" else path.as_posix()


def base_command(name: str, network: bool, interactive: bool = False) -> list[str]:
    """Gemeinsamer Anfang jedes Sandbox-Aufrufs: frischer Container, keine Rechte, Grenzen, eigenes Home."""
    engine = SETTINGS.sandbox
    cmd = [engine, "run", "--rm", "--name", name, "--init"]
    if interactive:
        cmd.append("-i")
    if not network:
        cmd += ["--network", "none"]
    cmd += ["--cap-drop", "ALL", "--security-opt", "no-new-privileges", *LIMITS, *user_flags(engine)]
    cmd += ["--mount", f"type=tmpfs,dst={CONTAINER_HOME},tmpfs-mode=1777", "-e", f"HOME={CONTAINER_HOME}"]
    cmd += ["--mount", "type=tmpfs,dst=/tmp,tmpfs-mode=1777"]
    return cmd


def proof_command(argv: list[str], work_path: Path, name: str) -> list[str]:
    """Prüfbefehl im Container: nur der Arbeitsordner, ohne Netz (außer --sandbox-net)."""
    inside = _container_path(work_path)
    cmd = base_command(name, network=SETTINGS.sandbox_net)
    cmd += _bind(work_path, inside) + ["-w", inside]
    cmd += _hide_git(work_path, inside)
    return cmd + [SETTINGS.sandbox_image, *argv]


def _hide_git(work_path: Path, inside: str) -> list[str]:
    # Ein .git-Ordner im Arbeitsordner (ohne Worktree) kann Zugangsdaten enthalten (z. B. Token in .git/config)
    if (work_path / ".git").is_dir():
        return ["--mount", f"type=tmpfs,dst={inside}/.git"]
    return []


def cli_command(binary: str, args: list[str], scope: Scope, cwd: Path | None, home: Path | None = None) -> list[str]:
    """Aufruf einer Bauleiter-CLI im Container: Arbeits- und Session-Ordner an denselben Pfaden, Anmeldedaten nur
    dieser CLI, Zugangs-Variablen nur mit Namen (Werte kommen aus der Umgebung), mit Netz für das Modell."""
    home = home or Path.home()
    cmd = base_command(f"claudegravity-{binary}-{uuid.uuid4().hex[:8]}", network=True, interactive=True)
    cmd += _bind(scope.work_path, scope.work_path.as_posix())
    if not scope.session_dir.resolve().is_relative_to(scope.work_path.resolve()):
        cmd += _bind(scope.session_dir, scope.session_dir.as_posix())
    cmd += _hide_git(scope.work_path, scope.work_path.as_posix())
    for rel in CREDENTIAL_PATHS.get(binary, ()):
        src = home / rel
        if src.exists():
            cmd += _bind(src, f"{CONTAINER_HOME}/{rel}")
    cmd += [arg for name in PASS_ENV if os.environ.get(name) for arg in ("-e", name)]
    cmd += ["-w", (cwd or scope.work_path).as_posix()]
    return cmd + [SETTINGS.sandbox_image, binary, *args]


def container_name(cmd: list[str]) -> str | None:
    """Name des Containers aus einem Sandbox-Befehl (für das Aufräumen nach Zeitüberschreitung)."""
    return cmd[cmd.index("--name") + 1] if "--name" in cmd else None


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run für Sandbox-Befehle; bei Zeitüberschreitung wird der Container entfernt, dann geht der Fehler weiter."""
    try:
        return subprocess.run(cmd, **kwargs)
    except subprocess.TimeoutExpired:
        name = container_name(cmd)
        if name:
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run([cmd[0], "rm", "-f", name], capture_output=True, timeout=60)
        raise


def current_scope() -> Scope | None:
    """Sandbox-Bereich des laufenden Bauleiter-Aufrufs; None außerhalb oder ohne Sandbox."""
    return _SCOPE if active() and cli_sandbox_supported() else None


@contextlib.contextmanager
def builder_scope(work_path: Path, session_dir: Path):
    """Bauleiter-Aufrufe in diesem Block laufen im Container (nur CLIs aus SANDBOX_CLIS)."""
    global _SCOPE
    previous = _SCOPE
    _SCOPE = Scope(work_path, session_dir)
    try:
        yield _SCOPE
    finally:
        _SCOPE = previous


def describe() -> str:
    """Kurzbeschreibung für den Kopf des Laufs."""
    where = tr("Prüfbefehl und CLI-Bauleiter") if cli_sandbox_supported() else tr("Prüfbefehl (CLI-Bauleiter unter Windows nicht)")
    net = tr("Prüfbefehl mit Netz") if SETTINGS.sandbox_net else tr("Prüfbefehl ohne Netz")
    return f"🐳 {SETTINGS.sandbox} ({SETTINGS.sandbox_image}): {where}, {net}"


def warn_windows() -> None:
    """Unter Windows läuft nur der Prüfbefehl im Container."""
    if active() and not cli_sandbox_supported():
        say("⚠️  Sandbox unter Windows: nur der Prüfbefehl läuft im Container, ein CLI-Bauleiter weiter mit deinen Rechten.")
