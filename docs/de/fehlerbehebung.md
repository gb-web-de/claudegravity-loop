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

## Automatische Neuversuche

Vorübergehende Fehler wiederholt der Loop selbst, bevor er dich fragt: Überlastung (`overloaded`, `529`), HTTP 500/502/503/504/408, abgerissene oder verweigerte Verbindungen und bei Cloud-Anbietern auch Zeitüberschreitungen. Die Wartezeit verdoppelt sich mit jedem Versuch; die Hälfte davon ist zufällig (Jitter), damit parallele Läufe nicht gleichzeitig wiederkommen.

| Anbieter | Versuche | Wartezeit (ohne Jitter) |
| :--- | :--- | :--- |
| Lokal (Ollama, LM Studio, Heimnetz) | 3 | 2 s, 4 s, 8 s (höchstens 20 s) |
| Cloud (CLIs, öffentliche Endpunkte) | 3 | 5 s, 10 s, 20 s (höchstens 60 s) |

Eine Zeitüberschreitung bei einem lokalen Modell wird nicht wiederholt, denn ein zweiter Versuch rechnet genauso lange; dort hilft `--timeout`. Ein echtes Ratenlimit mit Reset-Zeit geht direkt ins Limit-Menü. Klappt auch der letzte Neuversuch nicht, erscheint dasselbe Menü (Wechseln, Warten, Beenden), mit `--auto-switch` wird sofort gewechselt. Jeder Neuversuch steht in `LOG.md`, die Summe im Audit-Block der `.done`. `--retries <n>` ändert die Zahl der Versuche, `--retries 0` schaltet sie ab.

## Abbrechen

`Strg+C` beendet die aktuelle Runde sauber, der Stand bleibt erhalten. Fortsetzen mit `claudegravity -c`.

## Bekannte Einschränkungen

Diese Punkte entsprechen dem aktuellen Stand des Codes:

* **Effort nur für Antigravity und Codex:** `--effort` und die rollenbezogenen Effort-Flags werden an `agy` und `codex` übergeben. Bei anderen CLIs erscheinen sie nur im Audit-Bericht.
* **Prüfer-Sitzung fortsetzen nur bei Claude:** Ab Review-Runde 2 bekommt nur ein Claude-Prüfer den Plan-Diff statt des ganzen Plans. Andere Prüfer bekommen den vollständigen Plan.
* **Copilot:** Wird über `copilot suggest -t shell` angesprochen und eignet sich damit eher für Shell-Vorschläge als für Planung oder Bau.
* **Kosten-Erkennung bei Endpunkten:** Als kostenlos gelten `localhost`, private IPs und Rechnernamen im Heimnetz (ohne Punkt oder mit `.local`, `.lan`, `.fritz.box`, `.home.arpa`, `.internal`). Ein Server im Intranet mit öffentlichem Domainnamen erscheint im Audit als „API“.
