"""Kommandozeile: Parser, Konfiguration, --check, Trockenlauf und main(), das die Phasen aufruft."""

import argparse
import os
import platform
import shlex
import shutil
import sys
from pathlib import Path

from . import __version__
from .candidates import run_candidates
from .common import (
    CLOUD_PLANNER_ORDER,
    CLOUD_TIMEOUT,
    HYBRID_STRATEGIES,
    LOCAL_BACKEND_ORDER,
    LOCAL_TIMEOUT,
    SETTINGS,
    ask,
    say,
)
from .errors import classify_error, fail
from .i18n import help_text, prescan_lang, resolve_lang
from .backends import (
    AgentCLI,
    DEFAULT_MODEL_LABEL,
    _exec_endpoint_runner,
    check_cli_auth,
    detect_installed_agents,
    effort_label,
    is_private_endpoint,
)
from .session import LOG_FORMATS, find_latest_session, get_permission_flags, is_git_repo, task_preview
from .github import issue_task, load_issue
from .budget import (
    Budget,
    BudgetExceeded,
    collect_kpi_history,
    estimate_hints,
    estimate_run,
    format_estimate,
    handle_budget_exceeded,
)
from .roles import (
    ESCALATE_AFTER_DEFAULT,
    apply_auto_roles,
    choose_escalation,
    dry_run_command,
    normalize_strategy,
    pick_inspector,
    pick_plan_roles,
    stages_wanted,
)
from .config import apply_config_layers, format_effective_config, global_profile_path, source_label
from .wizard import (
    first_run_guide,
    print_welcome,
    run_setup_wizard,
    suggest_proof_command,
    unsafe_config_warnings,
    write_profile,
)
from .phases import (
    finish_run,
    open_session,
    prepare_build,
    print_run_banner,
    run_build_phase,
    run_plan_phase,
    setup_run,
)


EFFORT_CHOICES = ["low", "medium", "high", "xhigh", "max"]
STRATEGY_CHOICES = ["best-code", "quality", "eco", "economy", "cost", "local-free", "free", "local", "hybrid", "mixed", "balanced"]
STRATEGY_METAVAR = "{balanced,best-code,eco,local-free,hybrid}"
HELP_EPILOG = (
    'Erste Schritte: claudegravity init · Trockenlauf: claudegravity --dry-run "Aufgabe" · '
    "Alle Optionen mit Aliasen: claudegravity --help-all"
)


class LoopHelpFormatter(argparse.HelpFormatter):
    """Zeigt je Option nur den Hauptnamen (plus Kurzform); Aliase stehen nur in --help-all."""

    show_aliases = False

    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=30, width=min(shutil.get_terminal_size((100, 20)).columns, 110))

    def _format_action_invocation(self, action: argparse.Action) -> str:
        if not action.option_strings or self.show_aliases:
            return super()._format_action_invocation(action)
        shorts = [o for o in action.option_strings if not o.startswith("--")]
        names = shorts[:1] + [o for o in action.option_strings if o.startswith("--")][:1]
        if action.nargs == 0:
            return ", ".join(names)
        return ", ".join(names) + " " + self._format_args(action, self._get_default_metavar_for_optional(action))


class LoopFullHelpFormatter(LoopHelpFormatter):
    """Hilfe-Formatierung für --help-all: zeigt zusätzlich die Alias-Schreibweisen der Optionen."""

    show_aliases = True


