#!/usr/bin/env python3
"""Echte Läufe: prüft jedes installierte Backend mit echten Modellen statt Attrappen.

Je Backend (claude, agy, gemini, codex, copilot, Ollama, LM Studio, eigener Endpunkt):
  antwort    Kurzer Prompt im Lesemodus, die Antwort muss das verlangte Wort enthalten.
  lesend     Die Lese-Flags (`get_readonly_flags`) halten: Die Bitte, eine Datei anzulegen, darf nichts schreiben.
  fortsetzen Nur claude, codex und copilot: Die zweite Anfrage setzt die Sitzung fort (`--resume`) und kennt die Zahl
             aus der ersten. Prüft damit auch die Argument-Reihenfolge von `codex exec ... resume <id>`.
  loop       Nur mit --full: ganzer Lauf auf der Benchmark-Aufgabe `median-bug` mit diesem Backend als Bauleiter.

Ergebnis: Tabelle im Terminal, mit --out zusätzlich realrun.md und realrun.json. Exit-Code 0 nur, wenn alle
Prüfungen bestanden sind. Läuft in Wegwerf-Ordnern, nie in deinem Projekt.

Beispiele:
    python3 tools/realrun.py                         # alle erkannten Backends, ohne vollen Lauf
    python3 tools/realrun.py --backends codex,ollama --full --out ~/realrun
"""

import argparse
import datetime
import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402

# Backends ohne eigene Sitzung bzw. ohne Lese-Modus bekommen die passenden Prüfungen nicht
RESUME_BACKENDS = {"claude", "codex", "copilot"}
READONLY_BACKENDS = {"claude", "codex", "agy", "gemini", "copilot"}
PROBE_FILE = "realrun-probe.txt"
MARKS = {True: "✅", False: "❌", None: "⏭"}


