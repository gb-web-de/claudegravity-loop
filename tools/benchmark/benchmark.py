#!/usr/bin/env python3
"""Benchmark-Pack: feste Aufgaben mit mehreren Strategien laufen lassen und die Kennzahlen vergleichen.

Jede Aufgabe unter tasks/<name>/ hat task.txt (Aufgabentext), project/ (Startstand mit Tests, die
anfangs rot sind) und solution/ (nur für --fake). Pro Aufgabe und Strategie wird project/ in einen
leeren Ordner kopiert, als Git-Repository angelegt und `loop.py` mit `--plan-auto` und dem Prüfbefehl
`python -m unittest discover -s tests` gestartet. Ergebnis: Tabelle (Markdown) und JSON mit den
Kennzahlen aus `.done` bzw. `AUDIT.md`.

Gezählt wird ein Lauf nur, wenn danach auch die **Original-Tests** der Aufgabe grün sind: Der Benchmark
kopiert tests/ aus dem Aufgabenpaket zurück und prüft erneut. Ein Bauleiter, der Tests abschwächt oder
löscht, besteht also nicht. Mit --baseline läuft dieselbe Aufgabe zum Vergleich mit einer einzigen CLI
ohne Loop (ein Aufruf mit Schreibrechten, danach dieselbe Prüfung).

Beispiele:
    python3 tools/benchmark/benchmark.py --strategies balanced,hybrid -- --yolo
    python3 tools/benchmark/benchmark.py --strategies balanced --baseline claude,codex --repeat 3 --out bench -- --yolo
    python3 tools/benchmark/benchmark.py --tasks median-bug --strategies eco -- --bauer codex --yolo
    python3 tools/benchmark/benchmark.py --fake          # ohne Modelle, prüft nur den Ablauf

Alles nach `--` geht unverändert an loop.py. CLI-Bauleiter brauchen Schreibrechte (`-- --yolo`);
die Aufgaben laufen in Wegwerf-Ordnern, nicht in deinem Projekt.
"""

import argparse
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TASKS_DIR = HERE / "tasks"
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402

PROOF = f'"{sys.executable}" -m unittest discover -s tests'


def list_tasks() -> list[str]:
    """Namen aller Aufgaben im Aufgabenordner (jeder Unterordner mit task.txt)."""
    return sorted(p.name for p in TASKS_DIR.iterdir() if (p / "task.txt").exists())


def task_text(task: str) -> str:
    """Aufgabentext aus task.txt."""
    return (TASKS_DIR / task / "task.txt").read_text(encoding="utf-8").strip()


def prepare_project(task: str, target: Path, git: bool = True) -> None:
    """Startstand der Aufgabe in einen leeren Ordner kopieren und als Git-Repository anlegen."""
    shutil.copytree(TASKS_DIR / task / "project", target)
    if git and shutil.which("git"):
        git = ["git", "-c", "user.name=benchmark", "-c", "user.email=benchmark@localhost"]
        for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "Startstand"]):
            subprocess.run(git + cmd, cwd=target, capture_output=True)


# ---------- Fake-Modus: ein OpenAI-kompatibler Server, der die Musterlösung liefert ----------
def fake_answer(prompt: str, solution: Path) -> str:
    if "leitende Software-Architekt" in prompt:
        return "# Plan\n\n1. Funktion umsetzen\n2. Tests grün machen\n"
    if "Führe den genehmigten Plan" in prompt:
        blocks = [
            f"```filepath: {p.relative_to(solution).as_posix()}\n{p.read_text(encoding='utf-8')}```"
            for p in sorted(solution.rglob("*"))
            if p.is_file()
        ]
        done = re.search(r"unter: '([^']+)'", prompt)
        if done:
            blocks.append(f"```filepath: {done.group(1)}\nfertig\n```")
        return "\n\n".join(blocks)
    return "BEFUNDE:\n- keine\nVERDICT: APPROVED"


