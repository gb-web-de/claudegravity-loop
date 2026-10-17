# CLI-Referenz (`claudegravity` / `loop.py`)

[← Zurück zur Übersicht](../README.md) · [Dokumentations-Index](README.md)

```text
claudegravity [AUFGABE] [OPTIONEN]
```

Alle deutschen und englischen Schreibweisen eines Flags sind gleichwertig (z. B. `--bauer` = `--builder`).

## Allgemein

| Flag | Aliase | Beschreibung | Standard |
| :--- | :--- | :--- | :--- |
| `AUFGABE` | *(Positionsargument)* | Die Programmieraufgabe in Anführungszeichen. Ohne Aufgabe wird eine unterbrochene Sitzung angeboten, sonst die Hilfe gezeigt. | – |
| `-p`, `--project` | | Zielprojekt (absolut oder relativ). | `.` |
| `-m`, `--max-iterations` | | Maximale Runden im Bau-Loop (Phase 3). | `10` |
| `-d`, `--delay` | | Pause zwischen Bau-Runden in Sekunden. | `3` |
| `-c`, `--resume` | `--continue` | Letzte Sitzung im Projekt fortsetzen. | aus |
| `-i`, `--ask` | `--interview`, `--clarify` | Fragen-Modus: Architekt und Prüfstatiker dürfen Rückfragen stellen. | aus |
| `--yolo` | `--auto-approve` | Volle Schreib- und Tool-Rechte ohne Nachfrage. | aus |
| `--auto-switch` | `--fallback` | Bei Limit automatisch zur alternativen KI wechseln. | aus |
| `--swap` | `--swap-roles`, `--reverse` | Standardrollen tauschen: Antigravity/Gemini plant, Claude prüft. | aus |
| `--strategy` | `--preset` | `balanced`, `best-code` (`quality`), `eco` (`economy`, `cost`), `local-free` (`free`, `local`). Siehe [Strategien](strategien.md). | `balanced` |
| `--dry-run` | | Belegung, Kostenanalyse und Startbefehl anzeigen, ohne etwas auszuführen oder anzulegen. | aus |
| `--info` | `--check` | Erkannte CLIs/Endpunkte und Standard-Belegung anzeigen. | aus |

## Rollen

| Flag | Aliase | Beschreibung |
| :--- | :--- | :--- |
| `--architekt <key>` | `--planner` | Backend für Phase 1. |
| `--pruefstatiker <key>` | `--reviewer` | Backend für Phase 2. |
| `--bauer <key>` | `--builder` | Backend für Phase 3 (Standard: wie Architekt). |

Gültige Schlüssel: `claude`, `agy`, `gemini`, `codex`, `copilot`, `ollama`, `ollama-cli`, `lmstudio`, `endpoint`, `gb-web`, `architekt_ep`, `pruefstatiker_ep`, `bauer_ep` – sofern erkannt. Ein nicht erkannter Schlüssel fällt stillschweigend auf die Standardwahl zurück. Details: [Backends](backends.md).

## Modelle

| Flag | Aliase | Beschreibung |
| :--- | :--- | :--- |
| `--architekt-model <name>` | `--planner-model` | z. B. `sonnet`, `opus`, `gemini-2.5-pro` |
| `--pruefstatiker-model <name>` | `--reviewer-model` | z. B. `gemini-2.5-pro`, `sonnet` |
| `--bauer-model <name>` | `--builder-model` | z. B. `claude-3-5-haiku`, `gemini-2.5-flash`, `qwen2.5-coder:32b` |

Der Modellname wird als `--model <name>` an die CLI bzw. als `model` an den Endpunkt übergeben.

## Reasoning-Effort

Werte: `low`, `medium`, `high`, `xhigh`, `max`.

| Flag | Aliase | Gilt für |
| :--- | :--- | :--- |
| `--effort` | | Architekt und Prüfstatiker (wenn nicht einzeln gesetzt) |
| `--architekt-effort` | `--planner-effort` | Architekt |
| `--pruefstatiker-effort` | `--reviewer-effort` | Prüfstatiker |
| `--bauer-effort` | `--builder-effort` | Bauleiter |

Effort wird nur an `agy` weitergegeben.

## Endpunkte

| Flag | Aliase | Beschreibung |
| :--- | :--- | :--- |
| `--endpoint <url>` | `--api-base` | OpenAI-kompatibler Endpunkt, verfügbar als Schlüssel `endpoint`. |
| `--api-key <key>` | | Bearer-Token für den Endpunkt (besser per Umgebungsvariable, siehe [Backends](backends.md)). |
| `--architekt-endpoint <url>` | | Eigener Endpunkt, verfügbar als `architekt_ep`. |
| `--pruefstatiker-endpoint <url>` | | Eigener Endpunkt, verfügbar als `pruefstatiker_ep`. |
| `--bauer-endpoint <url>` | | Eigener Endpunkt, verfügbar als `bauer_ep`. |

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
  --bauer-endpoint https://ai.gb-web.de/v1 --bauer bauer_ep --bauer-model qwen2.5-coder:32b

# Lange Aufgabe: mehr Runden, ohne Pause, Fallback bei Limit
claudegravity "Großes Refactoring" -m 25 -d 0 --auto-switch --yolo

# Anderes Projekt fortsetzen
claudegravity -c -p ~/Projekte/kundenportal
```
