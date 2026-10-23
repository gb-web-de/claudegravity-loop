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

claudegravity init                                     # Erkennt KIs, fragt 3 Dinge, speichert ein Profil
claudegravity "Erstelle ein Python-Skript für Wetterabfragen mit Fehlerbehandlung"
```

Unter Windows: `claudegravity.bat` (CMD) bzw. `.\claudegravity.ps1` (PowerShell). Details: [Installation](docs/de/installation.md) · [Schnellstart](docs/de/schnellstart.md).

## Wähle deinen Weg

| Ziel | Befehl | Was passiert |
| :--- | :--- | :--- |
| ⚡ **Schnell** | `claudegravity "Deine Aufgabe"` | Standard-Belegung (`balanced`): eine Cloud-CLI plant und baut, eine andere prüft und nimmt ab. |
| 💶 **Günstig** | `claudegravity "Deine Aufgabe" --strategy hybrid --proof "npm test"` | Cloud nur für Plan und Abnahme, Prüfung und Bau laufen lokal mit Ollama oder LM Studio, in Etappen. Ohne lokales Modell: `--strategy eco`. |
| 🏆 **Maximale Qualität** | `claudegravity "Deine Aufgabe" --strategy best-code --template refactor --proof "npm test"` | Alle Rollen mit hohem Effort, strenger Prüfstatiker, Abnahme durch einen zweiten Anbieter. |

`npm test` durch den Testbefehl deines Projekts ersetzen. Unsicher? `claudegravity init` fragt dich und speichert die Wahl; `--dry-run` zeigt vorher, wer welche Rolle bekommt.

## Highlights

* **Einrichtung & Profile:** `claudegravity init`, Profile global oder pro Projekt, Vorlagen `--template bugfix|feature|refactor`, `--print-effective-config` zeigt, woher jeder Wert kommt. → [CLI-Referenz](docs/de/cli-referenz.md#vorrang-der-einstellungen)
* **Strategie-Presets:** `--strategy best-code | eco | local-free | hybrid | balanced` – bis zu ~70 % Token-Ersparnis oder 0 € im Bau-Loop mit lokalem Modell. → [Strategien](docs/de/strategien.md)
* **Cloud + lokal automatisch:** `--strategy hybrid` lässt z. B. Codex planen und abnehmen, Ollama prüfen und bauen; die Ollama-Modelle wählt der Loop aus den installierten, der Plan wird in Etappen gebaut und jede mit `--proof` geprüft. → [Ollama & Codex](docs/de/ollama-und-codex.md)
* **Beliebige Backends pro Rolle:** `claude`, `agy`, `gemini`, `codex`, `copilot`, Ollama, LM Studio oder eigene OpenAI-kompatible Server. → [Backends](docs/de/backends.md)
* **Trockenlauf:** `--dry-run` zeigt Belegung und Befehl, ohne etwas zu ändern.
* **Abnahme statt Selbstlob:** `--proof "<testbefehl>"` führt ClaudeGravity selbst aus; danach prüft ein anderes Modell den Diff. Prüfer lesen nur, Schreibrechte hat allein der Bauleiter. → [Bau-Loop](docs/de/bau-loop.md)
* **Als Skill:** [`skills/claudegravity/`](skills/claudegravity/SKILL.md) für Claude Code und Codex.
* **Limits im Griff:** Wechseln, Warten oder Sichern bei Ratenlimits; `--auto-switch` wechselt automatisch.
* **Fortsetzen:** `claudegravity -c` macht nach Abbruch genau dort weiter. → [Sessions & Dateien](docs/de/sessions-und-dateien.md)
* **Token- & Kosten-Audit** pro Rolle, Modell und Effort in der `.done`-Datei, mit Kennzahlen (Kosten je Aufgabe, Runden bis Erfolg, Nacharbeitsquote) zum Vergleichen von Sessions.
* **Robust & nachvollziehbar:** automatische Neuversuche mit Backoff bei Überlastung und Netzfehlern; geschwärzte Logs und ein Audit, wenn eine lesende Rolle doch schreibt.
* **MCP-Server** (`mcp_server.py`), mit dem Claude Code & Co. den optimalen Befehl berechnen und starten. → [MCP-Server](docs/de/mcp-server.md)
* **Plugins** für Claude Code, Codex, Antigravity, Copilot CLI, Cursor und Gemini CLI: ein Befehl, z. B. `/plugin marketplace add gb-web-de/claudegravity-loop`, bringt MCP-Server, Skill und `/claudegravity:run`. → [Plugins](docs/de/plugins.md)

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
| [Ollama & Codex](docs/de/ollama-und-codex.md) | Rollenbeispiele mit lokalem Ollama und Codex, Modelle für Mac M4 48 GB |
| [CLI-Referenz](docs/de/cli-referenz.md) | Alle Flags |
| [MCP-Server](docs/de/mcp-server.md) | Registrierung, Tools, Optimizer |
| [Plugins](docs/de/plugins.md) | Claude Code, Codex, Antigravity, Copilot CLI, Cursor, Gemini CLI |
| [Sessions & Dateien](docs/de/sessions-und-dateien.md) | `.dual-loop/`, `state.json`, `.done`, Projektkontext |
| [Sicherheit](docs/de/sicherheit.md) | Bedrohungsmodell, Schutzmaßnahmen, Empfehlungen |
| [Fehlerbehebung](docs/de/fehlerbehebung.md) | Entscheidungsbaum, Fehlercodes CG-xxxx, häufige Probleme, bekannte Einschränkungen |

---

## 🇬🇧 English Summary

ClaudeGravity is a zero-dependency (Python 3.10+ standard library) runner that splits AI coding work into separate roles, so the model that plans or builds never grades its own work:

1. **🏗️ Architect** drafts the plan.
2. **🧐 Reviewer** – a *different* model – stress-tests it for flaws, risks and missing tests.
3. **🔨 Builder** implements the approved plan in a loop, running tests until it writes `.done`.
4. **🔎 Acceptance check** – a provider other than the builder – runs `--proof` and reviews the final diff before the task counts as done.

Choose your path:

| Goal | Command |
| :--- | :--- |
| ⚡ **Fast** | `claudegravity "Your task"` |
| 💶 **Cheap** | `claudegravity "Your task" --strategy hybrid --proof "npm test"` (cloud plans and accepts, local model reviews and builds; without a local model: `--strategy eco`) |
| 🏆 **Maximum quality** | `claudegravity "Your task" --strategy best-code --template refactor --proof "npm test"` |

Not sure? `claudegravity init` asks three questions and saves a profile; `--dry-run` shows the role assignment first.

Key flags: `--strategy best-code|eco|local-free|hybrid|balanced`, `--template bugfix|feature|refactor`, `--print-effective-config`, `--etappen auto|an|aus` (build in stages), `--plan-auto`, `--dry-run`, `--proof "<test command>"`, `--abnahme <cli>`, `--auto-switch`, `-i`/`--ask`, `--yolo`, `-c`/`--resume`. Full documentation: 🇬🇧 [English](docs/en/README.md) · 🇩🇪 [Deutsch](docs/de/README.md). Role splits between local Ollama and Codex: [Ollama & Codex](docs/en/ollama-und-codex.md). Threat model: [Security](docs/en/sicherheit.md).

Plugins for Claude Code, Codex, Antigravity, Copilot CLI, Cursor and Gemini CLI bundle the MCP server, the skill and `run`/`optimize`/`status` commands: [Plugins](docs/en/plugins.md). In Claude Code:

```bash
/plugin marketplace add gb-web-de/claudegravity-loop
/plugin install claudegravity@claudegravity
```

MCP server for Claude Code without the plugin:

```bash
claude mcp add claudegravity -- python3 /path/to/claudegravity-loop/mcp_server.py
```

## 📜 Lizenz / License

MIT License.
