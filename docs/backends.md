# Backends: CLIs, lokale Modelle & eigene Server

[← Zurück zur Übersicht](../README.md) · [Dokumentations-Index](README.md)

Jede Rolle kann mit einem beliebigen erkannten Backend besetzt werden. Welche Backends auf deinem Rechner verfügbar sind, zeigt `claudegravity --info`.

## Erkannte Backends

| Schlüssel (für `--architekt`, `--pruefstatiker`, `--bauer`) | Erkennung | Aufruf durch ClaudeGravity | Token-Erfassung |
| :--- | :--- | :--- | :--- |
| `claude` | `claude` im `PATH` | `claude -p <prompt> --output-format json` | exakt (inkl. Kosten aus `total_cost_usd`) |
| `agy` | `agy` im `PATH` | `agy -p <prompt> --output-format json` | exakt (inkl. Thinking-Tokens) |
| `gemini` | `gemini` im `PATH` | `gemini -p <prompt>` | geschätzt (Zeichen / 4) |
| `codex` | `codex` im `PATH` | `codex exec -s <sandbox> <prompt>` | geschätzt |
| `copilot` | `copilot` oder `gh` im `PATH` | `copilot suggest -t shell …` bzw. `gh copilot suggest …` | geschätzt |
| `ollama-cli` | `ollama` im `PATH` | `ollama run <modell> <prompt>` | geschätzt |
| `ollama` | Server antwortet auf `http://localhost:11434` | OpenAI-API (`/v1/chat/completions`) | aus `usage`, sonst geschätzt |
| `lmstudio` | Server antwortet auf `http://localhost:1234` | OpenAI-API | aus `usage`, sonst geschätzt |
| `endpoint` | `--endpoint` oder Umgebungsvariable gesetzt | OpenAI-API | aus `usage`, sonst geschätzt |
| `gb-web` | wie `endpoint`, wenn die URL `ai.gb-web.de` enthält | OpenAI-API | aus `usage` |
| `architekt_ep`, `pruefstatiker_ep`, `bauer_ep` | `--architekt-endpoint` / `--pruefstatiker-endpoint` / `--bauer-endpoint` | OpenAI-API | aus `usage` |

Die lokalen Server werden mit einem kurzen GET (0,3 s Timeout) geprüft. Läuft Ollama oder LM Studio erst nach dem Start von ClaudeGravity an, wird es nicht erkannt.

## Lokale Modelle

### Ollama

```bash
ollama run qwen2.5-coder:32b      # Modell laden, Server läuft auf Port 11434
claudegravity "Baue ein REST-Interface" --strategy local-free --bauer ollama --bauer-model qwen2.5-coder:32b
```

Ohne `--bauer-model` nutzt der Ollama-Server-Bauleiter `qwen2.5-coder:latest`.

### LM Studio

In LM Studio *Local Server → Start Server* wählen. Danach:

```bash
claudegravity "Schreibe Unit-Tests" --strategy local-free --bauer lmstudio
```

## Eigene Server im Netzwerk / Intranet

Jeder OpenAI-kompatible Server (vLLM, Ollama, Open WebUI, LiteLLM, z. B. `https://ai.gb-web.de/v1`) funktioniert. Die URL wird normalisiert: `https://host`, `https://host/v1` und `https://host/v1/chat/completions` sind gleichwertig.

### Per Befehlszeile

```bash
claudegravity "Erstelle Unit-Tests für das API-Gateway" \
  --strategy local-free \
  --endpoint https://ai.gb-web.de/v1 \
  --bauer endpoint --bauer-model qwen2.5-coder:32b
```

### Pro Rolle ein eigener Server

```bash
claudegravity "Auth-Refactoring" \
  --architekt claude \
  --pruefstatiker-endpoint https://review.intern/v1 --pruefstatiker pruefstatiker_ep \
  --bauer-endpoint http://localhost:11434/v1 --bauer bauer_ep --bauer-model qwen2.5-coder:32b
```

### Dauerhaft per Umgebungsvariable

| Variable | Bedeutung |
| :--- | :--- |
| `CLAUDEGRAVITY_ENDPOINT` | Standard-Endpunkt (höchste Priorität nach `--endpoint`) |
| `OPENAI_BASE_URL` | Alternative, wird genutzt, wenn `CLAUDEGRAVITY_ENDPOINT` fehlt |
| `AI_ENDPOINT` | Weitere Alternative |
| `CLAUDEGRAVITY_API_KEY` / `OPENAI_API_KEY` | Bearer-Token für geschützte Endpunkte (`--api-key` hat Vorrang; `OPENAI_API_KEY` wird zuerst gelesen) |

Linux / macOS (`~/.bashrc` oder `~/.zshrc`):
```bash
export CLAUDEGRAVITY_ENDPOINT="https://ai.gb-web.de/v1"
```

Windows PowerShell (Profil, z. B. `$PROFILE`):
```powershell
$env:CLAUDEGRAVITY_ENDPOINT = "https://ai.gb-web.de/v1"
```

Windows dauerhaft für den Benutzer:
```cmd
setx CLAUDEGRAVITY_ENDPOINT "https://ai.gb-web.de/v1"
```

> [!CAUTION]
> Einen API-Key besser per Umgebungsvariable als per `--api-key` übergeben: Befehlszeilen landen in der Shell-Historie und sind für andere Prozesse sichtbar.

### Wie Endpunkt-Bauleiter Dateien schreiben

Endpunkte haben keinen Dateizugriff. ClaudeGravity fordert sie auf, jede Datei so auszugeben:

````
```filepath: src/app.py
<vollständiger Dateiinhalt>
```
````

Auch Überschriften wie `### Datei: src/app.py` direkt vor einem Codeblock werden erkannt. Die Blöcke werden relativ zum Projektordner geschrieben. Die Fertigmeldung erfolgt genauso über einen Block mit dem `.done`-Pfad.

Die Anfrage nutzt `temperature: 0.2` und ein Timeout von 180 Sekunden pro Runde. HTTP 429 wird als Ratenlimit behandelt.

## Rechte & YOLO

Mit `--yolo` (oder „J“ bei der Rechte-Abfrage vor Phase 3) werden diese Flags gesetzt:

| CLI | Flags |
| :--- | :--- |
| `claude`, `agy` | `--dangerously-skip-permissions` |
| `gemini` | `-y` |
| `codex` | gedacht: Sandbox `workspace-write`. Aktuell läuft `codex exec` jedoch immer mit `-s read-only`, siehe [Bekannte Einschränkungen](fehlerbehebung.md#bekannte-einschränkungen). |
| Endpunkte, `ollama`, `copilot` | keine (Dateien schreibt ClaudeGravity selbst) |

> [!WARNING]
> Im YOLO-Modus darf der Agent ohne Rückfrage Dateien ändern und Befehle ausführen. Nutze ihn nur in Projekten unter Versionskontrolle.
