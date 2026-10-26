# MCP-Server & Optimizer (`mcp_server.py`)

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/mcp-server.md)

`mcp_server.py` ist ein eigenständiger **Model Context Protocol**-Server (JSON-RPC 2.0 über stdio, Protokollversionen `2025-06-18`, `2025-03-26` und `2024-11-05`) ohne Abhängigkeiten. Damit kann ein KI-Assistent wie Claude Code, Antigravity oder Cursor für eine Aufgabe die passende ClaudeGravity-Konfiguration berechnen und starten. Dieselbe Logik ist auch direkt im Terminal nutzbar.

## Registrieren

**Noch einfacher:** Als [Plugin](plugins.md) bringen Claude Code, Codex, Antigravity, Copilot CLI, Cursor und Gemini CLI den Server samt Skill und Befehlen mit einem Befehl mit.

### Claude Desktop: Erweiterung mit einem Klick

Für Claude Desktop gibt es den Server als Erweiterung (`.mcpb`, MCP Bundle): Datei herunterladen, doppelklicken oder unter *Einstellungen → Erweiterungen* hineinziehen, fertig. Kein Klon, kein Installer, keine JSON-Datei.

* **Herunterladen:** am [Release](https://github.com/gb-web-de/claudegravity-loop/releases/latest) als `claudegravity.mcpb`, den neuesten Stand aus dem CI-Lauf auf `main` (Artefakt `claudegravity-mcpb`), oder selbst bauen: `python tools/build_mcpb.py` legt sie unter `dist/` ab.
* **Einstellungen** in Claude Desktop (alle optional): Standard-Projekt (`CLAUDEGRAVITY_PROJECT`), eigener Endpunkt und sein API-Schlüssel (geschützt gespeichert), Benachrichtigung (Standard `desktop`: Meldung, wenn ein Hintergrundlauf fertig ist, siehe [Live-Ansicht](live-ansicht.md)), Sprache und der Pfad zu Python.
* **Voraussetzung ist Python 3.10+.** Unter macOS und Linux sucht die Erweiterung selbst (Homebrew, `/usr/local/bin`, `~/.local/bin`, pyenv, PATH, zuletzt `uv run`); das alte `/usr/bin/python3` (3.9) überspringt sie. Findet sie keins, den Pfad in den Einstellungen angeben. Unter Windows startet sie über den Python-Launcher `py` (bei der Installation von python.org dabei).
* Die KI-CLIs (`codex`, `gemini`, `copilot`, `ollama` …) brauchst du weiterhin auf dem Rechner; der Server findet sie auch ohne Shell-PATH (siehe [Desktop-Apps](#desktop-apps-claude-desktop-cursor-)). Aus Claude Desktop plant `claude`, sofern die Claude-Code-CLI installiert ist.

### Am einfachsten: Installer

```bash
./install.sh                                    # Linux/macOS; Windows: install.bat oder .\install.ps1
./install.sh --project ~/Projekte/mein-projekt  # zusätzlich Standardprojekt für Desktop-Apps
./install.sh --only claude-desktop,codex        # nur bestimmte Clients
```

Der Installer trägt den Server in alle gefundenen Clients ein (Claude Code, Claude Desktop, Gemini CLI, Antigravity, Codex, Copilot CLI, Cursor, Windsurf, VS Code), immer mit dem **absoluten Pfad** des Pythons, mit dem er gestartet wurde. Das [fertige Programm](installation.md#fertiges-programm-ohne-python) macht dasselbe mit `claudegravity install` und trägt sich selbst ein (`"command": "…/claudegravity", "args": ["mcp"]`). `--project` setzt `CLAUDEGRAVITY_PROJECT` in der Server-Umgebung (siehe [Desktop-Apps](#desktop-apps-claude-desktop-cursor-)). Danach den Client neu starten.

### Von Hand

```bash
# Claude Code (alle Projekte)
claude mcp add --scope user claudegravity -- "$(command -v python3)" ~/Projekte/claudegravity-loop/mcp_server.py

# Codex CLI
codex mcp add claudegravity -- "$(command -v python3)" ~/Projekte/claudegravity-loop/mcp_server.py

# Windows (PowerShell)
claude mcp add --scope user claudegravity -- (Get-Command python).Source C:\claudegravity\mcp_server.py
```

Kontrolle: `claude mcp list` bzw. `codex mcp list`. Für JSON-Clients (Claude Desktop, Cursor, Gemini CLI, Antigravity, Windsurf):

```json
{
  "mcpServers": {
    "claudegravity": {
      "command": "/opt/homebrew/bin/python3",
      "args": ["/Users/<user>/Projekte/claudegravity-loop/mcp_server.py"],
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "CLAUDEGRAVITY_PROJECT": "/Users/<user>/Projekte/mein-projekt"
      }
    }
  }
}
```

| Client | Konfigurationsdatei |
| :--- | :--- |
| Claude Desktop | macOS `~/Library/Application Support/Claude/claude_desktop_config.json`, Windows `%APPDATA%\Claude\claude_desktop_config.json` |
| Cursor | `~/.cursor/mcp.json` |
| Gemini CLI | `~/.gemini/settings.json` |
| Antigravity (App) | `~/.gemini/config/mcp_config.json` (nicht `~/.gemini/antigravity/`; einen alten Eintrag dort räumt der Installer weg) |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| Codex CLI und Codex-App | `~/.codex/config.toml` (gemeinsam für beide), Abschnitt `[mcp_servers.claudegravity]` mit `command`, `args`, `env` |

Unter Windows Backslashes in JSON verdoppeln (`"C:\\claudegravity\\mcp_server.py"`) oder `claudegravity-mcp.bat` als `command` nutzen. `CLAUDEGRAVITY_PROJECT`, `CLAUDEGRAVITY_HOST` und weitere Variablen wie `CLAUDEGRAVITY_ENDPOINT` sind optional.

### Der aufrufende Client führt den Loop

Der Server merkt sich bei `initialize`, welcher Client ihn gestartet hat (`clientInfo.name`), und setzt dessen CLI als **Architekt** ein: aus Codex (CLI oder App) plant `codex`, aus der Antigravity-App `agy`, aus Claude Code oder Claude Desktop `claude`, aus der Gemini CLI `gemini`. Der Prüfstatiker ist nie derselbe Anbieter; bei Bedarf weicht er auf Ollama oder eine andere Cloud-CLI aus. Mit `priority: "auto"` (Standard) wird daraus die Strategie `hybrid`, sobald Ollama, LM Studio oder ein Endpunkt erreichbar ist: der Client plant und nimmt ab, **Ollama prüft und baut** in Etappen für 0 €. Ohne lokales Modell gilt `balanced`.

Voraussetzung ist, dass die CLI des Clients installiert ist (`codex`, `agy`, `claude`); sonst nennt die Empfehlung das und wählt wie bisher. Der Installer schreibt den Client zusätzlich als `CLAUDEGRAVITY_HOST` in die Konfiguration, falls eine App einen unbekannten Namen meldet. `CLAUDEGRAVITY_HOST=aus` schaltet das ab; ausdrückliche Rollen (`architekt` usw.) gehen immer vor.

Ollama selbst ist kein MCP-Client: Die Ollama-App ruft keine MCP-Server auf, sie ist im Loop Prüfstatiker und Bauleiter. Die Modelle wählt der Loop aus den installierten Modellen (`/api/tags`), oder man gibt sie mit `pruefstatiker_model` und `bauer_model` vor.

### Desktop-Apps (Claude Desktop, Cursor, …)

Desktop-Apps starten den Server anders als ein Terminal. Der Server fängt das so ab:

* **Kein Shell-PATH:** Unter macOS sieht eine Desktop-App meist nur `/usr/bin:/bin`. Der Server ergänzt beim Start vorhandene Ordner wie die CLI-Ordner der Codex-, Antigravity- und Ollama-App unter `/Applications`, `/opt/homebrew/bin`, `/usr/local/bin`, `~/.local/bin`, `~/.npm-global/bin`, `~/.bun/bin`, `~/.volta/bin`, `~/.cargo/bin` und die `bin`-Ordner von nvm (unter Windows `%APPDATA%\npm` und `%LOCALAPPDATA%\Programs\Ollama`), damit `claude`, `codex`, `gemini` oder `ollama` gefunden werden. Liegt eine CLI woanders, den Ordner in `env` → `PATH` eintragen. `claudegravity_info` zeigt, welche Ordner ergänzt wurden.
* **Falsches Arbeitsverzeichnis:** Der Server läuft dort meist in `/` oder im Home-Ordner. Ein relativer `project_path` wird mit dem zuletzt genutzten Projekt oder `CLAUDEGRAVITY_PROJECT` aufgelöst; fehlt beides, bittet der Server um einen absoluten Pfad. `~` wird aufgelöst.
* **Zu altes Python:** `command` muss auf Python 3.10+ zeigen (unter macOS ist `/usr/bin/python3` oft 3.9). Sonst bricht der Server mit einer klaren Meldung im Client-Log ab.
* **Kein Terminal:** Läufe aus Desktop-Apps mit `claudegravity_run` und `background: true` starten, mit `claudegravity_status` verfolgen und bei Bedarf mit `claudegravity_stop` abbrechen.

## Bereitgestellte Tools

### `claudegravity_optimize`

Analysiert die Aufgabe und liefert Rollenbelegung, Kosten-/Qualitäts-Einschätzung und den fertigen Befehl für Bash, CMD und PowerShell. Führt nichts aus.

| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `task` | string | *(Pflicht ohne `issue`)* | Aufgabenbeschreibung |
| `priority` | `auto` \| `best-code` \| `lowest-cost` \| `local-free` \| `hybrid` \| `balanced` | `auto` | Ziel; `auto` wird `hybrid`, wenn ein lokales Modell erreichbar ist, sonst `balanced`; `lowest-cost` entspricht `--strategy eco`, `hybrid` der Strategie `hybrid` (Cloud plant und nimmt ab, Ollama prüft und baut in Etappen) |
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
| `issue` | string | – | `--from-issue`: GitHub-Issue als Aufgabe (Nummer, `owner/repo#12` oder URL); `task` ist dann optional und gilt als Zusatz ([GitHub](github.md)) |
| `open_pr` | boolean | `false` | `--open-pr`: nach erfolgreichem Abschluss Branch pushen und Pull Request öffnen |
| `notify` | string | – | `--notify`: melden, wenn der Lauf wartet oder fertig ist (`desktop`, `bell`, `ntfy:<thema>`, `webhook:<url>`; [Live-Ansicht](live-ansicht.md)) |
| `watch` | boolean | `false` | `--watch`: Live-Ansicht im Browser; die Adresse zeigt `claudegravity_status` |

### `claudegravity_run`

Berechnet denselben Befehl und startet ihn.

| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `task`, `priority`, `endpoint`, `project_path`, `ask_mode`, `max_iterations`, `proof`, Rollen, `stages`, `approve_plan`, `merge`, `issue`, `open_pr`, `notify`, `watch` | | wie oben | |
| `yolo` | boolean | `false` | Volle Rechte für den Bauleiter. Nur auf ausdrücklichen Wunsch setzen; ohne `yolo` kann ein Claude-Bauleiter im Hintergrund nichts schreiben. |
| `background` | boolean | `false` | `true`: startet den Loop als eigenen Prozess im Projektordner (unter Windows ohne Konsolenfenster) und meldet PID und Log-Datei; setzt immer `--plan-auto` und lässt `-i` weg. Läuft im Projekt schon ein Hintergrundlauf, wird kein zweiter gestartet. `false`: gibt nur den Befehl zum Start im Terminal zurück (Bash bzw. PowerShell, mit dem Python des Servers). |

> [!WARNING]
> Im Hintergrund gibt es kein Terminal: Der Plan wird nur gebaut, wenn der Prüfstatiker `APPROVED` meldet (`--plan-auto`), und die Rechte-Abfrage vor Phase 3 entfällt. Ein CLI-Bauleiter wie Claude oder Codex darf dann nur mit `yolo: true` schreiben; lokale Bauleiter (Ollama, Endpunkte) brauchen das nicht, weil ClaudeGravity ihre Dateien selbst schreibt. Ergebnisse stehen in `.dual-loop/sessions/` des Projekts; die Terminal-Ausgabe des Laufs landet in `.dual-loop/sessions/<zeit>_background.log`. Gestartet wird `loop.py` direkt mit dem Python des MCP-Servers; PID und Startzeit stehen in `.dual-loop/sessions/<zeit>_background.json`.

### `claudegravity_status`

Zeigt den Stand der letzten Session eines Projekts, gedacht zum Nachsehen nach einem Hintergrundlauf: Aufgabe, Phase, Bau-Runde (mit Etappe), Tokens, gemeldete Kosten, Abbruchgrund, ob die Fertigmeldung vorliegt, ob der Hintergrundlauf noch läuft (mit Exit-Code, solange derselbe Server ihn gestartet hat), sowie das Ende von `LOG.md` und des Hintergrund-Logs. Liest nur, startet nichts.

| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `project_path` | string | `.` | Zielprojekt |
| `log_lines` | integer | `15` | Zeilen vom Ende der Logs (`0` = keine) |

### `claudegravity_stop`

Bricht den letzten Hintergrundlauf des Projekts ab, samt der gestarteten CLIs (POSIX: `SIGTERM` an die Prozessgruppe, Windows: `taskkill /T`). Es werden nur PIDs aus der eigenen `_background.json` beendet. Der Stand bleibt in der Session und lässt sich mit `claudegravity -c` fortsetzen.

| Parameter | Typ | Standard | Beschreibung |
| :--- | :--- | :--- | :--- |
| `project_path` | string | `.` | Zielprojekt |

### `claudegravity_info`

Zeigt Betriebssystem, Python des Servers, Arbeitsverzeichnis, `CLAUDEGRAVITY_PROJECT`, die beim Start ergänzten PATH-Ordner, erkannte CLIs und Endpunkte sowie Strategie-Empfehlungen. Keine Parameter. Erste Anlaufstelle, wenn eine Desktop-App keine CLIs findet.

## Wie der Optimizer entscheidet

1. **Backends erkennen** wie `loop.py` (CLIs im `PATH`, Ollama/LM Studio auf localhost, `CLAUDEGRAVITY_ENDPOINT`/`OPENAI_BASE_URL`/`AI_ENDPOINT`).
2. **Paarung:** Architekt ist der aufrufende Client (siehe oben), sonst `claude`; Prüfstatiker `agy` (sonst `gemini`, sonst ein anderer Anbieter als der Architekt).
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
| `--priority` | `auto`, `best-code`, `quality`, `eco`, `lowest-cost`, `cost`, `local-free`, `free`, `local`, `hybrid`, `mixed`, `balanced` | `auto` |
| `--endpoint <url>` | Endpunkt für den Bauleiter | – |
| `-p`, `--project` | Zielprojekt | `.` |
| `-i`, `--ask` | Fragen-Modus im Befehl | aus |
| `--yolo` | `--yolo` im Befehl | aus |
| `-m`, `--max-iterations` | Runden im Befehl | `10` |
| `--info` | Systemprüfung | aus |
| `--mcp` | Als MCP-Server starten (gleiches Verhalten wie ohne Argumente) | – |

## Protokoll-Details

Unterstützte Methoden: `initialize`, `ping`, `tools/list`, `tools/call`; `resources/list`, `resources/templates/list` und `prompts/list` liefern leere Listen. Notifications (Nachrichten ohne `id`, z. B. `notifications/initialized` oder `notifications/cancelled`) bekommen nie eine Antwort. Jede Zeile auf stdin ist eine JSON-RPC-Nachricht; Antworten gehen zeilenweise auf stdout. Unbekannte Methoden liefern einen JSON-RPC-Fehler.

Der Server handelt die Protokollversion aus (die des Clients, wenn bekannt, sonst `2025-06-18`), schickt bei `initialize` kurze `instructions` für das Modell mit und kennzeichnet die Tools mit `annotations` (`readOnlyHint` für optimize, status und info). Während er läuft, gehen versehentliche Ausgaben auf stdout nach stderr, damit sie das Protokoll nicht stören; stderr landet im Log des Clients (bei Claude Desktop unter `~/Library/Logs/Claude/mcp-server-claudegravity.log`).

Manueller Test:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp_server.py
```
