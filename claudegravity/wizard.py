"""Einrichtung (claudegravity init), Erstlauf-Hinweis und Warnungen vor riskanten Einstellungen."""

import datetime
import json
import os
import platform
from pathlib import Path

from .common import CLOUD_PLANNER_ORDER, say
from .backends import is_private_endpoint
from .config import global_profile_path, load_profile, project_profile_path


# ==========================================
# Einrichtung (claudegravity init), geführter Erstlauf und Warnungen
# ==========================================
WIZARD_GOALS = {
    "1": ("schnell", "Schnell: Standard-Belegung, ein Lauf ohne Umwege"),
    "2": ("guenstig", "Günstig: Cloud nur für Plan und Abnahme, Bau lokal (falls vorhanden)"),
    "3": ("qualitaet", "Maximale Qualität: alle Rollen mit hohem Effort"),
}

PROOF_HINTS = [
    ("composer.json", "vendor/bin/phpunit"),
    ("phpunit.xml.dist", "vendor/bin/phpunit"),
    ("phpunit.xml", "vendor/bin/phpunit"),
    ("package.json", "npm test"),
    ("pytest.ini", "python3 -m pytest"),
    ("pyproject.toml", "python3 -m pytest"),
    ("go.mod", "go test ./..."),
    ("Cargo.toml", "cargo test"),
    ("tests", "python3 -m unittest discover -s tests"),
]


def suggest_proof_command(project_path: Path) -> str | None:
    """Rät den Prüfbefehl aus typischen Projektdateien; None, wenn nichts passt."""
    for marker, command in PROOF_HINTS:
        if (project_path / marker).exists():
            if marker == "pyproject.toml" and "pytest" not in (project_path / marker).read_text(encoding="utf-8", errors="ignore"):
                continue
            return command
    return None


def strategy_for_goal(goal: str, agents: dict) -> tuple[str, str]:
    """Strategie zum Ziel des Nutzers, abhängig davon, was installiert ist. Liefert (Strategie, Begründung)."""
    cloud = [k for k in CLOUD_PLANNER_ORDER if k in agents]
    local = [k for k, a in agents.items() if a.local]
    if goal == "qualitaet":
        return "best-code", "alle Phasen mit Effort high"
    if goal == "guenstig":
        if cloud and local:
            return "hybrid", f"{agents[cloud[0]].name} plant und nimmt ab, {agents[local[0]].name} prüft und baut"
        if local:
            return "local-free", f"Bau-Loop lokal mit {agents[local[0]].name}"
        return "eco", "kein lokales Modell gefunden, daher Sparmodelle und Effort medium"
    return "balanced", "ausgewogene Standard-Belegung"


