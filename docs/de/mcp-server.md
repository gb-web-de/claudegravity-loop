# MCP-Server & Optimizer (`mcp_server.py`)

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/mcp-server.md)

`mcp_server.py` ist ein eigenständiger **Model Context Protocol**-Server (JSON-RPC 2.0 über stdio, Protokollversion `2024-11-05`) ohne Abhängigkeiten. Damit kann ein KI-Assistent wie Claude Code, Antigravity oder Cursor für eine Aufgabe die passende ClaudeGravity-Konfiguration berechnen und starten. Dieselbe Logik ist auch direkt im Terminal nutzbar.

## Registrieren

### Claude Code

```bash
# Linux / macOS
claude mcp add claudegravity -- python3 ~/Projekte/claudegravity-loop/mcp_server.py

# Windows
claude mcp add claudegravity -- python C:\claudegravity\mcp_server.py
```

Mit `--scope user` steht der Server in allen Projekten zur Verfügung. Kontrolle: `claude mcp list`.

### Andere MCP-Clients (Antigravity, Cursor, Claude Desktop, …)

Die meisten Clients nutzen dasselbe JSON-Format in ihrer MCP-Konfigurationsdatei:

```json
{
  "mcpServers": {
    "claudegravity": {
      "command": "python3",
      "args": ["/home/<user>/Projekte/claudegravity-loop/mcp_server.py"],
      "env": {
        "CLAUDEGRAVITY_ENDPOINT": "http://192.168.1.50:11434/v1"
      }
    }
  }
}
```

Unter Windows `"command": "python"` und einen Pfad wie `"C:\\claudegravity\\mcp_server.py"` verwenden, oder direkt `claudegravity-mcp.bat`. Der `env`-Block ist optional.

## Bereitgestellte Tools

### `claudegravity_optimize`

Analysiert die Aufgabe und liefert Rollenbelegung, Kosten-/Qualitäts-Einschätzung und den fertigen Befehl für Bash, CMD und PowerShell. Führt nichts aus.

| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `task` | string | *(Pflicht)* | Aufgabenbeschreibung |
| `priority` | `best-code` \| `lowest-cost` \| `local-free` \| `hybrid` \| `balanced` | `balanced` | Ziel; `lowest-cost` entspricht `--strategy eco`, `hybrid` der Strategie `hybrid` (Cloud plant und nimmt ab, Ollama prüft und baut in Etappen) |
| `endpoint` | string | – | OpenAI-kompatibler Endpunkt für den Bauleiter |
| `project_path` | string | `.` | Zielprojekt |
| `ask_mode` | boolean | `false` | Fragen-Modus (`-i`) |
| `yolo` | boolean | `false` | `--yolo` anhängen |
| `max_iterations` | integer | `10` | `-m` |
| `proof` | string | – | Prüfbefehl (`--proof`), den der Loop nach jeder Bau-Runde selbst ausführt |
| `architekt`, `pruefstatiker`, `bauer`, `abnahme` | string | – | Backend je Rolle, wie `--architekt` usw. (z. B. `codex`, `ollama`). Überschreibt die Wahl des Optimizers. |
| `architekt_model`, `pruefstatiker_model`, `bauer_model`, `abnahme_model` | string | – | Modell je Rolle. Fehlt es bei `ollama`, wählt der Loop aus den installierten Modellen. |
| `stages` | `auto` \| `an` \| `aus` | `auto` | Etappen-Modus (`--etappen`) |
| `approve_plan` | boolean | `false` | `--plan-auto`: Plan ohne Rückfrage übernehmen, sobald der Prüfstatiker `APPROVED` meldet |
| `merge` | boolean | `false` | `--merge`: Ergebnis nach der Abnahme in den Ausgangs-Branch mergen |

### `claudegravity_run`

Berechnet denselben Befehl und startet ihn.

| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `task`, `priority`, `endpoint`, `project_path`, `ask_mode`, `max_iterations`, `proof`, Rollen, `stages`, `approve_plan`, `merge` | | wie oben | |
| `yolo` | boolean | `false` | Volle Rechte für den Bauleiter. Nur auf ausdrücklichen Wunsch setzen; ohne `yolo` kann ein Claude-Bauleiter im Hintergrund nichts schreiben. |
| `background` | boolean | `false` | `true`: startet den Loop als Hintergrundprozess im Projektordner und meldet PID und Log-Datei; setzt dabei immer `--plan-auto`. `false`: gibt nur den Befehl zum manuellen Start zurück. |

