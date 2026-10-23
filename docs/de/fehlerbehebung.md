# Fehlerbehebung & bekannte Einschränkungen

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/fehlerbehebung.md)

## Häufige Probleme

| Symptom | Ursache | Lösung |
| :--- | :--- | :--- |
| `claudegravity: command not found` | Symlink fehlt oder `~/.local/bin` nicht im `PATH` | [Installation](installation.md) Schritt 2–3 prüfen; neue Shell öffnen. |
| `Python 3.10+ wurde nicht im System-PATH gefunden` (Windows) | Python fehlt oder nicht im `PATH` | Python von python.org installieren und „Add Python to PATH“ aktivieren. |
| Umlaute/Emojis kaputt (Windows) | Konsole nicht auf UTF-8 | `claudegravity.bat` bzw. `.ps1` statt `python loop.py` verwenden. |
| `Agent-CLI '…' ist nicht verfügbar` | Rolle auf ein nicht erkanntes Backend gesetzt | `claudegravity --info` prüfen, CLI installieren/anmelden. |
| Architekt und Prüfstatiker sind dasselbe Modell | Nur ein Backend installiert | Zweite CLI installieren oder einen Endpunkt als Prüfstatiker setzen. |
| Ollama / LM Studio wird nicht erkannt | Server lief beim Start nicht, oder anderer Port | Server zuerst starten; bei anderem Port `--bauer-endpoint http://localhost:<port>/v1 --bauer bauer_ep`. |
| `Verbindungsfehler zu …` | Endpunkt nicht erreichbar | URL im Browser/mit `curl` prüfen, VPN/Proxy prüfen. |
| `API-Fehler … HTTP 401` | Key fehlt oder falsch | `CLAUDEGRAVITY_API_KEY` setzen oder `--api-key` angeben. |
| „Modell versuchte eine Datei anzulegen“ | Architekt wollte trotz Planungsphase schreiben | Wird automatisch einmal wiederholt; bei Bedarf `--yolo` vermeiden. |
| Bau-Loop endet nach 10 Runden ohne `.done` | Rundenlimit erreicht | `claudegravity -c -m 20`. |
| Endpunkt-Bauleiter ändert keine Dateien | Antwort enthält keine `filepath:`-Blöcke | Größeres/besseres Modell wählen; Format siehe [Backends](backends.md#wie-endpunkt-bauleiter-dateien-schreiben). |
| Hängende Abfrage im Hintergrund (MCP `background: true`) | Interaktives Menü ohne Terminal | Lauf im Terminal starten oder `--yolo` nutzen und den Plan vorher prüfen. |

## Abbrechen

`Strg+C` beendet die aktuelle Runde sauber, der Stand bleibt erhalten. Fortsetzen mit `claudegravity -c`.

## Bekannte Einschränkungen

Diese Punkte entsprechen dem aktuellen Stand des Codes:

* **Effort nur für Antigravity und Codex:** `--effort` und die rollenbezogenen Effort-Flags werden an `agy` und `codex` übergeben. Bei anderen CLIs erscheinen sie nur im Audit-Bericht.
* **Prüfer-Sitzung fortsetzen nur bei Claude:** Ab Review-Runde 2 bekommt nur ein Claude-Prüfer den Plan-Diff statt des ganzen Plans. Andere Prüfer bekommen den vollständigen Plan.
* **Copilot:** Wird über `copilot suggest -t shell` angesprochen und eignet sich damit eher für Shell-Vorschläge als für Planung oder Bau.
* **Kosten-Erkennung bei Endpunkten:** Als kostenlos gelten `localhost`, private IPs und Rechnernamen im Heimnetz (ohne Punkt oder mit `.local`, `.lan`, `.fritz.box`, `.home.arpa`, `.internal`). Ein Server im Intranet mit öffentlichem Domainnamen erscheint im Audit als „API“.