def build_parser(full_help: bool = False, lang: str | None = None) -> argparse.ArgumentParser:
    """Kommandozeile in Gruppen. Ohne `full_help` zeigt --help nur die wichtigsten Optionen;
    alle übrigen bleiben gültig und erscheinen mit --help-all. `lang` (Standard: Sprache des Laufs) übersetzt die Hilfe."""
    lang = lang or SETTINGS.lang

    def text(value):
        return help_text(value, lang)

    parser = argparse.ArgumentParser(
        prog="claudegravity",
        usage=text('claudegravity [Optionen] "Aufgabe"') if not full_help else None,
        description=text("ClaudeGravity Loop: Ein Modell plant, ein anderes prüft, eines baut, ein anderer Anbieter nimmt ab."),
        epilog=text(HELP_EPILOG),
        formatter_class=LoopFullHelpFormatter if full_help else LoopHelpFormatter,
        add_help=False,
    )

    def group(title: str):
        g = parser.add_argument_group(text(title))

        def add(*flags, core: bool = False, **kw):
            if not (core or full_help):
                kw["help"] = argparse.SUPPRESS
            elif "help" in kw:
                kw["help"] = text(kw["help"])
            return g.add_argument(*flags, **kw)

        return add

    add = group("Start")
    add("task", nargs="?", default="", core=True, help="Die Aufgabe für den Loop")
    add("-p", "--project", default=".", core=True, help="Pfad zum Ziel-Projekt (absolut oder relativ, Standard: .)")
    add(
        "--init",
        "--einrichten",
        action="store_true",
        core=True,
        help="Einrichtung: erkennt System und KI-CLIs, fragt Ziel und Prüfbefehl, speichert ein Profil (auch: claudegravity init)",
    )
    add(
        "--dry-run",
        action="store_true",
        core=True,
        help="Trockenlauf: Zeigt Rollen, Modelle, Kosten-Analyse und generierten Befehl ohne Ausführung",
    )
    add("-c", "--resume", "--continue", dest="resume", action="store_true", core=True, help="Unterbrochene Sitzung fortsetzen")
    add(
        "--template",
        "--vorlage",
        default=None,
        core=True,
        help='Aufgaben-Vorlage: bugfix, feature, refactor oder eigene aus dem Profil ("templates"); einzelne Flags überschreiben sie',
    )
    add("--check", "--info", action="store_true", core=True, help="Installierte AI-CLIs, Standard-Modelle und Rollenkonfiguration anzeigen")
    add(
        "--print-effective-config",
        "--config",
        dest="print_effective_config",
        action="store_true",
        core=True,
        help="Wirksame Konfiguration mit Quelle je Einstellung (Kommandozeile, Session, Umgebung, Profil, Standard) anzeigen und beenden",
    )
    add("-h", "--help", action="help", core=True, help="Diese Hilfe (wichtigste Optionen)")
    add("--help-all", action="help", core=True, help="Alle Optionen mit Aliasen zeigen")
    add("--version", action="version", version=f"claudegravity {__version__}", core=True, help="Version anzeigen")

    add = group("Strategie und Kosten")
    add(
        "--strategy",
        "--preset",
        default=None,
        choices=STRATEGY_CHOICES,
        metavar=STRATEGY_METAVAR,
        core=True,
        help="Optimierungs-Strategie: best-code (beste Qualität), eco (bis zu 70%% Ersparnis), local-free (0€ Kosten in Phase 3 via Lokal/Intranet-Modell), hybrid (Cloud-CLI plant und nimmt ab, lokales Modell prüft und baut in Etappen), balanced (Standard). Aliase: quality, economy, cost, free, local, mixed",
    )
    add(
        "--budget-max",
        default=None,
        core=True,
        help="Harte Grenze für die Session: Tokens (500k, 1.5m) oder gemeldete Kosten (2.50usd); der Lauf endet nach dem Aufruf, der sie erreicht",
    )
    add("--budget-warn", default=None, help="Weiche Grenze: nur Warnung (Standard: 80 %% von --budget-max)")
    add("--budget-roles", "--budget-rollen", default=None, help='Harte Grenzen je Rolle, z. B. "bauleiter=300k,abnahme=0.50usd"')
    add(
        "--escalate",
        "--eskalation",
        default=None,
        metavar="ZIEL",
        help="Lokaler Bauleiter scheitert wiederholt: auf eine Cloud-CLI wechseln (auto oder z. B. claude, codex); einmal pro Session, steht in .done",
    )
    add(
        "--escalate-after",
        "--eskalation-nach",
        type=int,
        default=None,
        metavar="N",
        help=f"Erfolglose Bau-Runden in Folge bis zur Eskalation (Standard: {ESCALATE_AFTER_DEFAULT})",
    )

    add = group("Rollen und Modelle")
    add("--planner", "--architekt", default=None, core=True, help="Explizite CLI für Architekt / Planung (z.B. claude oder agy)")
    add("--reviewer", "--pruefstatiker", default=None, core=True, help="Explizite CLI für Prüfstatiker / Review (z.B. agy oder claude)")
    add(
        "--builder",
        "--bauer",
        default=None,
        core=True,
        help="Explizite CLI für Bauleiter / Umsetzung (Phase 3, z.B. claude oder agy, Standard: folgt Architekt)",
    )
    add(
        "--candidates",
        "--kandidaten",
        default=None,
        core=True,
        help="Best-of-N: mehrere Bauleiter bauen den Plan parallel in eigenen Worktrees, die Abnahme wählt den besten, "
        'z. B. "claude,codex" oder "codex,ollama=qwen3-coder:30b"',
    )
    add(
        "--inspector",
        "--abnahme",
        default=None,
        core=True,
        help="CLI für die Abnahme des fertigen Codes (Standard: Prüfstatiker, nie der Bauleiter)",
    )
    add(
        "--endpoint",
        "--api-base",
        default=None,
        core=True,
        help="OpenAI-kompatibler Endpunkt (z.B. http://localhost:11434/v1 oder http://192.168.1.50:11434/v1)",
    )
    add(
        "--swap",
        "--swap-roles",
        "--reverse",
        action="store_true",
        help="Rollen tauschen: Antigravity wird Architekt (Planung), Claude wird Prüfstatiker (Review)",
    )
    add("--planner-model", "--architekt-model", default=None, help="Modell für den Architekten (z.B. sonnet, gemini-4-argon, opus)")
    add("--reviewer-model", "--pruefstatiker-model", default=None, help="Modell für den Prüfstatiker (z.B. gemini-4-argon, sonnet, opus)")
    add(
        "--builder-model",
        "--bauer-model",
        default=None,
        help="Modell für den Bauleiter in Phase 3 (z.B. haiku, gemini-3.8-flash, sonnet)",
    )
    add("--inspector-model", "--abnahme-model", default=None, help="Modell für die Abnahme")
    add("--effort", default=None, choices=EFFORT_CHOICES, help="Reasoning-Intensität / Thinking Effort (für agy)")
    add(
        "--planner-effort",
        "--architekt-effort",
        default=None,
        choices=EFFORT_CHOICES,
        help="Spezifische Reasoning-Intensität für den Architekten (falls agy)",
    )
    add(
        "--reviewer-effort",
        "--pruefstatiker-effort",
        default=None,
        choices=EFFORT_CHOICES,
        help="Spezifische Reasoning-Intensität für den Prüfstatiker (für agy)",
    )
    add(
        "--builder-effort",
        "--bauer-effort",
        default=None,
        choices=EFFORT_CHOICES,
        help="Reasoning-Intensität für den Bauleiter in Phase 3 (für agy)",
    )
    add("--inspector-effort", "--abnahme-effort", default=None, choices=EFFORT_CHOICES, help="Reasoning-Intensität für die Abnahme")
    add("--architekt-endpoint", default=None, help="Spezifischer Endpunkt für den Architekten")
    add("--pruefstatiker-endpoint", default=None, help="Spezifischer Endpunkt für den Prüfstatiker")
    add("--bauer-endpoint", default=None, help="Spezifischer Endpunkt für den Bauleiter (Phase 3)")
    add("--api-key", default=None, help="Optionaler API-Key für geschützte KI-Endpunkte")
    add(
        "--timeout",
        type=int,
        default=None,
        help=f"Sekunden pro Runde für Endpunkte (Standard: {LOCAL_TIMEOUT} im Heimnetz, {CLOUD_TIMEOUT} sonst; auch CLAUDEGRAVITY_TIMEOUT)",
    )

    add = group("Ablauf")
    add(
        "--proof",
        "--pruefbefehl",
        default=None,
        core=True,
        help='Prüfbefehl, den der Loop nach jeder Bau-Runde selbst ausführt (z.B. "python -m unittest discover -s tests")',
    )
    add(
        "-i",
        "--ask",
        "--interview",
        "--clarify",
        action="store_true",
        core=True,
        help="Fragen-Modus: Beide Agenten stellen bei Unklarheiten gezielte Fragen an dich, bevor der Plan finalisiert wird",
    )
    add(
        "--plan-auto",
        "--approve-plan",
        dest="approve_plan",
        action="store_true",
        core=True,
        help="Plan ohne Rückfrage freigeben, sobald der Prüfstatiker APPROVED meldet (sonst kein Bau); für Läufe ohne Terminal",
    )
    add(
        "--builder-fresh",
        "--bauer-neu",
        dest="builder_fresh",
        action="store_true",
        help="Bauleiter jede Runde in neuer Sitzung starten; Standard: claude und codex setzen ihre Sitzung fort und bekommen nur Rückmeldung und nächsten Schritt",
    )
    add(
        "--etappen",
        "--stages",
        default="auto",
        choices=["auto", "an", "aus", "on", "off"],
        help="Etappen-Modus: Architekt plant Etappen, Bauleiter setzt sie einzeln um, Loop prüft jede mit --proof (auto: an bei lokalen/Endpunkt-Bauleitern)",
    )
    add(
        "--repo-map",
        "--repo-karte",
        default="auto",
        choices=["auto", "an", "aus", "on", "off"],
        help="Repo-Karte (Dateien mit Klassen und Funktionen) im Prompt: auto nur für Endpunkte ohne Dateizugriff, an für alle Rollen, aus nie",
    )
    add(
        "-m",
        "--max-iterations",
        type=int,
        default=None,
        help="Maximale autonome Iterationen (Standard: 10, im Etappen-Modus 2 pro Etappe + 2)",
    )
    add("--max-rounds", type=int, default=2, help="Maximale Review-Runden für den Plan (Standard: 2)")
    add("--max-inspections", type=int, default=2, help="Maximale Abnahme-Runden pro Lauf (Standard: 2)")
    add(
        "--test-guard",
        "--testwaechter",
        choices=["warn", "strict", "off"],
        default="warn",
        help="Geschönte Tests erkennen (gelöscht, Skip/Only, weniger Prüfungen): warn meldet es der Abnahme, "
        "strict weist die Fertigmeldung zurück, off schaltet ab (Standard: warn)",
    )
    add(
        "--no-inspect",
        "--ohne-abnahme",
        dest="inspect",
        action="store_false",
        help="Abnahme durch einen anderen Anbieter auslassen (wird im LOG.md vermerkt)",
    )
    add(
        "--auto-switch",
        "--fallback",
        action="store_true",
        help="Bei Erreichen eines AI-Limits automatisch zum alternativen Modell wechseln",
    )
    add(
        "--retries",
        "--neuversuche",
        type=int,
        default=None,
        help="Automatische Neuversuche bei vorübergehenden Fehlern (Überlastung, 5xx, Verbindungsabbruch) mit Backoff und Jitter (Standard: 3, 0 schaltet ab)",
    )
    add("-d", "--delay", type=int, default=3, help="Pause zwischen Runden in Sekunden")

    add = group("Rechte und Arbeitsbereich")
    add(
        "--yolo",
        "--auto-approve",
        action="store_true",
        core=True,
        help="Automatisch volle Schreib- und Toolrechte erteilen (keine Nachfrage)",
    )
    add(
        "--no-worktree",
        "--no-workspace",
        dest="worktree",
        action="store_false",
        help="Keinen eigenen Git-Workspace pro Session anlegen, sondern direkt im Projektverzeichnis bauen",
    )
    add(
        "--merge",
        "--worktree-merge",
        action="store_true",
        help="Session-Branch nach erfolgreichem Abschluss (.done) in den Ausgangs-Branch mergen",
    )
    add("--no-shield", action="store_true", help="Datenschutzschild aus: Zugangsdaten in Prompts an Cloud-Modelle nicht schwärzen")

    add = group("GitHub")
    add(
        "--from-issue",
        "--issue",
        "--aus-issue",
        dest="from_issue",
        default=None,
        metavar="NR|URL",
        core=True,
        help="GitHub-Issue als Aufgabe: Nummer (12, #12), owner/repo#12 oder URL; liest Titel, Text und Kommentare über gh oder GH_TOKEN",
    )
    add(
        "--open-pr",
        "--pr-oeffnen",
        dest="open_pr",
        action="store_true",
        core=True,
        help="Nach erfolgreichem Abschluss den Session-Branch pushen und einen Pull Request öffnen (mit „Closes #n“ bei --from-issue)",
    )
    add("--pr-draft", "--pr-entwurf", dest="pr_draft", action="store_true", help="Pull Request als Entwurf öffnen (schließt --open-pr ein)")

    add = group("Ausgabe")
    add(
        "--lang",
        "--sprache",
        choices=("de", "en", "auto"),
        default=None,
        core=True,
        help="Sprache der Ausgaben und Modellantworten: de, en oder auto (Locale); auch CLAUDEGRAVITY_LANG",
    )
    add(
        "--log-format",
        choices=LOG_FORMATS,
        default="text",
        help="json: zusätzlich events.jsonl im Session-Ordner, eine JSON-Zeile pro Ereignis (Aufruf, Prüfbefehl, Audit, Eskalation, Ende)",
    )
    add(
        "--no-progress", dest="progress", action="store_false", help='Keine Statuszeile nach jedem KI-Aufruf (im Profil: "progress": false)'
    )
    add(
        "--no-guide",
        dest="guide",
        action="store_false",
        help='Hinweis beim ersten Lauf ohne Profil nicht zeigen (im Profil: "guide": false)',
    )
    return parser