> [!WARNING]
> Im Hintergrund gibt es kein Terminal: Der Plan wird nur gebaut, wenn der Prüfstatiker `APPROVED` meldet (`--plan-auto`), und die Rechte-Abfrage vor Phase 3 entfällt. Ein CLI-Bauleiter wie Claude oder Codex darf dann nur mit `yolo: true` schreiben; lokale Bauleiter (Ollama, Endpunkte) brauchen das nicht, weil ClaudeGravity ihre Dateien selbst schreibt. Ergebnisse stehen in `.dual-loop/sessions/` des Projekts; die Terminal-Ausgabe des Laufs landet in `.dual-loop/sessions/<zeit>_background.log`. Gestartet wird `loop.py` direkt mit dem Python des MCP-Servers.

### `claudegravity_status`

Zeigt den Stand der letzten Session eines Projekts, gedacht zum Nachsehen nach einem Hintergrundlauf: Aufgabe, Phase, Bau-Runde (mit Etappe), Tokens, gemeldete Kosten, Abbruchgrund, ob die Fertigmeldung vorliegt, sowie das Ende von `LOG.md` und des Hintergrund-Logs. Liest nur, startet nichts.

| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `project_path` | string | `.` | Zielprojekt |
| `log_lines` | integer | `15` | Zeilen vom Ende der Logs (`0` = keine) |

### `claudegravity_info`

Zeigt Betriebssystem, Python-Version, erkannte CLIs und Endpunkte sowie Strategie-Empfehlungen. Keine Parameter.

## Wie der Optimizer entscheidet

1. **Backends erkennen** wie `loop.py` (CLIs im `PATH`, Ollama/LM Studio auf localhost, `CLAUDEGRAVITY_ENDPOINT`/`OPENAI_BASE_URL`/`AI_ENDPOINT`).
2. **Paarung:** Architekt `claude`, Prüfstatiker `agy` (sonst `gemini`, sonst ebenfalls `claude`).
3. **Komplexität** per Stichwortsuche in der Aufgabe: Refactoring, Sicherheit/Auth und Architektur/Migration/Schema → `hoch`; kleine Fixes/Typos → `niedrig`; sonst `mittel`.
4. **Priorität → Preset** (siehe [Strategien](strategien.md)); bei `lowest-cost` (nur für Claude/Gemini) und bei `local-free` mit Endpunkt wird `--bauer-model` gesetzt. Für Ollama wählt der Loop das Modell selbst aus den installierten Modellen. Bei `hybrid` plant die erste Cloud-CLI (`codex`, `claude`, `agy`, `gemini`), das lokale Modell prüft und baut.
5. **Ausdrückliche Rollen** (`architekt`, `bauer_model`, …) überschreiben die Wahl und landen als Flags im Befehl. Modellnamen zeigt der Optimizer nur für Claude und Gemini an; andere CLIs nutzen ihren CLI-Default.
6. Bei **Architektur-Aufgaben** wird automatisch `-i` (Fragen-Modus) ergänzt.

## Direkt im Terminal (ohne MCP-Client)

```bash
claudegravity-mcp --optimize "Baue ein Microservice-Backend" --priority local-free --endpoint http://192.168.1.50:11434/v1
claudegravity-mcp "Fixe den Login-Bug" --priority lowest-cost   # Aufgabe auch als Positionsargument
claudegravity-mcp --info
claudegravity-mcp                                              # ohne Argumente: startet den stdio-Server
```

| Flag | Beschreibung | Standard |
| :--- | :--- | :--- |
| `--optimize`, `-o <aufgabe>` | Aufgabe analysieren und Empfehlung ausgeben | – |
| `--priority` | `best-code`, `quality`, `eco`, `lowest-cost`, `cost`, `local-free`, `free`, `local`, `hybrid`, `mixed`, `balanced` | `balanced` |
| `--endpoint <url>` | Endpunkt für den Bauleiter | – |
| `-p`, `--project` | Zielprojekt | `.` |
| `-i`, `--ask` | Fragen-Modus im Befehl | aus |
| `--yolo` | `--yolo` im Befehl | aus |
| `-m`, `--max-iterations` | Runden im Befehl | `10` |
| `--info` | Systemprüfung | aus |
| `--mcp` | Als MCP-Server starten (gleiches Verhalten wie ohne Argumente) | – |

## Protokoll-Details

Unterstützte Methoden: `initialize`, `notifications/initialized`, `ping`, `tools/list`, `tools/call`. Jede Zeile auf stdin ist eine JSON-RPC-Nachricht; Antworten gehen zeilenweise auf stdout. Unbekannte Methoden liefern einen JSON-RPC-Fehler.

Manueller Test:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp_server.py
```
