# ClaudeGravity Loop - Projekt-Richtlinien

## Zweck
`claudegravity-loop` ist ein leichtgewichtiger, autonomer Runner für AI-Coding-Aufgaben mit **Claude Code**, **Google Antigravity (`agy`)** und weiteren CLIs bzw. lokalen Modellen.
Er basiert auf dem Prinzip des [claudex-loop](https://github.com/chaseai-yt/claudex-loop): **Das Modell, das den Plan entwirft oder baut, benotet sich niemals selbst.**

## Architektur
- `loop.py`: Haupt-CLI-Runner (benötigt nur Python 3.10+ Standardbibliothek).
  - **3 Rollen:** 🏗️ Architekt (Phase 1: Plan), 🧐 Prüfstatiker (Phase 2: Review), 🔨 Bauleiter (Phase 3: Umsetzung). Jede Rolle hat eigene Flags für CLI, Modell, Effort und Endpunkt (`--planner/--architekt`, `--reviewer/--pruefstatiker`, `--builder/--bauer`, jeweils `-model`, `-effort`, `-endpoint`).
  - **Abnahme (Phase 4):** Nach `.done` führt der Loop `--proof` selbst aus und lässt den Diff von einem anderen Anbieter als dem Bauleiter prüfen (`--abnahme`). Architekt, Prüfstatiker und Abnahme laufen immer lesend (`get_readonly_flags`); nur der Bauleiter bekommt Schreibrechte. Urteile werden nur über `parse_review()` gelesen (letzte `VERDICT:`-Zeile).
  - **Backends:** CLIs `claude`, `agy`, `gemini`, `codex`, `copilot`/`gh`, `ollama` sowie OpenAI-kompatible REST-Endpunkte (Ollama, LM Studio, vLLM, Intranet-Server via `--endpoint` oder `CLAUDEGRAVITY_ENDPOINT`).
  - **Konfiguration:** Kommandozeile > Session (`-c`) > Umgebung (`CLAUDEGRAVITY_<EINSTELLUNG>`) > Projekt-Profil (`.dual-loop/profile.json`) > globales Profil (`~/.config/claudegravity/profile.json`) > Standard, aufgelöst in `apply_config_layers()`; `--print-effective-config` zeigt die Quelle je Wert.
  - **Strategien:** `--strategy best-code|eco|local-free|hybrid|balanced`; `--dry-run` zeigt die Belegung und den vollständigen Befehl ohne Ausführung. `hybrid` und `apply_auto_roles()` besetzen fehlende Rollen und Ollama-Modelle (aus `/api/tags`) automatisch; ausdrückliche Flags haben immer Vorrang.
  - **Etappen-Modus:** `--etappen auto|an|aus`. Der Architekt schließt den Plan mit `## Etappen` ab (`parse_stages()`), der Bauleiter setzt pro Runde eine Etappe um und bekommt bei Endpunkten den aktuellen Dateistand (`stage_file_context()`); der Loop prüft jede Etappe mit `--proof`. `--plan-auto` gibt einen Plan mit `APPROVED` ohne Menü frei.
- `mcp_server.py`: Eigenständiger MCP-Server (JSON-RPC 2.0 stdio) & CLI-Optimizer für automatisierte Modell- & Rollenwahl (Tools: `claudegravity_optimize`, `claudegravity_run`, `claudegravity_info`).
- `claudegravity.bat`, `claudegravity.ps1`, `claudegravity-mcp.bat`: Windows-Launcher.
- `skills/claudegravity/SKILL.md`: Skill, mit dem Claude Code oder Codex den Loop mit getrennten Anbietern startet.
- `docs/de/` und `docs/en/`: Doku auf Deutsch und Englisch mit gleichen Dateinamen, gegenseitig verlinkt. Änderungen immer in beiden Sprachen nachziehen.
- `tests/`: `unittest`-Suite; läuft in GitHub Actions auf Linux, macOS und Windows (`.github/workflows/tests.yml`).
- `.dual-loop/`: Git-ignorierter Arbeitsordner. Enthält den Unterordner `sessions/` und optional `profile.json` (alle Pläne, Reviews und Logs sind aufgabenspezifisch darin isoliert).
- `projects/`: Ordner für gespiegelte Projekte (wie in der Claude UI).
  - Jedes Unterprojekt kann eine eigene `CLAUDE.md` und einen Ordner `knowledge/` besitzen.

## Richtlinien für Entwickler & Agenten
- Verwende ausschließlich Standard-Bibliotheken (`argparse`, `pathlib`, `subprocess`, `signal`, `shutil`, `urllib`, `unittest`).
- Cloud-Modelle werden über die offiziellen CLIs (`claude`, `agy`, `gemini`, …) mit bestehenden Abos angesprochen. API-Keys gibt es nur für eigene OpenAI-kompatible Endpunkte (`--api-key` oder `CLAUDEGRAVITY_API_KEY`) und werden nie ins Repository geschrieben.
- Token-Schonung hat oberste Priorität: Übergib nur den Plan oder relevante Diffs, keine aufgeblähten Chat-Historien.
- Sicherheit:
  - Modell-Ausgaben sind nicht vertrauenswürdig. Dateien aus Antworten werden nur über `resolve_project_target()` innerhalb des Projektordners geschrieben (keine absoluten Pfade, kein `..`, kein `.git/`, keine Geheimnis-Dateien wie `.env`, `.ssh/` oder `*.key`).
  - Lesende Rollen werden zusätzlich überwacht: Ändert sich der Git-Stand während Plan, Review oder Abnahme, oder blockiert `resolve_project_target()` einen Schreibversuch, landet das über `record_audit_event()` in `LOG.md`, `audit-events.jsonl` und im `.done`-Audit. Logs werden mit `mask_secrets()` geschwärzt.
  - Prozesse immer mit Argumentlisten und ohne `shell=True` starten. Unter Windows löst `build_cli_command()` npm-`.cmd`-Shims direkt auf; Aufgabentexte dürfen nie in einen Shell-String gelangen.
- Tests vor jedem Commit: `python -m unittest discover -s tests`. Neue Funktionen bekommen einen Test in `tests/`.
- Sobald eine autonome Aufgabe erfolgreich abgeschlossen ist, erstelle die Datei `.done` im jeweiligen Session-Ordner (`.dual-loop/sessions/<session>/.done`) und NICHT im Projekt-Hauptverzeichnis.
