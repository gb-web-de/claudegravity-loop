#!/usr/bin/env python3
"""Baut die Claude-Desktop-Erweiterung `dist/claudegravity-<version>.mcpb` (MCP Bundle, ein ZIP mit manifest.json).

Inhalt: mcpb/manifest.json, mcpb/icon.png, mcpb/launch.sh, mcp_server.py, loop.py, das Paket claudegravity/ und LICENSE.
Version und Tool-Liste im Manifest müssen zu claudegravity.__version__ und mcp_server.MCP_TOOLS passen, sonst bricht
der Bau ab. Das ZIP ist reproduzierbar (feste Zeitstempel, sortierte Einträge). Nur Standardbibliothek.

Aufruf:  python tools/build_mcpb.py [--out dist] [--check]
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mcp_server  # noqa: E402
from claudegravity import __version__  # noqa: E402

MANIFEST = ROOT / "mcpb" / "manifest.json"
BUNDLE_FILES = {
    "manifest.json": ROOT / "mcpb" / "manifest.json",
    "icon.png": ROOT / "mcpb" / "icon.png",
    "launch.sh": ROOT / "mcpb" / "launch.sh",
    "mcp_server.py": ROOT / "mcp_server.py",
    "loop.py": ROOT / "loop.py",
}
FIXED_TIME = (2020, 1, 1, 0, 0, 0)


def manifest_problems(manifest: dict) -> list[str]:
    """Abweichungen zwischen Manifest, Paketversion und den Tools des MCP-Servers."""
    problems = []
    if manifest.get("version") != __version__:
        problems.append(f"Version im Manifest {manifest.get('version')} ≠ Paket {__version__}")
    want = [(t["name"], t["description"]) for t in mcp_server.MCP_TOOLS]
    have = [(t.get("name"), t.get("description")) for t in manifest.get("tools", [])]
    if want != have:
        problems.append("Tools im Manifest passen nicht zu mcp_server.MCP_TOOLS (Namen oder Beschreibungen)")
    server = manifest.get("server", {})
    if server.get("entry_point") not in BUNDLE_FILES:
        problems.append(f"entry_point {server.get('entry_point')} fehlt im Bundle")
    return problems


def bundle_entries() -> list[tuple[str, Path]]:
    """(Pfad im Bundle, Quelldatei), sortiert; ohne Caches."""
    entries = list(BUNDLE_FILES.items())
    for path in sorted((ROOT / "claudegravity").rglob("*.py")):
        if "__pycache__" not in path.parts:
            entries.append((path.relative_to(ROOT).as_posix(), path))
    license_file = ROOT / "LICENSE"
    if license_file.exists():
        entries.append(("LICENSE", license_file))
    return sorted(entries)


def build(out_dir: Path) -> Path:
    """Bundle bauen und den Pfad liefern."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems = manifest_problems(manifest)
    if problems:
        raise SystemExit("mcpb/manifest.json: " + "; ".join(problems))
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"claudegravity-{__version__}.mcpb"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, source in bundle_entries():
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if name.endswith(".sh") else 0o644
            info.external_attr = (0o100000 | mode) << 16
            zf.writestr(info, source.read_bytes())
    return target


def main() -> int:
    """Kommandozeile: bauen oder mit --check nur prüfen."""
    parser = argparse.ArgumentParser(description="Claude-Desktop-Erweiterung (.mcpb) bauen")
    parser.add_argument("--out", default=str(ROOT / "dist"), help="Zielordner (Standard: dist/)")
    parser.add_argument("--check", action="store_true", help="Nur Manifest gegen Version und Tools prüfen")
    args = parser.parse_args()
    if args.check:
        problems = manifest_problems(json.loads(MANIFEST.read_text(encoding="utf-8")))
        for problem in problems:
            print(f"[!] {problem}", file=sys.stderr)
        return 1 if problems else 0
    target = build(Path(args.out))
    print(f"[+] {target} ({target.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