def start_fake_server(state: dict) -> tuple[http.server.HTTPServer, str]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = fake_answer(req["messages"][-1]["content"], state["solution"])
            body = json.dumps(
                {"choices": [{"message": {"content": out}}], "usage": {"prompt_tokens": 100, "completion_tokens": 20}}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/v1"


def fake_args(url: str) -> list[str]:
    return [
        "--architekt-endpoint",
        url,
        "--architekt",
        "architekt_ep",
        "--architekt-model",
        "planer",
        "--pruefstatiker-endpoint",
        url,
        "--pruefstatiker",
        "pruefstatiker_ep",
        "--pruefstatiker-model",
        "pruefer",
        "--bauer-endpoint",
        url,
        "--bauer",
        "bauer_ep",
        "--bauer-model",
        "bauer",
        "--abnahme",
        "pruefstatiker_ep",
        "--etappen",
        "aus",
    ]


def fake_env(tmp: Path) -> dict:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("CLAUDEGRAVITY_") and k not in ("OPENAI_BASE_URL", "AI_ENDPOINT", "OLLAMA_HOST")
    }
    (tmp / "leer").mkdir(exist_ok=True)
    env.update(PATH=str(tmp / "leer"), OLLAMA_HOST="127.0.0.1:9", PYTHONIOENCODING="utf-8", CLAUDEGRAVITY_CONFIG_DIR=str(tmp / "config"))
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return env


def check_original_tests(task: str, project: Path, timeout: int = 300) -> bool:
    """Original-Tests aus dem Aufgabenpaket zurückkopieren und laufen lassen; geänderte Tests zählen nicht."""
    original = TASKS_DIR / task / "project" / "tests"
    if not original.is_dir() or not project.is_dir():
        return False
    shutil.rmtree(project / "tests", ignore_errors=True)
    shutil.copytree(original, project / "tests")
    ok, _ = loop.run_proof(PROOF, project, timeout=timeout)
    return ok


