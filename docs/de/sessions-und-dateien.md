# Sessions, Dateien & Projektkontext

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/sessions-und-dateien.md)

## Was ClaudeGravity im Zielprojekt anlegt

```text
<projekt>/
├── .dual-loop/                      # git-ignoriert
│   ├── profile.json                 # optionales Projekt-Profil (siehe CLI-Referenz)
│   └── sessions/
│       └── 20261017_153000_Baue_ein_Kundenportal/
│           ├── state.json           # Fortschritt, Rollen, Modelle, Metriken
│           ├── PLAN_v1.md           # erster Entwurf des Architekten
│           ├── REVIEW_round1.md     # Urteil des Prüfstatikers
│           ├── PLAN_v2.md           # überarbeitete Version
│           ├── PLAN_v3_manual.md    # im Editor geänderte Version
│           ├── INSPECTION_round1.md # Urteil der Abnahme über den fertigen Code
│           ├── LOG.md               # Verlauf von Plan, Review, Abnahme, Limit-Wechseln, Neuversuchen
│           ├── audit-events.jsonl   # Sicherheitsereignisse (siehe Rechte-Audit)
│           ├── workspace/           # Git-Worktree der Session (Branch loop/<session>)
│           ├── AUDIT.md             # Audit-Bericht, wenn der Lauf ohne Fertigmeldung endet
│           └── .done                # Fertigmeldung + Audit-Bericht
└── logs/
    └── loop_<session>.log           # Ausgabe des Bauleiters pro Runde
```

* Der Ordnername ist `<Zeitstempel>_<erste 30 Zeichen der Aufgabe>`.
* Jede Aufgabe bekommt einen eigenen Ordner. Pläne, Reviews und Logs verschiedener Aufgaben vermischen sich nicht.
* Die neueste Planversion (`PLAN_v*.md`) ist der Plan, mit dem der Bauleiter arbeitet.
* Ältere Dateien `PLAN.md`, `REVIEW.md` und `PLAN-REVIEW-LOG.md` direkt in `.dual-loop/` stammen aus früheren Versionen und werden beim Start gelöscht.

Füge `.dual-loop/`, `logs/` und `.done` in die `.gitignore` deines Projekts ein, wenn sie nicht ins Repository sollen.

## Git-Workspace pro Session

Ist das Projekt ein Git-Repository, baut der Bauleiter nicht direkt im Projektordner, sondern in einem eigenen Worktree unter `<session>/workspace` auf dem Branch `loop/<session-id>`. Der Branch zweigt vom aktuellen `HEAD` ab. So bleibt dein Arbeitsverzeichnis unberührt.

* Nach erfolgreichem Abschluss committet ClaudeGravity offene Änderungen auf den Session-Branch und entfernt den Worktree. Der Branch bleibt erhalten, du kannst ihn prüfen und selbst mergen.
* Mit `--merge` wird der Branch nach `.done` und bestandener Abnahme automatisch in den Ausgangs-Branch gemergt, sofern das Projekt noch auf diesem Branch steht.
* Verweigert die Abnahme die Fertigmeldung, bleibt der Worktree bestehen und `claudegravity -c` macht dort weiter.
* Mit `--no-worktree` arbeitet der Bauleiter direkt im Projektordner. Ohne Git gibt es keinen Worktree.

## `state.json`

Hält alles, was zum Fortsetzen nötig ist, u. a.:

| Feld | Inhalt |
| :--- | :--- |
| `task` | Ursprüngliche Aufgabe |
| `phase` | `plan`, `review`, `build`, `inspection_open` oder `completed` |
| `user_approved`, `plan_approved` | Freigabe durch dich bzw. den Prüfstatiker |
| `approved_plan_sha256`, `approved_plan_file` | Inhalt, für den die Freigabe gilt |
| `build_base`, `build_plan_sha256` | Basis-Commit und Plan bei Baubeginn (für den Diff der Abnahme) |
| `proof`, `inspector_binary`, `inspector_model`, `inspection_rounds`, `pending_feedback` | Prüfbefehl, Abnahme und offene Rückmeldung an den Bauleiter |
| `last_iteration`, `max_iterations` | Fortschritt im Bau-Loop |
| `planner_model`, `reviewer_model`, `builder_model`, `*_effort` | gewählte Modelle und Effort |
| `swap_roles`, `yolo_enabled`, `auto_switch`, `ask_mode`, `strategy` | aktive Modi |
| `metrics` | gesammelte Token- und Kostenzahlen |

