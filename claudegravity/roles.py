"""Rollenbelegung: Strategien, automatische Rollen, Abnahme-Auswahl und Eskalation."""

from .common import CLOUD_PLANNER_ORDER, ENDPOINT_BINARIES, HYBRID_STRATEGIES, LOCAL_BACKEND_ORDER, OLLAMA_KEYS
from .backends import AgentCLI, DEFAULT_MODEL_LABEL, list_ollama_models, ollama_base_url, pick_ollama_model
from .session import get_permission_flags


def stages_wanted(mode: str | None, builder_binary: str) -> bool:
    """Etappen-Modus an? `auto` schaltet ihn für Bauleiter ohne eigenen Dateizugriff ein."""
    mode = (mode or "auto").lower()
    if mode in ("an", "on"):
        return True
    if mode in ("aus", "off"):
        return False
    return builder_binary in ENDPOINT_BINARIES


def apply_auto_roles(args, agents: dict[str, AgentCLI], models: list[dict] | None = None) -> list[str]:
    """Füllt fehlende Rollen (Strategie hybrid) und Ollama-Modelle aus den installierten Modellen.

    Ausdrückliche Angaben des Nutzers bleiben immer unverändert. Liefert Hinweise für die Ausgabe.
    """
    notes: list[str] = []
    if getattr(args, "resume", False):
        return notes
    strat = (args.strategy or "").lower()
    if strat in HYBRID_STRATEGIES:
        cloud = next((k for k in CLOUD_PLANNER_ORDER if k in agents), None)
        local = next((k for k in LOCAL_BACKEND_ORDER if k in agents), None)
        if not cloud or not local:
            notes.append(
                "⚠️ Strategie hybrid braucht eine Cloud-CLI (codex, claude, agy oder gemini) und ein lokales Modell "
                "(Ollama, LM Studio oder --endpoint). Es fehlt: " + ("Cloud-CLI" if not cloud else "lokales Modell") + "."
            )
        else:
            args.planner = args.planner or cloud
            args.reviewer = args.reviewer or local
            args.builder = args.builder or local
            if not args.inspector:
                args.inspector = args.planner if args.planner != args.builder else cloud
            notes.append(
                f"🧭 Strategie hybrid: Architekt {args.planner}, Prüfstatiker {args.reviewer}, "
                f"Bauleiter {args.builder}, Abnahme {args.inspector}."
            )

    builder_key = args.builder
    if not builder_key and strat in ("local-free", "free", "local"):
        builder_key = next((k for k in LOCAL_BACKEND_ORDER if k in agents), None)
    roles = [
        ("Bauleiter", builder_key, "builder_model", "builder"),
        ("Architekt", args.planner, "planner_model", "planner"),
        ("Prüfstatiker", args.reviewer, "reviewer_model", "reviewer"),
        ("Abnahme", args.inspector, "inspector_model", "reviewer"),
    ]
    if not any(key in OLLAMA_KEYS and not getattr(args, attr) for _, key, attr, _ in roles):
        return notes
    if models is None:
        models = list_ollama_models(ollama_base_url())
    if not models:
        notes.append("⚠️ Keine Ollama-Modelle gefunden (/api/tags). Es gelten die Standardmodelle; installiere eins mit `ollama pull`.")
        return notes

    for label, key, attr, pref in roles:
        if key not in OLLAMA_KEYS or getattr(args, attr):
            continue
        exclude: set[str] = set()
        if attr in ("reviewer_model", "inspector_model") and builder_key in OLLAMA_KEYS and args.builder_model:
            exclude.add(args.builder_model)
        if attr == "reviewer_model" and args.planner in OLLAMA_KEYS and args.planner_model:
            exclude.add(args.planner_model)
        if attr == "planner_model" and args.reviewer in OLLAMA_KEYS and args.reviewer_model:
            exclude.add(args.reviewer_model)
        chosen = pick_ollama_model(models, pref, exclude)
        if chosen is None:
            chosen = pick_ollama_model(models, pref)
            notes.append(
                f"⚠️ Nur ein passendes Ollama-Modell installiert: {label} nutzt {chosen} wie eine andere Rolle und ist damit nicht unabhängig."
            )
        setattr(args, attr, chosen)
        notes.append(f"🤖 {label}: Ollama-Modell {chosen} automatisch gewählt (ändern mit --{ROLE_MODEL_FLAGS[attr]}).")
    return notes