def load_cli_config(argv: list[str]) -> tuple[argparse.ArgumentParser, argparse.Namespace, dict] | None:
    """Kommandozeile lesen und mit Session, Umgebung und Profilen verrechnen. None, wenn nur die Konfiguration gezeigt wurde."""
    SETTINGS.lang = prescan_lang(argv)
    parser = build_parser(full_help="--help-all" in argv)
    args = parser.parse_args(argv)
    config_report = apply_config_layers(parser, args, argv)
    SETTINGS.lang = resolve_lang(args.lang)
    if args.print_effective_config:
        say(format_effective_config(config_report))
        return None
    for warning in config_report["warnings"]:
        say(warning)
    layered = [d for d, s in config_report["sources"].items() if s in ("env", "project", "global")]
    if layered:
        say(
            "⚙️  Aus Umgebung/Profil: "
            + ", ".join(f"{d}={config_report['values'][d]!r} ({source_label(config_report['sources'][d])})" for d in sorted(layered))
        )
    for conflict in config_report["conflicts"]:
        say(f"⚠️  Konfigurationskonflikt: {conflict}")
    template = config_report.get("template")
    if args.template and not template:
        fail("CG-1101", str(args.template))
    if template and not args.init and not args.check:
        say(f"🧩 Vorlage `{template['name']}` ({template['origin']})")
        if "proof" in template["requires"] and not args.proof and not args.resume:
            guessed = suggest_proof_command(Path(args.project).resolve())
            if not guessed:
                fail("CG-1102", f"Vorlage `{template['name']}`, kein Testbefehl im Projekt erkannt")
            args.proof = guessed
            config_report["sources"]["proof"] = "template"
            say(f"   Prüfbefehl aus dem Projekt geraten: {guessed} (anderer mit --proof)")
    return parser, args, config_report


