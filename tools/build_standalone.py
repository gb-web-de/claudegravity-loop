#!/usr/bin/env python3
"""Baut das eigenständige Programm für dieses System und packt es für das Release.

Das Programm bringt sein eigenes Python mit (PyInstaller, nur zum Bauen nötig) und ist Loop, MCP-Server und
Installer zugleich (`tools/standalone.py`). Ergebnis in dist/:

  claudegravity-<system>.tar.gz   macOS und Linux (darin claudegravity/claudegravity)
  claudegravity-<system>.zip      Windows (darin claudegravity/claudegravity.exe)

Danach prüft der Bau das Programm: Version, Hilfe, Trockenlauf, Handshake des MCP-Servers und Installer im Trockenlauf.

Aufruf:  python -m pip install pyinstaller==6.22.3
         python tools/build_standalone.py [--expect linux-x86_64] [--smoke <programm>]
"""

import argparse
import io
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from claudegravity import __version__  # noqa: E402

# Daten, die der Installer des Programms an die Clients verteilt
DATA_DIRS = ("skills", "commands")
README = """ClaudeGravity Loop {version} – eigenständiges Programm ({target})

Installieren (legt die Befehle an und trägt den MCP-Server in alle gefundenen Clients ein):
  {install}
Danach in einem neuen Terminal:
  claudegravity --info
  claudegravity "Aufgabe" -p <projekt>
Entfernen: claudegravity install --uninstall

Doku: https://github.com/gb-web-de/claudegravity-loop/blob/main/docs/de/installation.md
English: https://github.com/gb-web-de/claudegravity-loop/blob/main/docs/en/installation.md
"""


def target_name(system: str | None = None, machine: str | None = None) -> str:
    """Systemkennung im Dateinamen, z. B. linux-x86_64, linux-arm64, macos-arm64, windows-x86_64."""
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    os_name = {"darwin": "macos", "windows": "windows", "linux": "linux"}.get(system)
    arch = {"x86_64": "x86_64", "amd64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}.get(machine)
    if not os_name or not arch:
        raise SystemExit(f"Nicht unterstütztes System: {system} {machine}")
    return f"{os_name}-{arch}"


def program_file(target: str) -> str:
    """Dateiname des Programms im Archiv."""
    return "claudegravity.exe" if target.startswith("windows") else "claudegravity"


def archive_name(target: str) -> str:
    """Name des Release-Archivs (ohne Version, damit …/releases/latest/download/<name> immer passt)."""
    return f"claudegravity-{target}.zip" if target.startswith("windows") else f"claudegravity-{target}.tar.gz"


def pyinstaller_args(work: Path) -> list[str]:
    """Aufruf von PyInstaller: eine Datei, Paket claudegravity vollständig, Server und Installer dabei."""
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--console",
        "--noconfirm",
        "--clean",
        "--name",
        "claudegravity",
        "--paths",
        str(ROOT),
        "--collect-submodules",
        "claudegravity",
        "--hidden-import",
        "mcp_server",
        "--hidden-import",
        "install",
        "--distpath",
        str(work / "dist"),
        "--workpath",
        str(work / "build"),
        "--specpath",
        str(work),
    ]
    for name in DATA_DIRS:
        args += ["--add-data", f"{ROOT / name}{os.pathsep}{name}"]
    return args + [str(ROOT / "tools" / "standalone.py")]


