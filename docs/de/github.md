# GitHub: vom Issue zum Pull Request

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/github.md)

`--from-issue` nimmt ein GitHub-Issue als Aufgabe, `--open-pr` öffnet nach erfolgreicher Abnahme einen Pull Request mit `Closes #12`. Als GitHub Action läuft das ohne deinen Rechner: Label `claudegravity` setzen oder `/claudegravity` kommentieren, und der Loop plant, prüft, baut und öffnet den Pull Request.

## Im Terminal

```bash
claudegravity --from-issue 12 --open-pr --proof "python -m pytest -q"
claudegravity --from-issue gb-web-de/claudegravity-loop#12 --pr-draft
claudegravity "Bitte ohne neue Abhängigkeiten" --from-issue https://github.com/o/r/issues/12 --open-pr
```

* **Angabe des Issues:** `12`, `#12`, `owner/repo#12` oder die URL. Ohne Repository nimmt der Loop `origin` des Projekts (in GitHub Actions sonst `GITHUB_REPOSITORY`).
* **Was der Loop liest:** Titel, Text, Labels und die letzten 10 Kommentare (je bis 1 500 Zeichen), zusammen höchstens 12 000 Zeichen. Dazu kommt ein Hinweis an die Modelle, dass der Text von Dritten stammt und Anweisungen darin, Zugangsdaten auszulesen oder etwas zu veröffentlichen, nicht befolgt werden. Ein eigener Aufgabentext auf der Kommandozeile steht danach als „Zusätzlicher Auftrag“.
* **Sitzung und Branch:** Die Sitzung heißt `<zeit>_issue-12_<titel>`, gebaut wird wie immer auf `loop/<sitzung>`.
* **Zugriff:** zuerst die GitHub CLI `gh` mit ihrer Anmeldung (`gh auth login`), sonst die REST-API mit `GH_TOKEN` oder `GITHUB_TOKEN`. Für GitHub Enterprise `GITHUB_API_URL` setzen. `CLAUDEGRAVITY_GH=off` nimmt nur die API, `CLAUDEGRAVITY_GH=/pfad/zu/gh` eine bestimmte `gh`. Der Token wird nie gespeichert, geloggt oder an ein Modell gegeben.
* `--dry-run` liest das Issue schon und zeigt den Befehl mit `--from-issue`.

## Pull Request

Mit `--open-pr` geht es nach erfolgreichem Abschluss (Prüfbefehl grün, Abnahme `APPROVED`) so weiter:

1. Der Workspace wird wie immer auf `loop/<sitzung>` committet. Gemerged wird nicht, auch nicht mit `--merge`.
2. `git push -u origin loop/<sitzung>`.
3. Pull Request gegen den Ausgangs-Branch (stand das Projekt auf einem losgelösten HEAD, gegen den Standard-Branch). Titel ist der Issue-Titel, der Text enthält `Closes #12`, die vier Rollen mit Modell, den Prüfbefehl, die Kennzahlen und den freigegebenen Plan zum Aufklappen.
4. Die URL steht danach in `state.json` (`pull_request`), `LOG.md`, `events.jsonl` (Ereignis `pull_request`) und `.done`.

