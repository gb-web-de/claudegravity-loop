"""Gemeinsame Grundlagen: Ausgabe (say), Laufzeit-Einstellungen, Abbruch, Ratenlimits und Neuversuche."""

import dataclasses
import datetime
import random
import re
import signal
import sys
import time
from typing import TYPE_CHECKING

from .i18n import detect_lang, translate

if TYPE_CHECKING:
    from .budget import Budget

# Cross-Platform Console-Encoding (Windows CMD/PowerShell UTF-8 Fix)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def say(*parts: object, sep: str = " ", end: str = "\n", file=None, flush: bool = False) -> None:
    """Einzige Stelle für Terminal-Ausgaben des Loops (Statuszeilen, Menüs, Ergebnisse).
    Mit --lang en werden die Meldungen übersetzt. Maschinenlesbare Ereignisse gehen zusätzlich über
    log_event() nach events.jsonl."""
    if SETTINGS.lang != "de":
        parts = tuple(translate(p, SETTINGS.lang) if isinstance(p, str) else p for p in parts)
    print(*parts, sep=sep, end=end, file=file, flush=flush)


def tr(text: str) -> str:
    """Meldung in der Sprache des Laufs, für Texte, die nicht über say() gehen (z. B. Rückfragen)."""
    return translate(text, SETTINGS.lang)


def ask(prompt: str) -> str:
    """Rückfrage im Terminal (input) in der Sprache des Laufs."""
    return input(tr(prompt))


@dataclasses.dataclass
class RuntimeSettings:
    """Einstellungen eines Laufs, die tief im Code gebraucht werden. main() setzt sie einmal (apply_runtime_settings)."""

    endpoint_timeout: int | None = None  # Sekunden pro Runde für Endpunkte (None = automatisch, siehe endpoint_timeout)
    shield: bool = True  # Datenschutzschild: Zugangsdaten vor dem Versand an Cloud-Modelle schwärzen
    stage_planning: bool = False  # Architekt schneidet den Plan in Etappen
    retries: int | None = None  # --retries
    progress: bool = True  # --no-progress schaltet die Statuszeile ab
    log_format: str = "text"  # --log-format: json schreibt zusätzlich events.jsonl
    budget: "Budget | None" = None  # --budget-max/-warn/-roles
    stop_requested: bool = False  # Strg+C/SIGTERM: aktuelle Runde sauber beenden
    lang: str = dataclasses.field(default_factory=detect_lang)  # --lang / CLAUDEGRAVITY_LANG: de oder en
    repo_map: str = "auto"  # --repo-map: auto (nur Endpunkte), an (alle Rollen), aus
    sandbox: str = "aus"  # --sandbox: aus, docker oder podman (an ist schon aufgelöst)
    sandbox_image: str = "python:3.12-slim"  # --sandbox-image
    sandbox_net: bool = False  # --sandbox-net: Prüfbefehl im Container mit Netz


SETTINGS = RuntimeSettings()

CLOUD_TIMEOUT = 180
LOCAL_TIMEOUT = 900

PLANNING_DIRECTIVE = (
    "\n\nSTRIKTE VORGABE FÜR DIE PLANUNG:\n"
    "- Du befindest dich in der REINEN PLANUNGSPHASE.\n"
    "- Erstelle, modifiziere oder lösche KEINE Dateien auf der Festplatte (weder in docs/ noch im Code).\n"
    "- Gib den vollständigen, detaillierten Plan DIREKT als Markdown-Text auf stdout aus.\n"
    "- Beginne sofort mit dem Markdown-Inhalt des Plans (ohne Tool-Aufrufe zum Dateischreiben).\n"
)

# Etappen: Der Architekt schneidet den Plan in kleine Stücke, die der Bauleiter einzeln umsetzt
STAGE_DIRECTIVE = (
    "- Schließe den Plan mit dem Abschnitt `## Etappen` ab: eine nummerierte Liste (`1.`, `2.`, …) mit 2 bis 8 Etappen,\n"
    "  die nacheinander umsetzbar sind. Jede Etappe ändert höchstens zwei Dateien, nennt deren relative Pfade\n"
    "  und ist danach mit dem Prüfbefehl testbar. Eine Etappe pro Listenpunkt, ohne Unterpunkte.\n"
)
STAGE_MAX_TRIES = 3


