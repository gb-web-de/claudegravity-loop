# Installation

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/installation.md)

ClaudeGravity besteht aus zwei Startdateien (`loop.py` und `mcp_server.py`) und dem Paketordner `claudegravity/`, den `loop.py` aus dem eigenen Verzeichnis lädt. Der Ordner muss deshalb neben `loop.py` liegen bleiben; Symlinks auf `loop.py` funktionieren. Alles nutzt ausschließlich die Standardbibliothek. Es gibt **kein `pip install`**, keine virtuelle Umgebung und nichts zu kompilieren.

## Voraussetzungen

| Komponente | Pflicht? | Zweck |
| :--- | :--- | :--- |
| **Python 3.10+** | Ja | Laufzeit für `loop.py` und `mcp_server.py` (es werden `str \| None`-Typannotationen genutzt, daher mindestens 3.10). |
| **Mindestens eine KI-CLI** oder ein **OpenAI-kompatibler Endpunkt** | Ja | Ohne Backend kann keine Rolle besetzt werden. Siehe [Backends](backends.md). |
| **Zwei verschiedene Backends** | Empfohlen | Das 4-Augen-Prinzip greift nur, wenn Architekt und Prüfstatiker unterschiedliche Modelle sind. Mit nur einer CLI prüft sich das Modell selbst. |
| `git` | Optional | Zum Klonen und Aktualisieren. |

Unterstützte CLIs (werden automatisch im `PATH` gesucht): `claude`, `agy`, `gemini`, `codex`, `copilot` (bzw. `gh`), `ollama`. Die CLIs werden mit deinen bestehenden Abos angemeldet – ClaudeGravity selbst braucht keine API-Schlüssel.

> [!TIP]
> **Alles in einem Schritt:** Nach dem Klonen `./install.sh` (Linux/macOS), `install.bat` (CMD) oder `.\install.ps1` (PowerShell) ausführen. Das trägt den MCP-Server in alle gefundenen Clients ein (Claude Code, Claude Desktop, Gemini CLI, Antigravity, Codex, Copilot CLI, Cursor, Windsurf, VS Code) und macht `claudegravity`, `claudegravity-loop` und `claudegravity-mcp` global aufrufbar. `--project <pfad>` setzt ein Standardprojekt für Desktop-Apps (`CLAUDEGRAVITY_PROJECT`), `--status` zeigt den Stand, `--dry-run` simuliert, `--uninstall` entfernt alles wieder. Die manuellen Schritte unten sind dann nicht nötig.

## 🍏 macOS & 🐧 Linux

1. Repository klonen und Skripte ausführbar machen:
   ```bash
   git clone https://github.com/gb-web-de/claudegravity-loop.git ~/Projekte/claudegravity-loop
   cd ~/Projekte/claudegravity-loop
   chmod +x loop.py mcp_server.py
   ```
2. Globale Befehle per Symlink anlegen:
   ```bash
   mkdir -p ~/.local/bin
   ln -sf ~/Projekte/claudegravity-loop/loop.py       ~/.local/bin/claudegravity
   ln -sf ~/Projekte/claudegravity-loop/loop.py       ~/.local/bin/claudegravity-loop
   ln -sf ~/Projekte/claudegravity-loop/mcp_server.py ~/.local/bin/claudegravity-mcp
   ```
3. Falls `~/.local/bin` noch nicht im `PATH` liegt, in `~/.bashrc` bzw. `~/.zshrc` ergänzen und die Shell neu laden:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

Die Symlinks zeigen auf den Klon. Ein `git pull` im Repository aktualisiert damit automatisch die globalen Befehle.

## 🪟 Windows (CMD oder PowerShell)

1. Repository klonen (oder ZIP herunterladen und entpacken):
   ```cmd
   git clone https://github.com/gb-web-de/claudegravity-loop.git C:\claudegravity
   ```
2. Im Ordner liegen fertige Starter:

   | Datei | Shell | Startet |
   | :--- | :--- | :--- |
   | `claudegravity.bat` | CMD | `loop.py` |
   | `claudegravity.ps1` | PowerShell | `loop.py` |
   | `claudegravity-mcp.bat` | CMD | `mcp_server.py` |

   Die Starter setzen UTF-8 (`chcp 65001` bzw. `[Console]::OutputEncoding`, `PYTHONIOENCODING=utf-8`), damit Umlaute und Emojis korrekt erscheinen, und suchen nacheinander `python` und den Launcher `py -3`.
3. *(Optional)* `C:\claudegravity` zur Umgebungsvariable `PATH` hinzufügen, damit `claudegravity` in jedem Ordner funktioniert.

> [!NOTE]
> Falls PowerShell das Skript blockiert, hilft für den aktuellen Benutzer:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Installation prüfen

```bash
claudegravity --info        # erkannte CLIs, Endpunkte und Standard-Belegung
claudegravity-mcp --info    # dasselbe aus Sicht des MCP-Servers
```

Unter Windows entsprechend `claudegravity.bat --info` bzw. `.\claudegravity.ps1 --info`.

## Aktualisieren & Deinstallieren

* **Aktualisieren:** `git pull` im Repository-Ordner.
* **Deinstallieren:** Symlinks in `~/.local/bin` bzw. den `PATH`-Eintrag entfernen und den Ordner löschen. Projektbezogene Daten liegen in `.dual-loop/` und `logs/` des jeweiligen Zielprojekts.

## Weiter

* [Schnellstart](schnellstart.md)
* [MCP-Server in Claude Code & Co. registrieren](mcp-server.md)
