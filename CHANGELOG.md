# Änderungsprotokoll

🇬🇧 [English](CHANGELOG.en.md) · Versionen nach [Semantic Versioning](https://semver.org/lang/de/). Die Version steht in `claudegravity/__init__.py`, im MCP-Server und in allen Plugin-Manifesten (gemeinsam erhöhen, `tests/test_plugins.py` prüft das). `claudegravity --version` zeigt sie an.

## [Unveröffentlicht]

### Neu
- `tools/realrun.py`: prüft jedes installierte Backend mit echten Modellen (Antwort, Lesemodus hält, `--resume` setzt die Sitzung fort, mit `--full` ein ganzer Lauf als Bauleiter).
- Benchmark mit zehn Aufgaben; ein Lauf zählt nur, wenn die unveränderten Original-Tests grün sind. `--baseline <cli>` vergleicht mit einer einzelnen CLI ohne Loop, dazu `--repeat` und `--tasks-dir`.
- `claudegravity --version`.
- Kandidaten-Modus `--kandidaten claude,codex` (Best-of-N): mehrere Bauleiter setzen den Plan parallel in eigenen Worktrees um, der Loop prüft jeden selbst, die Abnahme wählt den besten und nimmt ihn ab.
- Testwächter (`--test-guard warn|strict|off`): erkennt nach grünem Prüfbefehl gelöschte Testdateien, neue Skip-/Only-Marker und weniger Testfälle oder Prüfungen; Audit CG-1504.
- Englische Ausgabe mit `--lang en` (auch `auto` nach Locale, `CLAUDEGRAVITY_LANG`, `"lang"` im Profil): Statuszeilen, Menüs, Hilfe, Fehlercodes mit Link auf die englische Doku, Berichte in `.done`/`AUDIT.md`; die Modelle antworten dann ebenfalls auf Englisch. Standard bleibt Deutsch.
- Installation als Paket ohne Klon: `pipx install git+https://github.com/gb-web-de/claudegravity-loop`, `uv tool install …` oder einmalig `uvx --from … claudegravity`; dazu `python -m claudegravity`. Keine Laufzeit-Abhängigkeiten, `pyproject.toml` nur für die Installation.
- Repo-Karte für Rollen ohne eigenen Dateizugriff (`--repo-map auto|an|aus`): Pfade mit Klassen und Funktionen, nach Bezug zur Aufgabe sortiert und auf 6 000 Zeichen begrenzt, damit Ollama und andere Endpunkte das Projekt kennen.
- Vom Issue zum Pull Request: `--from-issue 12` (auch `owner/repo#12` oder URL) nimmt Titel, Text und Kommentare als Aufgabe, `--open-pr`/`--pr-draft` pusht nach erfolgreicher Abnahme den Session-Branch und öffnet einen Pull Request mit `Closes #12`, Rollen, Kennzahlen und Plan. Über `gh` oder die REST-API (`GH_TOKEN`), Fehlercodes CG-1601/CG-1602. Das Repository ist dazu eine GitHub Action (`uses: gb-web-de/claudegravity-loop@main`), die ein Label oder `/claudegravity` startet; der MCP-Server kennt `issue` und `open_pr`.
- Der Benchmark baut direkt im Wegwerf-Ordner (`--no-worktree`), damit die Original-Tests das Ergebnis sehen.

### Geändert
- Prüfstatiker bewertet verhältnismäßig: HOCH/MITTEL nur, wenn der Plan die Aufgabe verfehlt, Daten beschädigt oder eine Sicherheitslücke öffnet. Mit `--plan-auto` wird nach dem Rundenlimit auch gebaut, wenn nur MITTEL/NIEDRIG offen sind (Befunde gehen an den Bauleiter). Im ersten echten Benchmark scheiterte `csv-report` daran, dass der Prüfstatiker zweimal Härtung außerhalb der Aufgabe verlangte.
- Prüfer-Sitzung ab Runde 2 fortsetzen jetzt auch bei Codex und Copilot (nur Plan-Diff statt ganzem Plan).
- Copilot läuft über die neue Copilot CLI (`copilot -s`, Prompt über stdin, eigene Sitzung mit `--resume`, Lesemodus über `--deny-tool`) und ist ein vollwertiger Bauleiter. `gh copilot suggest` wird nicht mehr unterstützt.

### Behoben
- Endpunkt-Bauleiter (Ollama, LM Studio, eigene Server) konnten im Git-Workspace ohne Etappen nie „fertig“ melden: Die Fertigmeldung liegt im Session-Ordner außerhalb des Workspace und wurde als Schreibversuch nach außen blockiert. Der Loop schreibt sie jetzt selbst.
- Eine fehlende Copilot CLI hinter `gh` galt als bereit, weil `gh copilot` mit Rückgabe 0 endet.
- `gh` ohne heruntergeladene Copilot CLI wird nicht mehr als Copilot erkannt; die automatische Rollenwahl nahm es sonst als Prüfstatiker.
- Rollen mit Copilot über `gh` brachen mit „Agent-CLI 'gh' ist nicht verfügbar“ ab.

## [1.5.0] – 2026-10-25

Erster festgehaltener Stand. Paket, MCP-Server (zuvor 1.4.0) und Plugin-Manifeste (zuvor 1.0.0) tragen ab hier dieselbe Version.

- Vier Rollen mit getrennten Anbietern: Architekt, Prüfstatiker, Bauleiter, Abnahme; Urteile nur über die letzte `VERDICT:`-Zeile.
- Backends `claude`, `agy`, `gemini`, `codex`, `copilot`, `ollama` und OpenAI-kompatible Endpunkte; Strategien `balanced`, `best-code`, `eco`, `local-free`, `hybrid`.
- Etappen-Modus, Bauleiter-Sitzung über Runden, Suchen/Ersetzen-Blöcke für Endpunkte, Plan-Auszug je Etappe.
- Einrichtung mit `claudegravity init`, Profile und Vorlagen, `--print-effective-config`, Trockenlauf mit Kostenschätzung, Budget-Grenzen, Eskalation zur Cloud.
- Sicherheit: lesende Rollen überwacht, Schreibziele nur im Projekt, geschwärzte Logs, Bedrohungsmodell.
- MCP-Server für Desktop-Apps und CLIs, Plugins für Claude Code, Codex, Antigravity, Copilot CLI, Cursor und Gemini CLI.
- Worktree je Session, Fortsetzen nach Abbruch, Fehlercodes CG-xxxx, Ereignis-Log `events.jsonl`, Smoke-Matrix auf Linux, macOS und Windows.
