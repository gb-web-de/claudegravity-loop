"""Fehlercodes CG-1xxx mit Lösungshinweis und Doku-Verweis."""

import re
import sys

from .common import SETTINGS, say
from .safety import mask_secrets


# ==========================================
# Fehlercodes (CG-1xxx) mit Lösungshinweis und Doku-Verweis
# ==========================================
ERROR_DOC = "docs/de/fehlerbehebung.md"
ERROR_CODES = {
    "CG-1001": (
        "Kein KI-Backend gefunden",
        "Eine KI-CLI installieren und anmelden (z. B. `claude`, `codex`, `agy`), Ollama starten oder --endpoint <url> angeben. Prüfen mit `claudegravity --info`.",
    ),
    "CG-1002": (
        "Gewählte CLI ist nicht verfügbar",
        "Name mit `claudegravity --info` vergleichen (z. B. `ollama` ist der Ollama-Server) und die CLI installieren oder anmelden.",
    ),
    "CG-1003": ("Projektordner existiert nicht", "Pfad bei -p prüfen oder in den Projektordner wechseln."),
    "CG-1004": ("Keine Sitzung zum Fortsetzen", "Mit -p das richtige Projekt angeben oder eine neue Aufgabe starten."),
    "CG-1101": (
        "Unbekannte Vorlage",
        "Eingebaute Vorlagen: bugfix, feature, refactor. Eigene Vorlagen stehen im Profil unter `templates`.",
    ),
    "CG-1103": (
        "Budget-Angabe ungültig",
        'Beispiele: --budget-max 500k (Tokens), --budget-max 2.50usd, --budget-roles "bauleiter=300k,abnahme=0.50usd".',
    ),
    "CG-1102": (
        "Vorlage braucht einen Prüfbefehl",
        '--proof "<testbefehl>" angeben oder `proof` ins Profil schreiben (`claudegravity init` hilft).',
    ),
    "CG-1201": (
        "Verbindung zum Endpunkt fehlgeschlagen",
        "Läuft der Server (Ollama: `ollama serve`)? URL und Port mit `curl <url>/models` prüfen, VPN/Firewall prüfen.",
    ),
    "CG-1202": (
        "Zeitüberschreitung beim Endpunkt",
        "Mehr Zeit mit --timeout <sekunden> bzw. CLAUDEGRAVITY_TIMEOUT, ein kleineres Modell oder kleinere Etappen (--etappen an).",
    ),
    "CG-1203": (
        "Anmeldung abgelehnt (HTTP 401/403)",
        "CLAUDEGRAVITY_API_KEY setzen oder --api-key angeben; bei CLIs neu anmelden (z. B. `claude login`, `codex login`).",
    ),
    "CG-1204": (
        "Modell oder Adresse nicht gefunden (HTTP 404)",
        "Modellnamen mit `ollama list` bzw. `curl <url>/models` prüfen; die URL endet meist auf /v1.",
    ),
    "CG-1205": ("Leere oder unlesbare Antwort", "Anderes Modell wählen; sehr kleine Modelle halten das Antwortformat oft nicht ein."),
    "CG-1206": (
        "KI-CLI meldet einen Fehler",
        "Die CLI einmal von Hand im Terminal starten und ihre Meldung lesen; oft fehlt die Anmeldung oder ein Update.",
    ),
    "CG-1301": (
        "Ratenlimit erreicht",
        "Wechseln, warten oder Stand sichern; mit --auto-switch wechselt der Loop selbst. Fortsetzen mit `claudegravity -c`.",
    ),
    "CG-1302": (
        "Anbieter antwortet auch nach Neuversuchen nicht",
        "Später mit `claudegravity -c` fortsetzen oder den Anbieter wechseln; Zahl der Neuversuche mit --retries.",
    ),
    "CG-1401": (
        "Rundenlimit ohne Fertigmeldung",
        "Mit `claudegravity -c -m 20` weitere Runden anhängen; ein --proof hilft dem Bauleiter, das Ziel zu erkennen.",
    ),
    "CG-1402": (
        "Abnahme-Limit erreicht, Befunde offen",
        "Befunde in INSPECTION_round*.md lesen und mit `claudegravity -c` nacharbeiten lassen; mehr Runden mit --max-inspections.",
    ),
    "CG-1403": (
        "Etappe nach drei Versuchen nicht grün",
        "Ausgabe des Prüfbefehls in LOG.md lesen, Plan oder Etappe anpassen und mit `claudegravity -c` weitermachen.",
    ),
    "CG-1404": (
        "Hartes Budget erreicht",
        "Bericht mit Abbruchgrund steht in AUDIT.md. Weiter mit höherem Budget: `claudegravity -c --budget-max <wert>`, oder günstiger mit --strategy hybrid/eco bzw. weniger Runden (-m).",
    ),
    "CG-1501": (
        "Schreibversuch blockiert",
        "Ein Modell wollte außerhalb des Projekts oder in eine Geheimnis-Datei schreiben. Plan und Aufgabe prüfen.",
    ),
    "CG-1502": (
        "Lesende Rolle hat Dateien geändert",
        "Änderungen mit `git status` prüfen und bei Bedarf zurücknehmen; für diese CLI nur als Bauleiter einsetzen.",
    ),
    "CG-1503": (
        "Mögliche Zugangsdaten in einer Modellantwort",
        "Antwort prüfen; Zugangsdaten nur über Umgebungsvariablen nutzen und kompromittierte Schlüssel erneuern.",
    ),
    "CG-1504": (
        "Tests abgeschwächt oder entfernt",
        "Diff der Testdateien prüfen. Ist die Änderung nicht gewollt, Tests wiederherstellen; mit --test-guard strict "
        "weist der Loop solche Fertigmeldungen selbst zurück.",
    ),
    "CG-1999": ("Unerwarteter Fehler", "Bitte mit der vollständigen Ausgabe als Issue melden."),
}
ERROR_CODES_EN = {
    "CG-1001": (
        "No AI backend found",
        "Install and sign in to an AI CLI (e.g. `claude`, `codex`, `agy`), start Ollama or pass --endpoint <url>. Check with `claudegravity --info`.",
    ),
    "CG-1002": (
        "Selected CLI is not available",
        "Compare the name with `claudegravity --info` (e.g. `ollama` is the Ollama server) and install or sign in to the CLI.",
    ),
    "CG-1003": ("Project folder does not exist", "Check the path given with -p or change into the project folder."),
    "CG-1004": ("No session to resume", "Point -p at the right project or start a new task."),
    "CG-1101": (
        "Unknown template",
        "Built-in templates: bugfix, feature, refactor. Your own templates live in a profile under `templates`.",
    ),
    "CG-1103": (
        "Invalid budget",
        'Examples: --budget-max 500k (tokens), --budget-max 2.50usd, --budget-roles "bauleiter=300k,abnahme=0.50usd".',
    ),
    "CG-1102": (
        "Template needs a proof command",
        'Pass --proof "<test command>" or put `proof` in a profile (`claudegravity init` helps).',
    ),
    "CG-1201": (
        "Connection to endpoint failed",
        "Is the server running (Ollama: `ollama serve`)? Check URL and port with `curl <url>/models`, check VPN/firewall.",
    ),
    "CG-1202": (
        "Endpoint timed out",
        "More time with --timeout <seconds> or CLAUDEGRAVITY_TIMEOUT, a smaller model or smaller stages (--etappen an).",
    ),
    "CG-1203": (
        "Authentication rejected (HTTP 401/403)",
        "Set CLAUDEGRAVITY_API_KEY or pass --api-key; for CLIs sign in again (e.g. `claude login`, `codex login`).",
    ),
    "CG-1204": (
        "Model or address not found (HTTP 404)",
        "Check the model name with `ollama list` or `curl <url>/models`; the URL usually ends in /v1.",
    ),
    "CG-1205": ("Empty or unreadable answer", "Choose another model; very small models often do not keep the answer format."),
    "CG-1206": (
        "AI CLI reports an error",
        "Start the CLI once by hand in a terminal and read its message; often the sign-in or an update is missing.",
    ),
    "CG-1301": (
        "Rate limit reached",
        "Switch, wait or save the state; with --auto-switch the loop switches by itself. Resume with `claudegravity -c`.",
    ),
    "CG-1302": (
        "Provider does not answer even after retries",
        "Resume later with `claudegravity -c` or switch providers; number of retries via --retries.",
    ),
    "CG-1401": (
        "Round limit without completion signal",
        "Add rounds with `claudegravity -c -m 20`; a --proof helps the builder see the goal.",
    ),
    "CG-1402": (
        "Acceptance limit reached, findings open",
        "Read the findings in INSPECTION_round*.md and let the builder rework them with `claudegravity -c`; more rounds with --max-inspections.",
    ),
    "CG-1403": (
        "Stage not green after three attempts",
        "Read the proof output in LOG.md, adjust the plan or stage and continue with `claudegravity -c`.",
    ),
    "CG-1404": (
        "Hard budget reached",
        "The report with the abort reason is in AUDIT.md. Continue with a higher budget: `claudegravity -c --budget-max <value>`, or cheaper with --strategy hybrid/eco or fewer rounds (-m).",
    ),
    "CG-1501": (
        "Write attempt blocked",
        "A model tried to write outside the project or into a secret file. Check the plan and the task.",
    ),
    "CG-1502": (
        "Read-only role changed files",
        "Check the changes with `git status` and revert them if needed; use this CLI only as builder.",
    ),
    "CG-1503": (
        "Possible credentials in a model answer",
        "Check the answer; use credentials only via environment variables and rotate compromised keys.",
    ),
    "CG-1504": (
        "Tests weakened or removed",
        "Check the diff of the test files. If the change is not intended, restore the tests; with --test-guard strict "
        "the loop rejects such completion reports itself.",
    ),
    "CG-1999": ("Unexpected error", "Please report it as an issue with the full output."),
}
ERROR_PATTERNS = [
    ("CG-1002", r"Agent-CLI '.*' ist nicht verfügbar"),
    ("CG-1203", r"HTTP 40[13]\b|unauthori[sz]ed|not logged in|nicht angemeldet|please (?:log ?in|login)|authentication"),
    ("CG-1204", r"HTTP 404\b|model .*not found|Modell .*nicht gefunden"),
    ("CG-1202", r"Zeitüberschreitung|Zeitlimit|timed? ?out"),
    ("CG-1201", r"Verbindungsfehler|connection (?:refused|reset)|Name or service not known|getaddrinfo"),
    ("CG-1205", r"Leere Antwort|JSONDecodeError|Expecting value"),
    ("CG-1206", r"Fehler \(Code \d+\)|(?:Claude|Antigravity|Codex) Fehler"),
]
AUDIT_EVENT_CODES = {"blocked_write": "CG-1501", "readonly_changed": "CG-1502", "secret_in_output": "CG-1503", "tests_weakened": "CG-1504"}


