# Strategie-Presets

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/strategien.md)

Statt jede Rolle einzeln einzustellen, wählst du mit `--strategy <name>` (Alias `--preset`) ein Preset. Es setzt **Standardwerte** für Effort und Bauleiter-Modell; alles, was du explizit angibst (`--bauer-model`, `--architekt-effort`, …), hat Vorrang.

## Übersicht

| Preset | Aliase | Architekt-Effort | Prüfstatiker-Effort | Bauleiter-Effort | Bauleiter-Modell (Standard) | Wofür |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `balanced` *(Standard)* | – | `high` nur bei `agy` | `high` nur bei `agy` | CLI-Default | wie Architekt | Alltag |
| `best-code` | `quality` | `high` | `high` | `high` | wie Architekt | Kernsysteme, Sicherheit, große Umbauten |
| `eco` | `economy`, `cost` | `medium` | `medium` | `low` | `claude-3-5-haiku` (bei `claude`), sonst `gemini-2.5-flash` | Bis zu ~70 % Token-Ersparnis |
| `local-free` | `free`, `local` | `high` | `high` | `low` | `qwen2.5-coder:32b` (Endpunkt), `qwen2.5-coder:latest` (Ollama), sonst `local-model` | 0 € API-Kosten im Bau-Loop |

> [!NOTE]
> `--effort`-Werte werden derzeit nur an `agy` (Antigravity) als `--effort` weitergereicht. Bei `claude` und anderen CLIs wirken sie nur als Anzeige im Audit-Bericht.

## `best-code`

Alle drei Phasen laufen auf Frontier-Modellen mit hohem Thinking-Effort. Höchste Qualität und gründlichste Tests, aber auch der höchste Verbrauch.

```bash
claudegravity "Sicherheits-Audit und Auth-Refactoring" --strategy best-code
```

## `eco`

Planung und Review bleiben stark (sie verbrauchen ohnehin wenig). Den teuren Bau-Loop übernimmt ein schnelles Sparmodell.

```bash
claudegravity "Füge strukturiertes Logging hinzu" --strategy eco
```

## `local-free`

Cloud-Modelle planen und prüfen; ein lokales oder Intranet-Modell baut. Endpunkte im eigenen Netz (`localhost`, private IPs wie `192.168.*`, `10.*`, `172.16–31.*` und Rechnernamen wie `nas`, `server.local` oder `pi.fritz.box`) werden im Audit mit 0 € verbucht.

ClaudeGravity sucht Bauleiter-Kandidaten in dieser Reihenfolge: `--bauer-endpoint` → Ollama-Server (`localhost:11434` oder `OLLAMA_HOST`) → LM Studio (`localhost:1234`) → `--endpoint`/`CLAUDEGRAVITY_ENDPOINT` → `ollama`-CLI.

Der gefundene Kandidat bleibt auch nach der Plan-Freigabe Bauleiter. Mit `--bauer` legst du ihn ausdrücklich fest. Die Abnahme übernimmt dann ein Cloud-Modell (standardmäßig der Prüfstatiker), weil das lokale Modell seinen eigenen Code nicht abnehmen soll.

```bash
# Ollama lokal
claudegravity "Baue ein REST-Interface" --strategy local-free --bauer ollama

# Eigener Server im Netzwerk
claudegravity "Refaktoriere das Modul" --strategy local-free \
  --endpoint http://192.168.1.50:11434/v1 --bauer endpoint --bauer-model qwen2.5-coder:7b
```

## Presets prüfen

Kombiniere jedes Preset mit `--dry-run`, um die konkrete Belegung auf deinem Rechner zu sehen:

```bash
claudegravity --dry-run "Neues Feature" --strategy eco
```

## Strategie per MCP wählen lassen

Der [MCP-Server](mcp-server.md) bildet die Ziele `best-code`, `lowest-cost` (→ `eco`), `local-free` und `balanced` auf diese Presets ab und erzeugt den passenden Befehl.
