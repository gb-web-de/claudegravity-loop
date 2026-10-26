# Live-Ansicht und Benachrichtigungen

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/live-ansicht.md)

Ein Lauf dauert schnell eine halbe Stunde. Damit du nicht im Terminal sitzen musst, zeigt der Loop seinen Stand im Browser und meldet sich, wenn er auf dich wartet oder fertig ist.

```bash
# Live-Ansicht neben dem Lauf und eine Desktop-Meldung, wenn er wartet oder fertig ist
claudegravity "Aufgabe" --watch --notify desktop

# Live-Ansicht ohne eigenen Lauf, z. B. für einen Hintergrundlauf aus dem MCP-Server
claudegravity watch -p ~/projekte/shop

# Aufs Handy über ntfy
claudegravity "Aufgabe" --notify ntfy:mein-geheimes-thema-4711
```

## Live-Ansicht

`--watch` startet neben dem Lauf eine kleine Seite auf `http://127.0.0.1:8765/?t=…` und öffnet sie im Browser. `claudegravity watch` macht dasselbe ohne Lauf, bis Strg+C, und zeigt alle Sessions des Projekts (Auswahl oben rechts). Die Seite aktualisiert sich alle zwei Sekunden und zeigt:

* Aufgabe, Phase und ob der Lauf noch läuft; welche Rolle gerade arbeitet und seit wann, oder dass der Prüfbefehl läuft;
* einen gelben Hinweis, wenn der Loop im Terminal auf eine Antwort wartet (z. B. Plan-Freigabe oder Rechte-Abfrage);
* Bau-Runde, Etappe, Tokens, gemeldete Kosten, Strategie, Branch und Prüfbefehl;
* je Rolle Anbieter, Modell, Aufrufe, Tokens und Kosten;
* geänderte Dateien mit hinzugefügten und entfernten Zeilen, auf Knopfdruck den ganzen Diff;
* das Ende von `LOG.md`, nach dem Lauf den Bericht aus `.done` bzw. `AUDIT.md` und den Link zum Pull Request.

Die Seite hat dieselbe Sprache wie der Lauf (`--lang`) und passt sich an helles und dunkles System-Design an.

| Option | Bedeutung |
| :--- | :--- |
| `--watch` (`--live`) | Live-Ansicht neben dem Lauf. Die Adresse steht im Kopf des Laufs und in `live.json`. |
| `--watch-port <port>` | Port (Standard 8765). Ist er belegt, nimmt der Loop einen freien und zeigt die Adresse an. |
| `claudegravity watch` | Live-Ansicht ohne Lauf für das Projekt in `-p` (Standard: aktueller Ordner). |

Den Browser öffnet der Loop nur, wenn es eine grafische Oberfläche gibt (macOS, Windows, Linux mit `DISPLAY` oder `WAYLAND_DISPLAY`); `CLAUDEGRAVITY_NO_BROWSER=1` verhindert es ganz. Über SSH leitest du den Port weiter: `ssh -L 8765:127.0.0.1:8765 server`.

**Schutz:** Der Server hört nur auf `127.0.0.1`, jede Anfrage braucht den Zufallstoken aus der Adresse, und der `Host`-Kopf muss `127.0.0.1` oder `localhost` sein (gegen DNS-Rebinding). Die Seite lädt nichts von außen und setzt eine strenge Content-Security-Policy. Wer die Adresse samt Token kennt, sieht Aufgabe, Log und Diff; teile sie nicht.

## Benachrichtigungen

`--notify` nimmt einen oder mehrere Kanäle, mit Komma getrennt:

| Kanal | Was passiert |
| :--- | :--- |
| `desktop` | Systemmeldung: macOS über `osascript`, Linux über `notify-send` (Paket `libnotify-bin` bzw. `libnotify`), Windows als Sprechblase über PowerShell. |
| `bell` | Terminal-Glocke (`\a`); viele Terminals zeigen dann ein Abzeichen oder blinken. |
| `ntfy:<thema>` | Push aufs Handy mit der App [ntfy](https://ntfy.sh): ein Thema auf `ntfy.sh` oder eine volle URL deines eigenen Servers, z. B. `ntfy:https://ntfy.example.org/loop`. Ein Token für geschützte Themen kommt aus `CLAUDEGRAVITY_NTFY_TOKEN` (oder `NTFY_TOKEN`). |
| `webhook:<url>` | JSON per POST an die URL, mit `text` und `content` (für Slack, Mattermost, Discord und ähnliche) sowie `title`, `message`, `event` und `url`. |

Gemeldet wird:

* **Wartet auf dich:** Bleibt eine Rückfrage im Terminal 20 Sekunden ohne Antwort, kommt „⏳ Wartet auf dich: …“. Die Wartezeit stellst du mit `CLAUDEGRAVITY_NOTIFY_WAIT=<sekunden>` ein.
* **Fertig:** „✅ Fertig: <Aufgabe>“, mit dem Pull Request, falls einer geöffnet wurde (bei ntfy zum Antippen).
* **Ohne Abschluss:** „🛑 Beendet ohne Abschluss: <Aufgabe> · <Grund>“ (Rundenlimit, Budget, Strg+C) oder „🛑 Fehler CG-xxxx“ bei einem Abbruch mit Fehlercode.

Dauerhaft einschalten über die Umgebung (`CLAUDEGRAVITY_NOTIFY=desktop`) oder das globale Profil (`"notify": "desktop"`). Aus dem Projekt-Profil wirkt `notify` nicht, damit ein fremdes Repository keine Meldungen an eigene Adressen schicken lässt. Im Kandidaten-Modus meldet nur der Hauptlauf.

**Was rausgeht:** die ersten Zeichen der Aufgabe, der Grund des Abbruchs und der Link zum Pull Request, geschwärzt wie in `LOG.md`. Ein Thema auf `ntfy.sh` kann jeder lesen, der es kennt: Nimm ein schwer zu ratendes Thema oder einen eigenen Server. Webhook-URLs und Themen sind Geheimnisse; im Kopf des Laufs, bei `--dry-run` und `--print-effective-config` erscheinen sie gekürzt. Scheitert der Versand, meldet der Loop das einmal und läuft weiter.

## Für Skripte: live.json

Der laufende Prozess schreibt `live.json` in den Session-Ordner: Prozess-ID, aktueller Aufruf (`activity`), offene Rückfrage (`waiting`), Pull Request, Adresse der Live-Ansicht und ob der Lauf beendet ist (`ended`). Die Ereignisse `call_start` und `proof_start` stehen mit `--log-format json` auch in `events.jsonl` ([Sessions & Dateien](sessions-und-dateien.md#strukturiertes-ereignis-log)). Der MCP-Server kennt `notify` und `watch` und zeigt die Adresse in `claudegravity_status` ([MCP-Server](mcp-server.md)).
