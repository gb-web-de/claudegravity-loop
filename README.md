# ClaudeGravity Loop 🚀

> **Universeller Cross-Model Dual-Loop für Claude Code, Google Antigravity, OpenAI Codex, GitHub Copilot & lokale Modelle (Ollama, LM Studio, Intranet-Server wie ai.gb-web.de).**
> Verhindert KI-Betriebsblindheit durch ein unabhängiges 4-Augen-Prinzip: *Wer den Plan entwirft oder Code baut, darf ihn niemals selbst benoten.*
> **Plattformunabhängig:** Läuft auf **Windows, macOS und Linux** nur mit Python 3.10+ – kein `pip install` nötig.

🇬🇧 [English summary below](#-english-summary)

## Wie es funktioniert

| Rolle | Phase | Aufgabe |
| :--- | :--- | :--- |
| 🏗️ **Architekt** | 1 – Planung | Entwirft einen detaillierten Plan (`PLAN_v1.md`). |
| 🧐 **Prüfstatiker** | 2 – Review | Ein *anderes* Modell prüft den Plan schonungslos auf Fehler, Risiken und fehlende Tests. |
| 🔨 **Bauleiter** | 3 – Bau-Loop | Setzt den freigegebenen Plan um und testet, bis die Fertigmeldung (`.done`) steht. |

Dazwischen gibst du den Plan frei, änderst ihn oder tauschst die Rollen. Mehr dazu in [Ablauf & Rollen](docs/ablauf-und-rollen.md).

## In 60 Sekunden starten

```bash
git clone https://github.com/gb-web-de/claudegravity-loop.git ~/Projekte/claudegravity-loop
cd ~/Projekte/claudegravity-loop && chmod +x loop.py mcp_server.py
mkdir -p ~/.local/bin && ln -sf "$PWD/loop.py" ~/.local/bin/claudegravity

claudegravity --info                                   # Welche KIs sind da?
claudegravity "Erstelle ein Python-Skript für Wetterabfragen mit Fehlerbehandlung"
```

Unter Windows: `claudegravity.bat` (CMD) bzw. `.\claudegravity.ps1` (PowerShell). Details: [Installation](docs/installation.md) · [Schnellstart](docs/schnellstart.md).

## Highlights

* **Strategie-Presets:** `--strategy best-code | eco | local-free | balanced` – bis zu ~70 % Token-Ersparnis oder 0 € im Bau-Loop mit lokalem Modell. → [Strategien](docs/strategien.md)
* **Beliebige Backends pro Rolle:** `claude`, `agy`, `gemini`, `codex`, `copilot`, Ollama, LM Studio oder eigene OpenAI-kompatible Server. → [Backends](docs/backends.md)
* **Trockenlauf:** `--dry-run` zeigt Belegung und Befehl, ohne etwas zu ändern.
* **Limits im Griff:** Wechseln, Warten oder Sichern bei Ratenlimits; `--auto-switch` wechselt automatisch.
* **Fortsetzen:** `claudegravity -c` macht nach Abbruch genau dort weiter. → [Sessions & Dateien](docs/sessions-und-dateien.md)
* **Token- & Kosten-Audit** pro Rolle, Modell und Effort in der `.done`-Datei.
* **MCP-Server** (`mcp_server.py`), mit dem Claude Code & Co. den optimalen Befehl berechnen und starten. → [MCP-Server](docs/mcp-server.md)

## Dokumentation

| Thema | |
| :--- | :--- |
| [Installation](docs/installation.md) | Voraussetzungen, Linux/macOS/Windows, globale Befehle |
| [Schnellstart](docs/schnellstart.md) | Erste Aufgabe, typische Kombinationen |
| [Ablauf & Rollen](docs/ablauf-und-rollen.md) | Phasen, Freigabe-Menü, Fragen-Modus, Limits |
| [Bau-Loop](docs/bau-loop.md) | Phase 3: Runden, Rechte, Abbruchbedingungen |
| [Tests](docs/tests.md) | Tests in Plan, Review und Bau; ClaudeGravity prüfen |
| [Strategien](docs/strategien.md) | Presets und ihre Standardwerte |
| [Backends](docs/backends.md) | CLIs, lokale Modelle, Intranet-Server, Umgebungsvariablen, YOLO |
| [CLI-Referenz](docs/cli-referenz.md) | Alle Flags |
| [MCP-Server](docs/mcp-server.md) | Registrierung, Tools, Optimizer |
| [Sessions & Dateien](docs/sessions-und-dateien.md) | `.dual-loop/`, `state.json`, `.done`, Projektkontext |
| [Fehlerbehebung](docs/fehlerbehebung.md) | Häufige Probleme, bekannte Einschränkungen |

---

## 🇬🇧 English Summary

ClaudeGravity is a zero-dependency (Python 3.10+ standard library) runner that splits AI coding work into three roles, so the model that plans or builds never grades its own work:

1. **🏗️ Architect** drafts the plan.
2. **🧐 Building Inspector** – a *different* model – stress-tests it for flaws, risks and missing tests.
3. **🔨 Builder** implements the approved plan in a loop, running tests until it writes `.done`.

```bash
claudegravity --info
claudegravity "Create a Python weather CLI tool with full test coverage"
claudegravity "Refactor auth" --strategy local-free --bauer ollama   # $0 build loop
```

Key flags: `--strategy best-code|eco|local-free|balanced`, `--dry-run`, `--auto-switch`, `-i`/`--ask`, `--yolo`, `-c`/`--resume`. The detailed documentation in [`docs/`](docs/README.md) is in German; flag names and examples are the same in any language.

MCP server for Claude Code:

```bash
claude mcp add claudegravity -- python3 /path/to/claudegravity-loop/mcp_server.py
```

## 📜 Lizenz / License

MIT License.