`state.json` wird atomar geschrieben (erst `state.json.tmp`, dann umbenannt); der vorige Stand bleibt als `state.json.bak`. Ist `state.json` nach einem Absturz beschädigt, setzt `-c` mit dem Stand aus `state.json.bak` fort und wiederholt höchstens die letzte Runde. Plan und Review werden beim Fortsetzen nie neu erstellt, wenn der Plan schon freigegeben war; lag die Fertigmeldung schon vor, geht es direkt zur Abnahme.

## Fortsetzen (`-c` / `--resume`)

```bash
cd ~/Projekte/mein-projekt
claudegravity -c
```

ClaudeGravity nimmt die neueste Sitzung, lädt Aufgabe, Plan und Einstellungen und macht dort weiter:

* War der Plan noch nicht freigegeben, geht es zurück in Review und Freigabe-Menü.
* War er freigegeben, startet der Bau-Loop bei `last_iteration + 1`.
* Wurde `--max-iterations` erreicht, hängt `claudegravity -c -m 20` weitere Runden an (die Zählung läuft bis zum neuen Maximum weiter).

Rufst du `claudegravity` **ohne Aufgabe** auf und die letzte Sitzung ist nicht abgeschlossen, fragt ClaudeGravity, ob sie fortgesetzt werden soll.

## Fertigmeldung & Audit-Bericht (`.done`)

Der Bauleiter legt `.dual-loop/sessions/<session>/.done` an, wenn alles umgesetzt und getestet ist. ClaudeGravity ergänzt darin einen Bericht:

```markdown
### 📊 Ressourcen-Verbrauch & Kosten (ClaudeGravity Audit)
* **Gesamt-Tokens:** 182,340 Tokens
  * **Input-Tokens:** 150,120
  * **Output-Tokens:** 32,220
* **Entstandene Kosten (geschätzt):** ~$0.8421 USD
* **Aufschlüsselung nach Rolle, Agent, Modell & Effort:**
  * **🏗️ Architekt (Planung & Entwurf) (Claude Code)**
    * **Modell:** `claude-sonnet-…`
    ...
```

Endet der Lauf ohne Fertigmeldung (Rundenlimit), steht der Bericht in `AUDIT.md` statt in `.done`, damit die Aufgabe beim Fortsetzen nicht als fertig gilt. Rollen ohne API-Kosten (Abo, lokal) erscheinen als „Abo-Inklusivkontingent“. Bei CLIs ohne Verbrauchsangabe sind die Token-Zahlen grob geschätzt (Zeichen / 4).

### Kennzahlen (KPI)

Vor dem Audit-Bericht steht ein Kennzahlen-Block im festen Format, damit sich Sessions vergleichen lassen:

```markdown
### 📈 Kennzahlen (ClaudeGravity KPI v1)
* **Ergebnis:** erfolgreich · Strategie `hybrid` · Dauer 12 min 30 s
* **Kosten je Aufgabe:** 0.1900 USD · **davon Abnahme:** 0.0900 USD (gemeldet von: Claude Code)
* **Runden:** Plan-Review 2 · Bau 3 (bis Erfolg: 3) · Etappen 2 · Abnahme 2
* **Nacharbeit:** 2 von 3 Bau-Runden (Quote 67 %); Prüfbefehl rot 1/2, Abnahme verweigert 1
```

