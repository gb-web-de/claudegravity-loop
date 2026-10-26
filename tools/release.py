#!/usr/bin/env python3
"""Bereitet ein GitHub-Release vor: prüft den Tag, legt die Installer-Skripte mit fester Version in dist/,
schreibt SHA256SUMS über alle Dateien in dist/ und die Release-Notizen (Deutsch und Englisch aus den CHANGELOGs).

Aufruf (im Release-Workflow, nachdem alle Programme in dist/ liegen):
  python tools/release.py v1.6.0 dist --notes release-notes.md
  python tools/release.py --check v1.6.0
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from claudegravity import __version__  # noqa: E402

REPO = "gb-web-de/claudegravity-loop"
INSTALLERS = ("claudegravity-install.sh", "claudegravity-install.ps1")
TAG_PLACEHOLDER = "__RELEASE_TAG__"


def check_tag(tag: str) -> None:
    """Der Tag muss genau v<Version des Pakets> sein."""
    if tag != f"v{__version__}":
        raise SystemExit(f"[!] Tag {tag} passt nicht zur Version {__version__} (erwartet v{__version__})")


def changelog_section(text: str, version: str) -> str:
    """Abschnitt `## [<version>]` eines CHANGELOGs ohne Überschrift; leer, wenn es ihn nicht gibt."""
    match = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.S | re.M)
    return match.group(1).strip() if match else ""


def stamp_installer(text: str, tag: str) -> str:
    """Installer-Skript auf die Version des Releases festlegen (Standard, solange CLAUDEGRAVITY_VERSION fehlt)."""
    if TAG_PLACEHOLDER not in text:
        raise SystemExit(f"[!] Platzhalter {TAG_PLACEHOLDER} fehlt im Installer-Skript")
    return text.replace(TAG_PLACEHOLDER, tag)


def sha256sums(dist: Path) -> str:
    """Inhalt von SHA256SUMS im Format von sha256sum: `<summe>  <datei>`, sortiert."""
    lines = []
    for path in sorted(p for p in dist.iterdir() if p.is_file() and p.name != "SHA256SUMS"):
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    return "\n".join(lines) + "\n"


def unix_label(assets: list[str]) -> str:
    """Systeme, für die das Release ein Programm für die Ein-Befehl-Installation unter macOS/Linux enthält."""
    names = {
        "macos-arm64": "macOS (Apple Silicon)",
        "macos-x86_64": "macOS (Intel)",
        "linux-x86_64": "Linux (x64)",
        "linux-arm64": "Linux (arm64, Raspberry Pi)",
    }
    return ", ".join(label for target, label in names.items() if f"claudegravity-{target}.tar.gz" in assets)


def notes(tag: str, assets: list[str]) -> str:
    """Release-Notizen: Installation in einem Befehl je System, Dateien, Änderungen auf Deutsch und Englisch."""
    base = f"https://github.com/{REPO}/releases/download/{tag}"
    de = changelog_section((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), __version__)
    en = changelog_section((ROOT / "CHANGELOG.en.md").read_text(encoding="utf-8"), __version__)
    wheel = next((a for a in assets if a.endswith(".whl")), None)
    rows = [
        (unix_label(assets), f"`curl -fsSL {base}/claudegravity-install.sh | sh`"),
        ("Windows (PowerShell)", f"`irm {base}/claudegravity-install.ps1 | iex`"),
        ("Claude Desktop", "`claudegravity.mcpb` herunterladen und doppelklicken · download and double-click"),
    ]
    if wheel:
        rows.append(("Python 3.10+ (pipx/uv)", f"`pipx install {base}/{wheel}`"))
    # In Tabellenzellen muss | auch in Code-Spannen maskiert sein
    rows = [(system, cmd.replace("|", "\\|")) for system, cmd in rows]
    lines = [
        "Fertige Programme ohne Python-Installation; der Befehl legt `claudegravity` an und trägt den MCP-Server in alle gefundenen Clients ein.",
        "Ready-made programs without a Python install; the command sets up `claudegravity` and registers the MCP server in every client it finds.",
        "",
        "| System | Installieren · Install |",
        "| :--- | :--- |",
        *[f"| {system} | {cmd} |" for system, cmd in rows],
        "",
        "Danach · then: `claudegravity --info` · Entfernen · remove: `claudegravity install --uninstall` · "
        f"[Installation (de)](https://github.com/{REPO}/blob/{tag}/docs/de/installation.md) · "
        f"[Installation (en)](https://github.com/{REPO}/blob/{tag}/docs/en/installation.md)",
        "",
        "Prüfsummen · checksums: `SHA256SUMS`. Die Programme sind nicht signiert; macOS und Windows warnen beim ersten Start aus dem Browser-Download, die Ein-Befehl-Installation nicht.",
        "",
    ]
    if de:
        lines += ["## Änderungen", "", de, ""]
    if en:
        lines += ["## Changes", "", en, ""]
    return "\n".join(lines)


def prepare(tag: str, dist: Path, notes_file: Path) -> list[str]:
    """Installer, SHA256SUMS und Notizen erzeugen; liefert die Dateien in dist/."""
    check_tag(tag)
    for name in INSTALLERS:
        text = (ROOT / "tools" / "release" / name).read_text(encoding="utf-8")
        (dist / name).write_text(stamp_installer(text, tag), encoding="utf-8", newline="\n" if name.endswith(".sh") else "\r\n")
    (dist / "SHA256SUMS").write_text(sha256sums(dist), encoding="utf-8", newline="\n")
    assets = sorted(p.name for p in dist.iterdir() if p.is_file())
    notes_file.write_text(notes(tag, assets), encoding="utf-8")
    return assets


def main() -> int:
    """Kommandozeile."""
    parser = argparse.ArgumentParser(description="GitHub-Release vorbereiten")
    parser.add_argument("tag", help="Versions-Tag, z. B. v1.6.0")
    parser.add_argument("dist", nargs="?", default=str(ROOT / "dist"), help="Ordner mit den Release-Dateien")
    parser.add_argument("--notes", default="release-notes.md", help="Ziel für die Release-Notizen")
    parser.add_argument("--check", action="store_true", help="Nur prüfen, ob der Tag zur Version passt")
    args = parser.parse_args()
    if args.check:
        check_tag(args.tag)
        return 0
    for name in prepare(args.tag, Path(args.dist), Path(args.notes)):
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
