"""Repo-Karte: Dateien des Projekts mit ihren wichtigsten Symbolen, für Rollen ohne eigenen Dateizugriff.

Endpunkte (Ollama, LM Studio, eigene Server) sehen das Projekt nicht. Statt ganzer Dateien bekommen sie eine
knappe Übersicht: Pfad und die Namen von Klassen und Funktionen, nach Bezug zur Aufgabe sortiert und auf
`REPO_MAP_LIMIT` Zeichen begrenzt. Nur Standardbibliothek; Python wird per `ast` gelesen, andere Sprachen per Regex.
"""

import ast
import os
import re
import subprocess
from pathlib import Path

from .common import ENDPOINT_BINARIES, SETTINGS
from .safety import is_sensitive_path

REPO_MAP_LIMIT = 6000
REPO_MAP_MODES = ("auto", "an", "aus")
MAX_FILE_BYTES = 200_000
MAX_FILES = 3000
SKIP_DIRS = {
    ".git",
    ".dual-loop",
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "dist",
    "build",
    "target",
    "logs",
    ".idea",
    ".vscode",
    ".next",
    ".cache",
    "coverage",
}
BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".mov",
    ".so",
    ".dll",
    ".exe",
    ".pyc",
    ".lock",
    ".min.js",
}
# Je Sprache: Muster für Deklarationen; die erste Gruppe ist die Art (class, def …), die zweite der Name
SYMBOL_PATTERNS = {
    (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"): [
        r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?(class|interface|enum)\s+([A-Za-z_$][\w$]*)",
        r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(function)\*?\s+([A-Za-z_$][\w$]*)",
        r"^\s*(?:export\s+)?(type)\s+([A-Za-z_$][\w$]*)\s*=",
        r"^\s*export\s+(const|let)\s+([A-Za-z_$][\w$]*)\s*=",
    ],
    (".php",): [
        r"^\s*(?:final\s+|abstract\s+|readonly\s+)*(class|interface|trait|enum)\s+(\w+)",
        r"^\s*(?:public\s+|protected\s+|private\s+|static\s+|final\s+|abstract\s+)*(function)\s+&?(\w+)",
    ],
    (".go",): [r"^(func)\s+(?:\([^)]*\)\s*)?(\w+)", r"^(type)\s+(\w+)\s+(?:struct|interface)"],
    (".rs",): [r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(fn|struct|enum|trait|mod)\s+(\w+)"],
    (".java", ".kt", ".cs", ".scala", ".swift"): [
        r"^\s*(?:(?:public|private|protected|internal|static|final|abstract|sealed|data|open|partial)\s+)*(class|interface|enum|record|object|struct)\s+(\w+)",
        r"^\s*(?:(?:public|private|protected|internal|static|final|override|suspend)\s+)*(fun|func)\s+(\w+)",
    ],
    (".rb",): [r"^\s*(class|module|def)\s+([\w.:?!]+)"],
    (".c", ".h", ".cpp", ".hpp", ".cc"): [r"^\s*(class|struct)\s+(\w+)\s*[{:]", r"^[A-Za-z_][\w\s\*&:<>,]*?\s(\w+)\s*\([^;]*\)\s*\{?\s*$"],
    (".sh", ".bash"): [r"^\s*(function)\s+(\w+)", r"^\s*(\w+)\s*\(\)\s*\{"],
}
WORD = re.compile(r"[A-Za-zÄÖÜäöüß_][\wÄÖÜäöüß]{2,}")
STOPWORDS = {"und", "oder", "der", "die", "das", "the", "and", "for", "mit", "eine", "einen", "ein", "von", "test", "tests"}


def list_project_files(project_path: Path) -> list[str]:
    """Relative Pfade (mit /) der Projektdateien: über git (ohne Ignoriertes), sonst durch Ablaufen des Ordners."""
    files: list[str] = []
    try:
        res = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=project_path,
            capture_output=True,
            timeout=20,
        )
        if res.returncode == 0:
            files = [f for f in res.stdout.decode("utf-8", errors="replace").split("\0") if f]
    except (OSError, subprocess.SubprocessError):
        files = []
    if not files:
        for root, dirs, names in os.walk(project_path):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            rel_root = Path(root).relative_to(project_path)
            files += [(rel_root / n).as_posix() for n in sorted(names)]
            if len(files) > MAX_FILES:
                break
    keep = []
    for rel in files:
        parts = rel.split("/")
        if any(p in SKIP_DIRS for p in parts[:-1]) or is_sensitive_path(rel):
            continue
        if any(rel.lower().endswith(s) for s in BINARY_SUFFIXES):
            continue
        keep.append(rel)
    return keep[:MAX_FILES]


