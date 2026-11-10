# Änderungsprotokoll

🇬🇧 [English](CHANGELOG.en.md) · Versionen nach [Semantic Versioning](https://semver.org/lang/de/). Die Version steht in `claudegravity/__init__.py`, im MCP-Server und in allen Plugin-Manifesten (gemeinsam erhöhen, `tests/test_plugins.py` prüft das). `claudegravity --version` zeigt sie an.

## [Unveröffentlicht]

## [1.7.0] – 2026-11-10

### Neu
- Chat-Oberfläche im Browser: `claudegravity chat` (Port `--chat-port`, Standard 8766). Aufgabe schreiben, Plan und Review lesen, mit einem Knopf freigeben oder in Worten ändern, Rückfragen beantworten, dem Bau zusehen, Diff und Bericht ansehen; dazu Stopp und Fortsetzen, Projektwechsel, alle Sitzungen des Projekts, Deutsch und Englisch, hell und dunkel, auch auf dem Handy. Nur auf `127.0.0.1` mit Token; schreibende Aufrufe verlangen JSON und die eigene Herkunft. → `docs/de/chat.md`
- `--session <name>` setzt eine bestimmte Sitzung fort statt der neuesten.
- Im Freigabe-Menü kannst du direkt einen Satz tippen, statt erst [2] und [3] zu wählen. Über dem Menü steht, ob der Prüfstatiker genehmigt hat oder noch Befunde offen sind.
- `timeline.jsonl` im Session-Ordner: Verlauf des Laufs (Plan, Review, Rückfragen und Antworten, Bau-Runden, Prüfbefehl, Abnahme, Ende).
- Der Diff in Live-Ansicht und Chat zeigt neue Dateien mit Inhalt (Geheimnis-, Binär- und große Dateien nur mit Namen); `__pycache__` und das Loop-Protokoll unter `logs/` erscheinen nicht mehr als Änderung.

### Behoben
- Fehlermeldungen einer KI-CLI zeigen nur noch ihren Text statt des ganzen JSON-Datensatzes; eine abgelaufene Anmeldung („OAuth session expired“) wird als CG-1203 mit dem Hinweis zum Anmelden gemeldet statt als CG-1206.
- Ein nach deinem Änderungswunsch überarbeiteter Plan wurde ohne neues Review gebaut und trotzdem als „geprüft“ angezeigt. Jetzt prüft der Prüfstatiker jede geänderte Fassung; der freigegebene Plan (auch im PR-Text) ist der tatsächlich gebaute.
- Strg+C an einer Rückfrage wirkte erst nach der Eingabetaste. Jetzt endet der Lauf sofort und nennt den Befehl zum Fortsetzen.
- Strg+C während Review oder Überarbeitung schrieb einen leeren `PLAN_vN.md`, den ein Fortsetzen dann benutzt hätte.
- Fortsetzen (`-c`) vergaß die Besetzung: `--planner`, `--reviewer`, `--builder` und eigene Endpunkte je Rolle mussten erneut angegeben werden, sonst lief die Sitzung mit anderen Rollen weiter oder brach mit CG-1001 ab.
- Zwei Läufe mit derselben Aufgabe in derselben Sekunde teilten sich einen Session-Ordner.
- Ab zehn Plan-Fassungen nahm ein Fortsetzen einen alten Plan (`PLAN_v10` lag vor `PLAN_v2`).
- „Im Editor öffnen“ stürzte unter macOS und Windows ab (fest `xdg-open`); jetzt `$VISUAL`/`$EDITOR`, sonst das Standardprogramm des Systems. Bearbeitet wird eine Kopie, das Original bleibt.
- Die interaktive CLI-Sitzung aus dem Menü stürzte bei Endpunkten ab.
- Endete ein Lauf im Freigabe-Menü, fehlten das Ereignis `session_end` und der Hinweis zum Fortsetzen.
- Stopp während eines laufenden CLI-Aufrufs endete als Fehler statt als sauberer Abbruch; Stopp während der Abnahme verwarf die Fertigmeldung mit leeren Befunden.
- Bei Endpunkten als Bauleiter fragte der Loop nach Schreibrechten „()“, die es dort nicht gibt.
- Ein Dateiende (EOF) an drei Rückfragen im Änderungs-Untermenü brach den Lauf mit einem Traceback ab.

## [1.6.0] – 2026-10-26

### Neu
- Fertige Programme am GitHub-Release für macOS (Apple Silicon, Intel), Linux (x64, arm64) und Windows, mit eigenem Python: `curl -fsSL …/claudegravity-install.sh | sh` bzw. `irm …/claudegravity-install.ps1 | iex` lädt das passende Archiv, prüft die SHA-256-Summe und installiert. Ein Programm ist Loop, MCP-Server (`claudegravity mcp`) und Installer (`claudegravity install`, kopiert sich nach `~/.local/bin` bzw. `%LOCALAPPDATA%\ClaudeGravity\bin` und trägt sich selbst als Server ein). Dazu am Release `claudegravity.mcpb`, Wheel, sdist und `SHA256SUMS`; `release.yml` baut alles bei einem Tag `v*` und testet die Installation auf jedem System.
- `tools/realrun.py`: prüft jedes installierte Backend mit echten Modellen (Antwort, Lesemodus hält, `--resume` setzt die Sitzung fort, mit `--full` ein ganzer Lauf als Bauleiter).
- Benchmark mit zehn Aufgaben; ein Lauf zählt nur, wenn die unveränderten Original-Tests grün sind. `--baseline <cli>` vergleicht mit einer einzelnen CLI ohne Loop, dazu `--repeat` und `--tasks-dir`.
- `claudegravity --version`.
- Kandidaten-Modus `--kandidaten claude,codex` (Best-of-N): mehrere Bauleiter setzen den Plan parallel in eigenen Worktrees um, der Loop prüft jeden selbst, die Abnahme wählt den besten und nimmt ihn ab.
- Testwächter (`--test-guard warn|strict|off`): erkennt nach grünem Prüfbefehl gelöschte Testdateien, neue Skip-/Only-Marker und weniger Testfälle oder Prüfungen; Audit CG-1504.
- Englische Ausgabe mit `--lang en` (auch `auto` nach Locale, `CLAUDEGRAVITY_LANG`, `"lang"` im Profil): Statuszeilen, Menüs, Hilfe, Fehlercodes mit Link auf die englische Doku, Berichte in `.done`/`AUDIT.md`; die Modelle antworten dann ebenfalls auf Englisch. Standard bleibt Deutsch.
- Installation als Paket ohne Klon: `pipx install git+https://github.com/gb-web-de/claudegravity-loop`, `uv tool install …` oder einmalig `uvx --from … claudegravity`; dazu `python -m claudegravity`. Keine Laufzeit-Abhängigkeiten, `pyproject.toml` nur für die Installation.
- Repo-Karte für Rollen ohne eigenen Dateizugriff (`--repo-map auto|an|aus`): Pfade mit Klassen und Funktionen, nach Bezug zur Aufgabe sortiert und auf 6 000 Zeichen begrenzt, damit Ollama und andere Endpunkte das Projekt kennen.
- Vom Issue zum Pull Request: `--from-issue 12` (auch `owner/repo#12` oder URL) nimmt Titel, Text und Kommentare als Aufgabe, `--open-pr`/`--pr-draft` pusht nach erfolgreicher Abnahme den Session-Branch und öffnet einen Pull Request mit `Closes #12`, Rollen, Kennzahlen und Plan. Über `gh` oder die REST-API (`GH_TOKEN`), Fehlercodes CG-1601/CG-1602. Das Repository ist dazu eine GitHub Action (`uses: gb-web-de/claudegravity-loop@main`), die ein Label oder `/claudegravity` startet; der MCP-Server kennt `issue` und `open_pr`.
- Sandbox (`--sandbox an|docker|podman`, `--sandbox-image`, `--sandbox-net`): Prüfbefehl und CLI-Bauleiter laufen in einem frischen Container mit deiner Benutzer-ID, ohne Capabilities und mit Grenzen; der Prüfbefehl ohne Netz, der Bauleiter sieht nur Arbeits- und Session-Ordner und die Anmeldedaten seiner eigenen CLI. `sandbox/Dockerfile` bringt die KI-CLIs mit. Fehlercodes CG-1701/CG-1702; nicht aus dem Projekt-Profil.
- Live-Ansicht und Benachrichtigungen: `--watch` (oder `claudegravity watch` ohne Lauf) zeigt im Browser Phase, aktuelle Rolle, Runde, Tokens, Kosten, geänderte Dateien, Diff und Log, nur auf `127.0.0.1` mit Token. `--notify desktop,bell,ntfy:<thema>,webhook:<url>` meldet, wenn eine Rückfrage 20 s offen ist und wenn der Lauf fertig ist oder abbricht. Neue Datei `live.json` im Session-Ordner, Ereignisse `call_start`/`proof_start`; der MCP-Server kennt `notify` und `watch`.
- Claude-Desktop-Erweiterung `claudegravity.mcpb` (MCP Bundle): Doppelklick installiert den MCP-Server samt Einstellungen für Projekt, Endpunkt, API-Schlüssel, Benachrichtigung, Sprache und Python. `tools/build_mcpb.py` baut sie reproduzierbar, CI prüft das Manifest mit `mcpb validate`, ein Versions-Tag hängt sie ans Release. Unter macOS/Linux sucht `launch.sh` ein Python ab 3.10.
- Der Benchmark baut direkt im Wegwerf-Ordner (`--no-worktree`), damit die Original-Tests das Ergebnis sehen.

### Geändert
- Prüfstatiker bewertet verhältnismäßig: HOCH/MITTEL nur, wenn der Plan die Aufgabe verfehlt, Daten beschädigt oder eine Sicherheitslücke öffnet. Mit `--plan-auto` wird nach dem Rundenlimit auch gebaut, wenn nur MITTEL/NIEDRIG offen sind (Befunde gehen an den Bauleiter). Im ersten echten Benchmark scheiterte `csv-report` daran, dass der Prüfstatiker zweimal Härtung außerhalb der Aufgabe verlangte.
- Prüfer-Sitzung ab Runde 2 fortsetzen jetzt auch bei Codex und Copilot (nur Plan-Diff statt ganzem Plan).
- Copilot läuft über die neue Copilot CLI (`copilot -s`, Prompt über stdin, eigene Sitzung mit `--resume`, Lesemodus über `--deny-tool`) und ist ein vollwertiger Bauleiter. `gh copilot suggest` wird nicht mehr unterstützt.

### Behoben
- Leere `CLAUDEGRAVITY_*`-Variablen gelten als nicht gesetzt statt als ungültiger Wert.
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