ROLE_MODEL_FLAGS = {
    "builder_model": "bauer-model",
    "planner_model": "architekt-model",
    "reviewer_model": "pruefstatiker-model",
    "inspector_model": "abnahme-model",
}


def dry_run_command(args, task: str, strat: str, default_b_model: str | None = None) -> list[str]:
    """Befehl, der genau die Belegung des Trockenlaufs startet (alle Rollen-, Modell- und Effort-Flags)."""
    if getattr(args, "from_issue", None):
        # Der Aufgabentext kommt aus dem Issue; nur ein eigener Zusatz steht im Befehl
        extra = getattr(args, "issue_extra", "")
        cmd = ["claudegravity"] + ([extra] if extra else []) + ["--from-issue", str(args.from_issue)]
    else:
        cmd = ["claudegravity", task]
    if strat != "balanced":
        cmd += ["--strategy", strat]
    pairs = [
        ("--endpoint", args.endpoint),
        ("--architekt-endpoint", args.architekt_endpoint),
        ("--pruefstatiker-endpoint", args.pruefstatiker_endpoint),
        ("--bauer-endpoint", args.bauer_endpoint),
        ("--architekt", args.planner),
        ("--architekt-model", args.planner_model),
        ("--architekt-effort", args.planner_effort),
        ("--pruefstatiker", args.reviewer),
        ("--pruefstatiker-model", args.reviewer_model),
        ("--pruefstatiker-effort", args.reviewer_effort),
        ("--bauer", args.builder),
        ("--bauer-model", args.builder_model or default_b_model),
        ("--bauer-effort", args.builder_effort),
        ("--kandidaten", getattr(args, "candidates", None)),
        ("--test-guard", None if getattr(args, "test_guard", "warn") == "warn" else args.test_guard),
        ("--lang", getattr(args, "lang", None)),
        ("--repo-map", None if getattr(args, "repo_map", "auto") == "auto" else args.repo_map),
        ("--abnahme", args.inspector),
        ("--abnahme-model", args.inspector_model),
        ("--abnahme-effort", args.inspector_effort),
        ("--effort", args.effort),
        ("--proof", args.proof),
        ("--escalate", args.escalate),
        ("--escalate-after", args.escalate_after),
    ]
    for flag, value in pairs:
        if value:
            cmd += [flag, str(value)]
    if args.etappen not in (None, "auto"):
        cmd += ["--etappen", args.etappen]
    for flag, on in (
        ("--swap", args.swap),
        ("-i", args.ask),
        ("--yolo", args.yolo),
        ("--plan-auto", args.approve_plan),
        ("--auto-switch", args.auto_switch),
        ("--merge", args.merge),
        ("--open-pr", getattr(args, "open_pr", False) and not getattr(args, "pr_draft", False)),
        ("--pr-draft", getattr(args, "pr_draft", False)),
        ("--no-inspect", not args.inspect),
    ):
        if on:
            cmd.append(flag)
    if args.max_iterations:
        cmd += ["-m", str(args.max_iterations)]
    if args.project != ".":
        cmd += ["-p", args.project]
    return cmd


def same_identity(a: AgentCLI, b: AgentCLI) -> bool:
    """Gleicher Anbieter und kein ausdrücklich anderes Modell: dann prüft sich das Modell selbst."""
    if a.binary != b.binary:
        return False
    ma = a.model if a.model and a.model != DEFAULT_MODEL_LABEL else None
    mb = b.model if b.model and b.model != DEFAULT_MODEL_LABEL else None
    return not (ma and mb and ma != mb)