def python_symbols(source: str) -> list[str]:
    """Klassen (mit Methoden) und Funktionen der obersten Ebene, Funktionen mit Parameternamen."""

    def signature(fn) -> str:
        names = [a.arg for a in fn.args.posonlyargs + fn.args.args if a.arg not in ("self", "cls")]
        if fn.args.vararg:
            names.append("*" + fn.args.vararg.arg)
        names += [a.arg for a in fn.args.kwonlyargs]
        if fn.args.kwarg:
            names.append("**" + fn.args.kwarg.arg)
        return f"{fn.name}({', '.join(names)})"

    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return [f"def {m}" for m in re.findall(r"^def\s+(\w+)", source, re.MULTILINE)]
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append("def " + signature(node))
        elif isinstance(node, ast.ClassDef):
            methods = [m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("__")]
            out.append(f"class {node.name}" + (f" [{', '.join(methods)}]" if methods else ""))
    return out


def file_symbols(rel: str, source: str) -> list[str]:
    """Symbole einer Datei je nach Sprache; leer für Dateien ohne bekannte Sprache."""
    lower = rel.lower()
    if lower.endswith((".py", ".pyi")):
        return python_symbols(source)
    for suffixes, patterns in SYMBOL_PATTERNS.items():
        if lower.endswith(suffixes):
            found: list[str] = []
            for line in source.splitlines():
                for pattern in patterns:
                    m = re.match(pattern, line)
                    if m:
                        kind, name = (m.group(1), m.group(2)) if m.lastindex and m.lastindex >= 2 else ("fn", m.group(1))
                        entry = f"{kind} {name}"
                        if entry not in found:
                            found.append(entry)
                        break
            return found
    return []


def focus_words(text: str) -> set[str]:
    """Wörter aus Aufgabe/Etappe, nach denen Dateien und Symbole sortiert werden (klein, ohne Füllwörter)."""
    words = set()
    for w in WORD.findall(text or ""):
        low = w.lower()
        if low not in STOPWORDS:
            words.add(low)
            words.update(p for p in re.split(r"_|(?<=[a-z])(?=[A-Z])", w) if len(p) > 2 and p.lower() not in STOPWORDS)
    return {w.lower() for w in words}


def score_file(rel: str, symbols: list[str], focus: set[str], mentioned: set[str]) -> int:
    """Bezug zur Aufgabe: genannte Datei zuerst, dann Treffer im Pfad, dann Treffer in Symbolnamen."""
    score = 100 if rel in mentioned or Path(rel).name in mentioned else 0
    path_words = set(re.split(r"[/_.\-]", rel.lower()))
    score += 10 * len(focus & path_words)
    symbol_words = {w.lower() for s in symbols for w in re.split(r"[\s\[\](),_]+", s) if w}
    score += 2 * len(focus & symbol_words)
    return score


def repo_map(project_path: Path, focus: str = "", limit: int = REPO_MAP_LIMIT) -> str:
    """Repo-Karte als Text: eine Zeile je Datei `pfad: symbol, symbol …`, nach Bezug zu `focus` sortiert.
    Leer, wenn das Projekt keine lesbaren Dateien hat. Hält `limit` Zeichen ein und nennt, was fehlt."""
    files = list_project_files(project_path)
    if not files:
        return ""
    words = focus_words(focus)
    mentioned = {m.strip("`") for m in re.findall(r"`?((?:[\w.-]+/)*[\w-]+\.[A-Za-z0-9]{1,8})`?", focus or "")}
    entries = []
    for rel in files:
        path = project_path / rel
        symbols: list[str] = []
        try:
            if path.is_file() and path.stat().st_size <= MAX_FILE_BYTES:
                raw = path.read_bytes()
                if b"\0" not in raw[:2048]:
                    symbols = file_symbols(rel, raw.decode("utf-8", errors="replace"))
        except OSError:
            continue
        entries.append((score_file(rel, symbols, words, mentioned), rel.count("/"), rel, symbols))
    entries.sort(key=lambda e: (-e[0], e[1], e[2]))
    lines, used = [], 0
    for index, (_score, _depth, rel, symbols) in enumerate(entries):
        # Erst die passendsten Dateien mit Symbolen, danach nur noch Pfade, damit die Karte das ganze Projekt zeigt
        if symbols and used < limit * 0.7:
            line = rel + ": " + ", ".join(symbols)
            if len(line) > 300:
                line = line[:299] + "…"
        else:
            line = rel
        # Platz für den Schlusshinweis lassen, damit die Karte `limit` sicher einhält
        if used + len(line) + 1 > limit - 50:
            lines.append(f"(… {len(entries) - index} weitere Dateien ausgelassen)")
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


def wants_repo_map(binary: str) -> bool:
    """Ob eine Rolle mit diesem Programm die Repo-Karte bekommt (--repo-map: auto nur Endpunkte, an alle, aus keine)."""
    mode = SETTINGS.repo_map
    return mode == "an" or (mode == "auto" and binary in ENDPOINT_BINARIES)


def repo_map_block(text: str) -> str:
    """Repo-Karte mit Überschrift für einen Prompt; leer, wenn es keine Karte gibt."""
    if not text:
        return ""
    return (
        "--- REPO-KARTE (Dateien mit Klassen und Funktionen; Inhalte der genannten Dateien folgen, wo nötig) ---\n"
        f"{text}\n--- ENDE REPO-KARTE ---\n\n"
    )