def write_profile(path: Path, updates: dict) -> dict:
    """Übernimmt `updates` in ein bestehendes Profil (andere Schlüssel bleiben) und speichert es."""
    data, warnings = load_profile(path)
    if warnings:
        raise ValueError(warnings[0])
    data.update(updates)
    data["_erstellt_von"] = f"claudegravity init, {datetime.date.today().isoformat()}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def run_setup_wizard(project_path: Path, agents: dict, input_fn=input, global_path: Path | None = None) -> Path | None:
    """`claudegravity init`: erkennt Umgebung, fragt drei Dinge, schreibt ein Profil und zeigt den Startbefehl."""

    def ask(question: str, default: str, allowed: tuple[str, ...] | None = None) -> str:
        while True:
            try:
                answer = input_fn(f"{question} [{default}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                raise SystemExit("\nEinrichtung abgebrochen, nichts gespeichert.") from None
            answer = answer or default
            if not allowed or answer in allowed:
                return answer
            say(f"   Bitte eine der Möglichkeiten wählen: {', '.join(allowed)}")

    say("🧭 ClaudeGravity einrichten\n")
    say(f"🖥️  System : {platform.system()} {platform.release()}, Python {platform.python_version()}")
    say(f"📁 Projekt: {project_path}")
    cloud = [k for k in CLOUD_PLANNER_ORDER if k in agents]
    local = [k for k, a in agents.items() if a.local]
    say("🔍 Gefunden:")
    for key, agent in agents.items():
        say(f"   [x] {agent.name} (`{key}`, {'lokal' if agent.local else 'Cloud'})")
    if not agents:
        say("   (nichts) Installiere zuerst eine KI-CLI (z. B. `claude`, `codex`, `agy`) oder starte Ollama.")
        return None
    if len(cloud) + len(local) < 2:
        say("⚠️  Nur ein Anbieter gefunden: Architekt und Prüfstatiker wären dasselbe Modell, das sich selbst prüft.")
        say("   Besser: eine zweite CLI installieren oder Ollama/LM Studio starten.")

    say("\nWas ist dir am wichtigsten?")
    for key, (_, text) in WIZARD_GOALS.items():
        say(f"  [{key}] {text}")
    default_goal = "2" if local else "1"
    goal = WIZARD_GOALS[ask("Auswahl", default_goal, tuple(WIZARD_GOALS))][0]
    strategy, why = strategy_for_goal(goal, agents)
    say(f"   → Strategie `{strategy}`: {why}")

    suggested = suggest_proof_command(project_path)
    say("\nMit welchem Befehl prüft der Loop jede Bau-Runde selbst (Tests)? Ohne Prüfbefehl entscheidet nur die Abnahme.")
    proof = ask("Prüfbefehl (- für keinen)", suggested or "-")
    proof = None if proof.strip() == "-" else proof.strip()

    g_path = global_path or global_profile_path()
    p_path = project_profile_path(project_path)
    say("\nWo speichern? Das Projekt-Profil gilt nur hier und schlägt das globale.")
    say(f"  [1] Projekt: {p_path}")
    say(f"  [2] Global : {g_path}")
    where = ask("Auswahl", "1", ("1", "2"))
    target = p_path if where == "1" else g_path

    updates: dict = {"strategy": strategy}
    if proof:
        updates["proof"] = proof
    if strategy == "hybrid" or (strategy == "local-free" and local):
        updates["etappen"] = "auto"
    try:
        write_profile(target, updates)
    except (OSError, ValueError) as exc:
        say(f"❌ Profil nicht gespeichert: {exc}")
        return None

    say("\n" + "=" * 68)
    say(f"✅ Profil gespeichert: {target}")
    for key, value in updates.items():
        say(f"   {key} = {value}")
    say("\nSo geht es weiter:")
    say("  1. Erst ansehen, was passieren würde (legt nichts an):")
    say('     claudegravity --dry-run "Deine Aufgabe"')
    say("  2. Dann starten:")
    say('     claudegravity "Deine Aufgabe"')
    say("  Wirksame Einstellungen und ihre Herkunft: claudegravity --print-effective-config")
    say("=" * 68)
    return target


def unsafe_config_warnings(args, project_path: Path, git_repo: bool) -> list[str]:
    """Hinweise auf Einstellungen, bei denen Fehler teuer oder schwer rückgängig zu machen sind."""
    warnings: list[str] = []
    if args.yolo and not git_repo:
        warnings.append("⚠️  --yolo ohne Git: Der Bauleiter schreibt mit vollen Rechten, Änderungen lassen sich nicht per Git zurückholen.")
    elif args.yolo and not args.worktree:
        warnings.append("⚠️  --yolo mit --no-worktree: Der Bauleiter schreibt mit vollen Rechten direkt in deinen Arbeitsstand.")
    if not args.proof:
        warnings.append("ℹ️  Kein --proof: Der Loop führt keine Tests aus; über „fertig“ entscheidet nur die Abnahme.")
    if not args.inspect:
        warnings.append("⚠️  --no-inspect: Kein zweiter Anbieter prüft den fertigen Code.")
    if args.no_shield:
        warnings.append("⚠️  --no-shield: Zugangsdaten in Prompts gehen ungeschwärzt an Cloud-Modelle.")
    for ep in (args.endpoint, args.architekt_endpoint, args.pruefstatiker_endpoint, args.bauer_endpoint):
        if ep and ep.startswith("http://") and not is_private_endpoint(ep) and (args.api_key or os.environ.get("CLAUDEGRAVITY_API_KEY")):
            warnings.append(f"⚠️  API-Key wird unverschlüsselt (http://) an {ep} geschickt. Besser https:// verwenden.")
    return warnings


def first_run_guide(args, input_fn=input) -> str:
    """Erstlauf ohne Profil: Trockenlauf vorschlagen. Liefert dry-run, init, run oder quiet."""
    say("\n👋 Erster Lauf ohne Profil. Empfohlen: erst ansehen, welche Modelle welche Rolle bekommen.")
    say("  [1] Trockenlauf zeigen, nichts ausführen (Standard)")
    say("  [2] Einrichtung starten (claudegravity init)")
    say("  [3] Jetzt starten")
    say("  [4] Jetzt starten und diesen Hinweis nicht mehr zeigen")
    try:
        choice = input_fn("Auswahl [1]: ").strip() or "1"
    except (EOFError, KeyboardInterrupt):
        choice = "1"
    return {"1": "dry-run", "2": "init", "3": "run", "4": "quiet"}.get(choice, "dry-run")


def print_welcome() -> None:
    """Start ohne Aufgabe: kurzer Wegweiser statt der vollen Hilfe."""
    say("ClaudeGravity Loop: Ein Modell plant, ein anderes prüft, eines baut, ein anderer Anbieter nimmt ab.\n")
    say("  claudegravity init                       Einrichtung (erkennt KIs, speichert ein Profil)")
    say('  claudegravity "Deine Aufgabe"            Loop starten')
    say('  claudegravity --dry-run "Deine Aufgabe"  Nur zeigen, wer welche Rolle bekommt')
    say("  claudegravity --resume                   Unterbrochene Sitzung fortsetzen")
    say("  claudegravity --help                     Wichtigste Optionen (alle: --help-all)")