def apply_runtime_settings(args: argparse.Namespace) -> None:
    """Einstellungen, die tief im Code gebraucht werden (Zeitlimits, Schild, Budget, Ausgabe), modulweit setzen."""
    SETTINGS.lang = resolve_lang(getattr(args, "lang", None))
    SETTINGS.retries = args.retries
    SETTINGS.repo_map = {"on": "an", "off": "aus"}.get(args.repo_map, args.repo_map)
    SETTINGS.progress = args.progress
    SETTINGS.log_format = args.log_format
    try:
        SETTINGS.budget = Budget(args.budget_max, args.budget_warn, args.budget_roles)
    except ValueError as exc:
        fail("CG-1103", str(exc))
    env_timeout = os.environ.get("CLAUDEGRAVITY_TIMEOUT", "")
    SETTINGS.endpoint_timeout = args.timeout or (int(env_timeout) if env_timeout.isdigit() else None)
    SETTINGS.shield = not args.no_shield and os.environ.get("CLAUDEGRAVITY_SHIELD", "").lower() != "off"


def setup_agents(args: argparse.Namespace) -> dict[str, AgentCLI]:
    """Installierte CLIs und Endpunkte erkennen, dazu die ausdrücklich angegebenen Rollen-Endpunkte."""
    custom_ep = args.endpoint or args.bauer_endpoint or args.architekt_endpoint or args.pruefstatiker_endpoint
    agents = detect_installed_agents(
        custom_endpoint=custom_ep, api_key=args.api_key, default_model=args.builder_model or args.planner_model
    )

    if args.architekt_endpoint and "architekt_ep" not in agents:
        agents["architekt_ep"] = AgentCLI(
            f"Architekt Endpoint ({args.architekt_endpoint})",
            "architekt_ep",
            _exec_endpoint_runner(args.architekt_endpoint, args.planner_model or "default", args.api_key),
            local=is_private_endpoint(args.architekt_endpoint),
        )
    if args.pruefstatiker_endpoint and "pruefstatiker_ep" not in agents:
        agents["pruefstatiker_ep"] = AgentCLI(
            f"Prüfstatiker Endpoint ({args.pruefstatiker_endpoint})",
            "pruefstatiker_ep",
            _exec_endpoint_runner(args.pruefstatiker_endpoint, args.reviewer_model or "default", args.api_key),
            local=is_private_endpoint(args.pruefstatiker_endpoint),
        )
    if args.bauer_endpoint and "bauer_ep" not in agents:
        agents["bauer_ep"] = AgentCLI(
            f"Bauleiter Endpoint ({args.bauer_endpoint})",
            "bauer_ep",
            _exec_endpoint_runner(args.bauer_endpoint, args.builder_model or "qwen2.5-coder:32b", args.api_key),
            local=is_private_endpoint(args.bauer_endpoint),
        )
    return agents