# ---------- Ein Lauf ----------
def run_one(
    task: str,
    strategy: str,
    extra: list[str],
    tmp: Path,
    timeout: int,
    fake_url: str | None = None,
    out_dir: Path | None = None,
    run: int = 1,
) -> dict:
    """Aufgabe einmal mit dem Loop und einer Strategie lösen lassen; liefert die Kennzahlen."""
    name = f"{task}-{strategy}" + (f"-{run}" if run > 1 else "")
    project = tmp / name
    prepare_project(task, project, git=not fake_url)
    cmd = [
        sys.executable,
        str(ROOT / "loop.py"),
        task_text(task),
        "-p",
        str(project),
        "--strategy",
        strategy,
        "--plan-auto",
        "--no-guide",
        "--log-format",
        "json",
        "--proof",
        PROOF,
        "-d",
        "0",
    ]
    # Wegwerf-Ordner: direkt darin bauen, damit die Original-Tests das Ergebnis sehen (nicht einen Worktree-Branch)
    cmd.append("--no-worktree")
    if fake_url:
        cmd += fake_args(fake_url)
    cmd += extra
    env = fake_env(tmp) if fake_url else None
    started = time.monotonic()
    try:
        res = subprocess.run(cmd, input="", capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
        returncode, stdout = res.returncode, res.stdout + res.stderr
    except subprocess.TimeoutExpired as exc:
        returncode, stdout = None, f"Zeitlimit {timeout} s überschritten\n{exc.stdout or ''}"
    sessions = sorted((project / ".dual-loop" / "sessions").glob("*")) if (project / ".dual-loop").exists() else []
    kpi = loop.read_session_kpi(sessions[-1]) if sessions else None
    wall = round(time.monotonic() - started, 1)
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{name}.log").write_text(stdout, encoding="utf-8")
    loop_ok = bool(kpi and kpi.get("success"))
    tests_ok = check_original_tests(task, project) if loop_ok else False
    return {
        "task": task,
        "strategy": strategy,
        "run": run,
        "returncode": returncode,
        "wall_s": wall,
        "success": loop_ok and tests_ok,
        "loop_success": loop_ok,
        "original_tests": tests_ok,
        "build_rounds": kpi.get("build_rounds") if kpi else None,
        "tokens_total": kpi.get("tokens_total") if kpi else None,
        "cost_usd_task": kpi.get("cost_usd_task") if kpi else None,
        "rework_rate": kpi.get("rework_rate") if kpi else None,
        "escalation": (kpi or {}).get("escalation"),
        "abort_reason": (kpi or {}).get("abort_reason")
        or (None if kpi else "keine Kennzahlen (Lauf vorzeitig beendet)")
        or (None if tests_ok or not loop_ok else "Original-Tests rot (Tests geändert?)"),
    }


def baseline_prompt(task: str) -> str:
    """Auftrag für den Vergleichslauf ohne Loop: dieselbe Aufgabe, derselbe Prüfbefehl."""
    return (
        f"{task_text(task)}\n\nArbeite direkt im aktuellen Ordner. Prüfe dein Ergebnis mit "
        "`python -m unittest discover -s tests` und arbeite weiter, bis alle Tests grün sind."
    )


def run_baseline(task: str, cli: str, tmp: Path, timeout: int, agents: dict, out_dir: Path | None = None, run: int = 1) -> dict:
    """Vergleichslauf: eine einzige CLI löst die Aufgabe in einem Aufruf mit Schreibrechten, ohne Plan, Review und Abnahme."""
    strategy = f"allein:{cli}"
    name = f"{task}-allein-{cli}" + (f"-{run}" if run > 1 else "")
    project = tmp / name
    prepare_project(task, project)
    metrics = loop.SessionMetrics()
    agent = loop.create_agent(cli, agents, role="Bauleiter", metrics_tracker=metrics)
    started = time.monotonic()
    saved = os.environ.get("CLAUDEGRAVITY_CLI_TIMEOUT")
    os.environ["CLAUDEGRAVITY_CLI_TIMEOUT"] = str(timeout)
    error = None
    try:
        output = agent.run(baseline_prompt(task), cwd=project, extra_flags=loop.get_permission_flags(agent.binary))
    except Exception as exc:  # ein Fehler der CLI ist ein Ergebnis, kein Absturz des Benchmarks
        output, error = "", f"{type(exc).__name__}: {exc}"
    finally:
        if saved is None:
            os.environ.pop("CLAUDEGRAVITY_CLI_TIMEOUT", None)
        else:
            os.environ["CLAUDEGRAVITY_CLI_TIMEOUT"] = saved
    wall = round(time.monotonic() - started, 1)
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{name}.log").write_text(error or output, encoding="utf-8")
    tests_ok = False if error else check_original_tests(task, project)
    return {
        "task": task,
        "strategy": strategy,
        "run": run,
        "returncode": None,
        "wall_s": wall,
        "success": tests_ok,
        "loop_success": None,
        "original_tests": tests_ok,
        "build_rounds": 1,
        "tokens_total": metrics.total_tokens or None,
        "cost_usd_task": metrics.cost_usd or None,
        "rework_rate": None,
        "escalation": None,
        "abort_reason": error[:200] if error else (None if tests_ok else "Original-Tests rot"),
    }


def format_table(results: list[dict]) -> str:
    lines = [
        "| Aufgabe | Strategie | Ergebnis | Original-Tests | Bau-Runden | Tokens | Kosten (gemeldet) | Dauer |",
        "| :--- | :--- | :--- | :---: | ---: | ---: | ---: | ---: |",
    ]
    for r in results:
        verdict = "✅" if r["success"] else f"❌ {r['abort_reason'] or ''}".strip()
        if r.get("escalation"):
            verdict += f" (eskaliert zu {r['escalation'].get('to')})"
        tokens = loop.format_budget("tokens", r["tokens_total"]) if r["tokens_total"] else "–"
        cost = loop.format_budget("usd", r["cost_usd_task"]) if r["cost_usd_task"] else "–"
        lines.append(
            f"| {r['task']} | {r['strategy']} | {verdict} | {'✅' if r.get('original_tests') else '❌'} "
            f"| {r['build_rounds'] if r['build_rounds'] is not None else '–'} "
            f"| {tokens} | {cost} | {loop.format_duration(r['wall_s'])} |"
        )
    by_strategy: dict[str, list[dict]] = {}
    for r in results:
        by_strategy.setdefault(r["strategy"], []).append(r)
    lines += [
        "",
        "| Strategie | Erfolg | Quote | Ø Tokens je Erfolg | Kosten gesamt | Ø Dauer |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for strategy, rows in by_strategy.items():
        ok = sum(r["success"] for r in rows)
        tokens = sum(r["tokens_total"] or 0 for r in rows)
        cost = sum(r["cost_usd_task"] or 0 for r in rows)
        per_success = loop.format_budget("tokens", tokens / ok) if tokens and ok else "–"
        avg_wall = loop.format_duration(sum(r["wall_s"] for r in rows) / len(rows))
        lines.append(
            f"| {strategy} | {ok}/{len(rows)} | {round(100 * ok / len(rows))} % | {per_success} "
            f"| {loop.format_budget('usd', cost) if cost else '–'} | {avg_wall} |"
        )
    return "\n".join(lines)


def report_line(result: dict) -> None:
    """Kurzmeldung nach jedem Lauf."""
    mark = "✅" if result["success"] else "❌"
    print(f"  {mark} {result['build_rounds']} Bau-Runden, {result['wall_s']} s {result['abort_reason'] or ''}".rstrip(), flush=True)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    extra = argv[argv.index("--") + 1 :] if "--" in argv else []
    own = argv[: argv.index("--")] if "--" in argv else argv
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tasks", default="all", help=f"Kommagetrennt oder all ({', '.join(list_tasks())})")
    parser.add_argument("--strategies", default="balanced", help="Kommagetrennt, z. B. balanced,hybrid,eco")
    parser.add_argument("--timeout", type=int, default=1800, help="Sekunden je Lauf (Standard: 1800)")
    parser.add_argument("--out", default=None, help="Ordner für results.json, results.md und die Logs je Lauf")
    parser.add_argument("--fake", action="store_true", help="Ohne Modelle: ein lokaler Fake-Server liefert die Musterlösung")
    parser.add_argument("--baseline", default="", help="Vergleich ohne Loop, kommagetrennte CLIs (z. B. claude,codex)")
    parser.add_argument("--repeat", type=int, default=1, help="Jeden Lauf so oft wiederholen (Streuung der Modelle)")
    parser.add_argument("--tasks-dir", default=None, help="Eigenes Aufgabenpaket statt tools/benchmark/tasks")
    args = parser.parse_args(own)
    if args.tasks_dir:
        global TASKS_DIR
        TASKS_DIR = Path(args.tasks_dir).expanduser().resolve()

    tasks = list_tasks() if args.tasks == "all" else [t.strip() for t in args.tasks.split(",") if t.strip()]
    unknown = [t for t in tasks if t not in list_tasks()]
    if unknown:
        parser.error(f"Unbekannte Aufgabe(n): {', '.join(unknown)}")
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    baselines = [b.strip() for b in args.baseline.split(",") if b.strip()]
    out_dir = Path(args.out) if args.out else None
    agents = {}
    if baselines:
        if args.fake:
            parser.error("--baseline braucht echte CLIs und geht nicht mit --fake")
        agents = loop.detect_installed_agents()
        missing = [b for b in baselines if b not in agents]
        if missing:
            parser.error(f"Nicht gefunden: {', '.join(missing)}")

    results = []
    with tempfile.TemporaryDirectory(prefix="cg-benchmark-") as tmp_name:
        tmp = Path(tmp_name)
        fake_state: dict = {}
        server = None
        if args.fake:
            server, url = start_fake_server(fake_state)
        try:
            for task in tasks:
                for run in range(1, max(1, args.repeat) + 1):
                    for strategy in strategies:
                        print(f"▶ {task} · {strategy} ...", flush=True)
                        fake_state["solution"] = TASKS_DIR / task / "solution"
                        fake_url = url if args.fake else None
                        result = run_one(task, strategy, extra, tmp, args.timeout, fake_url=fake_url, out_dir=out_dir, run=run)
                        report_line(result)
                        results.append(result)
                    for cli in baselines:
                        print(f"▶ {task} · allein:{cli} ...", flush=True)
                        result = run_baseline(task, cli, tmp, args.timeout, agents, out_dir=out_dir, run=run)
                        report_line(result)
                        results.append(result)
        finally:
            if server:
                server.shutdown()
                server.server_close()

    table = format_table(results)
    print("\n" + table)
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        (out_dir / "results.md").write_text(table + "\n", encoding="utf-8")
    return 0 if all(r["success"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
