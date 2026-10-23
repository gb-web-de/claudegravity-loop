# CLI-Referenz (`claudegravity` / `loop.py`)

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/cli-referenz.md)

```text
claudegravity [AUFGABE] [OPTIONEN]
```

Alle deutschen und englischen Schreibweisen eines Flags sind gleichwertig (z. B. `--bauer` = `--builder`).

## Allgemein

| Flag | Aliase | Beschreibung | Standard |
| :--- | :--- | :--- | :--- |
| `AUFGABE` | *(Positionsargument)* | Die Programmieraufgabe in Anführungszeichen. Ohne Aufgabe wird eine unterbrochene Sitzung angeboten, sonst die Hilfe gezeigt. | – |
| `-p`, `--project` | | Zielprojekt (absolut oder relativ). | `.` |
| `-m`, `--max-iterations` | | Maximale Runden im Bau-Loop (Phase 3). | `10`, im Etappen-Modus 2 pro Etappe + 2 |
| `-d`, `--delay` | | Pause zwischen Bau-Runden in Sekunden. | `3` |
| `-c`, `--resume` | `--continue` | Letzte Sitzung im Projekt fortsetzen. | aus |
| `-i`, `--ask` | `--interview`, `--clarify` | Fragen-Modus: Architekt und Prüfstatiker dürfen Rückfragen stellen. | aus |
| `--yolo` | `--auto-approve` | Volle Schreib- und Tool-Rechte für den **Bauleiter** ohne Nachfrage. Architekt, Prüfstatiker und Abnahme bleiben lesend. | aus |
| `--max-rounds` | | Maximale Review-Runden für den Plan. | `2` |
| `--auto-switch` | `--fallback` | Bei Limit automatisch zur alternativen KI wechseln. | aus |
| `--swap` | `--swap-roles`, `--reverse` | Standardrollen tauschen: Antigravity/Gemini plant, Claude prüft. | aus |
| `--strategy` | `--preset` | `balanced`, `best-code` (`quality`), `eco` (`economy`, `cost`), `local-free` (`free`, `local`), `hybrid` (`mixed`). Siehe [Strategien](strategien.md). | `balanced` |
| `--dry-run` | | Belegung, Kostenanalyse und Startbefehl anzeigen, ohne etwas auszuführen oder anzulegen. | aus |
| `--info` | `--check` | Erkannte CLIs/Endpunkte und Standard-Belegung anzeigen. | aus |
| `--etappen <modus>` | `--stages` | `auto`, `an`, `aus`. Der Architekt schneidet den Plan in Etappen, der Bauleiter setzt sie einzeln um, der Loop prüft jede mit `--proof`. `auto` schaltet den Modus für Bauleiter ohne eigenen Dateizugriff ein (Ollama, LM Studio, Endpunkte). Siehe [Bau-Loop](bau-loop.md#etappen-modus). | `auto` |
| `--plan-auto` | `--approve-plan` | Plan ohne Freigabe-Menü übernehmen, sobald der Prüfstatiker `APPROVED` meldet. Meldet er das nicht, wird nicht gebaut. Für Läufe ohne Terminal. | aus |

## Rollen

| Flag | Aliase | Beschreibung |
| :--- | :--- | :--- |
| `--architekt <key>` | `--planner` | Backend für Phase 1. |
| `--pruefstatiker <key>` | `--reviewer` | Backend für Phase 2. |
| `--bauer <key>` | `--builder` | Backend für Phase 3 (Standard: wie Architekt). |

Gültige Schlüssel: `claude`, `agy`, `gemini`, `codex`, `copilot`, `ollama`, `ollama-cli`, `lmstudio`, `endpoint`, `architekt_ep`, `pruefstatiker_ep`, `bauer_ep` – sofern erkannt. Ein nicht erkannter Schlüssel fällt stillschweigend auf die Standardwahl zurück. Details: [Backends](backends.md).

## Abnahme & Prüfbefehl

| Flag | Aliase | Beschreibung | Standard |
| :--- | :--- | :--- | :--- |
| `--proof "<befehl>"` | `--pruefbefehl` | Befehl, den ClaudeGravity nach jeder Bau-Runde selbst ausführt (ohne Shell). Rot: `.done` wird zurückgewiesen und die Ausgabe geht an den Bauleiter. | – |
| `--abnahme <key>` | `--inspector` | Backend für die Abnahme des fertigen Codes. Nie der Bauleiter selbst. | Prüfstatiker |
| `--abnahme-model <name>` | `--inspector-model` | Modell für die Abnahme. | – |
| `--abnahme-effort <stufe>` | `--inspector-effort` | Effort für die Abnahme. | – |
| `--max-inspections <n>` | | Abnahme-Runden pro Lauf; danach bleibt die Aufgabe offen (`phase = inspection_open`). | `2` |
| `--no-inspect` | `--ohne-abnahme` | Abnahme auslassen (wird in `LOG.md` vermerkt). | an |

## Modelle

| Flag | Aliase | Beschreibung |
| :--- | :--- | :--- |
| `--architekt-model <name>` | `--planner-model` | z. B. `sonnet`, `opus`, `gemini-2.5-pro` |
| `--pruefstatiker-model <name>` | `--reviewer-model` | z. B. `gemini-2.5-pro`, `sonnet` |
| `--bauer-model <name>` | `--builder-model` | z. B. `claude-3-5-haiku`, `gemini-2.5-flash`, `qwen2.5-coder:32b` |

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

## Datenschutz

| Flag | Beschreibung |
| :--- | :--- |
| `--no-shield` | Datenschutzschild ausschalten (auch `CLAUDEGRAVITY_SHIELD=off`). Siehe [Sessions & Dateien](sessions-und-dateien.md#datenschutzschild). |

## Vorrang der Einstellungen

1. Explizites Flag in diesem Aufruf
2. Gespeicherter Wert aus `state.json` (bei `-c`)
3. Standardwert des gewählten Presets
4. CLI-Default des Backends

## Beispiele

```bash
# Alles getrennt einstellen
claudegravity "Sicherheits-Audit und Auth-Refactoring" \
  --architekt claude --architekt-model opus \
  --pruefstatiker agy --pruefstatiker-model gemini-2.5-pro --pruefstatiker-effort max \
  --bauer-endpoint http://192.168.1.50:11434/v1 --bauer bauer_ep --bauer-model qwen2.5-coder:7b

# Lange Aufgabe: mehr Runden, ohne Pause, Fallback bei Limit
claudegravity "Großes Refactoring" -m 25 -d 0 --auto-switch --yolo

# Anderes Projekt fortsetzen
claudegravity -c -p ~/Projekte/kundenportal
```
