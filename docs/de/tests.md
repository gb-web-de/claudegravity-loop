# Tests

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/tests.md)

Tests ziehen sich durch alle drei Phasen. Diese Seite beschreibt, wie ClaudeGravity mit Tests in deinem Projekt umgeht und wie du ClaudeGravity selbst prüfst.

## Tests im Ablauf

| Phase | Was mit Tests passiert |
| :--- | :--- |
| 🏗️ **Architekt** | Der Plan muss **Testkriterien** enthalten (neben betroffenen Dateien, Architektur und Randfällen). |
| 🧐 **Prüfstatiker** | Prüft den Plan ausdrücklich auf **fehlende Tests** und fordert sie per `VERDICT: REVISE` nach. |
| 🔨 **Bauleiter** | Soll in jeder Runde Tests ausführen und `.done` erst anlegen, wenn alles getestet ist. |

Mit `--proof "<testbefehl>"` führt ClaudeGravity den Testbefehl nach jeder Bau-Runde bzw. Etappe **selbst** aus; eine Fertigmeldung zählt erst, wenn er grün ist und die Abnahme zustimmt. Ohne `--proof` verlässt sich der Loop auf Bauleiter, Plan und Abnahme (siehe [Bau-Loop](bau-loop.md)).

## Tests zuverlässig machen

* **Testbefehl in die `CLAUDE.md` des Projekts schreiben**, z. B. `Tests: python -m pytest -q`. Die Datei geht als Kontext an den Architekten, der den Befehl in den Plan übernimmt (siehe [Sessions & Dateien](sessions-und-dateien.md#projektkontext-claudemd--knowledge)).
* **Abschlusskriterium festlegen**, z. B. „Erstelle `.done` erst, wenn `pytest` ohne Fehler durchläuft.“
* **Im Freigabe-Menü prüfen** ([4] Anzeigen), ob der Plan konkrete Tests nennt. Falls nicht: [2] Changes → [3] Feedback, z. B. „Ergänze Unit-Tests für alle Randfälle.“
* **Mit `--strategy best-code`** bekommen alle Phasen hohen Effort, was sich bei testintensiven Aufgaben auszahlt.
* **Nach dem Lauf selbst nachprüfen**: Testsuite einmal lokal ausführen, bevor du committest.

### Endpunkt-Bauleiter und Tests

Ollama-, LM-Studio- und eigene Server-Bauleiter können **keine Befehle ausführen**. Sie schreiben nur Dateien über `filepath:`-Blöcke. Mit `--proof` führt der Loop die Tests für sie aus und gibt die Ausgabe in der nächsten Runde zurück; ohne `--proof` laufen keine Tests.

## ClaudeGravity selbst prüfen

Die Unit-Tests brauchen nur Python und keine KI:

```bash
python3 -m unittest discover -s tests
```

| Suite | Prüft |
| :--- | :--- |
| `test_adapters.py` | Vertrag aller Backend-Adapter: Text- und Müll-Ausgaben, Fehler, Ratenlimits, Zeitlimits, HTTP-Fehler |
| `test_resume.py` | Atomarer Sitzungsstand, beschädigte `state.json`, Absturz per SIGKILL mitten im Bau und nach der Fertigmeldung |
| `test_smoke.py` | Ganzer Ablauf mit Fake-Server für `balanced` und `local-free` |
| `test_review_safety.py`, `test_stages.py` | Ende-zu-Ende mit Fake-CLIs bzw. Fake-Endpunkten, Abnahme, Etappen |
| `test_config.py`, `test_templates.py`, `test_wizard.py` | Profile, Umgebung, Vorlagen, Einrichtung |
| `test_retry.py`, `test_audit.py`, `test_errors.py`, `test_kpi.py` | Neuversuche, Audit, Fehlercodes, Kennzahlen |
| `test_budget.py`, `test_estimate.py` | Budget-Grenzen, Kostenschätzung vorab aus früheren Sessions |
| `test_progress.py` | Statuszeile nach jedem KI-Aufruf, Abbruchgrund bei Rundenlimit |

### Smoke-Matrix

Der CI-Job `smoke` (`.github/workflows/tests.yml`) läuft auf Linux, macOS und Windows je mit `balanced` und `local-free`. Ein Fake-Server spielt über die OpenAI-kompatible API alle Rollen, der Loop baut, führt `--proof` aus und nimmt ab. Stdout, Session-Ordner, Bau-Logs und `summary.json` mit den Kennzahlen hängen als Artefakt `smoke-<os>-<strategie>` am Lauf. Lokal:

```bash
python3 tests/smoke/run_smoke.py --strategy local-free --out smoke-artifacts
```

Echte CLIs (`claude`, `codex`, `agy` …) laufen in CI nicht, weil dort keine Abos angemeldet sind.

### Golden Fixtures

`tests/test_golden.py` vergleicht zentrale Ausgaben mit Referenzdateien in `tests/golden/`: Kennzahlen-Block, Fehlerkatalog, `--print-effective-config` mit Profil, Vorlage und Umgebung, einen Trockenlauf mit `local-free` und den kompletten Smoke-Lauf (Dateien im Session-Ordner, `LOG.md`, Kennzahlen). Pfade, Zeiten und Ports werden vorher vereinheitlicht. Ändert ein Commit eine dieser Ausgaben, schlägt CI fehl und zeigt den Unterschied. Ist die Änderung gewollt:

```bash
UPDATE_GOLDEN=1 python3 -m unittest tests.test_golden
```

und die geänderten Dateien in `tests/golden/` mit committen.

Ohne KI-Aufrufe und ohne Dateien zu ändern:

```bash
# Erkennung von CLIs und Endpunkten
claudegravity --info

# Rollen- und Modellbelegung für ein Preset
claudegravity --dry-run "Testaufgabe" --strategy local-free

# Optimizer
claudegravity-mcp --optimize "Fixe den Login-Bug" --priority lowest-cost

# MCP-Server antwortet auf tools/list
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp_server.py
```

Einen echten Durchlauf ohne Risiko machst du am besten im Demo-Projekt:

```bash
claudegravity "Ergänze eine Begrüßungsfunktion mit Test" -p projects/demo -m 3
```
