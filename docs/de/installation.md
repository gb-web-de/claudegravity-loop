# Installation

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/installation.md)

ClaudeGravity besteht aus zwei Startdateien (`loop.py` und `mcp_server.py`) und dem Paketordner `claudegravity/`, den `loop.py` aus dem eigenen Verzeichnis lädt. Der Ordner muss deshalb neben `loop.py` liegen bleiben; Symlinks auf `loop.py` funktionieren. Alles nutzt ausschließlich die Standardbibliothek. Ein `pip install` ist **nicht nötig**: keine Abhängigkeiten, keine virtuelle Umgebung, nichts zu kompilieren. Wer Befehle lieber über pipx oder uv verwaltet, kann ClaudeGravity trotzdem als Paket installieren (siehe [unten](#mit-pipx-oder-uv)). Ganz ohne Python geht es mit dem [fertigen Programm](#fertiges-programm-ohne-python) aus dem Release.

## Fertiges Programm (ohne Python)

Jedes [Release](https://github.com/gb-web-de/claudegravity-loop/releases) enthält ClaudeGravity als eigenständiges Programm, das sein eigenes Python mitbringt. Ein Befehl lädt es, prüft die SHA-256-Summe, legt `claudegravity`, `claudegravity-loop` und `claudegravity-mcp` an und trägt den MCP-Server und den Skill in alle gefundenen Clients ein:

```bash
# macOS (Apple Silicon und Intel) und Linux (x64 und arm64, z. B. Raspberry Pi)
curl -fsSL https://github.com/gb-web-de/claudegravity-loop/releases/latest/download/claudegravity-install.sh | sh
```

```powershell
# Windows (PowerShell)
irm https://github.com/gb-web-de/claudegravity-loop/releases/latest/download/claudegravity-install.ps1 | iex
```

Danach ein neues Terminal öffnen und `claudegravity --info` aufrufen. Argumente gehen an den Installer, z. B. `curl … | sh -s -- --project ~/projekte/shop` (Standardprojekt für Desktop-Apps) oder `--no-path`. Eine bestimmte Version nimmst du mit `CLAUDEGRAVITY_VERSION=v1.6.0`.

| Release-Datei | Für |
| :--- | :--- |
| `claudegravity-macos-arm64.tar.gz` | macOS mit Apple Silicon (M1 bis M4) |
| `claudegravity-macos-x86_64.tar.gz` | macOS mit Intel-Prozessor |
| `claudegravity-linux-x86_64.tar.gz` | Linux x64 mit glibc 2.35 oder neuer (Ubuntu 22.04, Debian 12 …) |
| `claudegravity-linux-arm64.tar.gz` | Linux arm64, z. B. Raspberry Pi 4/5 mit 64-Bit-System |
| `claudegravity-windows-x86_64.zip` | Windows 10/11 (auf ARM-Geräten über die eingebaute Emulation) |
| `claudegravity.mcpb` | Claude Desktop, siehe [Erweiterung](mcp-server.md#claude-desktop-erweiterung-mit-einem-klick) |
| `claudegravity_loop-<version>-py3-none-any.whl` | Python 3.10+ mit pipx oder uv, siehe [unten](#mit-pipx-oder-uv) |
| `SHA256SUMS` | Prüfsummen aller Dateien |

* **Von Hand:** Archiv entpacken und `./claudegravity/claudegravity install` aufrufen (Windows: `claudegravity\claudegravity.exe install`). Das Programm kopiert sich nach `~/.local/bin` bzw. `%LOCALAPPDATA%\ClaudeGravity\bin` und ergänzt den `PATH`; es läuft aber auch ohne Installation direkt aus dem Ordner.
* **Ein Programm für alles:** `claudegravity "Aufgabe"` startet den Loop, `claudegravity mcp` den MCP-Server (so trägt der Installer ihn ein), `claudegravity install` installiert. Die KI-CLIs (`claude`, `codex`, `gemini`, `ollama` …) brauchst du weiterhin.
* **Nicht signiert:** Über den Browser geladen blockiert macOS den ersten Start („Apple konnte nicht überprüfen …“). Dann `xattr -d com.apple.quarantine claudegravity/claudegravity` ausführen oder unter *Systemeinstellungen → Datenschutz & Sicherheit* „Dennoch öffnen“ wählen. Windows SmartScreen meldet sich mit „Der Computer wurde durch Windows geschützt“: *Weitere Informationen → Trotzdem ausführen*. Die Ein-Befehl-Installation lädt ohne Browser und ist davon normalerweise nicht betroffen.
* **Aktualisieren:** denselben Befehl noch einmal ausführen. **Entfernen:** `claudegravity install --uninstall` (Programm, Befehle, MCP-Einträge und Skill).

## Voraussetzungen

| Komponente | Pflicht? | Zweck |
| :--- | :--- | :--- |
| **Python 3.10+** | Ja (nicht beim [fertigen Programm](#fertiges-programm-ohne-python)) | Laufzeit für `loop.py` und `mcp_server.py` (es werden `str \| None`-Typannotationen genutzt, daher mindestens 3.10). |
| **Mindestens eine KI-CLI** oder ein **OpenAI-kompatibler Endpunkt** | Ja | Ohne Backend kann keine Rolle besetzt werden. Siehe [Backends](backends.md). |
| **Zwei verschiedene Backends** | Empfohlen | Das 4-Augen-Prinzip greift nur, wenn Architekt und Prüfstatiker unterschiedliche Modelle sind. Mit nur einer CLI prüft sich das Modell selbst. |
| `git` | Optional | Zum Klonen und Aktualisieren. |

Unterstützte CLIs (werden automatisch im `PATH` gesucht): `claude`, `agy`, `gemini`, `codex`, `copilot` (bzw. `gh`), `ollama`. Die CLIs werden mit deinen bestehenden Abos angemeldet – ClaudeGravity selbst braucht keine API-Schlüssel.

> [!TIP]
> **Alles in einem Schritt:** Nach dem Klonen `./install.sh` (Linux/macOS), `install.bat` (CMD) oder `.\install.ps1` (PowerShell) ausführen. Das trägt den MCP-Server und den Skill in alle gefundenen Clients ein (Claude Code, Claude Desktop, Gemini CLI, Antigravity, Codex, Copilot CLI, Cursor, Windsurf, VS Code) und macht `claudegravity`, `claudegravity-loop` und `claudegravity-mcp` global aufrufbar. `--project <pfad>` setzt ein Standardprojekt für Desktop-Apps (`CLAUDEGRAVITY_PROJECT`), `--status` zeigt den Stand, `--dry-run` simuliert, `--uninstall` entfernt alles wieder. Die manuellen Schritte unten sind dann nicht nötig. Nur Claude Desktop? Dann reicht die [Erweiterung `.mcpb`](mcp-server.md#claude-desktop-erweiterung-mit-einem-klick).

## Mit pipx oder uv

Ohne Klon, direkt aus GitHub; legt `claudegravity`, `claudegravity-loop` und `claudegravity-mcp` an (auf PyPI liegt das Paket noch nicht):

```bash
pipx install git+https://github.com/gb-web-de/claudegravity-loop
# oder
uv tool install git+https://github.com/gb-web-de/claudegravity-loop
# einmalig ausprobieren, ohne etwas zu installieren:
uvx --from git+https://github.com/gb-web-de/claudegravity-loop claudegravity --dry-run "Deine Aufgabe"
```

Aus einem Klon geht auch `pipx install .` bzw. `uv tool install .`; `python -m claudegravity` ist derselbe Einstieg wie `loop.py`. Aktualisieren mit `pipx upgrade claudegravity-loop` bzw. `uv tool upgrade claudegravity-loop`. Für MCP-Clients ist dann `claudegravity-mcp` der Befehl (statt `python3 /pfad/mcp_server.py`). Die Plugins und `install.py` erwarten weiterhin einen Klon.

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

* **Aktualisieren:** `git pull` im Repository-Ordner (mit pipx/uv: `pipx upgrade claudegravity-loop` bzw. `uv tool upgrade claudegravity-loop`; fertiges Programm: den [Ein-Befehl-Installer](#fertiges-programm-ohne-python) noch einmal ausführen).
* **Deinstallieren:** fertiges Programm mit `claudegravity install --uninstall`, sonst Symlinks in `~/.local/bin` bzw. den `PATH`-Eintrag entfernen und den Ordner löschen. Projektbezogene Daten liegen in `.dual-loop/` und `logs/` des jeweiligen Zielprojekts.

## Weiter

* [Schnellstart](schnellstart.md)
* [MCP-Server in Claude Code & Co. registrieren](mcp-server.md)