Darunter folgen dieselben Werte als eine JSON-Zeile in einem ` ```json `-Block (`version`, `success`, `duration_s`, `build_rounds`, `rework_rate`, `cost_usd_task`, `cost_usd_by_role`, `tokens_by_role` usw.), die sich per Skript auswerten lässt.

* **Kosten** stammen nur aus Angaben der Anbieter (Claude Code, API-Endpunkte mit `usage.cost` wie OpenRouter). Abo-CLIs und lokale Modelle melden keine Kosten; es gibt keine Preistabelle, die Tokens je Rolle stehen zum Nachrechnen dabei. Einheit ist USD, wie die Anbieter sie melden.
* **Nacharbeit** zählt Bau-Runden, die auf einen roten Prüfbefehl oder eine verweigerte Abnahme folgten, höchstens alle Bau-Runden nach der ersten.
* **Bau-Runden bis Erfolg** gibt es nur bei abgeschlossenen Sessions.
* **Abbruchgrund** (`abort_reason`) steht nur bei offenen Sessions: Rundenlimit, Abnahme-Limit, Etappe nicht grün, Budget, Beenden im Limit-Menü oder Strg+C. Beim Fortsetzen mit `-c` wird er gelöscht.

## Projektkontext: `CLAUDE.md` & `knowledge/`

Beim Planen liest ClaudeGravity aus dem Zielprojekt:

1. **Alle** vorhandenen Regeldateien aus `CLAUDE.md`, `AGENTS.md`, `.claude/rules.md` (vollständig; identische Inhalte nur einmal).
2. Aus `knowledge/` die Dateien, deren Name oder Anfang ein Wort der Aufgabe (ab 4 Buchstaben) enthält, mit den ersten 500 Zeichen. Die übrigen nur als Dateiname, damit der Architekt sie bei Bedarf selbst liest. Geheimnis-Dateien wie `.env` oder `*.key` werden übersprungen.

Dieser Kontext geht nur an den Architekten. So bleibt der Prompt klein.

## Datenschutzschild

Bevor ein Prompt an ein Cloud-Modell geht (Claude, Antigravity, Gemini, Codex, Copilot oder ein Endpunkt außerhalb des Heimnetzes), ersetzt ClaudeGravity darin gefundene Zugangsdaten durch `[GESCHWÄRZT: …]` und meldet das mit 🛡️. Erkannt werden private Schlüssel, API-Keys und Tokens (Anthropic, OpenAI, GitHub, Google, AWS, Slack, Stripe, JWT), Zuweisungen wie `PASSWORD=…` oder `token: …`, Passwörter in URLs, gültige IBANs und Kreditkartennummern. Prompts an Ollama, LM Studio und Server im Heimnetz bleiben unverändert.

Der Schild schützt nur den Prompt, den ClaudeGravity selbst verschickt. Liest eine CLI wie Claude Code im Bau-Loop selbst Dateien, gelten deren eigene Regeln. Ausschalten mit `--no-shield` oder `CLAUDEGRAVITY_SHIELD=off`.

### Logs, Warnungen und sichere Umgebungsvariablen

Unabhängig vom Schild schwärzt ClaudeGravity dieselben Muster in `LOG.md`, `audit-events.jsonl` und den Bau-Logs unter `logs/`. Pläne, Reviews und Abnahmen im Session-Ordner bleiben unverändert, weil die nächsten Schritte sie wörtlich weiterverwenden; der Session-Ordner ist git-ignoriert.

Enthält die Aufgabe selbst Zugangsdaten, meldet der Loop das beim Start; bei ausgeschaltetem Schild mit dem Hinweis, an welche Cloud-Modelle sie im Klartext gehen. Enthält eine Modellantwort Zugangsdaten, gibt es eine Audit-Meldung (siehe unten).

Zugangsdaten gehören nicht in Aufgabe, Profil oder Repository, sondern in Umgebungsvariablen: `CLAUDEGRAVITY_API_KEY` für eigene Endpunkte, für dein Projekt dessen eigene Variablen (z. B. `.env`, das Endpunkt-Bauleiter nicht schreiben dürfen). In der Aufgabe reicht der Name der Variablen, etwa „lies den Schlüssel aus `STRIPE_KEY`“.

## Rechte-Audit

Architekt, Prüfstatiker und Abnahme laufen mit Lese-Flags (Claude: nur die Werkzeuge Read, Glob und Grep, Codex: `-s read-only`). Weil nicht jede CLI so ein Flag hat (Antigravity, Gemini, Copilot), prüft der Loop zusätzlich: Er vergleicht vor und nach jedem Aufruf einer lesenden Rolle den Git-Stand des Arbeitsordners. Ändert sich eine Datei, meldet er das mit 🛑 und hält es fest. Rückgängig macht er nichts, weil auch du gerade im Projekt gearbeitet haben könntest.

| Ereignis | Wann |
| :--- | :--- |
| Blockierter Schreibversuch | Ein Endpunkt-Bauleiter will außerhalb des Projekts, in `.git/`, in Geheimnis-Dateien oder in `.dual-loop/profile.json` schreiben. |
| Änderung durch lesende Rolle | Der Arbeitsordner hat sich während Plan, Review oder Abnahme geändert (nur in Git-Projekten). |
| Mögliche Zugangsdaten in Modellantwort | Eine Antwort enthält Muster wie API-Keys, Tokens oder Passwörter. |

Jedes Ereignis steht in `LOG.md` und als JSON-Zeile in `audit-events.jsonl` im Session-Ordner; die Anzahl je Art erscheint im Audit-Block der `.done`.

## Gespiegelte Projekte (`projects/`)

Im ClaudeGravity-Repository liegt der Ordner `projects/` für Projekte, die wie in der Claude-UI organisiert sind: jedes Unterprojekt mit eigener `CLAUDE.md` und optionalem `knowledge/`-Ordner. Beispiel:

```text
projects/demo/
├── CLAUDE.md
└── knowledge/
    └── api_guidelines.md
```

```bash
claudegravity "Ergänze eine Begrüßungsfunktion" -p projects/demo
```