def classify_error(text: str) -> str:
    """Fehlercode CG-1xxx zu einem Fehlertext; CG-1999, wenn kein Muster passt."""
    for code, pattern in ERROR_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return code
    return "CG-1999"


def error_entry(code: str) -> tuple[str, str]:
    """(Titel, Lösungshinweis) eines Fehlercodes in der Sprache des Laufs; unbekannte Codes wie CG-1999."""
    codes = ERROR_CODES_EN if SETTINGS.lang == "en" else ERROR_CODES
    return codes.get(code, codes["CG-1999"])


def error_doc_link(code: str) -> str:
    """Link auf den Abschnitt des Fehlercodes in der Doku zur Fehlerbehebung (docs/en bei --lang en)."""
    doc = ERROR_DOC.replace("docs/de/", "docs/en/") if SETTINGS.lang == "en" else ERROR_DOC
    return f"{doc}#{code.lower()}"


def format_error(code: str, detail: str | None = None) -> str:
    """Fehlermeldung mit Code, Lösungshinweis und Doku-Link; Geheimnisse im Detail werden geschwärzt."""
    title, fix = error_entry(code)
    lines = [f"❌ [{code}] {title}" + (f": {mask_secrets(detail.strip())}" if detail and detail.strip() else "")]
    lines.append(f"   👉 {fix}")
    lines.append(f"   📖 {error_doc_link(code)}")
    return "\n".join(lines)


def fail(code: str, detail: str | None = None, exit_code: int = 1):
    """Beendet mit Fehlercode, Lösungshinweis und Doku-Verweis."""
    say(format_error(code, detail), file=sys.stderr)
    sys.exit(exit_code)