def planning_directive() -> str:
    """Anweisung an den Architekten, im Etappen-Modus mit dem Zusatz für den Abschnitt ## Etappen."""
    return PLANNING_DIRECTIVE + (STAGE_DIRECTIVE if SETTINGS.stage_planning else "")


def sigint_handler(signum, frame):
    """Strg+C: Abbruch vormerken, damit die laufende Runde sauber endet."""
    say("\n[!] Abbruch empfangen. Beende aktuelle Iteration sauber...")
    SETTINGS.stop_requested = True


signal.signal(signal.SIGINT, sigint_handler)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, sigint_handler)


class RateLimitError(Exception):
    """Ein Backend meldet ein Limit oder eine Störung, die auch nach den Neuversuchen bleibt."""

    def __init__(self, binary: str, message: str, reset_time: str | None = None, reset_seconds: int | None = None, transient: bool = False):
        super().__init__(f"{binary} Limit erreicht: {message}")
        self.binary = binary
        self.message = message
        self.reset_time = reset_time
        self.reset_seconds = reset_seconds
        # True: vorübergehende Störung, deren automatische Wiederholungen aufgebraucht sind
        self.transient = transient


RATE_LIMIT_PATTERNS = [
    r"hit your session limit",
    r"rate limit",
    r"rate_limit",
    r"quota exceeded",
    r"resource_exhausted",
    r"too many requests",
    r"usage limit",
    r"hit your limit",
    r"credit balance is too low",
    r"capacity",
    r"overloaded",
]

TIME_PATTERNS = [
    r"resets?\s+(?:in\s+|at\s+)?([0-9]+\s*(?:hours?|hrs?|minutes?|mins?|seconds?|secs?|h|m|s))\b",
    r"resets?\s+(?:in\s+|at\s+)?([0-9]+(?::[0-9]+)?\s*(?:am|pm)?(?:\s*\([^\)]+\))?)\b",
    r"try again in\s+([0-9]+\s*(?:hours?|hrs?|minutes?|mins?|seconds?|secs?|h|m|s))\b",
]


def is_rate_limit(text: str) -> bool:
    """True, wenn der Text nach Rate-Limit, Kontingent oder Überlastung klingt."""
    return any(re.search(p, text, re.IGNORECASE) for p in RATE_LIMIT_PATTERNS)


# Vorübergehende Störungen: Überlastung, Serverfehler, abgerissene Verbindungen
TRANSIENT_PATTERNS = [
    r"overloaded",
    r"\bcapacity\b",
    r"HTTP 5(?:00|02|03|04|29)\b",
    r"\b(?:502|503|504|529)\b",
    r"HTTP 408\b",
    r"internal server error",
    r"bad gateway",
    r"service unavailable",
    r"gateway time-?out",
    r"temporarily unavailable",
    r"econnreset",
    r"etimedout",
    r"socket hang up",
    r"connection (?:reset|aborted|refused)",
    r"Verbindungsfehler zu",
    r"Zeitüberschreitung nach",
    r"network error",
]

# Wiederholungen je Anbieterart: lokale Server starten schnell neu, Cloud-Dienste brauchen länger
RETRY_POLICIES = {
    "local": {"attempts": 3, "base": 2.0, "cap": 20.0},
    "cloud": {"attempts": 3, "base": 5.0, "cap": 60.0},
}


def is_transient_error(text: str, local: bool = False) -> bool:
    """Lohnt ein automatischer Neuversuch? Zeitüberschreitungen nur bei Cloud-Anbietern:
    ein lokales Modell, das 15 Minuten rechnet, wird durch einen Neuversuch nicht schneller."""
    if local and re.search(r"Zeitüberschreitung nach", text):
        return False
    return any(re.search(p, text, re.IGNORECASE) for p in TRANSIENT_PATTERNS)


def retry_policy(local: bool) -> dict:
    """Neuversuch-Regeln (Versuche, Wartezeiten) für Cloud oder lokal, mit --retries als Vorrang."""
    policy = dict(RETRY_POLICIES["local" if local else "cloud"])
    if SETTINGS.retries is not None:
        policy["attempts"] = max(0, SETTINGS.retries)
    return policy


