# Plugins für Claude Code, Codex, Antigravity & Co.

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/plugins.md)

Das Repository ist selbst ein Plugin. Ein Befehl im jeweiligen Client lädt den [MCP-Server](mcp-server.md) mit allen Tools (`claudegravity_optimize`, `claudegravity_run`, `claudegravity_status`, `claudegravity_stop`, `claudegravity_info`), den Skill `claudegravity` und drei Befehle. Kein Pfad muss von Hand eingetragen werden, und der Client wird automatisch Architekt.

| Befehl | Wirkung |
| :--- | :--- |
| `loop_run <Aufgabe>` | Rollen ermitteln, nach deinem OK im Hintergrund starten, Ergebnis berichten |
| `loop_optimize <Aufgabe>` | Beste Rollenverteilung und fertigen `claudegravity`-Befehl zeigen, ohne zu starten |
| `loop_status` | Stand des letzten Laufs im aktuellen Projekt, auf Wunsch abbrechen |

Voraussetzung ist wie beim Loop nur **Python 3.10+** als `python3` im PATH. Die Rollen-CLIs (`claude`, `agy`, `codex`, `ollama`, …) brauchst du wie gewohnt.

## Installieren

| Client | Befehl | Aufruf danach |
| :--- | :--- | :--- |
| **Claude Code** | `/plugin marketplace add gb-web-de/claudegravity-loop` und `/plugin install claudegravity@claudegravity` (oder `python3 install.py`) | `/loop_run …`, `/loop_optimize …`, `/loop_status` (oder `/claudegravity:loop_…`) |
| **Codex** (CLI und App) | `codex plugin marketplace add gb-web-de/claudegravity-loop`, dann in Codex unter Plugins installieren | Skill `claudegravity` oder `@claudegravity` |
| **Antigravity** (`agy`, App, IDE) | `agy plugin install https://github.com/gb-web-de/claudegravity-loop` | Skill `claudegravity`, Tools im Agenten |
| **GitHub Copilot CLI** | `copilot plugin marketplace add gb-web-de/claudegravity-loop` und `copilot plugin install claudegravity@claudegravity` | Skill `claudegravity` |
| **Cursor** | Repository als Plugin-Quelle bzw. Team-Marketplace eintragen (`.cursor-plugin/marketplace.json`) | `/loop_run`, `/loop_optimize`, `/loop_status` |
| **Gemini CLI** | `gemini extensions install https://github.com/gb-web-de/claudegravity-loop` | `/claudegravity:loop_run …`, `/claudegravity:loop_optimize …`, `/claudegravity:loop_status` |

Für Claude Desktop gibt es die [Erweiterung `.mcpb`](mcp-server.md#claude-desktop-erweiterung-mit-einem-klick) (Doppelklick genügt). Für VS Code und Windsurf gibt es kein passendes Plugin-Format; dort trägt der [Installer](mcp-server.md#am-einfachsten-installer) den MCP-Server ein.

**Lokal testen** (ohne GitHub): statt `gb-web-de/claudegravity-loop` den Pfad des Checkouts angeben, z. B. `/plugin marketplace add ~/Projekte/claudegravity-loop` oder `agy plugin install ~/Projekte/claudegravity-loop`.

**Plugin oder Installer, nicht beides:** Beide registrieren einen Server namens `claudegravity`. Wer auf das Plugin umsteigt, entfernt den alten Eintrag mit `python3 install.py --uninstall --only <client>`.

## Dateien im Repository

Jeder Client liest nur seine eigenen Dateien. Alle starten denselben Server `mcp_server.py` aus dem Plugin-Ordner.

| Datei | Client | Plugin-Ordner im MCP-Eintrag |
| :--- | :--- | :--- |
| `.claude-plugin/plugin.json` | Claude Code (MCP-Server, Skill aus `skills/`, Befehle aus `commands/*.md`) | `${CLAUDE_PLUGIN_ROOT}` |
| `.claude-plugin/marketplace.json` | Claude Code, Copilot CLI und Codex (Marketplace mit dem Repository als einzigem Plugin) | – |
| `plugin.json` + `mcp.json` | offener Standard [Agent Plugins](https://agent-plugins.org) (Codex, Copilot CLI); `plugin.json` ist zugleich das Antigravity-Manifest | `${PLUGIN_ROOT}` |
| `mcp_config.json` | Antigravity | `${PLUGIN_ROOT}` |
| `.cursor-plugin/plugin.json`, `.cursor-plugin/mcp.json`, `.cursor-plugin/marketplace.json` | Cursor | `${CURSOR_PLUGIN_ROOT}` |
| `gemini-extension.json` + `commands/claudegravity/*.toml` | Gemini CLI | `${extensionPath}` |
| `commands/*.md` | Befehle für Claude Code und Cursor | – |
| `skills/claudegravity/SKILL.md` | Skill für alle Clients | – |

Jeder Eintrag setzt `CLAUDEGRAVITY_HOST` passend zum Client (`claude`, `agy`, `gemini`), soweit das Format es erlaubt; sonst erkennt der Server den Client an `clientInfo` (siehe [Der aufrufende Client führt den Loop](mcp-server.md#der-aufrufende-client-führt-den-loop)).

**Befehle ändern:** `commands/*.md` ist die Vorlage, die TOML-Dateien für Gemini CLI enthalten denselben Text mit `{{args}}` statt `$ARGUMENTS`. `tests/test_plugins.py` prüft, dass beide gleich bleiben, dass alle Manifeste denselben Namen und dieselbe Version tragen und dass jeder MCP-Eintrag `mcp_server.py` startet. Bei einer neuen Version die `version` in `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json` und `gemini-extension.json` gemeinsam erhöhen. Claude Code prüft das Plugin mit `claude plugin validate .`.

## Bekannte Grenzen

- Getestet ist bisher nur Claude Code (Installation aus dem lokalen Marketplace, Server verbunden). Codex, Antigravity, Copilot CLI, Cursor und Gemini CLI folgen ihrer Dokumentation von Oktober 2026 und sind noch nicht im echten Client ausprobiert.
- Kennt ein Client die Plugin-Variable im MCP-Eintrag nicht, startet der Server nicht. Dann hilft der [Installer](mcp-server.md#am-einfachsten-installer) für diesen Client.
- Unter Windows heißt Python oft `python` oder `py` statt `python3`. Fehlt `python3`, den Server per Installer eintragen; der nutzt den absoluten Pfad des Pythons.
- Desktop-Apps starten den Server nicht im Projektordner. Die Befehle geben deshalb immer den absoluten `project_path` mit.