def print_system_check(agents: dict[str, AgentCLI]) -> None:
    """--check: erkannte KIs, Standard-Belegung und die wichtigsten Flags."""
    os_name = f"{platform.system()} {platform.release()}"
    say(f"🖥️  Betriebssystem: {os_name} (Python {platform.python_version()})")
    say("🔍 Erkannte KI-Systeme & Endpoints auf deinem System:")
    for key, agent in agents.items():
        ok, msg = check_cli_auth(agent.binary)
        indicator = "[x]" if ok else "[!]"
        suffix = f" – {msg}" if msg else ""
        say(f"  {indicator} {agent.name} (`{key}` / `{agent.binary}`){suffix}")
    if not agents:
        say("  (keine) Installiere z.B. `claude` oder `agy`, oder gib --endpoint <url> an.")
        return
    def_planner = agents.get("claude") or next(iter(agents.values()))
    others = [a for a in agents.values() if a.binary != def_planner.binary]
    def_reviewer = next((a for a in others if a.binary == "agy"), others[0] if others else def_planner)
    local_cand = next((agents[k] for k in LOCAL_BACKEND_ORDER if k in agents), None)
    eco_model = "haiku" if def_planner.binary == "claude" else "gemini-3.8-flash"

    def default_effort(binary: str) -> str:
        return "high (CLI-Default)" if binary == "agy" else "Voreinstellung der CLI (via --effort nur für agy/codex steuerbar)"

    say("\n" + "=" * 68)
    say("🎯 Standard-Belegung auf diesem System (wenn NICHTS explizit angegeben wird):")
    say("=" * 68)
    say("1. 🏗️ Architekt (Phase 1: Planung & Entwurf):")
    say(f"   • CLI           : {def_planner.name} (`{def_planner.binary}`)")
    say(f"   • Modell        : {DEFAULT_MODEL_LABEL} von {def_planner.name} (änderbar via --architekt-model)")
    say(f"   • Thinking-Effort: {default_effort(def_planner.binary)}")
    say("   • Aufgabe       : Entwirft den Plan (Phase 1) [nur ~10-15% aller Tokens]")
    say("\n2. 🧐 Prüfstatiker (Phase 2: Prüfung & Review / Stresstest):")
    if def_reviewer is def_planner:
        say(f"   • CLI           : {def_reviewer.name} (`{def_reviewer.binary}`) – kein zweites Modell gefunden, prüft sich selbst!")
    else:
        say(f"   • CLI           : {def_reviewer.name} (`{def_reviewer.binary}`)")
    say(f"   • Modell        : {DEFAULT_MODEL_LABEL} von {def_reviewer.name} (änderbar via --pruefstatiker-model)")
    say(f"   • Thinking-Effort: {default_effort(def_reviewer.binary)}")
    say("   • Aufgabe       : Grillt den Plan unabhängig auf Schwachstellen (Phase 2) [nur ~5-10% aller Tokens]")
    say("\n3. 🔨 Bauleiter (Phase 3: Bau & Umsetzung / Implementation):")
    say(f"   • CLI           : {def_planner.name} wie der Architekt (oder separat via --bauer / --builder)")
    say("   • Modell        : Wie der Architekt (oder Sparmodell via --bauer-model / lokaler Server)")
    say("   • Thinking-Effort: Wie der Architekt (oder steuerbar via --bauer-effort, nur für agy/codex)")
    say("   • Aufgabe       : Setzt den Plan autonom im Code um [verbraucht ~80-90% aller Tokens!]")
    say("=" * 68)
    say("\n💡 Spar-Strategien & Kombi-Möglichkeiten:")
    say("  • '--strategy eco'        : Bis zu 70% Token-Ersparnis (Architekt/Prüfstatiker Effort medium,")
    say(f"                             Bauleiter {def_planner.name} mit `{eco_model}`)")
    if local_cand:
        say(f"  • '--strategy local-free' : 0 € Kosten im Bau-Loop! {def_planner.name} plant, {local_cand.name} baut!")
    else:
        say("  • '--strategy local-free' : 0 € Kosten im Bau-Loop – aktuell kein lokaler Server erkannt")
        say("                             (Ollama, LM Studio oder --bauer-endpoint <url> angeben)")
    say("  • '--strategy best-code'  : Effort high in allen 3 Phasen (wirkt nur bei agy)")
    hybrid_cloud = next((agents[k].name for k in CLOUD_PLANNER_ORDER if k in agents), None)
    if hybrid_cloud and local_cand:
        say(f"  • '--strategy hybrid'     : {hybrid_cloud} plant und nimmt ab, {local_cand.name} prüft und baut in Etappen")
    say("=" * 68)
    say("\n⚙️  Wichtigste Steuerungs-Flags:")
    say("  - Strategie-Presets      : --strategy <best-code|eco|local-free|balanced>")
    say("  - Trockenlauf            : --dry-run (zeigt Rollen, Modelle & Befehl ohne Ausführung)")
    say("  - Eigener Endpunkt       : --endpoint <url> (z.B. http://localhost:11434/v1 oder http://192.168.1.50:11434/v1)")
    say("  - Bauleiter-Endpunkt     : --bauer-endpoint <url> (z.B. http://localhost:11434/v1)")
    say("  - Bauleiter festlegen    : --bauer / --builder <claude|agy|ollama|lmstudio|endpoint|codex|copilot>")
    say("  - Bauleiter-Modell       : --bauer-model <name> (z.B. qwen2.5-coder:32b, haiku, gemini-3.8-flash)")
    say("  - Auto-Fallback bei Limit: --auto-switch / --fallback (wechselt bei Limit nahtlos zum Alternativmodell)")
    say("  - Fragen-Modus aktivieren: -i / --ask (Agenten stellen bei Unklarheiten gezielte Fragen an dich)")
    say('  - Prüfbefehl             : --proof "python -m unittest" (Loop führt ihn nach jeder Bau-Runde selbst aus)')
    say("  - Abnahme                : --abnahme <cli> (prüft den fertigen Code, nie der Bauleiter; --no-inspect schaltet ab)")
    say("  - Etappen                : --etappen auto|an|aus (Plan in kleinen Stücken; auto: an bei lokalen Bauleitern)")
    say("  - Ohne Freigabe-Menü     : --plan-auto (baut nur, wenn der Prüfstatiker APPROVED meldet)")
    say("  - Token & Kosten-Audit   : Automatisch aktiv (wird in .done auditiert inkl. Rolle, Modell & Effort)")


