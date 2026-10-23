# Backends: CLIs, lokale Modelle & eigene Server

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/backends.md)

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
| `ollama` | Server antwortet auf `http://localhost:11434` oder auf die Adresse in `OLLAMA_HOST` | OpenAI-API (`/v1/chat/completions`) | aus `usage`, sonst geschätzt |
| `lmstudio` | Server antwortet auf `http://localhost:1234` | OpenAI-API | aus `usage`, sonst geschätzt |
| `endpoint` | `--endpoint` oder Umgebungsvariable gesetzt | OpenAI-API | aus `usage`, sonst geschätzt |
| `architekt_ep`, `pruefstatiker_ep`, `bauer_ep` | `--architekt-endpoint` / `--pruefstatiker-endpoint` / `--bauer-endpoint` | OpenAI-API | aus `usage` |

Die lokalen Server werden mit einem kurzen GET geprüft (0,3 s, für `OLLAMA_HOST` im Netz 1,5 s). Läuft Ollama oder LM Studio erst nach dem Start von ClaudeGravity an, wird es nicht erkannt.

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

Jeder OpenAI-kompatible Server (vLLM, Ollama, Open WebUI, LiteLLM, z. B. `https://ki.firma.intern/v1`) funktioniert. Die URL wird normalisiert: `https://host`, `https://host/v1` und `https://host/v1/chat/completions` sind gleichwertig.

### Per Befehlszeile

```bash
claudegravity "Erstelle Unit-Tests für das API-Gateway" \
  --strategy local-free \
  --endpoint http://192.168.1.50:11434/v1 \
  --bauer endpoint --bauer-model qwen2.5-coder:7b
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
export CLAUDEGRAVITY_ENDPOINT="http://192.168.1.50:11434/v1"
```

Windows PowerShell (Profil, z. B. `$PROFILE`):
```powershell
$env:CLAUDEGRAVITY_ENDPOINT = "http://192.168.1.50:11434/v1"
```

Windows dauerhaft für den Benutzer:
```cmd
setx CLAUDEGRAVITY_ENDPOINT "http://192.168.1.50:11434/v1"
```

> [!CAUTION]
> Einen API-Key besser per Umgebungsvariable als per `--api-key` übergeben: Befehlszeilen landen in der Shell-Historie und sind für andere Prozesse sichtbar.

### Ollama & Co. aus dem lokalen Netzwerk

Ein Modellserver muss nicht auf demselben Rechner laufen. Ein Rechner im Heimnetz (z. B. ein Raspberry Pi oder ein PC mit Grafikkarte) kann für alle anderen Geräte bauen.

**1. Server im Netz erreichbar machen.** Ollama hört ab Werk nur auf `127.0.0.1`.

| System | Einstellung |
| :--- | :--- |
| Linux (systemd) | `sudo systemctl edit ollama`, dort `[Service]` und `Environment="OLLAMA_HOST=0.0.0.0:11434"` eintragen, dann `sudo systemctl restart ollama` |
| macOS | `launchctl setenv OLLAMA_HOST "0.0.0.0:11434"`, danach die Ollama-App neu starten |
| Windows | Benutzer-Umgebungsvariable `OLLAMA_HOST` = `0.0.0.0:11434` setzen, Ollama neu starten |
| LM Studio | *Developer → Server Settings → Serve on Local Network* einschalten (Port 1234) |

Den Port in der Firewall nur fürs Heimnetz öffnen, z. B. `sudo ufw allow from 192.168.0.0/16 to any port 11434`.

**2. Vom eigenen Rechner aus prüfen.** Gib dem Server im Router eine feste IP oder nutze seinen Namen im Heimnetz (z. B. `server.local` oder `server.fritz.box`).

```bash
curl http://<server>:11434/api/tags     # Ollama: installierte Modelle mit exakten Namen
curl http://<server>:11434/v1/models    # OpenAI-kompatible Liste (Ollama, LM Studio, LiteLLM)
```

**3. In ClaudeGravity verwenden.** Setzt du auf deinem Rechner `OLLAMA_HOST=<server>:11434` (dieselbe Variable wie für die Ollama-CLI), erkennt ClaudeGravity den Server als `ollama`. Sonst gibst du ihn selbst an, mit dem Modellnamen genau so, wie `/api/tags` ihn meldet:

```bash
claudegravity "Schreibe Unit-Tests" --strategy local-free \
  --bauer-endpoint http://<server>:11434/v1 --bauer bauer_ep --bauer-model qwen2.5-coder:7b
```

Dauerhaft geht es mit `export CLAUDEGRAVITY_ENDPOINT="http://<server>:11434/v1"` und `--bauer endpoint`.

**Gateways mit Schlüssel** (LiteLLM, eigener Router, Open WebUI) brauchen ein Bearer-Token in `CLAUDEGRAVITY_API_KEY`. Bei Open WebUI heißt die OpenAI-Adresse `/api/chat/completions`; dort die volle URL angeben: `--endpoint https://<server>/api/chat/completions`. Die Modellnamen liefert `/api/models`.

