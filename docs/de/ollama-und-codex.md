# Rollenbeispiele mit Ollama und Codex

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/ollama-und-codex.md)

Diese Seite spielt durch, wie du die vier Rollen zwischen **Codex** (Cloud, über dein ChatGPT-Abo) und **Ollama** (lokal, 0 €) aufteilst. Die Befehle sind aus den Optionen von `loop.py` und `mcp_server.py` abgeleitet, aber noch nicht mit echtem Codex und Ollama durchgelaufen. Prüfe jede Belegung vor dem ersten echten Lauf mit `--dry-run`.

**Faustregel:** Ollama ist schnell und kostenlos, solange die Stücke klein sind. Codex lohnt sich dort, wo wenige Tokens viel entscheiden: Plan, Plan-Prüfung und Abnahme.

## Inhalt

1. [Einrichtung von Ollama und Codex](#1-einrichtung-von-ollama-und-codex)
2. [Was du vorher wissen solltest](#2-was-du-vorher-wissen-solltest)
3. [Variante A: Codex plant, Ollama prüft, anderes Ollama-Modell baut, Codex nimmt ab](#variante-a-codex-plant-ollama-prüft-anderes-ollama-modell-baut-codex-nimmt-ab)
4. [Variante B: Ollama plant, Codex prüft, Ollama baut, Codex nimmt ab](#variante-b-ollama-plant-codex-prüft-ollama-baut-codex-nimmt-ab)
5. [Variante C: Alles lokal, nur die Abnahme macht Codex](#variante-c-alles-lokal-nur-die-abnahme-macht-codex)
6. [Variante D: Schwere Aufgabe, Codex baut, Ollama nimmt ab](#variante-d-schwere-aufgabe-codex-baut-ollama-nimmt-ab)
7. [Variante E: Etappen, die Aufgabe in kleinen Stücken](#variante-e-etappen-die-aufgabe-in-kleinen-stücken)
8. [Welche Variante wann?](#welche-variante-wann)
9. [Über MCP: Einrichtung und Aufrufe](#über-mcp-einrichtung-und-aufrufe)
10. [Ollama-Modelle für einen Mac M4 mit 48 GB](#ollama-modelle-für-einen-mac-m4-mit-48-gb)
11. [Checkliste bei Problemen](#checkliste-bei-problemen)

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
| Ollama-Bauleiter hat kein Gedächtnis | Jede Bau-Runde bekommt den ganzen Plan und die Rückmeldung des Prüfbefehls, aber weder die bisherigen Antworten noch den aktuellen Dateistand. Er schreibt jede Datei vollständig neu. | Aufgaben so klein schneiden, dass eine Runde reicht. Für mehr: [Variante E](#variante-e-etappen-die-aufgabe-in-kleinen-stücken). |
| Ollama führt keine Tests aus | Der Bauleiter schreibt nur Dateien. | Immer `--proof "<testbefehl>"` angeben, der Loop führt ihn selbst aus. |
| Urteil nur aus `VERDICT:` | Fehlt die letzte Zeile `VERDICT: APPROVED`, zählt das Review nicht als Freigabe. | Für Prüfer- und Abnahme-Rollen Modelle nehmen, die Formatvorgaben einhalten (siehe [Modelle](#ollama-modelle-für-einen-mac-m4-mit-48-gb)). |
| Zwei Ollama-Rollen | Gleiches Backend mit **verschiedenen Modellen** gilt als andere Identität. Gleiches Modell prüft sich selbst. | Für Architekt/Prüfstatiker bzw. Bauleiter/Abnahme immer unterschiedliche Modelle wählen. |
| Abnahme | Standard ist der Prüfstatiker, nie der Bauleiter. Ist der Prüfstatiker ein anderes Ollama-Modell, nimmt **Ollama** ab, nicht Codex. | Codex als Abnahme ausdrücklich mit `--abnahme codex` setzen. |
| Freigabe-Menü | Nach dem Review fragt der Loop im Terminal nach der Freigabe, vor Phase 3 nach den Schreibrechten. | Im Terminal starten. `--yolo` überspringt nur die Rechte-Frage. |

Die Aufgabe selbst ist dein stärkster Hebel: Schreib in den Aufgabentext, wie der Plan aussehen soll, zum Beispiel „Gliedere den Plan in nummerierte Schritte; jeder Schritt ändert höchstens eine Datei und nennt seinen Test“. Der Architekt bekommt den Text wörtlich.

In allen Beispielen sind `~/Projekte/rechnung` das Projekt und `python3 -m unittest discover -s tests` der Prüfbefehl. Ersetze beides durch dein Projekt und seinen eigenen Testbefehl (z. B. `npm test`, `vendor/bin/phpunit`).

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

> [!NOTE]
> Für den echten Lauf denselben Befehl ohne `--dry-run` verwenden. Der „Generierte Shell-Befehl“ am Ende des Trockenlaufs lässt derzeit `--architekt`, `--pruefstatiker`, `--bauer` und die Effort-Flags weg und ist für diese Varianten nicht vollständig. Außerdem zeigt der Trockenlauf ohne `--abnahme` manchmal Codex als Abnahme, obwohl im echten Lauf ein anderes Ollama-Modell abnehmen würde. Deshalb `--abnahme` immer ausdrücklich setzen.

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

Das ist die Antwort auf „Ollama arbeitet schneller mit kleinen Stücken“. Der Loop teilt eine Aufgabe nicht selbst auf, und ein Ollama-Bauleiter sieht in Runde 2 nicht, was er in Runde 1 geschrieben hat. Deshalb zerlegt Codex die Aufgabe einmal in Etappen, und jede Etappe läuft als eigener kurzer Loop mit dem Stand der vorigen Etappe.

**Schritt 1: Etappen von Codex schneiden lassen** (nur lesend, ohne Loop):

```bash
cd ~/Projekte/rechnung
codex exec -s read-only --output-last-message etappen.txt \
  "Zerlege diese Aufgabe in 3 bis 8 Etappen, die nacheinander umsetzbar sind. Jede Etappe ändert höchstens zwei Dateien und ist danach testbar. Gib nur die Etappen aus, eine pro Zeile, ohne Nummern und ohne Leerzeilen. Aufgabe: CSV-Export für Rechnungen mit Filter nach Zeitraum und Kunde."
cat etappen.txt   # lesen, kürzen, umsortieren: du entscheidest
```

**Schritt 2: Etappen nacheinander bauen**, jede mit Variante A:

```bash
ZIEL="CSV-Export für Rechnungen mit Filter nach Zeitraum und Kunde"
while IFS= read -r etappe <&3; do
  [ -z "$etappe" ] && continue
  echo "=== Etappe: $etappe"
  claudegravity "Gesamtziel: $ZIEL. Setze jetzt NUR diese Etappe um: $etappe" \
    -p ~/Projekte/rechnung \
    --architekt codex --architekt-effort medium \
    --pruefstatiker ollama --pruefstatiker-model gpt-oss:20b \
    --bauer ollama --bauer-model qwen3-coder:30b \
    --abnahme codex \
    --proof "python3 -m unittest discover -s tests" \
    --merge -m 3
done 3< etappen.txt
```

**Handlungsanweisungen**

1. `3< etappen.txt` und `<&3` sind Absicht: So liest die Schleife die Etappen über einen eigenen Kanal, und das Freigabe-Menü des Loops liest weiter von deiner Tastatur.
2. `--merge` ist Pflicht: Erst damit landet jede abgenommene Etappe in deinem Branch und die nächste Etappe baut darauf auf.
3. Der Loop bricht die Schleife nicht von selbst ab. Wird eine Etappe nicht abgenommen, im Freigabe-Menü der nächsten Etappe `[5] Beenden` wählen oder mit Strg+C abbrechen, dann die offene Etappe mit `claudegravity -c -p ~/Projekte/rechnung` fortsetzen.
4. Codex braucht hier pro Etappe einen kleinen Plan und eine Abnahme. Für noch weniger Codex-Verbrauch in Schritt 2 Variante C statt A einsetzen.
5. Unter Windows (PowerShell) sieht die Schleife so aus: `foreach ($etappe in Get-Content etappen.txt) { if ($etappe) { .\claudegravity.ps1 "Gesamtziel: $ZIEL. Setze jetzt NUR diese Etappe um: $etappe" <weitere Flags wie oben> } }`.

## Welche Variante wann?

| Situation | Variante | Codex-Verbrauch |
| :--- | :--- | :--- |
| Mittlere Aufgabe in bestehendem Projekt | A | Plan + Abnahme |
| Neues kleines Projekt, Plan darf lokal entstehen | B | Review + Abnahme |
| Kleiner Fix mit bekannten Dateien | C | nur Abnahme |
| Großer Umbau, viele Dateien, Tests im Projekt | D | Review + gesamter Bau |
| Größere Aufgabe, aber lokal bauen | E | Etappen + je Etappe Plan und Abnahme |

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

**2. Befehl berechnen lassen**: Tool `claudegravity_optimize`:

```json
{
  "task": "Füge einen CSV-Export für Rechnungen hinzu",
  "priority": "local-free",
  "project_path": "/Users/<name>/Projekte/rechnung",
  "proof": "python3 -m unittest discover -s tests",
  "max_iterations": 6
}
```

Sind außer Codex und Ollama keine weiteren CLIs installiert, ergibt das `claudegravity '…' --strategy local-free --bauer-model qwen2.5-coder:latest --proof '…' -m 6 -p …`. Im Lauf wird daraus ungefähr Variante A: Codex plant, `ollama run qwen2.5-coder:latest` prüft, der Ollama-Server baut mit `qwen2.5-coder:latest`, Codex nimmt ab. Ist zusätzlich `claude` installiert, plant Claude statt Codex.

> [!WARNING]
> Die MCP-Tools kennen keine Rollen- oder Modell-Parameter. Die Modellnamen, die `claudegravity_optimize` für Architekt und Prüfstatiker anzeigt (z. B. `gemini-2.5-pro`), sind Vorgaben für Claude/Gemini und gelten für Codex und Ollama nicht. Den Bauleiter-Wert `qwen2.5-coder:latest` musst du vorher mit `ollama pull qwen2.5-coder` laden. Für die Varianten A bis E mit eigenen Modellen den Befehl von dieser Seite verwenden.

**3. Eine Variante über den Assistenten starten**: Weil die Tools keine Rollen annehmen, gibst du dem Assistenten den fertigen Befehl. Beispiel für den Prompt in Codex oder Claude Code:

```text
Starte im Terminal claudegravity nach Variante A aus docs/de/ollama-und-codex.md
für das Projekt ~/Projekte/rechnung mit der Aufgabe „CSV-Export für Rechnungen“.
Führe zuerst denselben Befehl mit --dry-run aus und zeig mir die Belegung.
```

Mit dem Skill [`skills/claudegravity`](../../skills/claudegravity/SKILL.md) kennt der Assistent die Rollen-Flags bereits.

**4. `claudegravity_run`**: mit `background: false` liefert das Tool nur den Befehl mit `cd` zum Kopieren. `background: true` ist für diese Varianten nicht geeignet: Freigabe-Menü und Rechte-Frage brauchen ein Terminal.

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