def maybe_first_run_guide(args: argparse.Namespace, agents: dict, project_path: Path, config_report: dict) -> bool | None:
    """Erstlauf ohne Profil im Terminal: Trockenlauf, Einrichtung oder Start anbieten.
    Liefert True, wenn ein geführter Trockenlauf folgt, None, wenn die Einrichtung schon alles erledigt hat."""
    guided_dry_run = False
    no_profile = not any(config_report["loaded"].values())
    if args.task and not args.resume and not args.dry_run and args.guide and no_profile and sys.stdin.isatty() and sys.stdout.isatty():
        choice = first_run_guide(args)
        if choice == "init":
            run_setup_wizard(project_path, agents)
            return None
        if choice == "dry-run":
            args.dry_run = guided_dry_run = True
        if choice == "quiet":
            try:
                saved = write_profile(global_profile_path(), {"guide": False})
                say(f"   Hinweis abgeschaltet ({global_profile_path()}, guide = {saved['guide']}).")
            except (OSError, ValueError) as exc:
                say(f"   Konnte das globale Profil nicht schreiben: {exc}")
    return guided_dry_run


def show_dry_run(args: argparse.Namespace, agents: dict, project_path: Path, config_warnings: list[str], guided_dry_run: bool) -> bool:
    """Trockenlauf: Belegung, Kostenschätzung und Startbefehl zeigen. True nur, wenn der Nutzer danach starten will."""
    dry_task = args.task or "Refaktoriere das Modul und erstelle Unit-Tests"
    architekt_choice = args.planner or ("architekt_ep" if args.architekt_endpoint else None)
    pruefstatiker_choice = args.reviewer or ("pruefstatiker_ep" if args.pruefstatiker_endpoint else None)
    planner, reviewer = pick_plan_roles(agents, architekt_choice, pruefstatiker_choice, args.swap, bool(args.planner or args.reviewer))

    strat = normalize_strategy(args.strategy or "balanced")

    default_p_effort = None
    default_r_effort = None
    default_b_effort = None
    default_b_model = None
    local_cand = next((agents[k] for k in LOCAL_BACKEND_ORDER if k in agents), None)

    if strat == "best-code":
        default_p_effort = "high"
        default_r_effort = "high"
        default_b_effort = "high"
        builder_choice = args.builder or planner.binary
        builder = agents.get(builder_choice, planner)
    elif strat == "eco":
        default_p_effort = "medium"
        default_r_effort = "medium"
        default_b_effort = "low"
        builder_choice = args.builder or planner.binary
        builder = agents.get(builder_choice, planner)
        default_b_model = {"claude": "haiku", "agy": "gemini-3.8-flash", "gemini": "gemini-2.5-flash"}.get(builder.binary)
    elif strat == "local-free":
        default_p_effort = "high"
        default_r_effort = "high"
        default_b_effort = "low"
        if args.builder and args.builder in agents:
            builder = agents[args.builder]
        elif local_cand:
            builder = local_cand
        else:
            builder = planner
        default_b_model = args.builder_model or (
            "qwen2.5-coder:32b"
            if "endpoint" in builder.binary
            else ("qwen2.5-coder:latest" if "ollama" in builder.binary else "local-model")
        )
    else:  # balanced
        default_p_effort = "high" if planner.binary == "agy" else None
        default_r_effort = "high" if reviewer.binary == "agy" else None
        builder_choice = args.builder or planner.binary
        builder = agents.get(builder_choice, planner)

    p_model = args.planner_model or DEFAULT_MODEL_LABEL
    p_effort = args.planner_effort or args.effort or default_p_effort or ("high (CLI Default)" if planner.binary == "agy" else None)

    r_model = args.reviewer_model or DEFAULT_MODEL_LABEL
    r_effort = args.reviewer_effort or args.effort or default_r_effort or ("high (CLI Default)" if reviewer.binary == "agy" else None)

    b_model = args.builder_model or default_b_model or (p_model if builder.binary == planner.binary else DEFAULT_MODEL_LABEL)
    b_effort = args.builder_effort or default_b_effort or ("CLI Default" if builder.binary == "agy" else None)

    say("\n" + "=" * 68)
    say("🔍 ClaudeGravity Loop — Trockenlauf (Dry Run)")
    say("=" * 68)
    say(f"📌 Aufgabe        : {task_preview(dry_task)}")
    say(f"🎯 Strategie      : {strat.upper()}")
    say(f"📁 Ziel-Projekt   : {project_path}")
    say("\n1. 🏗️ Architekt (Phase 1: Planung & Entwurf):")
    say(f"   • CLI/Endpoint  : {planner.name} (`{planner.binary}`)")
    say(f"   • Modell        : {p_model}")
    say(f"   • Effort        : {effort_label(planner.binary, p_effort) or 'Standard'}")
    say("   • Token-Anteil  : Leichtgewichtig (~10-15% aller Tokens)")
    say("\n2. 🧐 Prüfstatiker (Phase 2: Prüfung & Review / Stresstest):")
    say(f"   • CLI/Endpoint  : {reviewer.name} (`{reviewer.binary}`)")
    say(f"   • Modell        : {r_model}")
    say(f"   • Effort        : {effort_label(reviewer.binary, r_effort) or 'Standard'}")
    say("   • Token-Anteil  : Leichtgewichtig (~5-10% aller Tokens)")
    say("\n3. 🔨 Bauleiter (Phase 3: Bau & Umsetzung / Implementation):")
    say(f"   • CLI/Endpoint  : {builder.name} (`{builder.binary}`)")
    say(f"   • Modell        : {b_model}")
    say(f"   • Effort        : {effort_label(builder.binary, b_effort) or 'Standard'}")
    say("   • Token-Anteil  : Schwergewicht (~80-90% aller Tokens!)")
    if args.escalate:
        after = args.escalate_after or ESCALATE_AFTER_DEFAULT
        key, why = choose_escalation(builder, agents, args.escalate, prefer=planner.binary, write_allowed=True)
        if key:
            rights = (
                ""
                if args.yolo or not get_permission_flags(agents[key].binary)
                else " (braucht Schreibrechte: --yolo oder Ja bei der Rechte-Abfrage)"
            )
            say(f"   • Eskalation    : nach {after} erfolglosen Runden einmalig zu {agents[key].name}{rights}")
        else:
            say(f"   • Eskalation    : nicht möglich ({why})")
    say("\n4. 🔎 Abnahme (Phase 4: Prüfung des fertigen Codes):")
    if not args.inspect:
        say("   • Abgeschaltet (--no-inspect)")
    else:

        def with_model(agent: AgentCLI, model: str | None) -> AgentCLI:
            return AgentCLI(
                agent.name, agent.binary, agent.run_fn, model=model if model and model != DEFAULT_MODEL_LABEL else None, local=agent.local
            )

        dry_candidates = [with_model(agents[args.inspector], args.inspector_model)] if args.inspector in agents else []
        dry_inspector = pick_inspector(
            with_model(builder, b_model), dry_candidates + [with_model(reviewer, r_model), with_model(planner, p_model)], agents
        )
        if dry_inspector is None:
            say("   • Kein zweiter Anbieter verfügbar: keine unabhängige Abnahme möglich!")
        else:
            say(f"   • CLI/Endpoint  : {dry_inspector.name} (`{dry_inspector.binary}`), nie der Bauleiter")
            if dry_inspector.model or args.inspector_model:
                say(f"   • Modell        : {args.inspector_model or dry_inspector.model}")
    say(f"   • Prüfbefehl    : {args.proof or 'keiner (--proof <befehl>)'}")
    dry_builder_final = builder if (args.builder or strat == "local-free") else planner
    if stages_wanted(args.etappen, dry_builder_final.binary):
        say(
            "\n🧩 Etappen-Modus: Architekt schneidet den Plan in Etappen, der Bauleiter setzt sie einzeln um, der Loop prüft jede (--etappen aus schaltet ab)."
        )
    say("\n💡 Wirtschaftlichkeits- & Qualitäts-Analyse:")
    if strat == "local-free":
        say("   • Spareffekt: 100% kostenlose Bau-Iterationen (0 € API-Kosten in Phase 3)!")
        say(f"   • Grund: Phase 1 & 2 planen mit {planner.name} und {reviewer.name}. Der rechenintensive Bau-Loop")
        say(f"     läuft komplett auf {builder.name} (Modell: {b_model}).")
    elif strat == "eco":
        say("   • Spareffekt: Bis zu ~70% Kosten- und Tokenersparnis!")
        say(f"   • Grund: Phase 1 & 2 planen mit {planner.name} und {reviewer.name} (Effort medium). Das ressourcenintensive")
        say(f"     Bauen in Phase 3 übernimmt {builder.name} mit dem Spar-Modell `{b_model}`.")
    elif strat in HYBRID_STRATEGIES:
        say(f"   • Spareffekt: Cloud nur für Plan und Abnahme ({planner.name}); Prüfung und Bau laufen lokal für 0 €.")
        say("   • Grund: Kleine Etappen passen in den Kontext lokaler Modelle; jede Etappe prüft der Loop mit --proof.")
    elif strat == "best-code":
        say("   • Fokus: Höchste Code-Qualität, tiefes Reasoning und maximale Fehlertoleranz.")
        say(f"   • Alle Phasen laufen mit Effort high: {planner.name}, {reviewer.name}, {builder.name}.")
        if any(a.binary != "agy" for a in (planner, reviewer, builder)):
            say("   • Hinweis: Effort wird nur an agy übergeben; andere CLIs nutzen ihre eigene Voreinstellung.")
    else:
        say("   • Ausgewogenes Standard-Verhältnis zwischen starker Planung und stabiler Umsetzung.")

    estimate = estimate_run(collect_kpi_history(project_path), strat, args.max_iterations or 10)
    for line in format_estimate(estimate, estimate_hints(estimate, strat, SETTINGS.budget, local_cand is not None, args.proof)):
        say(line)

    if config_warnings:
        say("\n🔔 Hinweise:")
        for warning in config_warnings:
            say(f"   {warning}")

    say("\n🚀 Generierter Shell-Befehl (zum Starten):")
    say(f"   {shlex.join(dry_run_command(args, dry_task, strat, default_b_model))}")
    say("=" * 68)
    if not guided_dry_run:
        return False
    try:
        go = ask("\nSo starten? [j/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        go = ""
    if go not in ("j", "ja", "y", "yes"):
        say("Nichts ausgeführt. Tipp: `claudegravity init` speichert deine Wahl als Profil.")
        return False
    args.dry_run = False
    return True


def main():
    """Einstieg: Konfiguration laden, Sonderbefehle (init, --check, Trockenlauf) erledigen, sonst die Phasen eines Laufs ausführen."""
    loaded = load_cli_config(sys.argv[1:])
    if loaded is None:
        return
    _parser, args, config_report = loaded
    apply_runtime_settings(args)
    agents = setup_agents(args)

    if args.init or (args.task.strip().lower() == "init" and not args.resume):
        run_setup_wizard(Path(args.project).resolve(), agents)
        return
    if args.check:
        print_system_check(agents)
        return

    for note in apply_auto_roles(args, agents):
        say(note)
    project_path = Path(args.project).resolve()
    if not project_path.exists():
        fail("CG-1003", str(project_path))
    if not agents:
        fail("CG-1001")

    if args.from_issue and not args.resume:
        issue = load_issue(project_path, args.from_issue)
        config_report["issue"] = issue
        args.issue_extra = args.task
        args.task = issue_task(issue, args.task)

    guided_dry_run = maybe_first_run_guide(args, agents, project_path, config_report)
    if guided_dry_run is None:
        return

    config_warnings = unsafe_config_warnings(args, project_path, is_git_repo(project_path))
    if not args.dry_run and (args.task or args.resume):
        for warning in config_warnings:
            say(warning)
    if args.dry_run and not show_dry_run(args, agents, project_path, config_warnings, guided_dry_run):
        return

    if not args.task and not args.resume and find_latest_session(project_path / ".dual-loop") is None:
        print_welcome()
        return
    session_dir, state, task = open_session(args, project_path, config_report)
    run = setup_run(args, agents, project_path, session_dir, state, task)
    print_run_banner(run)
    if not run_plan_phase(run):
        return
    if args.candidates:
        run_candidates(run)
        return
    prepare_build(run)
    run_build_phase(run)
    finish_run(run)


def run_cli():
    """Einstieg: unerwartete Fehler mit Fehlercode, Lösungshinweis und Doku-Verweis statt Traceback."""
    try:
        main()
    except BudgetExceeded as exc:
        handle_budget_exceeded(exc)
    except (RuntimeError, ValueError, OSError) as exc:
        if os.environ.get("CLAUDEGRAVITY_DEBUG"):
            raise
        fail(classify_error(str(exc)), str(exc), exit_code=2)