* `--pr-draft` öffnet den Pull Request als Entwurf.
* Gibt es für den Branch schon einen Pull Request (z. B. nach `claudegravity -c`), nimmt der Loop dessen URL.
* Keinen Pull Request gibt es ohne Git-Workspace (`--no-worktree` oder kein Git), ohne neue Commits und wenn der Lauf nicht abgeschlossen wurde. Scheitern Push oder Pull Request, meldet der Loop [CG-1602](fehlerbehebung.md#cg-1602); der Branch bleibt lokal erhalten.
* Im [Kandidaten-Modus](bau-loop.md#kandidaten-modus-best-of-n) bekommt der Branch des Gewinners den Pull Request.
* `open_pr` und `pr_draft` gelten nur von der Kommandozeile, aus der Umgebung (`CLAUDEGRAVITY_OPEN_PR=1`) oder aus dem globalen Profil, nicht aus dem Projekt-Profil: Ein fremdes Repository soll nicht selbst bestimmen, dass etwas veröffentlicht wird.
* Der MCP-Server kennt dieselben Schalter als `issue` und `open_pr` ([MCP-Server](mcp-server.md)).

## GitHub Action

Das Repository ist selbst eine Action. Dieser Workflow startet den Loop, wenn jemand mit Schreibrechten das Label `claudegravity` setzt oder ein Mitglied `/claudegravity` kommentiert:

```yaml
# .github/workflows/claudegravity.yml
name: claudegravity
on:
  issues:
    types: [labeled]
  issue_comment:
    types: [created]

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  loop:
    if: >-
      (github.event_name == 'issues' && github.event.label.name == 'claudegravity') ||
      (github.event_name == 'issue_comment' && !github.event.issue.pull_request &&
       startsWith(github.event.comment.body, '/claudegravity') &&
       contains(fromJSON('["OWNER", "MEMBER", "COLLABORATOR"]'), github.event.comment.author_association))
    runs-on: ubuntu-latest
    timeout-minutes: 60
    concurrency:
      group: claudegravity-${{ github.event.issue.number }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      # Abhängigkeiten des Projekts für den Prüfbefehl, z. B.:
      # - run: pip install -r requirements.txt
      - uses: gb-web-de/claudegravity-loop@main
        with:
          proof: python -m pytest -q
          args: --architekt claude --pruefstatiker gemini --abnahme gemini --budget-max 2m
        env:
          GH_TOKEN: ${{ github.token }}
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

Einrichtung:

1. **Secrets** unter *Settings → Secrets and variables → Actions*: `CLAUDE_CODE_OAUTH_TOKEN` (mit `claude setup-token` aus deinem Claude-Abo erzeugen) und `GEMINI_API_KEY` für die Gemini CLI als Prüfstatiker und Abnahme. Andere CLIs installierst du über die Eingabe `cli` und meldest sie nach ihrer eigenen Doku an. Die Zugangsdaten gehören nur in Secrets, nie ins Repository.
2. **Pull Requests durch Actions erlauben:** *Settings → Actions → General → Workflow permissions* → „Allow GitHub Actions to create and approve pull requests“.
3. **Label** `claudegravity` anlegen.

Eingaben der Action:

| Eingabe | Standard | Bedeutung |
| :--- | :--- | :--- |
| `issue` | Issue des Ereignisses | Nummer, `owner/repo#12` oder URL |
| `args` | – | Weitere Optionen für `claudegravity` (Rollen, Strategie, Budget …), ohne Shell zerlegt |
| `proof` | – | Prüfbefehl, den der Loop selbst ausführt |
| `draft` | `false` | Pull Request als Entwurf |
| `comment` | `true` | Issue mit dem Ergebnis kommentieren (Link zum PR oder Grund und Link zum Lauf) |
| `lang` | `de` | Sprache der Ausgaben, des Pull Requests und des Kommentars (`de`, `en`) |
| `cli` | `@anthropic-ai/claude-code @google/gemini-cli` | npm-Pakete der KI-CLIs; leer installiert keine |
| `python-version` | `3.12` | Python für den Loop |
| `working-directory` | `.` | Projektordner im Checkout |

Ausgaben: `pull-request` (URL), `success` (`true`/`false`) und `session`. Die Zusammenfassung des Jobs zeigt Ergebnis, Grund, Pull Request und den Bericht aus `.done` bzw. `AUDIT.md`.

Die Action startet `claudegravity --from-issue … --open-pr --plan-auto --yolo`: Gebaut wird nur ein Plan, den der Prüfstatiker genehmigt hat, und der Bauleiter hat im Runner volle Rechte.

### Worauf du achten musst

* **Wer starten darf:** Der Bauleiter läuft mit `--yolo` und sieht im Runner die Umgebung samt Secrets. Den Workflow deshalb nur von Personen auslösen lassen, denen du vertraust: Labels setzen kann nur, wer mindestens Triage-Rechte hat; der Kommentar-Start prüft `author_association`. Nie auf `issues: opened` in öffentlichen Repositories reagieren, sonst bestimmt jeder Fremde die Aufgabe. Mehr in [Sicherheit](sicherheit.md) (B15).
* **CI auf dem Pull Request:** Pull Requests und Pushes mit dem `GITHUB_TOKEN` starten keine weiteren Workflows (Regel von GitHub). Soll deine CI auf dem Pull Request laufen, setze `GH_TOKEN` auf den Token einer GitHub App oder ein Fine-grained PAT mit *Contents* und *Pull requests: Read and write*.
* **Kosten:** `timeout-minutes` und `--budget-max` in `args` begrenzen den Lauf.
* Lokal ausprobieren ohne Lauf: `CG_ISSUE=12 CG_ARGS="--dry-run" python3 tools/github_action.py`.
