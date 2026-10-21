# Sessions, Dateien & Projektkontext

[← Zurück zur Übersicht](../README.md) · [Dokumentations-Index](README.md)

## Was ClaudeGravity im Zielprojekt anlegt

```text
<projekt>/
├── .dual-loop/                      # git-ignoriert, enthält nur sessions/
│   └── sessions/
│       └── 20261017_153000_Baue_ein_Kundenportal/
│           ├── state.json           # Fortschritt, Rollen, Modelle, Metriken
│           ├── PLAN_v1.md           # erster Entwurf des Architekten
│           ├── REVIEW_round1.md     # Urteil des Prüfstatikers
│           ├── PLAN_v2.md           # überarbeitete Version
│           ├── PLAN_v3_manual.md    # im Editor geänderte Version
│           ├── INSPECTION_round1.md # Urteil der Abnahme über den fertigen Code
│           ├── LOG.md               # Verlauf von Plan, Review, Abnahme, Limit-Wechseln
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

## Projektkontext: `CLAUDE.md` & `knowledge/`

Beim Planen liest ClaudeGravity aus dem Zielprojekt:

1. **Alle** vorhandenen Regeldateien aus `CLAUDE.md`, `AGENTS.md`, `.claude/rules.md` (vollständig; identische Inhalte nur einmal).
2. Aus `knowledge/` die Dateien, deren Name oder Anfang ein Wort der Aufgabe (ab 4 Buchstaben) enthält, mit den ersten 500 Zeichen. Die übrigen nur als Dateiname, damit der Architekt sie bei Bedarf selbst liest. Geheimnis-Dateien wie `.env` oder `*.key` werden übersprungen.

Dieser Kontext geht nur an den Architekten. So bleibt der Prompt klein.

## Datenschutzschild

Bevor ein Prompt an ein Cloud-Modell geht (Claude, Antigravity, Gemini, Codex, Copilot oder ein Endpunkt außerhalb des Heimnetzes), ersetzt ClaudeGravity darin gefundene Zugangsdaten durch `[GESCHWÄRZT: …]` und meldet das mit 🛡️. Erkannt werden private Schlüssel, API-Keys und Tokens (Anthropic, OpenAI, GitHub, Google, AWS, Slack, Stripe, JWT), Zuweisungen wie `PASSWORD=…` oder `token: …`, Passwörter in URLs, gültige IBANs und Kreditkartennummern. Prompts an Ollama, LM Studio und Server im Heimnetz bleiben unverändert.

Der Schild schützt nur den Prompt, den ClaudeGravity selbst verschickt. Liest eine CLI wie Claude Code im Bau-Loop selbst Dateien, gelten deren eigene Regeln. Ausschalten mit `--no-shield` oder `CLAUDEGRAVITY_SHIELD=off`.

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
