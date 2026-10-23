# Strategie-Presets

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/strategien.md)

Statt jede Rolle einzeln einzustellen, wählst du mit `--strategy <name>` (Alias `--preset`) ein Preset. Es setzt **Standardwerte** für Effort und Bauleiter-Modell; alles, was du explizit angibst (`--bauer-model`, `--architekt-effort`, …), hat Vorrang.

## Übersicht

| Preset | Aliase | Architekt-Effort | Prüfstatiker-Effort | Bauleiter-Effort | Bauleiter-Modell (Standard) | Wofür |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `balanced` *(Standard)* | – | `high` nur bei `agy` | `high` nur bei `agy` | CLI-Default | wie Architekt | Alltag |
| `best-code` | `quality` | `high` | `high` | `high` | wie Architekt | Kernsysteme, Sicherheit, große Umbauten |
| `eco` | `economy`, `cost` | `medium` | `medium` | `low` | `claude-3-5-haiku` (bei `claude`), `gemini-2.5-flash` (bei `agy`/`gemini`), sonst CLI-Default | Bis zu ~70 % Token-Ersparnis |
| `local-free` | `free`, `local` | `high` | `high` | `low` | Ollama: automatisch aus den installierten Modellen; Endpunkt: `qwen2.5-coder:32b`; sonst `local-model` | 0 € API-Kosten im Bau-Loop |
| `hybrid` | `mixed` | CLI-Default | – | – | Ollama: automatisch | Cloud plant und nimmt ab, lokal wird geprüft und in Etappen gebaut |

> [!NOTE]
> `--effort`-Werte werden an `agy` (`--effort`) und `codex` (`model_reasoning_effort`) weitergereicht. Bei `claude` und anderen CLIs wirken sie nur als Anzeige im Audit-Bericht.

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

## `hybrid`

Die Aufteilung für Cloud-CLI plus lokales Modell, ohne jede Rolle einzeln zu setzen:

| Rolle | Wird besetzt mit |
| :--- | :--- |
| 🏗️ Architekt | erste erkannte Cloud-CLI in der Reihenfolge `codex`, `claude`, `agy`, `gemini` |
| 🧐 Prüfstatiker | lokales Modell (Ollama-Server, LM Studio, Endpunkt), Denk-Modell automatisch |
| 🔨 Bauleiter | dasselbe lokale Backend, Code-Modell automatisch und nie dasselbe wie der Prüfstatiker |
| 🔎 Abnahme | der Architekt (Cloud), also nie der Bauleiter |

Dazu ist der [Etappen-Modus](bau-loop.md#etappen-modus) an: Der Architekt schneidet den Plan in Etappen, das lokale Modell baut sie einzeln und bekommt jedes Mal den aktuellen Stand der betroffenen Dateien. Jede Rolle, die du selbst angibst (`--architekt claude`, `--bauer-model …`), bleibt so, wie du sie setzt. Fehlt eine Cloud-CLI oder ein lokales Modell, meldet ClaudeGravity das und nutzt die normale Belegung.

```bash
claudegravity "CSV-Export für Rechnungen" --strategy hybrid --proof "python3 -m unittest discover -s tests"
```

Beispiele und Modellempfehlungen: [Ollama & Codex](ollama-und-codex.md).

## Presets prüfen

Kombiniere jedes Preset mit `--dry-run`, um die konkrete Belegung auf deinem Rechner zu sehen:

```bash
claudegravity --dry-run "Neues Feature" --strategy eco
```

## Strategie per MCP wählen lassen

Der [MCP-Server](mcp-server.md) bildet die Ziele `best-code`, `lowest-cost` (→ `eco`), `local-free`, `hybrid` und `balanced` auf diese Presets ab und erzeugt den passenden Befehl.