def backoff_delay(attempt: int, base: float, cap: float, rng=random.random) -> float:
    """Exponentieller Backoff mit Jitter: halbe Wartezeit fest, halbe zufällig (attempt ab 1)."""
    delay = min(cap, base * (2 ** (attempt - 1)))
    return delay / 2 + rng() * delay / 2


def interruptible_sleep(seconds: float) -> bool:
    """Schläft in kleinen Schritten; False, wenn währenddessen abgebrochen wurde."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if SETTINGS.stop_requested:
            return False
        time.sleep(min(0.5, max(0.0, end - time.monotonic())))
    return not SETTINGS.stop_requested


def extract_reset_time(text: str) -> str | None:
    """Zeitangabe zum Limit-Ende aus einer Fehlermeldung ziehen, z. B. "3:45 PM" oder "20 minutes"."""
    for p in TIME_PATTERNS:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def parse_reset_seconds(time_str: str | None) -> int | None:
    """Zeitangabe in Sekunden bis zum Reset umrechnen; Dauern und Uhrzeiten, None wenn unlesbar."""
    if not time_str:
        return None
    s = time_str.strip().lower()

    dur_m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)$", s)
    if dur_m:
        val = float(dur_m.group(1))
        unit = dur_m.group(2)
        if unit.startswith("h"):
            return int(val * 3600)
        elif unit.startswith("m"):
            return int(val * 60)
        elif unit.startswith("s"):
            return int(val)

    now = datetime.datetime.now()
    s_clean = re.sub(r"\(.*?\)", "", s).strip()
    for fmt in ["%I:%M%p", "%I%p", "%H:%M", "%H:%M:%S"]:
        try:
            t = datetime.datetime.strptime(s_clean, fmt).time()
            target = datetime.datetime.combine(now.date(), t)
            diff = int((target - now).total_seconds())
            if -3600 <= diff <= 0:
                return 15
            elif diff < -3600:
                target += datetime.timedelta(days=1)
                diff = int((target - now).total_seconds())
            if diff > 0:
                return diff
        except ValueError:
            continue
    return None


def wait_countdown(seconds: int, reset_str: str = "") -> bool:
    """Sichtbar bis zum Reset warten; False bei Abbruch durch Strg+C."""
    say(f"\n⏳ Starte Countdown ({seconds}s bis {reset_str or 'Reset'}). Drücke [Strg+C] zum Abbrechen...")
    try:
        for remaining in range(seconds, 0, -1):
            if SETTINGS.stop_requested:
                return False
            mins, secs = divmod(remaining, 60)
            hours, mins = divmod(mins, 60)
            time_display = f"{hours:02d}:{mins:02d}:{secs:02d}" if hours else f"{mins:02d}:{secs:02d}"
            sys.stdout.write(f"\r⏳ Warte noch: {time_display} ... ")
            sys.stdout.flush()
            time.sleep(1)
        say("\n⏰ Wartezeit abgelaufen! Setze Ausführung fort...")
        return True
    except KeyboardInterrupt:
        say("\n[!] Warten durch Nutzer abgebrochen.")
        return False


def extract_flag_value(flags: list[str] | None, flag_name: str) -> str | None:
    """Extrahiert den Wert eines Flags wie --model <name> oder --effort=<val> aus einer Flag-Liste."""
    if not flags:
        return None
    for i, f in enumerate(flags):
        if f == flag_name and i + 1 < len(flags):
            return flags[i + 1]
        elif f.startswith(f"{flag_name}="):
            return f.split("=", 1)[1]
    return None


# Backends ohne eigenen Dateizugriff: Der Loop schreibt ihre filepath-Blöcke und gibt ihnen Plan und Dateistand mit
# CLIs, deren Sitzung der Loop fortsetzen kann (Prüfstatiker ab Runde 2, Bauleiter ab Bau-Runde 2)
RESUMABLE_CLIS = ("claude", "codex", "copilot", "gh")
ENDPOINT_BINARIES = ("endpoint", "ollama", "lmstudio", "architekt_ep", "pruefstatiker_ep", "bauer_ep")
CLOUD_PLANNER_ORDER = ("codex", "claude", "agy", "gemini")
LOCAL_BACKEND_ORDER = ("bauer_ep", "ollama", "lmstudio", "endpoint", "ollama-cli")
OLLAMA_KEYS = ("ollama", "ollama-cli")
HYBRID_STRATEGIES = ("hybrid", "mixed")
