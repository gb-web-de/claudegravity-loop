# Bau-Loop (Phase 3)

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/bau-loop.md)

Der Bau-Loop startet erst, wenn du den Plan im Freigabe-Menü bestätigt hast (siehe [Ablauf & Rollen](ablauf-und-rollen.md)). Hier verbraucht ClaudeGravity rund 80–90 % aller Tokens, deshalb lohnt sich hier ein günstigeres oder lokales Modell (siehe [Strategien](strategien.md)).

## Wer baut?

* Standard: dieselbe CLI wie der Architekt, der den freigegebenen Plan geschrieben hat (nach einem Swap also der neue Architekt).
* Mit `--bauer <key>` (Alias `--builder`) ein beliebiges anderes Backend, z. B. `--bauer ollama` oder `--bauer bauer_ep`.
* Modell und Effort: `--bauer-model`, `--bauer-effort` oder die Standardwerte des Presets.

## Rechte-Abfrage vor dem Start

Ohne `--yolo` fragt ClaudeGravity:

```
Soll 🔨 Bauleiter (Claude Code) volle Schreib-/Tool-Rechte erhalten (--dangerously-skip-permissions)? [J/n]:
```

* **[Enter] / J:** Die Rechte-Flags werden gesetzt und in `state.json` gemerkt (siehe [Backends](backends.md#rechte--yolo)).
* **n:** Eingeschränkter Modus. Die CLI fragt dann selbst bei jedem Tool-Aufruf nach. Da ClaudeGravity die CLIs nicht interaktiv startet, kommt der Bauleiter in diesem Modus oft nicht weiter.

## Ablauf einer Runde

1. ClaudeGravity prüft, ob `.dual-loop/sessions/<session>/.done` schon existiert. Falls ja, folgt die Abnahme (siehe unten).
2. `last_iteration` und Metriken werden in `state.json` gespeichert. So kann nach einem Abbruch genau hier fortgesetzt werden.
3. Der Bauleiter bekommt einen kurzen Prompt: Pfad zur freigegebenen Planversion, die Aufgabe, den Auftrag „Dateien erstellen/ändern, Tests durchführen“, den Prüfbefehl und den genauen Pfad für die Fertigmeldung. Es wird **keine Chat-Historie** mitgeschickt, nur der Plan und gegebenenfalls die Rückmeldung der letzten Runde (roter Prüfbefehl oder Befunde der Abnahme).
4. Die Antwort wird im Terminal ausgegeben und an `logs/loop_<session>.log` angehängt.
5. Bei **Endpunkt-Bauleitern** (Ollama-Server, LM Studio, eigene Server) liest ClaudeGravity die `filepath:`-Codeblöcke aus der Antwort und schreibt die Dateien selbst (Format siehe [Backends](backends.md#wie-endpunkt-bauleiter-dateien-schreiben)). Geschriebene Dateien werden aufgelistet.
6. Erneute Prüfung auf `.done`. Ohne `.done` läuft der Prüfbefehl trotzdem; ist er rot, geht seine Ausgabe in die nächste Runde. Dann `--delay` Sekunden Pause (Standard 3) und die nächste Runde.

Ein Fehler in einer Runde (z. B. Absturz der CLI) beendet den Loop nicht: Er wird gemeldet, und die nächste Runde startet.

### Bauleiter-Sitzung fortsetzen

Ist der Bauleiter `claude` oder `codex`, setzt ClaudeGravity ab der zweiten Runde dieselbe Sitzung fort (`claude --resume <id>` bzw. `codex exec resume <id>`). Der Bauleiter hat Aufgabe, Plan und die schon gelesenen Dateien dann noch im Kontext und bekommt nur noch die Rückmeldung der letzten Runde (Ende der Prüfbefehl-Ausgabe oder Befunde der Abnahme) und den nächsten Schritt. Das spart bei mehreren Runden den größten Teil der Eingabe-Tokens und die Zeit zum erneuten Einlesen des Projekts.

* Lässt sich die Sitzung nicht fortsetzen (z. B. gelöscht oder abgelaufen), startet dieselbe Runde in einer frischen Sitzung mit vollem Auftrag.
* Nach einem Wechsel wegen Limit oder einer Eskalation startet der neue Bauleiter immer frisch.
* Die Sitzungs-ID steht in `state.json` (`builder_session`), damit auch `claudegravity -c` weitermacht. Fortgesetzte Runden zählt `builder_resumed` in den Kennzahlen.
* `--builder-fresh` (Alias `--bauer-neu`) schaltet das ab: jede Runde neue Sitzung wie früher.
* Endpunkt-Bauleiter haben keine Sitzung; sie bekommen weiter Plan und Dateistand in jeder Runde.

## Etappen-Modus

Kleine lokale Modelle arbeiten schneller und sicherer mit kleinen Stücken. Im Etappen-Modus (`--etappen an`, oder `auto` bei Bauleitern ohne eigenen Dateizugriff wie Ollama, LM Studio und Endpunkten) läuft Phase 3 so:

1. Der Architekt bekommt die Vorgabe, den Plan mit dem Abschnitt `## Etappen` abzuschließen: 2 bis 8 nummerierte Etappen, jede ändert höchstens zwei Dateien und ist danach testbar. Der Prüfstatiker prüft die Etappen mit dem Plan.
2. Nach der Freigabe liest ClaudeGravity die Etappen aus dem Plan und zeigt sie an.
3. Pro Runde bekommt der Bauleiter **nur die aktuelle Etappe**, die Liste der erledigten Etappen, den Plan und den **aktuellen Inhalt** der Dateien, die die Etappe nennt oder die er vorher geschrieben hat (bis 40 000 Zeichen). So sieht auch ein Ollama-Modell, was in den Runden davor entstanden ist. Ist der Plan länger als 6 000 Zeichen, geht nur ein Auszug mit: Kopf, Abschnitte zu Zielen, Abnahmekriterien, Tests, Risiken und Schnittstellen sowie die Abschnitte, die eine Datei der Etappe nennen; der Abschnitt `## Etappen` fällt weg, weil die Etappe ohnehin dabei ist. Gleichbleibende Teile (Aufgabe, Plan, Format) stehen vorn und Wechselndes (Etappe, Dateistand, Rückmeldung) hinten, damit Prompt-Caching bei Anbieter und Ollama greift.
4. Danach führt ClaudeGravity `--proof` aus. Grün: Die Etappe ist erledigt und steht in `LOG.md`. Rot: Die Ausgabe geht in die nächste Runde derselben Etappe. Nach 3 roten Versuchen hält der Loop an (`phase = stage_open`); `claudegravity -c` macht dort weiter.
5. Nach der letzten Etappe folgen Prüfbefehl und Abnahme wie unten. Verweigert die Abnahme, hängt ClaudeGravity eine Nacharbeits-Etappe mit den Befunden an. Eine `.done` des Bauleiters zählt in diesem Modus nicht; abgeschlossen wird nach der letzten Etappe.

Fehlt der Abschnitt `## Etappen` oder hat er weniger als zwei Etappen, baut der Bauleiter den ganzen Plan wie bisher. Ohne `--proof` gilt jede Etappe nach einer Runde als erledigt; deshalb im Etappen-Modus immer einen Prüfbefehl angeben. Ein Prüfbefehl, der ohne Tests rot ist (z. B. `unittest` in einem Projekt ohne Tests), hält schon die erste Etappe auf: dann zuerst einen Test anlegen oder die erste Etappe einen schreiben lassen.

Auch ohne Etappen-Modus bekommen Endpunkt-Bauleiter ab der zweiten Runde den aktuellen Inhalt der Dateien mit, die sie schon geschrieben haben.

## Repo-Karte

Claude Code, Codex und die anderen CLIs schauen sich das Projekt selbst an. Ein Endpunkt (Ollama, LM Studio, eigener Server) sieht dagegen nur, was im Prompt steht. Damit Architekt, Prüfstatiker und Bauleiter auf einem Endpunkt trotzdem wissen, welche Dateien und Funktionen es gibt, legt ClaudeGravity eine **Repo-Karte** dazu:

```
--- REPO-KARTE (Dateien mit Klassen und Funktionen; …) ---
src/stats.py: def median(values), def mean(values)
tests/test_stats.py: class StatsTest [test_median_even, test_median_odd]
README.md
--- ENDE REPO-KARTE ---
```

* Eine Zeile je Datei mit den Klassen (samt Methoden) und Funktionen der obersten Ebene. Python liest ClaudeGravity mit `ast` (mit Parameternamen), JavaScript/TypeScript, PHP, Go, Rust, Java/Kotlin/C#, Ruby, C/C++ und Shell über Muster.
* Dateien, die die Aufgabe, der Plan oder die Etappe nennt, stehen oben, dann Treffer im Pfad, dann Treffer in Symbolnamen. Die Karte ist auf 6 000 Zeichen begrenzt; sind es mehr Dateien, folgen nach den passendsten nur noch Pfade und am Ende ein Hinweis, wie viele ausgelassen wurden.
* Die Dateien kommen aus `git ls-files` (ohne Ignoriertes), sonst aus dem Ordner. `node_modules/`, `vendor/`, `.venv/`, Build-Ordner, Binärdateien und Geheimnis-Dateien wie `.env` oder `*.key` fehlen immer.
* Architekt und Prüfstatiker bekommen die Karte zur Aufgabe, der Bauleiter zur Aufgabe und zum Plan. Fortgesetzte Bauleiter-Sitzungen bekommen sie nicht noch einmal.
* `--repo-map auto` (Standard) gibt die Karte nur Rollen ohne eigenen Dateizugriff, `an` allen Rollen, `aus` keiner. Alias `--repo-karte`, in Profilen `"repo_map"`.

## Kandidaten-Modus (Best-of-N)

Mit `--kandidaten claude,codex` bauen mehrere Bauleiter denselben freigegebenen Plan **gleichzeitig**, jeder in einem eigenen Git-Worktree auf einem eigenen Branch (`loop/<session>-<kandidat>`). Ein Modell pro Kandidat gibst du mit `=` an: `--kandidaten codex=gpt-5,ollama=qwen3-coder:30b`.

```bash
claudegravity "Rabattberechnung reparieren" --kandidaten claude,codex --abnahme agy --proof "npm test" --yolo
```

1. Plan und Review laufen einmal wie gewohnt.
2. Jeder Kandidat läuft als eigener Loop ohne Abnahme bis zu seiner Fertigmeldung; Ausgabe in `<session>/candidates/<name>/loop.log` bzw. dem Session-Ordner daneben.
3. ClaudeGravity führt `--proof` in jedem Worktree selbst aus und lässt den [Testwächter](#testwächter) laufen. Nur grüne Kandidaten kommen weiter.
4. Die Abnahme (möglichst ein Anbieter, der nicht mitgebaut hat) bekommt Plan und Diffs aller grünen Kandidaten, wählt mit `WINNER: <name>` den besten und nimmt ihn mit `VERDICT` ab. Nennt sie keinen gültigen Namen, gewinnt der kleinste Eingriff ohne Testwächter-Funde.
5. Alle Kandidaten behalten ihren Branch; mit `--merge` wird nur der abgenommene Gewinner gemerged. Tabelle und Gewinner stehen in `.done`, Verbrauch aller Kandidaten in den Kennzahlen.

Voraussetzungen: ein Git-Repository mit mindestens einem Commit und Schreibrechte ohne Rückfrage (`--yolo` oder die einmalige Frage am Start), weil die Kandidaten ohne Terminal laufen. Wird der Gewinner nicht abgenommen, bleibt die Aufgabe offen (`phase = inspection_open`); die Branches liegen zum Weiterarbeiten bereit.

## Ende des Loops

| Auslöser | Ergebnis |
| :--- | :--- |
| `.done` gefunden, Prüfbefehl grün, Abnahme erteilt | `phase = completed`, Audit-Bericht wird in `.done` geschrieben und angezeigt. |
| Abnahme nach `--max-inspections` Runden weiter verweigert | `phase = inspection_open`, Befunde in `INSPECTION_round*.md`. Worktree wird nicht gemerged. Weiter mit `claudegravity -c -m <neues Maximum>`. |
| `.done` im Projekt-Hauptordner | Wird in den Session-Ordner verschoben und wie oben behandelt. |
| Etappe nach 3 Versuchen nicht grün | `phase = stage_open`, Stand und erledigte Etappen bleiben in `state.json`. Weiter mit `claudegravity -c`. |
| `--max-iterations` erreicht (Standard 10, im Etappen-Modus 2 pro Etappe + 2) | Stand gesichert, Audit-Bericht in `AUDIT.md` (kein `.done`, sonst gälte die Aufgabe beim Fortsetzen als fertig). Weiter mit `claudegravity -c -m <neues Maximum>`. |
| `Strg+C` | Aktuelle Runde wird sauber beendet, Stand bleibt erhalten. |
| Ratenlimit | Menü Wechseln / Warten / Beenden oder automatischer Wechsel mit `--auto-switch` (siehe [Ablauf & Rollen](ablauf-und-rollen.md#limits--auto-switch)). |

## Wann ist der Bauleiter „fertig“?

Der Bauleiter meldet mit `.done`, dass er fertig ist. Fertig **ist** die Aufgabe erst, wenn

1. der Prüfbefehl (`--proof`) grün ist – ClaudeGravity führt ihn selbst aus und glaubt nicht der Erfolgsmeldung des Bauleiters, und
2. die **Abnahme** zustimmt: Ein anderer Anbieter bekommt in einer frischen, lesenden Sitzung den Plan, das Ergebnis des Prüfbefehls und den Diff seit Baubeginn (`git diff` gegen den Basis-Commit plus neue Dateien, gekürzt auf 60 000 Zeichen). Er prüft auch, ob die Tests die Anforderung prüfen statt nur das, was die Umsetzung gerade tut.

Weist eines davon die Meldung zurück, löscht ClaudeGravity `.done` und gibt die Befunde in der nächsten Runde an den Bauleiter. Jede Abnahme steht als `INSPECTION_roundN.md` im Session-Ordner und in `LOG.md`. Ohne Git bekommt die Abnahme keinen Diff und liest die im Plan genannten Dateien selbst. Wie du die Tests absicherst, steht in [Tests](tests.md).

### Testwächter

Ein grüner Prüfbefehl beweist wenig, wenn der Bauleiter vorher die Tests abgeschwächt hat. Nach jedem grünen `--proof` vergleicht ClaudeGravity die Testdateien mit dem Basis-Commit und sucht nach gelöschten Testdateien, neuen Skip- oder Only-Markern (`@unittest.skip`, `pytest.mark.skip/xfail`, `it.skip`, `describe.only`, `xit`, `markTestSkipped`, `@Disabled`, `t.Skip` …) sowie nach weniger Testfällen oder Prüfungen als vorher. Funde erscheinen im Terminal, als Audit-Ereignis CG-1504 in `LOG.md` und `audit-events.jsonl` und im Kennzahlen-Zähler `tests_weakened`.

| `--test-guard` | Verhalten |
| :--- | :--- |
| `warn` (Standard) | Die Funde gehen mit in den Abnahme-Prompt; die Abnahme entscheidet, ob die Änderung begründet ist. |
| `strict` | Die Fertigmeldung wird sofort zurückgewiesen, der Bauleiter bekommt die Funde als Rückmeldung. |
| `off` | Keine Prüfung. |

Ohne Git-Basis-Commit (kein Repository) prüft der Wächter nichts.

## Nützliche Flags für Phase 3

| Flag | Wirkung |
| :--- | :--- |
| `-m`, `--max-iterations <n>` | Maximale Runden |
| `--etappen auto\|an\|aus` | Etappen-Modus (siehe oben) |
| `-d`, `--delay <s>` | Pause zwischen Runden, `0` für keine Pause |
| `--yolo` | Rechte-Abfrage überspringen (nur Bauleiter) |
| `--proof "<befehl>"` | Prüfbefehl, den ClaudeGravity selbst ausführt |
| `--abnahme`, `--abnahme-model`, `--max-inspections`, `--no-inspect` | Abnahme steuern |
| `--auto-switch` | Bei Limit automatisch Backend wechseln |
| `--bauer`, `--bauer-model`, `--bauer-effort`, `--bauer-endpoint` | Bauleiter festlegen |

Vollständige Liste: [CLI-Referenz](cli-referenz.md).
