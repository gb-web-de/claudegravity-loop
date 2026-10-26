# CLI-Referenz (`claudegravity` / `loop.py`)

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/cli-referenz.md)

```text
claudegravity [AUFGABE] [OPTIONEN]
```

Alle deutschen und englischen Schreibweisen eines Flags sind gleichwertig (z. B. `--bauer` = `--builder`).

`claudegravity --help` zeigt die wichtigsten Optionen in Gruppen (Start, Strategie und Kosten, Rollen und Modelle, Ablauf, Rechte und Arbeitsbereich), je Option nur den Hauptnamen. `claudegravity --help-all` zeigt alle Optionen mit allen Aliasen. Ausgeblendete Optionen funktionieren immer, auch in Profilen.

## Allgemein

| Flag | Aliase | Beschreibung | Standard |
| :--- | :--- | :--- | :--- |
| `AUFGABE` | *(Positionsargument)* | Die Programmieraufgabe in Anführungszeichen. Ohne Aufgabe wird eine unterbrochene Sitzung angeboten, sonst ein kurzer Wegweiser (`init`, Start, Trockenlauf, `--resume`, `--help`). | – |
| `-p`, `--project` | | Zielprojekt (absolut oder relativ). | `.` |
| `-m`, `--max-iterations` | | Maximale Runden im Bau-Loop (Phase 3). | `10`, im Etappen-Modus 2 pro Etappe + 2 |
| `-d`, `--delay` | | Pause zwischen Bau-Runden in Sekunden. | `3` |
| `-c`, `--resume` | `--continue` | Letzte Sitzung im Projekt fortsetzen. | aus |
| `-i`, `--ask` | `--interview`, `--clarify` | Fragen-Modus: Architekt und Prüfstatiker dürfen Rückfragen stellen. | aus |
| `--yolo` | `--auto-approve` | Volle Schreib- und Tool-Rechte für den **Bauleiter** ohne Nachfrage. Architekt, Prüfstatiker und Abnahme bleiben lesend. | aus |
| `--max-rounds` | | Maximale Review-Runden für den Plan. | `2` |
| `--auto-switch` | `--fallback` | Bei Limit automatisch zur alternativen KI wechseln. | aus |
| `--retries <n>` | `--neuversuche` | Automatische Neuversuche bei vorübergehenden Fehlern (Überlastung, HTTP 5xx, Verbindungsabbruch) mit exponentiellem Backoff und Jitter. `0` schaltet ab. Siehe [Fehlerbehebung](fehlerbehebung.md#automatische-neuversuche). | `3` |
| `--swap` | `--swap-roles`, `--reverse` | Standardrollen tauschen: Antigravity/Gemini plant, Claude prüft. | aus |
| `--strategy` | `--preset` | `balanced`, `best-code` (`quality`), `eco` (`economy`, `cost`), `local-free` (`free`, `local`), `hybrid` (`mixed`). Siehe [Strategien](strategien.md). | `balanced` |
| `--dry-run` | | Belegung, Kostenschätzung aus früheren Sessions, Hinweise (z. B. fehlendes `--proof`) und Startbefehl anzeigen, ohne etwas auszuführen oder anzulegen. | aus |
| `-h`, `--help` | | Wichtigste Optionen in Gruppen. | – |
| `--help-all` | | Alle Optionen mit Aliasen. | – |
| `--info` | `--check` | Erkannte CLIs/Endpunkte, Anmeldestatus und Standard-Belegung anzeigen. | aus |
| `--budget-max <wert>` | | Harte Grenze für die Session in Tokens (`500k`, `1.5m`) oder gemeldeten Kosten (`2.50usd`). Siehe [Budget](#budget). | – |
| `--budget-warn <wert>` | | Weiche Grenze, nur Warnung. | 80 % von `--budget-max` |
| `--budget-roles <liste>` | `--budget-rollen` | Harte Grenzen je Rolle, z. B. `"bauleiter=300k,abnahme=0.50usd"`. | – |
| `--escalate <ziel>` | `--eskalation` | Lokaler Bauleiter scheitert wiederholt: einmalig auf eine Cloud-CLI wechseln (`auto` oder z. B. `claude`). Siehe [Eskalation](strategien.md#eskalation-zur-cloud). | aus |
| `--escalate-after <n>` | `--eskalation-nach` | Erfolglose Bau-Runden in Folge bis zur Eskalation. | 2 |
| `--template <name>` | `--vorlage` | Aufgaben-Vorlage `bugfix`, `feature`, `refactor` oder eine eigene aus dem Profil. Siehe [Aufgaben-Vorlagen](#aufgaben-vorlagen). | – |
| `init`, `--init` | `--einrichten` | Einrichtung: erkennt System und KI-CLIs, fragt Ziel, Prüfbefehl und Speicherort und schreibt ein Profil. Siehe [Schnellstart](schnellstart.md#1-einrichten). | – |
| `--log-format text\|json` | | `json` schreibt zusätzlich `events.jsonl` in den Session-Ordner, eine JSON-Zeile pro Ereignis. Siehe [Sessions & Dateien](sessions-und-dateien.md#strukturiertes-ereignis-log). | `text` |
| `--no-progress` | | Keine Statuszeile nach jedem KI-Aufruf (im Profil `"progress": false`). | aus |
| `--lang de\|en\|auto` | `--sprache` | Sprache der Terminal-Ausgaben, der Hilfe, der Fehlercodes und der Berichte in `.done`/`AUDIT.md`; mit `en` antworten auch die Modelle auf Englisch (Formatmarken wie `VERDICT:` bleiben). `auto` folgt der Locale (`LANG`). Auch `CLAUDEGRAVITY_LANG` oder `"lang"` im Profil. Siehe [Sprache der Ausgabe](#sprache-der-ausgabe). | `de` |
| `--no-guide` | | Hinweis beim ersten Lauf ohne Profil nicht zeigen (im Profil `"guide": false`). | aus |
| `--print-effective-config` | `--config` | Wirksame Einstellungen mit Quelle (Kommandozeile, Session, Umgebung, Profil, Standard) anzeigen und beenden. Siehe [Vorrang der Einstellungen](#vorrang-der-einstellungen). | aus |
| `--builder-fresh` | `--bauer-neu` | Bauleiter jede Runde in neuer Sitzung starten. Ohne das Flag setzen `claude` und `codex` ihre Sitzung fort und bekommen nur Rückmeldung und nächsten Schritt. Siehe [Bau-Loop](bau-loop.md#bauleiter-sitzung-fortsetzen). | aus |
| `--etappen <modus>` | `--stages` | `auto`, `an`, `aus`. Der Architekt schneidet den Plan in Etappen, der Bauleiter setzt sie einzeln um, der Loop prüft jede mit `--proof`. `auto` schaltet den Modus für Bauleiter ohne eigenen Dateizugriff ein (Ollama, LM Studio, Endpunkte). Siehe [Bau-Loop](bau-loop.md#etappen-modus). | `auto` |
| `--repo-map <modus>` | `--repo-karte` | `auto`, `an`, `aus`. Legt eine Repo-Karte (Pfade mit Klassen und Funktionen, nach Bezug zur Aufgabe sortiert, höchstens 6 000 Zeichen) in den Prompt. `auto` nur für Rollen ohne eigenen Dateizugriff (Ollama, LM Studio, Endpunkte), `an` für alle Rollen. Siehe [Bau-Loop](bau-loop.md#repo-karte). | `auto` |
| `--plan-auto` | `--approve-plan` | Plan ohne Freigabe-Menü übernehmen, sobald der Prüfstatiker `APPROVED` meldet. Endet das Review am Rundenlimit nur noch mit MITTEL- oder NIEDRIG-Befunden, wird ebenfalls gebaut, und der Bauleiter bekommt diese Befunde als Hinweise. Bei einem offenen HOCH-Befund, `BLOCKED` oder ohne lesbares Urteil wird nicht gebaut. Für Läufe ohne Terminal. | aus |

## Sprache der Ausgabe

Der Loop spricht Deutsch, solange nichts anderes eingestellt ist. Für Englisch:

```bash
claudegravity --lang en "Fix the median bug"     # einmalig
export CLAUDEGRAVITY_LANG=en                     # für die Shell
claudegravity --lang auto --help                 # nach Locale: de_* → Deutsch, sonst Englisch
```

Übersetzt werden Statuszeilen, Menüs und Rückfragen, `--help`/`--help-all`, Fehlercodes samt Doku-Link (`docs/en/…`) und die Berichte, die der Loop in `.done` und `AUDIT.md` schreibt. Die Modelle bekommen mit `en` den Hinweis, Plan, Befunde und Zusammenfassungen auf Englisch zu schreiben; Formatmarken wie `VERDICT:`, `## Etappen` und `filepath:` bleiben, weil der Loop sie liest. Die Arbeitsanweisungen an die Modelle selbst bleiben deutsch, ebenso Dateinamen wie `PLAN_v1.md` und die Zeilen in `LOG.md`.

Neue Meldungen im Code bekommen ihren englischen Text in `claudegravity/i18n.py`; `tests/test_i18n.py` schlägt fehl, wenn eine deutsche Meldung keinen hat.

## Rollen

| Flag | Aliase | Beschreibung |
| :--- | :--- | :--- |
| `--architekt <key>` | `--planner` | Backend für Phase 1. |
| `--pruefstatiker <key>` | `--reviewer` | Backend für Phase 2. |
| `--bauer <key>` | `--builder` | Backend für Phase 3 (Standard: wie Architekt). |
| `--kandidaten <liste>` | `--candidates` | Best-of-N: mehrere Bauleiter parallel, z. B. `claude,codex` oder `codex,ollama=qwen3-coder:30b`; siehe [Kandidaten-Modus](bau-loop.md#kandidaten-modus-best-of-n). |

Gültige Schlüssel: `claude`, `agy`, `gemini`, `codex`, `copilot`, `ollama`, `ollama-cli`, `lmstudio`, `endpoint`, `architekt_ep`, `pruefstatiker_ep`, `bauer_ep` – sofern erkannt. Ein nicht erkannter Schlüssel fällt stillschweigend auf die Standardwahl zurück. Details: [Backends](backends.md).

## Abnahme & Prüfbefehl

| Flag | Aliase | Beschreibung | Standard |
| :--- | :--- | :--- | :--- |
| `--proof "<befehl>"` | `--pruefbefehl` | Befehl, den ClaudeGravity nach jeder Bau-Runde selbst ausführt (ohne Shell). Rot: `.done` wird zurückgewiesen und die Ausgabe geht an den Bauleiter. | – |
| `--abnahme <key>` | `--inspector` | Backend für die Abnahme des fertigen Codes. Nie der Bauleiter selbst. | Prüfstatiker |
| `--abnahme-model <name>` | `--inspector-model` | Modell für die Abnahme. | – |
| `--abnahme-effort <stufe>` | `--inspector-effort` | Effort für die Abnahme. | – |
| `--max-inspections <n>` | | Abnahme-Runden pro Lauf; danach bleibt die Aufgabe offen (`phase = inspection_open`). | `2` |
| `--test-guard warn\|strict\|off` | `--testwaechter` | Geschönte Tests erkennen (gelöscht, Skip/Only, weniger Prüfungen); siehe [Testwächter](bau-loop.md#testwächter). | `warn` |
| `--no-inspect` | `--ohne-abnahme` | Abnahme auslassen (wird in `LOG.md` vermerkt). | an |

## Modelle

| Flag | Aliase | Beschreibung |
| :--- | :--- | :--- |
| `--architekt-model <name>` | `--planner-model` | z. B. `sonnet`, `opus`, `gemini-4-argon` |
| `--pruefstatiker-model <name>` | `--reviewer-model` | z. B. `gemini-4-argon`, `sonnet` |
| `--bauer-model <name>` | `--builder-model` | z. B. `haiku`, `gemini-3.8-flash`, `qwen2.5-coder:32b` |

Der Modellname wird als `--model <name>` an die CLI bzw. als `model` an den Endpunkt übergeben.

Ist eine Rolle mit `ollama` oder `ollama-cli` besetzt und fehlt ihr Modell, wählt ClaudeGravity eins aus den installierten Modellen (`/api/tags`): für den Bauleiter ein Code-Modell (`qwen3-coder`, `qwen2.5-coder`, `devstral`, …), für Prüfstatiker und Abnahme ein Denk-Modell (`gpt-oss`, `qwen3`, `deepseek-r1`, …), jeweils das größte bis 25 GB. Prüfstatiker und Abnahme bekommen nie dasselbe Modell wie der Bauleiter, Architekt und Prüfstatiker nie dasselbe untereinander. Die Wahl steht im Terminal; ein ausdrückliches `--…-model` hat immer Vorrang.

## Reasoning-Effort

Werte: `low`, `medium`, `high`, `xhigh`, `max`.

| Flag | Aliase | Gilt für |
| :--- | :--- | :--- |
| `--effort` | | Architekt und Prüfstatiker (wenn nicht einzeln gesetzt) |
| `--architekt-effort` | `--planner-effort` | Architekt |
| `--pruefstatiker-effort` | `--reviewer-effort` | Prüfstatiker |
| `--bauer-effort` | `--builder-effort` | Bauleiter |

Effort wird an `agy` (`--effort`) und `codex` (`-c model_reasoning_effort`, `max` wird zu `xhigh`) weitergegeben.

## Endpunkte

| Flag | Aliase | Beschreibung |
| :--- | :--- | :--- |
| `--endpoint <url>` | `--api-base` | OpenAI-kompatibler Endpunkt, verfügbar als Schlüssel `endpoint`. |
| `--api-key <key>` | | Bearer-Token für den Endpunkt (besser per Umgebungsvariable, siehe [Backends](backends.md)). |
| `--architekt-endpoint <url>` | | Eigener Endpunkt, verfügbar als `architekt_ep`. |
| `--pruefstatiker-endpoint <url>` | | Eigener Endpunkt, verfügbar als `pruefstatiker_ep`. |
| `--bauer-endpoint <url>` | | Eigener Endpunkt, verfügbar als `bauer_ep`. |
| `--timeout <sek>` | | Sekunden pro Runde für Endpunkte. Standard: 900 im Heimnetz, 180 sonst. Auch `CLAUDEGRAVITY_TIMEOUT`. |

## Git-Workspace

| Flag | Aliase | Beschreibung | Standard |
| :--- | :--- | :--- | :--- |
| `--no-worktree` | `--no-workspace` | Keinen eigenen Git-Worktree pro Session anlegen, sondern direkt im Projektordner bauen. | Worktree an (nur in Git-Repositories) |
| `--merge` | `--worktree-merge` | Session-Branch nach erfolgreichem Abschluss (`.done`, Abnahme bestanden) in den Ausgangs-Branch mergen. | aus |

Details: [Sessions & Dateien](sessions-und-dateien.md#git-workspace-pro-session).

## GitHub

| Flag | Aliase | Beschreibung | Standard |
| :--- | :--- | :--- | :--- |
| `--from-issue <nr\|url>` | `--issue`, `--aus-issue` | GitHub-Issue als Aufgabe: `12`, `#12`, `owner/repo#12` oder die URL. Liest Titel, Text, Labels und die letzten Kommentare über `gh` oder die REST-API (`GH_TOKEN`). Ein Aufgabentext daneben gilt als Zusatz. Nicht über Umgebung oder Profil setzbar. | – |
| `--open-pr` | `--pr-oeffnen` | Nach erfolgreichem Abschluss den Session-Branch pushen und einen Pull Request öffnen, bei `--from-issue` mit `Closes #n`. Merged nie, auch nicht mit `--merge`. Nicht aus dem Projekt-Profil. | aus |
| `--pr-draft` | `--pr-entwurf` | Pull Request als Entwurf öffnen (schließt `--open-pr` ein). | aus |

Details und GitHub Action: [GitHub](github.md).

## Sandbox

| Flag | Aliase | Beschreibung | Standard |
| :--- | :--- | :--- | :--- |
| `--sandbox an\|docker\|podman\|aus` | | Prüfbefehl und CLI-Bauleiter in einem Container: nur Arbeitsordner (und beim Bauleiter Session-Ordner und eigene Anmeldedaten), deine Benutzer-ID, keine Capabilities. `an` nimmt Docker, sonst Podman. Unter Windows nur der Prüfbefehl. Nicht aus dem Projekt-Profil. | `aus` |
| `--sandbox-image <image>` | | Image für die Sandbox. Für CLI-Bauleiter eines mit der CLI: `docker build -t claudegravity-sandbox sandbox/`. | `python:3.12-slim` |
| `--sandbox-net` | | Prüfbefehl in der Sandbox mit Netz (der CLI-Bauleiter hat immer Netz). | aus |

Details: [Sandbox](sandbox.md).

## Datenschutz

| Flag | Beschreibung |
| :--- | :--- |
| `--no-shield` | Datenschutzschild ausschalten (auch `CLAUDEGRAVITY_SHIELD=off`). Siehe [Sessions & Dateien](sessions-und-dateien.md#datenschutzschild). |

## Vorrang der Einstellungen

Jede Einstellung kommt aus der ersten Quelle, die sie setzt:

1. **Kommandozeile:** Flag in diesem Aufruf
2. **Session:** gespeicherter Wert aus `state.json` (nur bei `-c`)
3. **Vorlage:** Werte der gewählten [Aufgaben-Vorlage](#aufgaben-vorlagen)
4. **Umgebung:** `CLAUDEGRAVITY_<EINSTELLUNG>`, z. B. `CLAUDEGRAVITY_STRATEGY=hybrid` oder `CLAUDEGRAVITY_BUILDER_MODEL=qwen2.5-coder:7b`
5. **Projekt-Profil:** `<projekt>/.dual-loop/profile.json` (git-ignoriert)
6. **Globales Profil:** `~/.config/claudegravity/profile.json` (`$XDG_CONFIG_HOME` wird beachtet, unter Windows `%APPDATA%\claudegravity\profile.json`, abweichender Ordner mit `CLAUDEGRAVITY_CONFIG_DIR`)
7. **Standard:** Wert des Flags bzw. des gewählten Presets, danach der CLI-Default des Backends

Ein Profil ist ein flaches JSON-Objekt. Die Schlüssel sind die Flag-Namen ohne `--`, mit `-` oder `_` geschrieben, auch die deutschen Aliase:

```json
{
  "_kommentar": "Schlüssel mit _ oder $ am Anfang werden übersprungen",
  "strategy": "hybrid",
  "proof": "python3 -m unittest discover -s tests",
  "bauer-model": "qwen2.5-coder:7b",
  "etappen": "auto",
  "worktree": false
}
```

Ja/Nein-Flags nehmen `true`/`false` (in der Umgebung auch `1`, `ja`, `an`, `0`, `nein`, `aus`). Bei `--no-worktree` und `--no-inspect` heißt der Schlüssel `worktree` bzw. `inspect`. Unbekannte Schlüssel und ungültige Werte werden mit einer Warnung übersprungen.

Nicht aus Umgebung oder Profil kommen: Aufgabe, `--project`, `--resume`, `--info`, `--dry-run`, `--no-shield` (dafür gibt es `CLAUDEGRAVITY_SHIELD=off`) und `--api-key` (nur `CLAUDEGRAVITY_API_KEY`, nie in eine Datei). `yolo` wirkt nur aus der Umgebung oder dem globalen Profil, weil ein Bauleiter mit Schreibrechten in den Projektordner schreiben kann. Endpunkt-Bauleiter dürfen `.dual-loop/profile.json` gar nicht schreiben.

Woher jeder Wert kommt, zeigt:

```bash
claudegravity --print-effective-config -p ~/Projekte/rechnung
```

Setzen zwei Quellen dieselbe Einstellung verschieden, markiert die Ausgabe das als **Konflikt** und nennt den überschriebenen Wert. Beim normalen Start zeigt der Loop in einer Zeile, welche Werte aus Umgebung oder Profil kommen, und meldet Konflikte.

## Budget

```bash
claudegravity "Neue Exportfunktion" --budget-max 400k --budget-warn 250k --budget-roles "abnahme=0.50usd"
```

Nach jedem KI-Aufruf vergleicht der Loop den Verbrauch der Session mit den Grenzen. Eine weiche Grenze erzeugt einmal eine 💶-Warnung (auch in `LOG.md`); ohne `--budget-warn` warnt er bei 80 % jeder harten Grenze. Erreicht der Verbrauch eine harte Grenze, endet der Lauf nach diesem Aufruf (ein laufender Aufruf wird nicht abgebrochen), der Stand wird gesichert und `AUDIT.md` nennt im Kennzahlen-Block den **Abbruchgrund** (Fehlercode CG-1404). Weiter geht es mit `claudegravity -c --budget-max <höherer wert>`; das Budget gilt für die ganze Session, auch über Fortsetzungen.

* **Tokens** zählt der Loop bei allen Anbietern (bei CLIs ohne Verbrauchsangabe geschätzt).
* **USD** zählt nur, was Anbieter melden (Claude Code, API-Endpunkte mit `usage.cost`). Abo-CLIs und lokale Modelle verbrauchen damit kein USD-Budget.
* Wie alle Einstellungen gehen `budget_max`, `budget_warn` und `budget_roles` auch ins Profil oder in eine Vorlage.
* Einen passenden Wert zeigt `--dry-run`: Die Kostenschätzung vorab nennt den ungünstigsten Fall früherer Sessions und warnt, wenn `--budget-max` dafür nicht reicht ([Schnellstart](schnellstart.md#2-erst-ansehen-dann-starten-trockenlauf)).

## Aufgaben-Vorlagen

`--template <name>` (`--vorlage`) setzt mehrere Einstellungen passend zur Art der Aufgabe und hängt dem Aufgabentext eine kurze Arbeitsanweisung an. Einzelne Flags überschreiben die Vorlage.

| Vorlage | Einstellungen | Pflicht | Anweisung an die Modelle |
| :--- | :--- | :--- | :--- |
| `bugfix` | `strategy: eco`, `etappen: aus`, `max_iterations: 5` | `--proof` | Kleinste Änderung, zuerst ein Test, der den Fehler zeigt. |
| `feature` | `strategy: balanced`, `etappen: auto` | – | Vollständig umsetzen, mit Tests und kurzer Doku. |
| `refactor` | `reviewer_effort: high`, `inspect: true`, `max_rounds: 3` | `--proof` | Struktur ändern, Verhalten nicht; bestehende Tests bleiben grün. |

Fehlt ein Pflicht-Prüfbefehl, rät der Loop ihn aus dem Projekt (wie `claudegravity init`); findet er keinen, bricht er mit Hinweis ab.

Vorlagen ändern oder eigene anlegen geht im globalen oder im Projekt-Profil unter `templates`. Projekt-Einträge ergänzen die globalen, die globalen die eingebauten:

```json
{
  "template": "feature",
  "templates": {
    "bugfix": { "max_iterations": 8 },
    "typo3": {
      "strategy": "hybrid",
      "proof": "vendor/bin/phpunit",
      "requires": ["proof"],
      "hint": "Halte dich an die TYPO3-Coding-Guidelines und ergänze Functional Tests."
    }
  }
}
```

`template` im Profil wählt eine Standard-Vorlage für jeden Lauf. In einer Vorlage gelten dieselben Schlüssel wie im Profil, dazu `hint` (Anweisung) und `requires` (Pflicht-Einstellungen). `yolo` ist in Vorlagen nicht erlaubt. Welche Vorlage mit welchen Werten wirkt, zeigt `--print-effective-config`.

## Beispiele

```bash
# Alles getrennt einstellen
claudegravity "Sicherheits-Audit und Auth-Refactoring" \
  --architekt claude --architekt-model opus \
  --pruefstatiker agy --pruefstatiker-model gemini-4-argon --pruefstatiker-effort max \
  --bauer-endpoint http://192.168.1.50:11434/v1 --bauer bauer_ep --bauer-model qwen2.5-coder:7b

# Lange Aufgabe: mehr Runden, ohne Pause, Fallback bei Limit
claudegravity "Großes Refactoring" -m 25 -d 0 --auto-switch --yolo

# Anderes Projekt fortsetzen
claudegravity -c -p ~/Projekte/kundenportal
```
