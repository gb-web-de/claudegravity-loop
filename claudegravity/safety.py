"""Schutz vor nicht vertrauenswürdigen Modell-Ausgaben: Geheimnisse schwärzen, Schreibziele prüfen, Dateien anwenden."""

import re
from pathlib import Path

from .common import say


SECRET_PATTERNS = [
    ("privater Schlüssel", re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----.*?-----END (?:[A-Z]+ )*PRIVATE KEY-----", re.DOTALL)),
    ("Anthropic-Key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI-Key", re.compile(r"\bsk-(?!ant-)(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}")),
    ("GitHub-Token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("Google-API-Key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("AWS-Zugangsschlüssel", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Slack-Token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Stripe-Key", re.compile(r"\b[rs]k_live_[A-Za-z0-9]{20,}")),
    ("JWT/Bearer-Token", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]
# Nur der Wert hinter "passwort=", "token: " usw. wird ersetzt, der Name bleibt lesbar.
SECRET_ASSIGNMENT = re.compile(
    r"((?<![A-Za-z])(?:passwor[dt]|kennwort|passphrase|pwd|secret|client[_-]?secret|api[_-]?key|token)\s*[:=]\s*[\"']?)"
    r"(?!\*+|x{3,}|<|\{|\$|TOKEN_HIER|BITTE)([^\s\"']{6,})",
    re.IGNORECASE,
)
URL_CREDENTIALS = re.compile(r"(\b[a-z][a-z0-9+.-]*://[^\s:/@]+:)([^\s@/]{4,})(@)", re.IGNORECASE)
IBAN_CANDIDATE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b")
CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


def _iban_valid(raw: str) -> bool:
    s = re.sub(r"\s+", "", raw).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s):
        return False
    moved = s[4:] + s[:4]
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in moved)
    return int(digits) % 97 == 1


def _luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def redact_secrets(text: str) -> tuple[str, list[str]]:
    """Ersetzt Zugangsdaten, IBANs und Kartennummern durch Platzhalter. Gibt Text und Fundarten zurück."""
    found: list[str] = []

    def mark(label: str) -> str:
        if label not in found:
            found.append(label)
        return f"[GESCHWÄRZT: {label}]"

    for label, pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda m, lb=label: mark(lb), text)

    def assignment(m: re.Match) -> str:
        value = m.group(2)
        # Code wie token = createToken() oder api_key = os.environ[...] bleibt stehen; Geheimnisse enthalten fast immer Ziffern.
        if not re.search(r"\d", value) or re.search(r"[()\[\]]", value):
            return m.group(0)
        return m.group(1) + mark("Passwort/Token")

    text = SECRET_ASSIGNMENT.sub(assignment, text)
    text = URL_CREDENTIALS.sub(lambda m: m.group(1) + mark("Zugangsdaten in URL") + m.group(3), text)
    text = IBAN_CANDIDATE.sub(lambda m: mark("IBAN") if _iban_valid(m.group(0)) else m.group(0), text)

    def card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        return mark("Kreditkartennummer") if digits[0] in "3456" and _luhn_valid(digits) else m.group(0)

    text = CARD_CANDIDATE.sub(card, text)
    return text, found


SENSITIVE_PATHS = [
    re.compile(r"(?:^|/)\.env(?:\.(?!example|dist|sample|template|defaults?)[\w-]+)*$"),
    re.compile(r"(?:^|/)\.(?:ssh|gnupg|git)(?:/|$)"),
    re.compile(r"(?:^|/)id_(?:rsa|dsa|ecdsa|ed25519)(?!\.pub)\b"),
    re.compile(r"\.(?:pem|key|p12|pfx|jks|keystore|kdbx)$"),
    re.compile(r"(?:^|/)\.(?:netrc|git-credentials|pgpass|npmrc|pypirc)$"),
    re.compile(r"(?:^|/)(?:credentials|secrets?|service-account[\w-]*|client_secret[\w-]*)\.(?:json|ya?ml|toml)$"),
    re.compile(r"(?:^|/)auth\.json$"),
    re.compile(r"(?:^|/)\.dual-loop/profile\.json$"),
]


def is_sensitive_path(rel_path: str) -> bool:
    """True für Geheimnis-Dateien (.env, .ssh/, *.key, …), die Modell-Ausgaben nie schreiben dürfen."""
    p = rel_path.replace("\\", "/")
    return any(r.search(p) for r in SENSITIVE_PATHS)


def resolve_project_target(project_path: Path, rel_path: str) -> Path | None:
    """Liefert den Zielpfad nur, wenn er innerhalb des Projektordners liegt und keine Geheimnis-Datei ist (sonst None)."""
    cleaned = rel_path.strip().strip("\"'").replace("\\", "/")
    if not cleaned or cleaned.startswith("~") or Path(cleaned).is_absolute() or re.match(r"^[a-zA-Z]:", cleaned):
        return None
    root = project_path.resolve()
    target = (root / cleaned).resolve()
    if target == root or not target.is_relative_to(root):
        return None
    if is_sensitive_path(target.relative_to(root).as_posix()):
        return None
    return target


def apply_code_blocks(project_path: Path, text: str, on_blocked=None) -> list[str]:
    """Extrahiert Code-Blöcke mit Dateipfaden aus Modell-Antworten und schreibt sie auf die Festplatte.

    Es wird ausschließlich innerhalb des Projektordners geschrieben: absolute Pfade, `..`-Ausbrüche,
    Symlinks nach außen, `.git/` und Geheimnis-Dateien (.env, .ssh, Schlüssel) werden abgelehnt.
    """
    written_files = []

    def write_block(rel_path: str, content: str):
        rel_path = rel_path.strip().strip("\"'")
        if rel_path in written_files:
            return
        target = resolve_project_target(project_path, rel_path)
        if target is None:
            say(f"[!] Blockiert: {rel_path} liegt außerhalb des Projektordners oder ist eine Geheimnis-Datei und wird nicht geschrieben.")
            if on_blocked:
                on_blocked(rel_path)
            return
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written_files.append(rel_path)
        except Exception as ex:
            say(f"[!] Fehler beim Schreiben von {rel_path}: {ex}")

    # Muster 1: ```filepath: path/to/file.ext oder ```file: path/to/file.ext
    pattern1 = re.compile(r"```(?:filepath:|file:)\s*([^\s\n\r`]+)\r?\n(.*?)```", re.DOTALL)
    for match in pattern1.finditer(text):
        write_block(match.group(1), match.group(2))

    # Muster 2: Dateiname in Header vor Code-Block (### Datei: path/to/file.ext)
    pattern2 = re.compile(
        r"(?:###|##|\*\*)\s*(?:Datei|File|Pfad|Path)[:\s]+`?([a-zA-Z0-9_\-./\\]+\.[a-zA-Z0-9]+)`?.*?\n\s*```[a-zA-Z0-9_-]*\r?\n(.*?)```",
        re.DOTALL,
    )
    for match in pattern2.finditer(text):
        write_block(match.group(1), match.group(2))

    return written_files


def mask_secrets(text: str) -> str:
    """Schwärzt Zugangsdaten für Logs und Berichte (unabhängig vom Datenschutzschild)."""
    return redact_secrets(text)[0]
