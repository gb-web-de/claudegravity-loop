# Änderungsprotokoll

🇬🇧 [English](CHANGELOG.en.md) · Versionen nach [Semantic Versioning](https://semver.org/lang/de/). Die Version steht in `claudegravity/__init__.py`, im MCP-Server und in allen Plugin-Manifesten (gemeinsam erhöhen, `tests/test_plugins.py` prüft das). `claudegravity --version` zeigt sie an.

## [Unveröffentlicht]

### Neu
- `tools/realrun.py`: prüft jedes installierte Backend mit echten Modellen (Antwort, Lesemodus hält, `--resume` setzt die Sitzung fort, mit `--full` ein ganzer Lauf als Bauleiter).
- Benchmark mit zehn Aufgaben; ein Lauf zählt nur, wenn die unveränderten Original-Tests grün sind. `--baseline <cli>` vergleicht mit einer einzelnen CLI ohne Loop, dazu `--repeat` und `--tasks-dir`.
- `claudegravity --version`.
- Testwächter (`--test-guard warn|strict|off`): erkennt nach grünem Prüfbefehl gelöschte Testdateien, neue Skip-/Only-Marker und weniger Testfälle oder Prüfungen; Audit CG-1504.
- Der Benchmark baut direkt im Wegwerf-Ordner (`--no-worktree`), damit die Original-Tests das Ergebnis sehen.

### Geändert
- Copilot läuft über die neue Copilot CLI (`copilot -s`, Prompt über stdin, eigene Sitzung mit `--resume`, Lesemodus über `--deny-tool`) und ist ein vollwertiger Bauleiter. `gh copilot suggest` wird nicht mehr unterstützt.

### Behoben
- Eine fehlende Copilot CLI hinter `gh` galt als bereit, weil `gh copilot` mit Rückgabe 0 endet.
- `gh` ohne heruntergeladene Copilot CLI wird nicht mehr als Copilot erkannt; die automatische Rollenwahl nahm es sonst als Prüfstatiker.
- Rollen mit Copilot über `gh` brachen mit „Agent-CLI 'gh' ist nicht verfügbar“ ab.

## [1.0.0] – 2026-10-25

Erster festgehaltener Stand.

- Vier Rollen mit getrennten Anbietern: Architekt, Prüfstatiker, Bauleiter, Abnahme; Urteile nur über die letzte `VERDICT:`-Zeile.
- Backends `claude`, `agy`, `gemini`, `codex`, `copilot`, `ollama` und OpenAI-kompatible Endpunkte; Strategien `balanced`, `best-code`, `eco`, `local-free`, `hybrid`.
- Etappen-Modus, Bauleiter-Sitzung über Runden, Suchen/Ersetzen-Blöcke für Endpunkte, Plan-Auszug je Etappe.
- Einrichtung mit `claudegravity init`, Profile und Vorlagen, `--print-effective-config`, Trockenlauf mit Kostenschätzung, Budget-Grenzen, Eskalation zur Cloud.
- Sicherheit: lesende Rollen überwacht, Schreibziele nur im Projekt, geschwärzte Logs, Bedrohungsmodell.
- MCP-Server für Desktop-Apps und CLIs, Plugins für Claude Code, Codex, Antigravity, Copilot CLI, Cursor und Gemini CLI.
- Worktree je Session, Fortsetzen nach Abbruch, Fehlercodes CG-xxxx, Ereignis-Log `events.jsonl`, Smoke-Matrix auf Linux, macOS und Windows.
