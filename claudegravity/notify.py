"""Benachrichtigungen, wenn der Loop auf dich wartet oder fertig ist: Desktop, ntfy, Webhook oder Terminal-Glocke.

`--notify desktop,ntfy:mein-thema,webhook:https://…` (auch CLAUDEGRAVITY_NOTIFY oder globales Profil). Die Texte
werden mit mask_secrets() geschwärzt und gekürzt; ein Fehler beim Versand hält den Lauf nie an.
Nur Standardbibliothek; Prozesse mit Argumentlisten, Texte nie in einem Shell- oder Skript-String.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

from .common import SETTINGS, say, tr
from .safety import mask_secrets

CHANNEL_KINDS = ("desktop", "ntfy", "webhook", "bell")
NTFY_SERVER = "https://ntfy.sh"
NTFY_TOPIC_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MESSAGE_LIMIT = 300
SEND_TIMEOUT = 10
TITLE = "ClaudeGravity"
# Sekunden, die eine Rückfrage unbeantwortet bleibt, bevor die Meldung „wartet auf dich“ kommt
WAIT_DELAY_DEFAULT = 20
OFF_VALUES = ("", "aus", "off", "0", "false", "nein", "no")

_WARNED: set[str] = set()


def parse_channels(spec: str | None) -> tuple[list[tuple[str, str]], list[str]]:
    """`desktop,ntfy:thema,webhook:https://…,bell` in Kanäle (Art, Ziel) zerlegen; dazu Hinweise zu ungültigen Angaben."""
    found: list[tuple[str, str]] = []
    problems: list[str] = []
    if (spec or "").strip().lower() in OFF_VALUES:
        return found, problems
    for raw in (spec or "").split(","):
        item = raw.strip()
        if not item:
            continue
        kind, _, target = item.partition(":")
        kind = kind.strip().lower()
        url = ntfy_url(target.strip()) if kind == "ntfy" else None
        if kind in ("desktop", "bell") and not target:
            found.append((kind, ""))
        elif url:
            found.append((kind, url))
        elif kind == "ntfy":
            problems.append(f"ntfy: ungültiges Thema oder ungültige URL ({redact_item(item)})")
        elif kind == "webhook" and target.strip().lower().startswith(("https://", "http://")):
            found.append((kind, target.strip()))
        else:
            problems.append(f"Unbekannter Benachrichtigungs-Kanal: {redact_item(item)} (desktop, bell, ntfy:<thema>, webhook:<url>)")
    return found, problems


def ntfy_url(target: str) -> str | None:
    """ntfy-Ziel als volle URL: ein bloßes Thema geht an ntfy.sh, sonst die angegebene https-URL mit Thema im Pfad."""
    if NTFY_TOPIC_RE.match(target):
        return f"{NTFY_SERVER}/{target}"
    parts = urllib.parse.urlsplit(target)
    topic = parts.path.strip("/")
    if parts.scheme in ("https", "http") and parts.netloc and NTFY_TOPIC_RE.match(topic):
        return f"{parts.scheme}://{parts.netloc}/{topic}"
    return None


def redact_item(item: str) -> str:
    """Ein Kanal zum Anzeigen: Thema und Webhook-Pfad sind Geheimnisse (wer sie kennt, liest mit oder schreibt)."""
    kind, sep, target = item.partition(":")
    if not sep:
        return item
    if kind.strip().lower() == "webhook":
        parts = urllib.parse.urlsplit(target.strip())
        return f"{kind}:{parts.scheme}://{parts.netloc}/…" if parts.netloc else f"{kind}:…"
    if kind.strip().lower() == "ntfy":
        parts = urllib.parse.urlsplit(target.strip())
        if parts.netloc:
            return f"{kind}:{parts.scheme}://{parts.netloc}/…"
        return f"{kind}:{target.strip()[:2]}…"
    return f"{kind}:…"


def redact(spec: str | None) -> str:
    """Ganze --notify-Angabe zum Anzeigen (Kopf des Laufs, --dry-run, --print-effective-config)."""
    return ",".join(redact_item(i.strip()) for i in (spec or "").split(",") if i.strip())


def channels() -> list[tuple[str, str]]:
    """Eingestellte Kanäle dieses Laufs."""
    return parse_channels(SETTINGS.notify)[0]


def active() -> bool:
    """Ob in diesem Lauf benachrichtigt wird."""
    return bool(channels())


def wait_delay() -> float:
    """Wartezeit bis zur Meldung bei einer offenen Rückfrage (CLAUDEGRAVITY_NOTIFY_WAIT, Sekunden)."""
    raw = os.environ.get("CLAUDEGRAVITY_NOTIFY_WAIT", "").strip()
    try:
        return max(0.0, float(raw)) if raw else float(WAIT_DELAY_DEFAULT)
    except ValueError:
        return float(WAIT_DELAY_DEFAULT)


def shorten(text: str, limit: int = MESSAGE_LIMIT) -> str:
    """Eine Zeile, geschwärzt und gekürzt."""
    text = " ".join(mask_secrets(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def desktop_command(title: str, message: str) -> tuple[list[str], dict | None] | None:
    """Befehl für eine Desktop-Meldung je System; Titel und Text gehen als Argument bzw. Umgebung, nie in ein Skript."""
    if sys.platform == "darwin":
        script = ["-e", "on run argv", "-e", "display notification (item 2 of argv) with title (item 1 of argv)", "-e", "end run"]
        return ["osascript", *script, title, message], None
    if os.name == "nt":
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
            "$n = New-Object System.Windows.Forms.NotifyIcon; $n.Icon = [System.Drawing.SystemIcons]::Information; "
            "$n.BalloonTipTitle = $env:CG_NOTIFY_TITLE; $n.BalloonTipText = $env:CG_NOTIFY_TEXT; $n.Visible = $true; "
            "$n.ShowBalloonTip(10000); Start-Sleep -Seconds 10; $n.Dispose()"
        )
        env = dict(os.environ, CG_NOTIFY_TITLE=title, CG_NOTIFY_TEXT=message)
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env
    if shutil.which("notify-send"):
        return ["notify-send", "--app-name=ClaudeGravity", title, message], None
    return None


def _post(url: str, payload: dict, headers: dict | None = None) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=SEND_TIMEOUT) as res:
        res.read(1024)


def deliver(kind: str, target: str, title: str, message: str, event: str, link: str | None = None) -> None:
    """Eine Meldung über einen Kanal senden; Fehler gehen als Ausnahme an send()."""
    if kind == "bell":
        sys.stdout.write("\a")
        sys.stdout.flush()
    elif kind == "desktop":
        found = desktop_command(title, message)
        if found is None:
            raise OSError(tr("keine Desktop-Meldung möglich (unter Linux notify-send installieren)"))
        cmd, env = found
        # Nicht warten: Die Meldung unter Windows bleibt einige Sekunden stehen
        subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif kind == "ntfy":
        server, _, topic = target.rpartition("/")
        payload = {"topic": topic, "title": title, "message": message, "tags": [event]}
        if link and link.startswith("https://"):
            payload["click"] = link
        token = os.environ.get("CLAUDEGRAVITY_NTFY_TOKEN") or os.environ.get("NTFY_TOKEN")
        _post(server + "/", payload, {"Authorization": f"Bearer {token}"} if token else None)
    elif kind == "webhook":
        text = f"{title}: {message}" + (f" {link}" if link else "")
        _post(target, {"text": text, "content": text, "title": title, "message": message, "event": event, "url": link})


def send(message: str, event: str = "info", link: str | None = None, title: str = TITLE) -> int:
    """Meldung an alle eingestellten Kanäle; liefert die Zahl erfolgreicher Kanäle. Bricht nie den Lauf ab."""
    sent = 0
    text = shorten(message)
    for kind, target in channels():
        try:
            deliver(kind, target, title, text, event, link)
            sent += 1
        except (OSError, ValueError, urllib.error.URLError) as exc:
            key = f"{kind}:{target}"
            if key not in _WARNED:
                _WARNED.add(key)
                say(f"⚠️  Benachrichtigung über {redact_item(key) if target else kind} fehlgeschlagen: {exc}")
    return sent


def warn_problems() -> None:
    """Beim Start: ungültige Angaben in --notify und fehlende Desktop-Meldung (Linux ohne notify-send) melden."""
    found, problems = parse_channels(SETTINGS.notify)
    for problem in problems:
        say(f"⚠️  {problem}")
    if ("desktop", "") in found and desktop_command(TITLE, "") is None:
        say("⚠️  --notify desktop: keine Desktop-Meldung möglich (unter Linux notify-send installieren).")