def package(binary: Path, target: str, out_dir: Path) -> Path:
    """Programm mit README in ein Archiv packen; Inhalt liegt im Ordner claudegravity/."""
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / archive_name(target)
    windows = target.startswith("windows")
    install = r"claudegravity\claudegravity.exe install" if windows else "./claudegravity/claudegravity install"
    readme = README.format(version=__version__, target=target, install=install)
    name = program_file(target)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(binary, f"claudegravity/{name}")
            zf.writestr("claudegravity/README.txt", readme.replace("\n", "\r\n"))
    else:
        with tarfile.open(archive, "w:gz") as tf:
            info = tf.gettarinfo(str(binary), f"claudegravity/{name}")
            info.mode, info.uid, info.gid, info.uname, info.gname = 0o755, 0, 0, "", ""
            with binary.open("rb") as fh:
                tf.addfile(info, fh)
            data = readme.encode("utf-8")
            info = tarfile.TarInfo("claudegravity/README.txt")
            info.size, info.mode, info.mtime = len(data), 0o644, int(binary.stat().st_mtime)
            tf.addfile(info, io.BytesIO(data))
    return archive


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Befehl ausführen und bei Fehler mit Ausgabe abbrechen."""
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, **kwargs)
    if res.returncode != 0:
        raise SystemExit(f"[!] {' '.join(cmd)} → {res.returncode}\n{res.stdout[-3000:]}\n{res.stderr[-3000:]}")
    return res


def mcp_handshake(program: list[str], env: dict) -> dict:
    """MCP-Server starten wie ein Client: initialize, tools/list, claudegravity_info."""
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "smoke", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "claudegravity_info", "arguments": {}}},
    ]
    res = run(program, input="\n".join(json.dumps(r) for r in requests) + "\n", env=env)
    responses = {r.get("id"): r for r in (json.loads(line) for line in res.stdout.splitlines() if line.strip())}
    if 2 not in responses or not responses[2]["result"]["tools"] or responses.get(3, {}).get("result", {}).get("isError"):
        raise SystemExit(f"[!] MCP-Handshake fehlgeschlagen:\n{res.stdout[-2000:]}\n{res.stderr[-2000:]}")
    return responses


def smoke(binary: Path) -> None:
    """Fertiges Programm prüfen, ohne etwas zu installieren oder ein Modell aufzurufen."""
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        project = Path(tmp) / "projekt"
        home.mkdir()
        project.mkdir()
        env = dict(
            os.environ,
            HOME=str(home),
            USERPROFILE=str(home),
            APPDATA=str(home / "AppData" / "Roaming"),
            LOCALAPPDATA=str(home / "AppData" / "Local"),
            CLAUDEGRAVITY_NO_BROWSER="1",
            PYTHONIOENCODING="utf-8",
        )
        version = run([str(binary), "--version"], env=env).stdout.strip()
        if version != f"claudegravity {__version__}":
            raise SystemExit(f"[!] Version: {version!r} statt claudegravity {__version__}")
        run([str(binary), "--help"], env=env)
        # Eigener Endpunkt (nicht erreichbar), damit der Trockenlauf ohne installierte KI-CLIs eine Belegung hat
        endpoint = "http://127.0.0.1:9/v1"
        dry = run([str(binary), "Hallo Welt ausgeben", "-p", str(project), "--endpoint", endpoint, "--dry-run"], env=env, cwd=tmp)
        if "claudegravity" not in dry.stdout:
            raise SystemExit(f"[!] Trockenlauf ohne Befehl:\n{dry.stdout[-2000:]}")
        mcp_handshake([str(binary), "mcp"], env)
        installer = run([str(binary), "install", "--dry-run", "--all-clients"], env=env).stdout
        if "Trockenlauf beendet" not in installer or str(home) not in installer:
            raise SystemExit(f"[!] Installer im Trockenlauf:\n{installer[-2000:]}")
    print(f"[+] {binary}: Version, Hilfe, Trockenlauf, MCP-Handshake und Installer in Ordnung")


def build(out_dir: Path) -> Path:
    """Programm bauen, prüfen und packen; liefert das Archiv."""
    target = target_name()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        run(pyinstaller_args(work), cwd=tmp)
        binary = work / "dist" / program_file(target)
        smoke(binary)
        archive = package(binary, target, out_dir)
    print(f"[+] {archive} ({archive.stat().st_size // (1024 * 1024)} MB)")
    return archive


def main() -> int:
    """Kommandozeile."""
    parser = argparse.ArgumentParser(description="Eigenständiges Programm für dieses System bauen und packen")
    parser.add_argument("--out", default=str(ROOT / "dist"), help="Zielordner (Standard: dist/)")
    parser.add_argument("--expect", default=None, help="Abbrechen, wenn das System nicht diese Kennung hat (CI)")
    parser.add_argument("--smoke", default=None, metavar="PROGRAMM", help="Nur ein fertiges Programm prüfen")
    args = parser.parse_args()
    if args.smoke:
        smoke(Path(args.smoke).resolve())
        return 0
    if args.expect and args.expect != target_name():
        raise SystemExit(f"[!] System {target_name()} statt {args.expect}")
    build(Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