def load_benchmark():
    """Benchmark-Modul (tools/benchmark/benchmark.py) laden, ohne es als Paket zu installieren."""
    spec = importlib.util.spec_from_file_location("benchmark", ROOT / "tools" / "benchmark" / "benchmark.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def timed(fn) -> tuple[bool, str, float]:
    """Prüfung ausführen; Ausnahmen zählen als nicht bestanden. Liefert (ok, Detail, Sekunden)."""
    started = time.monotonic()
    try:
        ok, detail = fn()
    except Exception as exc:  # jede Ausnahme eines echten Backends ist ein Befund, kein Absturz
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    return ok, " ".join(str(detail).split())[:300], round(time.monotonic() - started, 1)


def check_answer(agent, cwd: Path) -> tuple[bool, str]:
    """Antwortet das Backend überhaupt (Anmeldung, Aufruf, Ausgabe-Format)?"""
    text = agent.run("Antworte nur mit dem Wort BANANE und sonst nichts.", cwd=cwd, extra_flags=loop.get_readonly_flags(agent.binary))
    return "BANANE" in text.upper(), text


def check_readonly(agent, cwd: Path) -> tuple[bool, str]:
    """Halten die Lese-Flags? Das Modell wird gebeten, eine Datei anzulegen; sie darf nicht entstehen."""
    probe = cwd / PROBE_FILE
    probe.unlink(missing_ok=True)
    agent.run(
        f"Lege im aktuellen Ordner die Datei {PROBE_FILE} mit dem Inhalt 'x' an. Benutze dafür deine Werkzeuge.",
        cwd=cwd,
        extra_flags=loop.get_readonly_flags(agent.binary),
    )
    if probe.exists():
        return False, f"{PROBE_FILE} wurde trotz Lesemodus geschrieben"
    return True, "nichts geschrieben"


def check_resume(agent, cwd: Path) -> tuple[bool, str]:
    """Setzt `--resume` die Sitzung wirklich fort? Die zweite Antwort muss die Zahl aus der ersten kennen."""
    flags = loop.get_readonly_flags(agent.binary)
    agent.run("Merke dir die Geheimzahl 4711. Antworte nur mit OK.", cwd=cwd, extra_flags=flags)
    resume = loop.builder_resume_flags(agent)
    if not resume:
        return False, "keine Sitzungs-ID gemeldet"
    text = agent.run("Wie lautet die Geheimzahl? Antworte nur mit der Zahl.", cwd=cwd, extra_flags=flags + resume)
    return "4711" in text, text


def check_loop(backend: str, tmp: Path, timeout: int, out_dir: Path | None) -> tuple[bool, str]:
    """Ganzer Lauf auf `median-bug` mit diesem Backend als Bauleiter (Schreibrechte nur im Wegwerf-Ordner)."""
    benchmark = load_benchmark()
    result = benchmark.run_one("median-bug", "balanced", ["--bauer", backend, "--yolo"], tmp / backend, timeout, out_dir=out_dir)
    detail = f"{result['build_rounds']} Bau-Runden, Rückgabe {result['returncode']}"
    if result.get("abort_reason"):
        detail += f", {result['abort_reason']}"
    return result["success"], detail


def run_checks(agents: dict, backends: list[str], full: bool, timeout: int, out_dir: Path | None) -> list[dict]:
    """Alle Prüfungen für die gewählten Backends; liefert eine Zeile je Prüfung."""
    results = []
    with tempfile.TemporaryDirectory(prefix="cg-realrun-") as tmp_name:
        tmp = Path(tmp_name)
        for backend in backends:
            cwd = tmp / backend
            cwd.mkdir()
            ready, status = loop.check_cli_auth(agents[backend].binary)
            if not ready:
                print(f"⏭  {backend}: {status}", flush=True)
                results.append({"backend": backend, "check": "bereit", "ok": None, "detail": status, "seconds": 0.0})
                continue
            checks = [("antwort", check_answer)]
            if backend in READONLY_BACKENDS:
                checks.append(("lesend", check_readonly))
            if backend in RESUME_BACKENDS:
                checks.append(("fortsetzen", check_resume))
            for name, fn in checks:
                agent = loop.create_agent(backend, agents, role="Prüfstatiker")
                print(f"▶ {backend} · {name} ...", flush=True)
                ok, detail, seconds = timed(lambda: fn(agent, cwd))
                print(f"  {'✅' if ok else '❌'} {detail[:120]}", flush=True)
                results.append({"backend": backend, "check": name, "ok": ok, "detail": detail, "seconds": seconds})
            if full:
                print(f"▶ {backend} · loop ...", flush=True)
                ok, detail, seconds = timed(lambda: check_loop(backend, tmp, timeout, out_dir))
                print(f"  {'✅' if ok else '❌'} {detail[:120]}", flush=True)
                results.append({"backend": backend, "check": "loop", "ok": ok, "detail": detail, "seconds": seconds})
    return results


def format_report(results: list[dict], when: datetime.datetime | None = None) -> str:
    """Markdown-Bericht: Kopf mit Zeitpunkt und Bilanz, danach eine Zeile je Prüfung."""
    when = when or datetime.datetime.now()
    ok = sum(r["ok"] is True for r in results)
    skipped = sum(r["ok"] is None for r in results)
    summary = f"{ok} von {len(results) - skipped} Prüfungen bestanden."
    if skipped:
        summary += f" {skipped} Backend(s) übersprungen, weil nicht bereit."
    lines = [
        f"# Echte Läufe {when:%Y-%m-%d %H:%M}",
        "",
        summary,
        "",
        "| Backend | Prüfung | Ergebnis | Dauer | Detail |",
        "| :--- | :--- | :---: | ---: | :--- |",
    ]
    for r in results:
        detail = r["detail"].replace("|", "\\|")[:160]
        lines.append(f"| {r['backend']} | {r['check']} | {MARKS[r['ok']]} | {r['seconds']} s | {detail} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backends", default="all", help="Kommagetrennt (z. B. claude,codex,ollama) oder all")
    parser.add_argument("--full", action="store_true", help="Zusätzlich ein ganzer Lauf je Backend als Bauleiter")
    parser.add_argument("--timeout", type=int, default=1800, help="Sekunden je vollem Lauf (Standard: 1800)")
    parser.add_argument("--out", default=None, help="Ordner für realrun.md, realrun.json und die Logs")
    args = parser.parse_args(argv)

    agents = loop.detect_installed_agents()
    agents.pop("ollama-cli", None)  # dieselben Modelle wie der Ollama-Endpunkt, nur langsamer
    wanted = sorted(agents) if args.backends == "all" else [b.strip() for b in args.backends.split(",") if b.strip()]
    missing = [b for b in wanted if b not in agents]
    if missing:
        print(f"Nicht gefunden: {', '.join(missing)} (erkannt: {', '.join(sorted(agents)) or 'keine'})", file=sys.stderr)
        wanted = [b for b in wanted if b in agents]
    if not wanted:
        print("Kein Backend zum Prüfen gefunden.", file=sys.stderr)
        return 2

    out_dir = Path(args.out).expanduser() if args.out else None
    results = run_checks(agents, wanted, args.full, args.timeout, out_dir)
    report = format_report(results)
    print("\n" + report)
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "realrun.md").write_text(report + "\n", encoding="utf-8")
        (out_dir / "realrun.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    passed = [r for r in results if r["ok"] is not None]
    return 0 if passed and all(r["ok"] for r in passed) and not missing else 1


if __name__ == "__main__":
    sys.exit(main())
