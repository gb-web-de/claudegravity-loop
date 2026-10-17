# MCP-Server & Optimizer (`mcp_server.py`)

[← Zurück zur Übersicht](../README.md) · [Dokumentations-Index](README.md)

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
        "CLAUDEGRAVITY_ENDPOINT": "https://ai.gb-web.de/v1"
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
| `priority` | `best-code` \| `lowest-cost` \| `local-free` \| `balanced` | `balanced` | Ziel; `lowest-cost` entspricht `--strategy eco` |
| `endpoint` | string | – | OpenAI-kompatibler Endpunkt für den Bauleiter |
| `project_path` | string | `.` | Zielprojekt |
| `ask_mode` | boolean | `false` | Fragen-Modus (`-i`) |
| `yolo` | boolean | `false` | `--yolo` anhängen |
| `max_iterations` | integer | `10` | `-m` |

### `claudegravity_run`

Berechnet denselben Befehl und startet ihn.

| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `task`, `priority`, `endpoint`, `project_path`, `ask_mode`, `max_iterations` | | wie oben | |
| `yolo` | boolean | **`true`** | Bei Agent-Ausführung standardmäßig volle Rechte |
| `background` | boolean | `false` | `true`: startet den Loop als Hintergrundprozess im Projektordner und meldet die PID. `false`: gibt nur den Befehl zum manuellen Start zurück. |

> [!WARNING]
> Im Hintergrund laufen keine interaktiven Menüs (Plan-Freigabe, Rechte-Abfrage). Der Prozess ist ohne Terminal gestartet; prüfe Ergebnisse in `.dual-loop/sessions/` und `logs/` des Projekts. Der Befehl ruft `claudegravity` auf, das daher im `PATH` liegen muss.

### `claudegravity_info`

Zeigt Betriebssystem, Python-Version, erkannte CLIs und Endpunkte sowie Strategie-Empfehlungen. Keine Parameter.

## Wie der Optimizer entscheidet

1. **Backends erkennen** wie `loop.py` (CLIs im `PATH`, Ollama/LM Studio auf localhost, `CLAUDEGRAVITY_ENDPOINT`/`OPENAI_BASE_URL`/`AI_ENDPOINT`).
2. **Paarung:** Architekt `claude`, Prüfstatiker `agy` (sonst `gemini`, sonst ebenfalls `claude`).
3. **Komplexität** per Stichwortsuche in der Aufgabe: Refactoring, Sicherheit/Auth und Architektur/Migration/Schema → `hoch`; kleine Fixes/Typos → `niedrig`; sonst `mittel`.
4. **Priorität → Preset** (siehe [Strategien](strategien.md)); bei `lowest-cost` und `local-free` wird `--bauer-model` gesetzt.
5. Bei **Architektur-Aufgaben** wird automatisch `-i` (Fragen-Modus) ergänzt.

## Direkt im Terminal (ohne MCP-Client)

```bash
claudegravity-mcp --optimize "Baue ein Microservice-Backend" --priority local-free --endpoint https://ai.gb-web.de/v1
claudegravity-mcp "Fixe den Login-Bug" --priority lowest-cost   # Aufgabe auch als Positionsargument
claudegravity-mcp --info
claudegravity-mcp                                              # ohne Argumente: startet den stdio-Server
```

| Flag | Beschreibung | Standard |
| :--- | :--- | :--- |
| `--optimize`, `-o <aufgabe>` | Aufgabe analysieren und Empfehlung ausgeben | – |
| `--priority` | `best-code`, `quality`, `eco`, `lowest-cost`, `cost`, `local-free`, `free`, `local`, `balanced` | `balanced` |
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
