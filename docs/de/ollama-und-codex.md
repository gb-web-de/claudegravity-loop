# Rollenbeispiele mit Ollama und Codex

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/ollama-und-codex.md)

Diese Seite spielt durch, wie du die vier Rollen zwischen **Codex** (Cloud, über dein ChatGPT-Abo) und **Ollama** (lokal, 0 €) aufteilst. Die Befehle sind aus den Optionen von `loop.py` und `mcp_server.py` abgeleitet, aber noch nicht mit echtem Codex und Ollama durchgelaufen. Prüfe jede Belegung vor dem ersten echten Lauf mit `--dry-run`.

**Faustregel:** Ollama ist schnell und kostenlos, solange die Stücke klein sind. Codex lohnt sich dort, wo wenige Tokens viel entscheiden: Plan, Plan-Prüfung und Abnahme.

**Automatisch:** `--strategy hybrid` stellt die Aufteilung von Variante A selbst ein (Cloud-CLI plant und nimmt ab, Ollama prüft und baut), wählt die Ollama-Modelle aus den installierten und baut den Plan in Etappen. Die Varianten unten zeigen, was dabei passiert und wie du davon abweichst.

## Inhalt

1. [Einrichtung von Ollama und Codex](#1-einrichtung-von-ollama-und-codex)
2. [Was du vorher wissen solltest](#2-was-du-vorher-wissen-solltest)
3. [Der schnellste Weg: `--strategy hybrid`](#der-schnellste-weg---strategy-hybrid)
4. [Variante A: Codex plant, Ollama prüft, anderes Ollama-Modell baut, Codex nimmt ab](#variante-a-codex-plant-ollama-prüft-anderes-ollama-modell-baut-codex-nimmt-ab)
5. [Variante B: Ollama plant, Codex prüft, Ollama baut, Codex nimmt ab](#variante-b-ollama-plant-codex-prüft-ollama-baut-codex-nimmt-ab)
6. [Variante C: Alles lokal, nur die Abnahme macht Codex](#variante-c-alles-lokal-nur-die-abnahme-macht-codex)
7. [Variante D: Schwere Aufgabe, Codex baut, Ollama nimmt ab](#variante-d-schwere-aufgabe-codex-baut-ollama-nimmt-ab)
8. [Variante E: Etappen, die Aufgabe in kleinen Stücken](#variante-e-etappen-die-aufgabe-in-kleinen-stücken)
9. [Welche Variante wann?](#welche-variante-wann)
10. [Über MCP: Einrichtung und Aufrufe](#über-mcp-einrichtung-und-aufrufe)
11. [Ollama-Modelle für einen Mac M4 mit 48 GB](#ollama-modelle-für-einen-mac-m4-mit-48-gb)
12. [Checkliste bei Problemen](#checkliste-bei-problemen)

## 1. Einrichtung von Ollama und Codex

### Ollama (macOS)

```bash
brew install ollama            # oder die App von https://ollama.com/download
ollama serve                   # nur nötig ohne App; die App startet den Server selbst

ollama pull qwen3-coder:30b    # Bauleiter
ollama pull gpt-oss:20b        # Prüfstatiker / Abnahme
ollama pull qwen3:30b          # Architekt
curl http://localhost:11434/api/tags   # zeigt die Modelle mit exakten Namen
```

Einstellungen, die für den Loop wichtig sind (bei der App per `launchctl`, danach Ollama beenden und neu starten):

```bash
launchctl setenv OLLAMA_CONTEXT_LENGTH 32768   # Plan + Dateien passen in den Kontext
launchctl setenv OLLAMA_KEEP_ALIVE 30m         # Modell bleibt zwischen den Runden geladen
launchctl setenv OLLAMA_MAX_LOADED_MODELS 2    # z. B. Prüfer und Bauleiter gleichzeitig
launchctl setenv OLLAMA_FLASH_ATTENTION 1      # weniger Speicher für den Kontext
```

Läuft `ollama serve` im Terminal, setzt du dieselben Variablen mit `export` davor. Ob der Kontext wirkt, zeigt `ollama ps` (Spalte `CONTEXT` in neueren Versionen).

> [!IMPORTANT]
> ClaudeGravity spricht Ollama über die OpenAI-Schnittstelle (`/v1/chat/completions`) an. Dort lässt sich die Kontextlänge nicht pro Anfrage setzen. Ohne `OLLAMA_CONTEXT_LENGTH` nutzt Ollama seine Voreinstellung, die je nach Version nur wenige tausend Tokens beträgt. Dann schneidet Ollama Plan oder Diff stillschweigend ab.

Ollama muss **vor** ClaudeGravity laufen, sonst wird es nicht erkannt. Läuft Ollama auf einem anderen Rechner im Heimnetz, setzt du `OLLAMA_HOST=<rechner>:11434`; alles Weitere steht unter [Backends](backends.md#ollama--co-aus-dem-lokalen-netzwerk).

### Codex CLI

```bash
npm install -g @openai/codex   # oder: brew install --cask codex
codex login                    # mit dem ChatGPT-Konto anmelden (Abo), kein API-Key nötig
codex exec -s read-only "Antworte nur mit OK"   # Anmeldung und Sandbox prüfen
```

ClaudeGravity ruft Codex als `codex exec -s <sandbox> --json` auf und schickt den Prompt über stdin. Architekt, Prüfstatiker und Abnahme bekommen `-s read-only`; nur ein Codex-Bauleiter bekommt `-s workspace-write`, und zwar erst nach deinem „J“ vor Phase 3 oder mit `--yolo`. `--architekt-effort`, `--pruefstatiker-effort`, `--bauer-effort` und `--abnahme-effort` werden an Codex als `model_reasoning_effort` weitergegeben (`max` wird zu `xhigh`). Ein Modell setzt du mit `--architekt-model` usw.; ohne Angabe nimmt Codex sein Standardmodell.

> [!NOTE]
> `codex exec` arbeitet nur in einem Git-Repository. Lege dein Projekt also mit `git init` an. Das passt ohnehin, weil ClaudeGravity pro Session einen eigenen Git-Workspace anlegt.

### Kontrolle

```bash
claudegravity --info
```

In der Liste müssen `codex` und `ollama` stehen (meist zusätzlich `ollama-cli`). Fehlt `ollama`, antwortet der Server nicht auf `http://localhost:11434` bzw. die Adresse aus `OLLAMA_HOST`.

## 2. Was du vorher wissen solltest

Diese Punkte entscheiden, ob eine Aufteilung mit Ollama klappt:

| Punkt | Was passiert | Was du tust |
| :--- | :--- | :--- |
| `--bauer ollama` usw. | Der Schlüssel `ollama` ist der Ollama-**Server** (OpenAI-API). Fehlt er bei `--info`, nimmt der Loop ohne Fehlermeldung ein anderes Backend. | Vor jedem Lauf `--dry-run`. |
| Ollama sieht keine Dateien | Ein Ollama-Prüfstatiker bekommt nur Aufgabe und Plan, eine Ollama-Abnahme nur den Diff (bis 60 000 Zeichen). Codex dagegen liest das Projekt selbst. | Ollama dort einsetzen, wo der Text reicht. Codex dort, wo man das Projekt kennen muss. |
| Ollama-Bauleiter sieht keine Dateien | Endpunkt-Bauleiter bekommen den Plan und ab der zweiten Runde den aktuellen Inhalt der Dateien, die sie geschrieben haben; im Etappen-Modus zusätzlich die Dateien, die die Etappe nennt. Jede Datei schreiben sie vollständig neu. | Den [Etappen-Modus](#variante-e-etappen-die-aufgabe-in-kleinen-stücken) nutzen (bei Ollama-Bauleitern automatisch an). |
| Ollama führt keine Tests aus | Der Bauleiter schreibt nur Dateien. | Immer `--proof "<testbefehl>"` angeben, der Loop führt ihn selbst aus. |
| Urteil nur aus `VERDICT:` | Fehlt die letzte Zeile `VERDICT: APPROVED`, zählt das Review nicht als Freigabe. | Für Prüfer- und Abnahme-Rollen Modelle nehmen, die Formatvorgaben einhalten (siehe [Modelle](#ollama-modelle-für-einen-mac-m4-mit-48-gb)). |
| Zwei Ollama-Rollen | Gleiches Backend mit **verschiedenen Modellen** gilt als andere Identität. Gleiches Modell prüft sich selbst. Fehlt das Modell, wählt der Loop eins aus den installierten und gibt Prüfstatiker und Abnahme nie das Modell des Bauleiters. | Für Architekt/Prüfstatiker bzw. Bauleiter/Abnahme unterschiedliche Modelle; ohne Angabe übernimmt das der Loop. |
| Abnahme | Standard ist der Prüfstatiker, nie der Bauleiter. Ist der Prüfstatiker ein anderes Ollama-Modell, nimmt **Ollama** ab, nicht Codex. | Codex als Abnahme ausdrücklich mit `--abnahme codex` setzen. |
| Freigabe-Menü | Nach dem Review fragt der Loop im Terminal nach der Freigabe, vor Phase 3 nach den Schreibrechten. | Im Terminal starten. `--yolo` überspringt die Rechte-Frage, `--plan-auto` die Freigabe (gebaut wird dann nur ein Plan mit `APPROVED`). |

Die Aufgabe selbst ist dein stärkster Hebel: Schreib in den Aufgabentext, wie der Plan aussehen soll, zum Beispiel „Gliedere den Plan in nummerierte Schritte; jeder Schritt ändert höchstens eine Datei und nennt seinen Test“. Der Architekt bekommt den Text wörtlich.

In allen Beispielen sind `~/Projekte/rechnung` das Projekt und `python3 -m unittest discover -s tests` der Prüfbefehl. Ersetze beides durch dein Projekt und seinen eigenen Testbefehl (z. B. `npm test`, `vendor/bin/phpunit`).

## Der schnellste Weg: `--strategy hybrid`

```bash
claudegravity "Füge einen CSV-Export für Rechnungen hinzu" \
  -p ~/Projekte/rechnung \
  --strategy hybrid \
  --proof "python3 -m unittest discover -s tests" \
  --dry-run
```

Das stellt der Loop dabei selbst ein (mit den Modellen aus Abschnitt 1 installiert):

| Rolle | Automatisch | Ändern mit |
| :--- | :--- | :--- |
| 🏗️ Architekt | erste Cloud-CLI aus `codex`, `claude`, `agy`, `gemini` | `--architekt` |
| 🧐 Prüfstatiker | Ollama mit Denk-Modell, z. B. `gpt-oss:20b` | `--pruefstatiker`, `--pruefstatiker-model` |
| 🔨 Bauleiter | Ollama mit Code-Modell, z. B. `qwen3-coder:30b` | `--bauer`, `--bauer-model` |
| 🔎 Abnahme | der Architekt | `--abnahme`, `--abnahme-model` |
| 🧩 Etappen | an: Plan mit `## Etappen`, jede Etappe eine Bau-Runde mit Prüfbefehl | `--etappen aus` |

Der Trockenlauf zeigt die Belegung und den vollständigen Befehl. Ohne `--dry-run` startet der echte Lauf. Willst du gar nicht gefragt werden, hängst du `--plan-auto` an: Dann baut der Loop, sobald der Prüfstatiker `APPROVED` meldet, und hält sonst an.

## Variante A: Codex plant, Ollama prüft, anderes Ollama-Modell baut, Codex nimmt ab

| Rolle | Backend | Modell |
| :--- | :--- | :--- |
| 🏗️ Architekt | Codex | Standard, Effort `high` |
| 🧐 Prüfstatiker | Ollama | `gpt-oss:20b` |
| 🔨 Bauleiter | Ollama | `qwen3-coder:30b` |
| 🔎 Abnahme | Codex | Standard, Effort `high` |

Codex kennt das Projekt und schreibt einen Plan in kleinen Schritten. Ein lokales Denk-Modell prüft den Plan kostenlos auf Lücken. Ein schnelles Code-Modell baut. Codex prüft am Ende den Diff mit Blick ins Projekt.

```bash
claudegravity "Füge einen CSV-Export für Rechnungen hinzu. Gliedere den Plan in nummerierte Schritte; jeder Schritt ändert höchstens eine Datei, nennt die Funktion und den Test dazu." \
  -p ~/Projekte/rechnung \
  --architekt codex --architekt-effort high \
  --pruefstatiker ollama --pruefstatiker-model gpt-oss:20b \
  --bauer ollama --bauer-model qwen3-coder:30b \
  --abnahme codex --abnahme-effort high \
  --proof "python3 -m unittest discover -s tests" \
  -m 6 --dry-run
```

Ohne `--dry-run` startet der echte Lauf.

**Handlungsanweisungen**

1. Im Trockenlauf prüfen: Prüfstatiker und Bauleiter zeigen `Ollama (Lokal: http://localhost:11434)` mit zwei verschiedenen Modellen, die Abnahme zeigt `Codex CLI`.
2. Nach Phase 2 im Freigabe-Menü mit `[4]` den Plan lesen. Hat ein Schritt mehr als eine Datei oder fehlt ein Test, mit `[2]` Änderungen anfordern. Codex überarbeitet, Ollama prüft erneut.
3. Bei der Rechte-Frage vor Phase 3 ist die Antwort egal: Ollama schreibt keine Dateien selbst, das übernimmt der Loop über `filepath:`-Blöcke.
4. Verweigert Codex die Abnahme, bekommt der Bauleiter die Befunde als Rückmeldung. Nach `--max-inspections` (Standard 2) bleibt die Aufgabe offen; `claudegravity -c` macht dort weiter.
5. Wird die Aufgabe für eine Bau-Runde zu groß (der Prüfbefehl bleibt rot, Dateien widersprechen sich), abbrechen und auf [Variante E](#variante-e-etappen-die-aufgabe-in-kleinen-stücken) wechseln.

## Variante B: Ollama plant, Codex prüft, Ollama baut, Codex nimmt ab

| Rolle | Backend | Modell |
| :--- | :--- | :--- |
| 🏗️ Architekt | Ollama | `qwen3:30b` |
| 🧐 Prüfstatiker | Codex | Standard, Effort `high` |
| 🔨 Bauleiter | Ollama | `qwen3-coder:30b` |
| 🔎 Abnahme | Codex | wie der Prüfstatiker (Standard) |

Der Plan kostet nichts. Codex prüft ihn mit Blick ins Projekt und fängt die typischen Fehler kleiner Modelle ab (erfundene Dateien, fehlende Randfälle). Die Abnahme fällt ohne weitere Angabe auf den Prüfstatiker Codex, weil er nicht der Bauleiter ist.

```bash
claudegravity "Füge einen CSV-Export für Rechnungen hinzu. Plane in nummerierten Schritten, jeder Schritt höchstens eine Datei." \
  -p ~/Projekte/rechnung \
  --architekt ollama --architekt-model qwen3:30b \
  --pruefstatiker codex --pruefstatiker-effort high \
  --bauer ollama --bauer-model qwen3-coder:30b \
  --proof "python3 -m unittest discover -s tests" \
  --max-rounds 3 -m 6
```

**Handlungsanweisungen**

1. Der lokale Architekt kennt nur den Aufgabentext und die geladenen `CLAUDE.md`/`AGENTS.md`/`knowledge/`-Dateien, nicht den Code. Schreib wichtige Dateinamen und Schnittstellen deshalb in die Aufgabe oder in `CLAUDE.md`.
2. `--max-rounds 3` gibt dem kleinen Architekten eine Runde mehr, um die Befunde von Codex einzuarbeiten.
3. Bleibt Codex nach allen Runden bei `REVISE`, im Freigabe-Menü `[3] Swap` wählen: Dann plant Codex und Ollama prüft, also Variante A.
4. Wer die Abnahme gründlicher will als das Review, setzt `--abnahme codex --abnahme-effort xhigh`.

## Variante C: Alles lokal, nur die Abnahme macht Codex

| Rolle | Backend | Modell |
| :--- | :--- | :--- |
| 🏗️ Architekt | Ollama | `qwen3:30b` |
| 🧐 Prüfstatiker | Ollama | `gpt-oss:20b` |
| 🔨 Bauleiter | Ollama | `qwen3-coder:30b` |
| 🔎 Abnahme | Codex | Standard, Effort `high` |

Der günstigste Weg: Codex wird genau einmal pro Abnahme-Runde aufgerufen. Planer und Prüfer sind zwei verschiedene lokale Modelle; das ist unabhängiger als Selbstprüfung, aber weniger unabhängig als zwei Anbieter. Codex ist hier die einzige Prüfung, die das Projekt selbst liest.

```bash
claudegravity "Ergänze die fehlende Validierung der Rechnungsnummer in src/rechnung.py und teste sie." \
  -p ~/Projekte/rechnung \
  --architekt ollama --architekt-model qwen3:30b \
  --pruefstatiker ollama --pruefstatiker-model gpt-oss:20b \
  --bauer ollama --bauer-model qwen3-coder:30b \
  --abnahme codex --abnahme-effort high \
  --proof "python3 -m unittest discover -s tests" \
  -m 5
```

**Handlungsanweisungen**

1. Nur für kleine, klar umrissene Aufgaben mit Dateinamen im Aufgabentext.
2. Drei Modelle mit je rund 14 bis 19 GB passen nicht gleichzeitig in den Speicher. Ollama lädt beim Rollenwechsel neu; das kostet pro Wechsel einige Sekunden. Mit `OLLAMA_MAX_LOADED_MODELS 2` bleiben Prüfer und Bauleiter oft beide geladen.
3. `--abnahme codex` nicht weglassen, sonst nimmt `gpt-oss:20b` ab und kein Modell mit Projektzugriff sieht den Code.

## Variante D: Schwere Aufgabe, Codex baut, Ollama nimmt ab

| Rolle | Backend | Modell |
| :--- | :--- | :--- |
| 🏗️ Architekt | Ollama | `qwen3:30b` |
| 🧐 Prüfstatiker | Codex | Standard, Effort `high` |
| 🔨 Bauleiter | Codex | Standard, Effort `medium` |
| 🔎 Abnahme | Ollama | `gpt-oss:20b` |

Für Aufgaben, die mehrere Dateien gleichzeitig ändern oder Tests im Projekt ausführen müssen. Codex baut mit `-s workspace-write`, sieht den Dateistand, führt selbst Befehle aus und behält zwischen den Runden den Überblick. Ollama übernimmt den Entwurf und die Abnahme, also die Rollen, die nur Text brauchen. Das kostet mehr Codex-Kontingent als A bis C.

```bash
claudegravity "Stelle die Rechnungsablage von JSON-Dateien auf SQLite um, mit Migration der Bestandsdaten." \
  -p ~/Projekte/rechnung \
  --architekt ollama --architekt-model qwen3:30b \
  --pruefstatiker codex --pruefstatiker-effort high \
  --bauer codex --bauer-effort medium \
  --abnahme ollama --abnahme-model gpt-oss:20b \
  --proof "python3 -m unittest discover -s tests" \
  -m 8
```

**Handlungsanweisungen**

1. Vor Phase 3 die Rechte-Frage mit „J“ beantworten (oder `--yolo` setzen), sonst darf Codex nicht schreiben.
2. Codex baut in der Session-Kopie (Git-Workspace), nicht in deinem Arbeitsordner. Mit `--merge` wird das Ergebnis nach `.done` in deinen Branch übernommen, sonst mergst du den Session-Branch selbst.
3. Die Ollama-Abnahme sieht den Diff bis 60 000 Zeichen (rund 15 000 Tokens). Mit `OLLAMA_CONTEXT_LENGTH 32768` passt das; bei größeren Umbauten lieber `--abnahme codex --abnahme-model <anderes Modell>` oder eine kleinere Aufgabe.
4. Hier prüft Codex den Plan und baut ihn auch. Das ist erlaubt (der Architekt ist Ollama), aber die einzige fremde Prüfung des Codes ist die Ollama-Abnahme plus der Prüfbefehl. Gute Tests sind hier besonders wichtig.

## Variante E: Etappen, die Aufgabe in kleinen Stücken

Das ist die Antwort auf „Ollama arbeitet schneller mit kleinen Stücken“, und der Loop macht es selbst. Der Etappen-Modus ist bei Ollama-, LM-Studio- und Endpunkt-Bauleitern automatisch an (`--etappen auto`), mit `--etappen an` auch für Codex oder Claude.

So läuft es:

1. Der Architekt (z. B. Codex) bekommt die Vorgabe, den Plan mit `## Etappen` abzuschließen: 2 bis 8 Etappen, jede ändert höchstens zwei Dateien und ist danach testbar.
2. Der Prüfstatiker prüft Plan und Etappen. Nach der Freigabe zeigt der Loop die Etappen an.
3. Pro Runde bekommt der Ollama-Bauleiter nur die aktuelle Etappe, die erledigten Etappen, den Plan und den **aktuellen Inhalt** der betroffenen und schon geschriebenen Dateien.
4. Der Loop führt `--proof` aus. Grün: nächste Etappe. Rot: Die Ausgabe geht zurück an den Bauleiter, bis zu 3 Versuche pro Etappe; danach hält der Loop an und `claudegravity -c` macht weiter.
5. Nach der letzten Etappe nimmt Codex den gesamten Diff ab. Bei Befunden hängt der Loop eine Nacharbeits-Etappe an.

```bash
claudegravity "CSV-Export für Rechnungen mit Filter nach Zeitraum und Kunde" \
  -p ~/Projekte/rechnung \
  --architekt codex --architekt-effort medium \
  --pruefstatiker ollama --pruefstatiker-model gpt-oss:20b \
  --bauer ollama --bauer-model qwen3-coder:30b \
  --abnahme codex \
  --proof "python3 -m unittest discover -s tests" \
  --merge
```

Kürzer, mit denselben Rollen: `--strategy hybrid --proof "…" --merge`.

**Handlungsanweisungen**

1. Ohne `--proof` gilt jede Etappe nach einer Runde als erledigt. Immer den Testbefehl des Projekts angeben.
2. Hat das Projekt noch keine Tests, ist `unittest discover` schon vor der ersten Etappe rot. Lege vorher einen kleinen Test an oder schreib in die Aufgabe, dass Etappe 1 die Tests anlegt.
3. Im Freigabe-Menü mit `[4]` den Abschnitt `## Etappen` lesen. Zu große Etappen mit `[2]` kleiner schneiden lassen.
4. `-m` brauchst du nicht: Ohne Angabe bekommt der Lauf 2 Runden pro Etappe plus 2.
5. Den Fortschritt zeigt `LOG.md` im Session-Ordner (`Etappe n/N erledigt`); `state.json` merkt sich Etappe und Stand für `-c`.
6. Etappen von Hand, jede als eigener Lauf, gehen weiterhin: eine Etappe als Aufgabe, `--etappen aus`, `--merge`.

## Welche Variante wann?

| Situation | Variante | Codex-Verbrauch |
| :--- | :--- | :--- |
| Mittlere Aufgabe in bestehendem Projekt | A | Plan + Abnahme |
| Neues kleines Projekt, Plan darf lokal entstehen | B | Review + Abnahme |
| Kleiner Fix mit bekannten Dateien | C | nur Abnahme |
| Großer Umbau, viele Dateien, Tests im Projekt | D | Review + gesamter Bau |
| Größere Aufgabe, aber lokal bauen | E oder `--strategy hybrid` | ein Plan in Etappen + eine Abnahme am Ende |

## Über MCP: Einrichtung und Aufrufe

Mit dem [MCP-Server](mcp-server.md) kann ein Assistent (Claude Code oder Codex selbst) ClaudeGravity für dich vorbereiten. Zuerst müssen Ollama und Codex wie in [Abschnitt 1](#1-einrichtung-von-ollama-und-codex) eingerichtet sein und `claudegravity --info` beide zeigen.

### Einrichtung in Codex

```bash
codex mcp add claudegravity -- python3 ~/Projekte/claudegravity-loop/mcp_server.py
codex mcp list
```

Oder direkt in `~/.codex/config.toml`:

```toml
[mcp_servers.claudegravity]
command = "python3"
args = ["/Users/<name>/Projekte/claudegravity-loop/mcp_server.py"]
env = { PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", OLLAMA_HOST = "localhost:11434" }
```

### Einrichtung in Claude Code

```bash
claude mcp add claudegravity --scope user -- python3 ~/Projekte/claudegravity-loop/mcp_server.py
claude mcp list
```

> [!TIP]
> Ein MCP-Server erbt den `PATH` des Programms, das ihn startet. Unter macOS fehlt dort oft `/opt/homebrew/bin`. Dann findet der Server weder `codex` noch `ollama`, und `claudegravity_info` meldet sie nicht. Den `PATH` deshalb wie oben im `env`-Block setzen.

### Aufrufe

**1. Prüfen, was der Server sieht**: Tool `claudegravity_info`, ohne Parameter. Erwartet: `Codex CLI (codex)`, `Ollama CLI (ollama-cli)` und `Ollama (Lokal: …) (ollama)`.

**2. Befehl berechnen lassen**: Tool `claudegravity_optimize`, Variante A automatisch:

```json
{
  "task": "Füge einen CSV-Export für Rechnungen hinzu",
  "priority": "hybrid",
  "project_path": "/Users/<name>/Projekte/rechnung",
  "proof": "python3 -m unittest discover -s tests"
}
```

Ergebnis: `claudegravity '…' --strategy hybrid --proof '…' -p …`. Die Ollama-Modelle wählt der Loop beim Start aus den installierten Modellen; der Optimizer zeigt dafür „automatisch“.

**3. Eine bestimmte Variante**: Die Tools nehmen Rollen und Modelle als Parameter. Variante B:

```json
{
  "task": "Füge einen CSV-Export für Rechnungen hinzu",
  "architekt": "ollama", "architekt_model": "qwen3:30b",
  "pruefstatiker": "codex",
  "bauer": "ollama", "bauer_model": "qwen3-coder:30b",
  "abnahme": "codex",
  "stages": "an",
  "proof": "python3 -m unittest discover -s tests"
}
```

Weitere Parameter: `abnahme_model`, `approve_plan` (`--plan-auto`) und `merge` (`--merge`). Modellnamen zeigt der Optimizer nur für Claude und Gemini; Codex nutzt sein Standardmodell, solange du keins setzt.

Mit dem Skill [`skills/claudegravity`](../../skills/claudegravity/SKILL.md) kennt der Assistent die Rollen-Flags bereits.

**4. `claudegravity_run`**: dieselben Parameter. Mit `background: false` liefert das Tool den Befehl mit `cd` zum Kopieren. Mit `background: true` startet der Loop ohne Terminal und mit `--plan-auto`: Gebaut wird nur, wenn der Prüfstatiker `APPROVED` meldet. Ollama-Bauleiter brauchen dafür kein `yolo`; ein Codex-Bauleiter (Variante D) schon. Den Stand zeigt danach `claudegravity_status`.

**Zum Testen ohne Client** (eine JSON-RPC-Zeile über stdin):

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"claudegravity_optimize","arguments":{"task":"CSV-Export","priority":"local-free","proof":"python3 -m unittest discover -s tests"}}}' \
  | python3 ~/Projekte/claudegravity-loop/mcp_server.py
```

## Ollama-Modelle für einen Mac M4 mit 48 GB

Ein Mac mit 48 GB teilt den Speicher zwischen System und Grafik. macOS gibt der GPU ab Werk rund drei Viertel davon, also etwa 36 GB. Davon gehen Kontext (KV-Cache) und Systemlast ab. Realistisch sind **ein Modell bis etwa 20 GB plus ein zweites bis etwa 14 GB gleichzeitig**. Ein 70B-Modell (Q4 rund 40 GB) passt nicht sinnvoll.

Die Größen gelten für die Standard-Quantisierung der Ollama-Bibliothek (meist `Q4_K_M`, bei `gpt-oss` `MXFP4`) und sind Downloadgrößen; im Betrieb kommt der Kontext dazu. Stand dieser Seite: Oktober 2026. Neue Modelle erscheinen laufend; prüfe auf [ollama.com/library](https://ollama.com/library), ob es Nachfolger gibt.

| Rolle | Empfehlung | Größe | Warum | Alternative |
| :--- | :--- | :--- | :--- | :--- |
| 🔨 Bauleiter | `qwen3-coder:30b` | ~19 GB | Mixture-of-Experts mit rund 3B aktiven Parametern: schnell wie ein kleines Modell, Code-Qualität eines großen. Ideal für kleine Stücke. | `qwen2.5-coder:32b` (~20 GB, dicht, langsamer, sehr stabil im Format), `devstral:24b` (~14 GB) |
| 🔨 Bauleiter, sehr kleine Stücke | `qwen2.5-coder:14b` | ~9 GB | Lässt Platz für einen großen Prüfer daneben. | `qwen2.5-coder:7b` (~4,7 GB) für Einzeldateien |
| 🧐 Prüfstatiker | `gpt-oss:20b` | ~14 GB | Denkt vor der Antwort (Reasoning), hält Formatvorgaben wie `VERDICT:` gut ein. | `qwen3:14b` (~9 GB), `deepseek-r1:14b` (~9 GB) |
| 🏗️ Architekt | `qwen3:30b` | ~19 GB | Schnelles MoE-Modell mit Denk-Modus, gut für strukturierte Pläne. | `qwen3:32b` (~20 GB, gründlicher, langsamer), `gpt-oss:20b` |
| 🔎 Abnahme (Variante D) | `gpt-oss:20b` | ~14 GB | Wie Prüfstatiker; der Diff braucht mindestens 32k Kontext. | `qwen3:30b` |

**Bewährte Paare, die gleichzeitig geladen bleiben** (mit `OLLAMA_MAX_LOADED_MODELS 2` und 32k Kontext):

| Paar | Zusammen | Passt zu |
| :--- | :--- | :--- |
| `gpt-oss:20b` + `qwen3-coder:30b` | ~33 GB | Variante A, E (Prüfer + Bauleiter) |
| `qwen3:30b` + `qwen3-coder:30b` | ~38 GB | Variante B; knapp, beim Rollenwechsel lädt Ollama eventuell neu |
| `gpt-oss:20b` + `qwen2.5-coder:14b` | ~23 GB | Variante A/E mit viel Luft für großen Kontext |

Wer mehr Grafikspeicher freigeben will, kann das Limit anheben, z. B. `sudo sysctl iogpu.wired_limit_mb=40960` (gilt bis zum Neustart). Dann bleiben dem System nur noch 8 GB; andere große Programme vorher schließen.

## Checkliste bei Problemen

| Symptom | Ursache | Lösung |
| :--- | :--- | :--- |
| Trockenlauf zeigt bei `--bauer ollama` ein anderes Backend | Ollama-Server lief beim Start nicht | Ollama starten, `curl http://localhost:11434/api/tags`, neu starten |
| Review endet ohne Freigabe, „kein lesbares VERDICT“ | Lokales Modell hält das Antwortformat nicht ein | Anderes Prüfer-Modell (`gpt-oss:20b`, `qwen3:14b`) |
| Bauleiter schreibt halbe Dateien oder vergisst Teile | Kontext zu klein oder Aufgabe zu groß | `OLLAMA_CONTEXT_LENGTH` erhöhen, Variante E |
| Zeitüberschreitung nach 900 s | Großes Modell, langer Plan | `--timeout 1800` oder kleineres Modell |
| `Codex Fehler: … not inside a trusted directory` o. ä. | Projekt ist kein Git-Repository | `git init` im Projekt |
| Codex-Bauleiter ändert nichts | Rechte-Frage mit „n“ beantwortet | Mit `claudegravity -c --yolo` fortsetzen |
| Codex-Limit erreicht | Abo-Kontingent aufgebraucht | Im Limit-Menü warten, oder `--auto-switch`: dann springt eine andere installierte CLI ein, nie der Anbieter der Gegenrolle |

Weitere Probleme: [Fehlerbehebung](fehlerbehebung.md).