def pick_inspector(builder: AgentCLI, candidates: list[AgentCLI], agents: dict[str, AgentCLI]) -> AgentCLI | None:
    """Abnahme-Agent: der erste Kandidat, der nicht der Bauleiter ist, sonst irgendeine andere CLI."""
    for cand in candidates:
        if cand is not None and not same_identity(cand, builder):
            return cand
    for cand in agents.values():
        if cand.binary != builder.binary:
            return cand
    return None


ESCALATE_AFTER_DEFAULT = 2


def choose_escalation(
    builder: AgentCLI,
    agents: dict[str, AgentCLI],
    choice: str | None,
    inspector: AgentCLI | None = None,
    prefer: str | None = None,
    write_allowed: bool = False,
) -> tuple[str | None, str]:
    """Ziel, auf das ein lokaler Bauleiter nach wiederholtem Scheitern eskaliert (Schlüssel in agents), oder None mit Grund.

    Nie die Abnahme (sonst prüft sich der neue Bauleiter selbst) und nie eine CLI, die ohne
    Schreibrechte nicht bauen kann.
    """
    if not choice:
        return None, "Eskalation ist aus"
    if not builder.local:
        return None, f"{builder.name} ist kein lokales Modell"

    def refusal(key: str) -> str:
        agent = agents.get(key)
        if agent is None:
            return f"`{key}` ist nicht verfügbar (claudegravity --info zeigt alle)"
        if agent.local or agent.binary == builder.binary:
            return f"{agent.name} ist selbst lokal"
        if inspector is not None and agent.binary == inspector.binary:
            return f"{agent.name} macht die Abnahme und darf nicht selbst bauen"
        if not write_allowed and get_permission_flags(agent.binary):
            return f"{agent.name} bräuchte Schreibrechte (--yolo oder Ja bei der Rechte-Abfrage)"
        return ""

    if choice != "auto":
        why = refusal(choice)
        return (None, why) if why else (choice, "")
    for key in ([prefer] if prefer in agents else []) + list(agents):
        if not refusal(key):
            return key, ""
    return None, "kein Cloud-Anbieter außer der Abnahme verfügbar"


def normalize_strategy(name: str) -> str:
    """Strategie-Aliase auf ihren Hauptnamen abbilden (quality → best-code, economy → eco, free → local-free)."""
    strat = name.lower()
    if strat in ["quality", "best"]:
        return "best-code"
    if strat in ["economy", "cost"]:
        return "eco"
    if strat in ["local-free", "free", "local"]:
        return "local-free"
    return strat


def pick_plan_roles(
    agents: dict[str, AgentCLI],
    architekt_choice: str | None,
    pruefstatiker_choice: str | None,
    swap_roles: bool,
    explicit: bool,
) -> tuple[AgentCLI, AgentCLI]:
    """Architekt und Prüfstatiker wählen: ausdrückliche Wahl, sonst plant Claude und ein anderer Anbieter
    (bevorzugt agy) prüft. --swap tauscht, solange keine Rolle ausdrücklich gesetzt ist (`explicit`)."""
    if swap_roles:
        if not architekt_choice and "agy" in agents:
            architekt_choice = "agy"
        elif not architekt_choice and "gemini" in agents:
            architekt_choice = "gemini"
        if not pruefstatiker_choice and "claude" in agents:
            pruefstatiker_choice = "claude"

    if architekt_choice and architekt_choice in agents:
        planner = agents[architekt_choice]
    elif "claude" in agents and not swap_roles:
        planner = agents["claude"]
    else:
        planner = list(agents.values())[0]

    remaining = [a for a in agents.values() if a.binary != planner.binary]
    if pruefstatiker_choice and pruefstatiker_choice in agents:
        reviewer = agents[pruefstatiker_choice]
    elif remaining:
        agy_cand = [a for a in remaining if a.binary == "agy"]
        reviewer = agy_cand[0] if agy_cand else remaining[0]
    else:
        reviewer = planner

    if swap_roles and not explicit and planner.binary == "claude" and reviewer.binary == "agy":
        planner, reviewer = reviewer, planner
    return planner, reviewer
