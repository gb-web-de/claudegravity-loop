"""Konfiguration in Schichten: Kommandozeile, Session, Vorlage, Umgebung, Projekt- und globales Profil."""

import argparse
import contextlib
import json
import os
from pathlib import Path

from .common import tr
from .session import find_latest_session, load_session_state


# ==========================================
# Konfiguration in Schichten: CLI > Umgebung > Profil > Standard
# ==========================================
CONFIG_ENV_PREFIX = "CLAUDEGRAVITY_"
PROFILE_FILE = "profile.json"
# Nicht über Umgebung oder Profil setzbar: Aufgabe/Ziel, einmalige Aktionen und Geheimnisse
CONFIG_EXCLUDED = {
    "help",
    "help_all",
    "version",
    "task",
    "project",
    "resume",
    "check",
    "dry_run",
    "print_effective_config",
    "api_key",
    "no_shield",
    "init",
    "from_issue",
}
# Das Projekt-Profil liegt im Projektordner, in den ein Bauleiter schreiben kann: keine Rechte daraus
PROJECT_PROFILE_FORBIDDEN = {"yolo", "open_pr", "pr_draft", "sandbox", "sandbox_image", "sandbox_net"}
# Standardwerte, die erst später im Lauf gesetzt werden (für --print-effective-config)
CONFIG_DISPLAY_DEFAULTS = {"strategy": "balanced", "max_iterations": "10 (Etappen: 2 je Etappe + 2)"}
# Beim Fortsetzen gilt der gespeicherte Stand der Session vor Umgebung und Profil
SESSION_CONFIG_KEYS = {
    "strategy": "strategy",
    "planner": "planner_binary",
    "reviewer": "reviewer_binary",
    "builder": "builder_binary",
    "planner_model": "planner_model",
    "reviewer_model": "reviewer_model",
    "builder_model": "builder_model",
    "planner_effort": "planner_effort",
    "reviewer_effort": "reviewer_effort",
    "builder_effort": "builder_effort",
    "inspector": "inspector_binary",
    "inspector_model": "inspector_model",
    "inspector_effort": "inspector_effort",
    "proof": "proof",
    "etappen": "stage_mode",
    "approve_plan": "approve_plan",
    "auto_switch": "auto_switch",
    "merge": "merge_worktree",
    "ask": "ask_mode",
    "swap": "swap_roles",
    "yolo": "yolo_enabled",
    "inspect": "inspect",
    "template": "template",
    "open_pr": "open_pr",
    "pr_draft": "pr_draft",
    "sandbox": "sandbox",
    "sandbox_image": "sandbox_image",
    "sandbox_net": "sandbox_net",
}
TEMPLATE_DEST = "template"
TEMPLATE_META_KEYS = {"hint", "hinweis", "requires", "pflicht", "beschreibung", "description"}
# Eingebaute Vorlagen; Profile ändern sie oder fügen eigene hinzu ("templates": {"bugfix": {...}, "typo3": {...}})
TASK_TEMPLATES = {
    "bugfix": {
        "beschreibung": "Fehler beheben: sparsam, ohne Etappen, Test zuerst",
        "strategy": "eco",
        "etappen": "aus",
        "max_iterations": 5,
        "requires": ["proof"],
        "hint": "Behebe den Fehler mit möglichst kleiner Änderung. Schreibe zuerst einen Test, der den Fehler zeigt, und lass ihn dann grün werden.",
    },
    "feature": {
        "beschreibung": "Neue Funktion: ausgewogen, Etappen nach Bedarf",
        "strategy": "balanced",
        "etappen": "auto",
        "hint": "Setze die Funktion vollständig um, mit Tests für die neuen Fälle und kurzer Doku, wo Nutzer sie brauchen.",
    },
    "refactor": {
        "beschreibung": "Umbau ohne Verhaltensänderung: strenge Prüfung, Abnahme an",
        "reviewer_effort": "high",
        "inspect": True,
        "max_rounds": 3,
        "requires": ["proof"],
        "hint": "Ändere die Struktur, nicht das Verhalten. Alle bestehenden Tests müssen unverändert grün bleiben.",
    },
}
CONFIG_SOURCE_LABELS = {
    "cli": "Kommandozeile",
    "session": "Session (Fortsetzen)",
    "template": "Vorlage",
    "env": "Umgebung",
    "project": "Projekt-Profil",
    "global": "Globales Profil",
    "default": "Standard",
}


