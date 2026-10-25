"""Fehlercodes CG-1xxx mit Lösungshinweis und Doku-Verweis."""

import re
import sys

from .common import say
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


def error_doc_link(code: str) -> str:
    """Link auf den Abschnitt des Fehlercodes in der Doku zur Fehlerbehebung."""
    return f"{ERROR_DOC}#{code.lower()}"


def format_error(code: str, detail: str | None = None) -> str:
    """Fehlermeldung mit Code, Lösungshinweis und Doku-Link; Geheimnisse im Detail werden geschwärzt."""
    title, fix = ERROR_CODES.get(code, ERROR_CODES["CG-1999"])
    lines = [f"❌ [{code}] {title}" + (f": {mask_secrets(detail.strip())}" if detail and detail.strip() else "")]
    lines.append(f"   👉 {fix}")
    lines.append(f"   📖 {error_doc_link(code)}")
    return "\n".join(lines)


def fail(code: str, detail: str | None = None, exit_code: int = 1):
    """Beendet mit Fehlercode, Lösungshinweis und Doku-Verweis."""
    say(format_error(code, detail), file=sys.stderr)
    sys.exit(exit_code)