> [!WARNING]
> Ollama und LM Studio haben keine Anmeldung. Port 11434 bzw. 1234 nie im Router nach außen freigeben. Für den Zugriff von unterwegs ein VPN nutzen.

> [!NOTE]
> Kleine Modelle auf schwacher Hardware (z. B. 7B auf einer CPU) brauchen für eine längere Datei mehrere Minuten. Endpunkte im Heimnetz bekommen deshalb 900 Sekunden pro Runde, Cloud-Endpunkte 180. Reicht das nicht: `--timeout 1800` oder `CLAUDEGRAVITY_TIMEOUT=1800`. Als Heimnetz gelten `localhost`, private IPs und Rechnernamen ohne Punkt oder mit `.local`, `.lan`, `.fritz.box`, `.home.arpa`, `.internal`; sie stehen im Audit mit 0 €.
>
> CLIs (`claude`, `codex`, `agy` …) haben ein eigenes Zeitlimit von 3600 Sekunden je Aufruf, damit ein hängender Prozess den Loop nicht ewig blockiert. Ändern mit `CLAUDEGRAVITY_CLI_TIMEOUT=<Sekunden>`, `0` schaltet es ab. Ein überschrittenes CLI-Zeitlimit wird nicht automatisch wiederholt.

### Wie Endpunkt-Bauleiter Dateien schreiben

Endpunkte haben keinen Dateizugriff. ClaudeGravity fordert sie auf, neue Dateien vollständig auszugeben:

````
```filepath: src/app.py
<vollständiger Dateiinhalt>
```
````

Bestehende Dateien dürfen sie sparsamer mit Suchen/Ersetzen-Blöcken ändern. Das spart Ausgabe-Tokens, und gerade lokale Modelle sind bei der Ausgabe langsam und stoßen bei großen Dateien an ihr Ausgabelimit:

````
```edit: src/app.py
<<<<<<< SUCHEN
    return a - b
=======
    return a + b
>>>>>>> ERSETZEN
```
````

Ein Block darf mehrere Paare enthalten; `SEARCH`/`REPLACE` geht auch. Jeder Suchtext muss in der Datei genau einmal vorkommen. Passt ein Paar nicht (nicht gefunden, mehrdeutig, Datei fehlt), bleibt die ganze Datei unverändert, und der Bauleiter bekommt den Fehler in der nächsten Runde zusammen mit dem aktuellen Dateistand zurück.

Auch Überschriften wie `### Datei: src/app.py` direkt vor einem Codeblock werden erkannt. Die Blöcke werden relativ zum Projektordner geschrieben. Pfade außerhalb des Projekts (`../`, absolute Pfade, `~`) und Geheimnis-Dateien (`.env`, `.ssh/`, `.git/`, `*.key`, `*.pem`, `credentials.json` …) werden blockiert und mit `[!] Blockiert` gemeldet. Den genehmigten Plan bekommen Endpunkt-Bauleiter als Text mit, weil sie die Plan-Datei nicht selbst öffnen können. Die Fertigmeldung erfolgt genauso über einen Block mit dem `.done`-Pfad.

Die Anfrage nutzt `temperature: 0.2` und ein Timeout von 900 Sekunden pro Runde im Heimnetz bzw. 180 Sekunden sonst (`--timeout`). HTTP 429 wird als Ratenlimit behandelt.

## Rechte & YOLO

Mit `--yolo` (oder „J“ bei der Rechte-Abfrage vor Phase 3) werden diese Flags gesetzt:

| CLI | Flags |
| :--- | :--- |
| `claude`, `agy` | `--dangerously-skip-permissions` |
| `gemini` | `-y` |
| `codex` | `-s workspace-write` |
| Endpunkte, `ollama`, `copilot` | keine (Dateien schreibt ClaudeGravity selbst) |

Diese Flags bekommt **nur der Bauleiter**. Architekt, Prüfstatiker und Abnahme laufen immer lesend, auch mit `--yolo`:

| CLI | Flags für lesende Rollen |
| :--- | :--- |
| `claude` | `--permission-mode dontAsk --tools Read,Glob,Grep --allowedTools Read,Glob,Grep --strict-mcp-config` (keine Shell, kein Schreiben, keine MCP-Server) |
| `codex` | `-s read-only` |
| `agy`, `gemini` | keine Rechte-Flags (Werkzeuge mit Rückfrage werden ohne Terminal abgelehnt) |

Prompts gehen bei `claude`, `codex`, `gemini` und `ollama` über stdin, nicht über die Kommandozeile. So tauchen Aufgabe und Plan nicht in der Prozessliste auf und werden unter Windows nicht an der Längengrenze (~32 KB) abgeschnitten.

> [!WARNING]
> Im YOLO-Modus darf der Bauleiter ohne Rückfrage Dateien ändern und Befehle ausführen. Nutze ihn nur in Projekten unter Versionskontrolle.
