# ClaudeGravity Loop 🚀

> **Universeller Cross-Model Dual-Loop für Claude Code, Google Antigravity, OpenAI Codex, GitHub Copilot & lokale Modelle (Ollama, LM Studio, eigene Server im Heimnetz oder Intranet).**
> Verhindert KI-Betriebsblindheit durch ein unabhängiges 4-Augen-Prinzip: *Wer den Plan entwirft oder Code baut, darf ihn niemals selbst benoten.*
> **Plattformunabhängig:** Läuft auf **Windows, macOS und Linux** nur mit Python 3.10+ – kein `pip install` nötig.

📖 Dokumentation: 🇩🇪 [Deutsch](docs/de/README.md) · 🇬🇧 [English](docs/en/README.md) · [English summary below](#-english-summary)

## Wie es funktioniert

| Rolle | Phase | Aufgabe |
| :--- | :--- | :--- |
| 🏗️ **Architekt** | 1 – Planung | Entwirft einen detaillierten Plan (`PLAN_v1.md`). |
| 🧐 **Prüfstatiker** | 2 – Review | Ein *anderes* Modell prüft den Plan schonungslos auf Fehler, Risiken und fehlende Tests. |
| 🔨 **Bauleiter** | 3 – Bau-Loop | Setzt den freigegebenen Plan um und testet, bis die Fertigmeldung (`.done`) steht. |
| 🔎 **Abnahme** | 4 – Abnahme | Ein *anderer* Anbieter als der Bauleiter prüft den fertigen Code; erst dann ist die Aufgabe fertig. |

Dazwischen gibst du den Plan frei, änderst ihn oder tauschst die Rollen. Mehr dazu in [Ablauf & Rollen](docs/de/ablauf-und-rollen.md).

## In 60 Sekunden starten

```bash
git clone https://github.com/gb-web-de/claudegravity-loop.git ~/Projekte/claudegravity-loop
cd ~/Projekte/claudegravity-loop && chmod +x loop.py mcp_server.py
mkdir -p ~/.local/bin && ln -sf "$PWD/loop.py" ~/.local/bin/claudegravity

claudegravity --info                                   # Welche KIs sind da?
claudegravity "Erstelle ein Python-Skript für Wetterabfragen mit Fehlerbehandlung"
```

Unter Windows: `claudegravity.bat` (CMD) bzw. `.\claudegravity.ps1` (PowerShell). Details: [Installation](docs/de/installation.md) · [Schnellstart](docs/de/schnellstart.md).

## Highlights

* **Strategie-Presets:** `--strategy best-code | eco | local-free | balanced` – bis zu ~70 % Token-Ersparnis oder 0 € im Bau-Loop mit lokalem Modell. → [Strategien](docs/de/strategien.md)
* **Beliebige Backends pro Rolle:** `claude`, `agy`, `gemini`, `codex`, `copilot`, Ollama, LM Studio oder eigene OpenAI-kompatible Server. → [Backends](docs/de/backends.md)
* **Trockenlauf:** `--dry-run` zeigt Belegung und Befehl, ohne etwas zu ändern.
* **Abnahme statt Selbstlob:** `--proof "<testbefehl>"` führt ClaudeGravity selbst aus; danach prüft ein anderes Modell den Diff. Prüfer lesen nur, Schreibrechte hat allein der Bauleiter. → [Bau-Loop](docs/de/bau-loop.md)
* **Als Skill:** [`skills/claudegravity/`](skills/claudegravity/SKILL.md) für Claude Code und Codex.
* **Limits im Griff:** Wechseln, Warten oder Sichern bei Ratenlimits; `--auto-switch` wechselt automatisch.
* **Fortsetzen:** `claudegravity -c` macht nach Abbruch genau dort weiter. → [Sessions & Dateien](docs/de/sessions-und-dateien.md)
* **Token- & Kosten-Audit** pro Rolle, Modell und Effort in der `.done`-Datei.
* **MCP-Server** (`mcp_server.py`), mit dem Claude Code & Co. den optimalen Befehl berechnen und starten. → [MCP-Server](docs/de/mcp-server.md)

## Dokumentation

| Thema | |
| :--- | :--- |
| [Installation](docs/de/installation.md) | Voraussetzungen, Linux/macOS/Windows, globale Befehle |
| [Schnellstart](docs/de/schnellstart.md) | Erste Aufgabe, typische Kombinationen |
| [Ablauf & Rollen](docs/de/ablauf-und-rollen.md) | Phasen, Freigabe-Menü, Fragen-Modus, Limits |
| [Bau-Loop](docs/de/bau-loop.md) | Phase 3: Runden, Rechte, Abbruchbedingungen |
| [Tests](docs/de/tests.md) | Tests in Plan, Review und Bau; ClaudeGravity prüfen |
| [Strategien](docs/de/strategien.md) | Presets und ihre Standardwerte |
| [Backends](docs/de/backends.md) | CLIs, lokale Modelle, Intranet-Server, Umgebungsvariablen, YOLO |
| [CLI-Referenz](docs/de/cli-referenz.md) | Alle Flags |
| [MCP-Server](docs/de/mcp-server.md) | Registrierung, Tools, Optimizer |
| [Sessions & Dateien](docs/de/sessions-und-dateien.md) | `.dual-loop/`, `state.json`, `.done`, Projektkontext |
| [Fehlerbehebung](docs/de/fehlerbehebung.md) | Häufige Probleme, bekannte Einschränkungen |

---

## 🇬🇧 English Summary

ClaudeGravity is a zero-dependency (Python 3.10+ standard library) runner that splits AI coding work into separate roles, so the model that plans or builds never grades its own work:

1. **🏗️ Architect** drafts the plan.
2. **🧐 Reviewer** – a *different* model – stress-tests it for flaws, risks and missing tests.
3. **🔨 Builder** implements the approved plan in a loop, running tests until it writes `.done`.
4. **🔎 Acceptance check** – a provider other than the builder – runs `--proof` and reviews the final diff before the task counts as done.

```bash
claudegravity --info
claudegravity "Create a Python weather CLI tool with full test coverage"
claudegravity "Refactor auth" --strategy local-free --bauer ollama   # $0 build loop
```

Key flags: `--strategy best-code|eco|local-free|balanced`, `--dry-run`, `--proof "<test command>"`, `--abnahme <cli>`, `--auto-switch`, `-i`/`--ask`, `--yolo`, `-c`/`--resume`. Full documentation: 🇬🇧 [English](docs/en/README.md) · 🇩🇪 [Deutsch](docs/de/README.md).

MCP server for Claude Code:

```bash
claude mcp add claudegravity -- python3 /path/to/claudegravity-loop/mcp_server.py
```

## 📜 Lizenz / License

MIT License.
