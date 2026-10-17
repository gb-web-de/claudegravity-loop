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
│           ├── LOG.md               # Verlauf von Plan & Review
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
| `phase` | `plan`, `review`, `build` oder `completed` |
| `user_approved`, `plan_approved` | Freigabe durch dich bzw. den Prüfstatiker |
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

Der Bericht wird auch geschrieben, wenn das Rundenlimit ohne Fertigmeldung erreicht wird. Rollen ohne API-Kosten (Abo, lokal) erscheinen als „Abo-Inklusivkontingent“. Bei CLIs ohne Verbrauchsangabe sind die Token-Zahlen grob geschätzt (Zeichen / 4).

## Projektkontext: `CLAUDE.md` & `knowledge/`

Beim Planen liest ClaudeGravity aus dem Zielprojekt:

1. Die **erste** gefundene Regeldatei aus `CLAUDE.md`, `AGENTS.md`, `.claude/rules.md` (vollständig).
2. Alle Dateien in `knowledge/` (jeweils die ersten 500 Zeichen).

Dieser Kontext geht nur an den Architekten. So bleibt der Prompt klein.

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