def source_label(source: str) -> str:
    """Anzeigename einer Konfigurationsquelle (cli, env, project …) in der Sprache des Laufs."""
    return tr(CONFIG_SOURCE_LABELS[source])


TRUE_WORDS = {"1", "true", "yes", "ja", "an", "on", "y", "j"}
FALSE_WORDS = {"0", "false", "no", "nein", "aus", "off", "n", ""}


def global_profile_path(env: dict | None = None) -> Path:
    """~/.config/claudegravity/profile.json (XDG_CONFIG_HOME bzw. %APPDATA% unter Windows)."""
    env = os.environ if env is None else env
    if env.get("CLAUDEGRAVITY_CONFIG_DIR"):
        base = Path(env["CLAUDEGRAVITY_CONFIG_DIR"]).expanduser()
    elif os.name == "nt" and env.get("APPDATA"):
        base = Path(env["APPDATA"]) / "claudegravity"
    else:
        base = Path(env.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "claudegravity"
    return base / PROFILE_FILE


def project_profile_path(project_path: Path) -> Path:
    """Pfad des Projekt-Profils (.dual-loop/profile.json)."""
    return project_path / ".dual-loop" / PROFILE_FILE


def config_actions(parser: argparse.ArgumentParser) -> dict[str, argparse.Action]:
    """Optionen des Parsers, die über Profile, Umgebung und Vorlagen setzbar sind (ohne Ausnahmen aus CONFIG_EXCLUDED)."""
    return {a.dest: a for a in parser._actions if a.dest not in CONFIG_EXCLUDED and a.option_strings}


def config_key_aliases(parser: argparse.ArgumentParser) -> dict[str, str]:
    """Profil-Schlüssel -> dest. Erlaubt dest (`builder_model`) und Flag-Namen (`bauer-model`)."""
    aliases: dict[str, str] = {}
    for dest, action in config_actions(parser).items():
        aliases[dest] = dest
        if isinstance(action, argparse._StoreFalseAction):
            continue  # `no_worktree: true` wäre doppelt verneint; nur `worktree: false` zulassen
        for opt in action.option_strings:
            if opt.startswith("--"):
                aliases[opt[2:].replace("-", "_")] = dest
    return aliases


def coerce_config_value(action: argparse.Action, value):
    """Prüft einen Wert aus Umgebung, Profil oder Session gegen Typ und Auswahl des Flags."""
    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in TRUE_WORDS:
            return True
        if text in FALSE_WORDS:
            return False
        raise ValueError(f"erwartet ja/nein, bekommen {value!r}")
    if isinstance(value, (bool, list, dict)) or value is None:
        raise ValueError(f"ungültiger Wert {value!r}")
    if action.type is int:
        if isinstance(value, float) or not str(value).strip().lstrip("-").isdigit():
            raise ValueError(f"erwartet eine ganze Zahl, bekommen {value!r}")
        value = int(str(value).strip())
    else:
        value = str(value)
    if action.choices and value not in action.choices:
        raise ValueError(f"{value!r} ist keine erlaubte Auswahl ({', '.join(map(str, action.choices))})")
    return value


def load_profile(path: Path) -> tuple[dict, list[str]]:
    """Liest ein Profil (flaches JSON-Objekt). Fehlt die Datei, ist das kein Fehler."""
    if not path.is_file():
        return {}, []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, [f"⚠️ Profil {path} nicht lesbar ({exc}); wird ignoriert."]
    if not isinstance(data, dict):
        return {}, [f"⚠️ Profil {path} muss ein JSON-Objekt sein; wird ignoriert."]
    return data, []


def resolve_config(
    parser: argparse.ArgumentParser,
    explicit: dict,
    env: dict,
    project_profile: dict,
    global_profile: dict,
    session_state: dict | None = None,
) -> tuple[dict, dict, list[str], list[str], dict | None]:
    """Ermittelt je Einstellung Wert und Quelle.

    Reihenfolge: Kommandozeile > Session (nur beim Fortsetzen) > Vorlage > Umgebung > Projekt-Profil
    > globales Profil > Standard. Liefert (Werte, Quellen, Konflikte, Warnungen, Vorlage).
    """
    actions = config_actions(parser)
    aliases = config_key_aliases(parser)
    warnings: list[str] = []
    layers: dict[str, dict] = {"session": {}, "env": {}, "project": {}, "global": {}}

    template_defs: dict[str, dict] = {name: dict(spec) for name, spec in TASK_TEMPLATES.items()}
    template_origin: dict[str, str] = {name: "eingebaut" for name in TASK_TEMPLATES}
    for layer, profile in (("global", global_profile), ("project", project_profile)):
        label = CONFIG_SOURCE_LABELS[layer]
        custom = profile.get("templates", profile.get("vorlagen"))
        if custom is not None and not isinstance(custom, dict):
            warnings.append(f"⚠️ {label}: `templates` muss ein Objekt sein; wird ignoriert.")
            custom = None
        for name, spec in (custom or {}).items():
            if not isinstance(spec, dict):
                warnings.append(f"⚠️ {label}: Vorlage `{name}` muss ein Objekt sein; wird ignoriert.")
                continue
            template_defs.setdefault(name.lower(), {}).update(spec)
            template_origin[name.lower()] = label
        entries = {k: v for k, v in profile.items() if k not in ("templates", "vorlagen")}
        layers[layer], more = parse_config_entries(
            entries, label, actions, aliases, forbidden=PROJECT_PROFILE_FORBIDDEN if layer == "project" else set()
        )
        warnings += more

    for dest, action in actions.items():
        name = CONFIG_ENV_PREFIX + dest.upper()
        if name in env:
            try:
                layers["env"][dest] = coerce_config_value(action, env[name])
            except ValueError as exc:
                warnings.append(f"⚠️ Umgebung: {name} {exc}; wird ignoriert.")

    for dest, state_key in SESSION_CONFIG_KEYS.items():
        if session_state and dest in actions and session_state.get(state_key) not in (None, ""):
            # Alter Session-Stand mit inzwischen anderen Auswahlwerten: Standard greift
            with contextlib.suppress(ValueError):
                layers["session"][dest] = coerce_config_value(actions[dest], session_state[state_key])

    # Vorlage: selbst eine Einstellung (Kommandozeile, Session, Umgebung, Profil), wirkt direkt nach der Session
    template_name = next(
        (
            src[TEMPLATE_DEST]
            for src in (explicit, layers["session"], layers["env"], layers["project"], layers["global"])
            if src.get(TEMPLATE_DEST)
        ),
        None,
    )
    layers["template"] = {}
    template_info = None
    if template_name:
        spec = template_defs.get(str(template_name).lower())
        if spec is None:
            warnings.append(f"❌ Unbekannte Vorlage `{template_name}`. Verfügbar: {', '.join(sorted(template_defs))}.")
        else:
            entries = {k: v for k, v in spec.items() if k not in TEMPLATE_META_KEYS}
            forbidden = PROJECT_PROFILE_FORBIDDEN | {TEMPLATE_DEST}
            layers["template"], more = parse_config_entries(entries, f"Vorlage `{template_name}`", actions, aliases, forbidden=forbidden)
            warnings += more
            template_info = {
                "name": str(template_name).lower(),
                "origin": template_origin.get(str(template_name).lower()),
                "hint": spec.get("hint") or spec.get("hinweis"),
                "requires": list(spec.get("requires") or spec.get("pflicht") or []),
            }

    values: dict = {}
    sources: dict = {}
    conflicts: list[str] = []
    for dest, action in actions.items():
        candidates = []
        if dest in explicit:
            candidates.append(("cli", explicit[dest]))
        for layer in ("session", "template", "env", "project", "global"):
            if dest in layers[layer]:
                candidates.append((layer, layers[layer][dest]))
        if candidates:
            source, value = candidates[0]
            losers = [(s, v) for s, v in candidates[1:] if v != value]
            if losers:
                overridden = ", ".join(f"{source_label(s)} {v!r}" for s, v in losers)
                conflicts.append(tr(f"{dest}: {source_label(source)} {value!r} überschreibt {overridden}"))
        else:
            source, value = "default", action.default
        values[dest] = value
        sources[dest] = source
    return values, sources, conflicts, warnings, template_info


def parse_config_entries(entries: dict, label: str, actions: dict, aliases: dict, forbidden: set) -> tuple[dict, list[str]]:
    """Prüft Einträge aus Profil oder Vorlage gegen die Flags. Liefert (dest -> Wert, Warnungen)."""
    result: dict = {}
    warnings: list[str] = []
    for raw_key, raw_value in entries.items():
        if raw_key.startswith(("_", "$")):
            continue  # Kommentare und Metadaten
        key = raw_key.strip().lower().replace("-", "_")
        if key in ("api_key", "apikey"):
            warnings.append(f"⚠️ {label}: `{raw_key}` wird ignoriert. Schlüssel gehören in CLAUDEGRAVITY_API_KEY, nie in eine Datei.")
            continue
        dest = aliases.get(key)
        if not dest:
            warnings.append(f"⚠️ {label}: unbekannte Einstellung `{raw_key}` wird ignoriert.")
            continue
        if dest in forbidden:
            warnings.append(
                f"⚠️ {label}: `{raw_key}` wird ignoriert. Schreib- und Veröffentlichungsrechte nur per Kommandozeile, Umgebung oder globalem Profil."
            )
            continue
        try:
            result[dest] = coerce_config_value(actions[dest], raw_value)
        except ValueError as exc:
            warnings.append(f"⚠️ {label}: `{raw_key}` {exc}; wird ignoriert.")
    return result, warnings


def explicit_cli_values(parser: argparse.ArgumentParser, argv: list[str]) -> dict:
    """Nur die Flags, die wirklich auf der Kommandozeile stehen (ohne Standardwerte)."""
    saved = {a.dest: a.default for a in parser._actions}
    try:
        for action in parser._actions:
            action.default = argparse.SUPPRESS
        namespace, _ = parser.parse_known_args(argv)
    finally:
        for action in parser._actions:
            action.default = saved[action.dest]
    return vars(namespace)


def apply_config_layers(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    argv: list[str],
    env: dict | None = None,
    global_path: Path | None = None,
) -> dict:
    """Setzt Werte aus Umgebung, Profilen und (beim Fortsetzen) der Session in `args`."""
    env = dict(os.environ) if env is None else env
    project_path = Path(args.project).expanduser().resolve()
    paths = {
        "global": global_path or global_profile_path(env),
        "project": project_profile_path(project_path),
    }
    global_profile, warnings = load_profile(paths["global"])
    project_profile, more = load_profile(paths["project"])
    warnings += more
    session_state = None
    if getattr(args, "resume", False):
        latest = find_latest_session(project_path / ".dual-loop")
        session_state = load_session_state(latest) if latest else None
    explicit = explicit_cli_values(parser, argv)
    values, sources, conflicts, more, template = resolve_config(parser, explicit, env, project_profile, global_profile, session_state)
    warnings += more
    for dest, value in values.items():
        setattr(args, dest, value)
    return {
        "values": values,
        "sources": sources,
        "conflicts": conflicts,
        "warnings": warnings,
        "paths": paths,
        "template": template,
        "loaded": {k: bool(v) for k, v in (("global", global_profile), ("project", project_profile))},
    }


def format_effective_config(report: dict) -> str:
    """Ausgabe für --print-effective-config: Schichten, geladene Profile und Wert mit Quelle je Einstellung."""
    lines = [
        tr("⚙️  Wirksame Konfiguration (Kommandozeile > Session > Vorlage > Umgebung > Projekt-Profil > globales Profil > Standard)"),
        "",
    ]
    for layer in ("project", "global"):
        state = tr("geladen" if report["loaded"][layer] else "nicht vorhanden")
        lines.append(f"  {source_label(layer):<16}: {report['paths'][layer]} ({state})")
    lines.append(f"  {tr('Umgebung'):<16}: " + tr(f"{CONFIG_ENV_PREFIX}<EINSTELLUNG>, z. B. {CONFIG_ENV_PREFIX}STRATEGY=hybrid"))
    tpl = report.get("template")
    if tpl:
        lines.append(
            f"  {tr('Vorlage'):<16}: {tpl['name']} ({tpl['origin']})"
            + (tr(f", Pflicht: {', '.join(tpl['requires'])}") if tpl["requires"] else "")
        )
    lines.append("")
    conflict_keys = {c.split(":", 1)[0] for c in report["conflicts"]}
    width = max(len(k) for k in report["values"])
    for dest in sorted(report["values"]):
        value = report["values"][dest]
        if value is None and report["sources"][dest] == "default" and dest in CONFIG_DISPLAY_DEFAULTS:
            value = tr(CONFIG_DISPLAY_DEFAULTS[dest])
        shown = "–" if value is None else (json.dumps(value, ensure_ascii=False) if isinstance(value, str) else str(value).lower())
        mark = tr("  ⚠️ Konflikt") if dest in conflict_keys else ""
        lines.append(f"  {dest:<{width}} = {shown:<28} [{source_label(report['sources'][dest])}]{mark}")
    if report["conflicts"]:
        lines += ["", tr("Konflikte:")] + [f"  ⚠️ {tr(c)}" for c in report["conflicts"]]
    if report["warnings"]:
        lines += [""] + [f"  {w}" for w in report["warnings"]]
    return "\n".join(lines)
