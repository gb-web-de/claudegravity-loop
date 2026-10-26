# Sandbox: Prüfbefehl und Bauleiter im Container

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/sandbox.md)

Ohne Sandbox laufen der Prüfbefehl und ein CLI-Bauleiter mit deinen Benutzerrechten: Modell-Code sieht dein Home mit SSH-Schlüsseln, Browser-Profilen und anderen Projekten. Mit `--sandbox an` startet der Loop beides in einem frischen Container (Docker oder Podman), der nur den Arbeitsordner sieht. Das verkleinert die Bedrohungen B8 und B9 aus dem [Bedrohungsmodell](sicherheit.md).

## Schnell

```bash
# Prüfbefehl im Container; reicht für Endpunkt-Bauleiter (Ollama, LM Studio, eigene Server)
claudegravity "Aufgabe" --strategy local-free --sandbox an --proof "python -m unittest"

# Auch der CLI-Bauleiter im Container: einmal das Image mit den KI-CLIs bauen
docker build -t claudegravity-sandbox sandbox/
claudegravity "Aufgabe" --bauer claude --sandbox an --sandbox-image claudegravity-sandbox --proof "python -m pytest -q"
```

Ohne Klon des Repositories (z. B. nach `pipx install`) baust du das Image direkt von GitHub: `docker build -t claudegravity-sandbox "https://github.com/gb-web-de/claudegravity-loop.git#main:sandbox"`.

## Was im Container läuft

| Teil | Im Container | Netz | Sieht |
| :--- | :--- | :--- | :--- |
| Prüfbefehl (`--proof`) | ja | aus (mit `--sandbox-net` an) | den Arbeitsordner |
| CLI-Bauleiter (`claude`, `codex`, `gemini`, `copilot`, `agy`) | ja, unter Linux und macOS | an, er braucht sein Modell | Arbeitsordner, Session-Ordner und die Anmeldedaten dieser einen CLI |
| Endpunkt-Bauleiter | nicht nötig: Er schreibt nichts selbst, der Loop legt seine Dateien über `resolve_project_target()` an | – | – |
| Architekt, Prüfstatiker, Abnahme | nein, sie laufen ohnehin lesend | – | – |
| Kandidaten (`--candidates`) | jeder Kandidat wie oben; der Hauptlauf prüft sie im Container | wie oben | wie oben |

Der Kopf des Laufs zeigt die Belegung, z. B. `[*] Sandbox : 🐳 docker (claudegravity-sandbox): Prüfbefehl und CLI-Bauleiter, Prüfbefehl ohne Netz`.

## So ist der Container eingerichtet

* Ein frischer Container pro Aufruf (`--rm`, Name `claudegravity-…`); nach einer Zeitüberschreitung entfernt der Loop ihn.
* Deine Benutzer-ID (`--user uid:gid`, bei Podman `--userns keep-id`), damit neue Dateien dir gehören.
* Keine Capabilities (`--cap-drop ALL`), `no-new-privileges`, Grenzen von 512 Prozessen, 4 GB Speicher und 2 CPUs.
* `HOME` und `/tmp` sind leer (tmpfs). Aus deinem Home kommen nur die Anmeldedaten der CLI, die gerade baut.
* Der Arbeitsordner liegt im Container am selben Pfad (unter Windows `/work`), damit Pfade in Plan, Ausgaben und Fehlermeldungen stimmen.
* Liegt ein `.git`-Ordner direkt im Arbeitsordner (mit `--no-worktree`), verdeckt ihn der Loop im Container mit einem leeren Ordner, denn `.git/config` kann Tokens enthalten. Im Git-Workspace (Standard) gibt es dort nur die Datei `.git`; Git-Befehle im Container gehen dann nicht, weil das Haupt-Repository nicht eingebunden ist. Committen macht der Loop selbst.

## Anmeldedaten

Nur die Ordner der CLI, die baut, werden eingebunden, und zwar beschreibbar, weil die CLIs ihre Tokens erneuern:

| CLI | aus deinem Home |
| :--- | :--- |
| `claude` | `~/.claude`, `~/.claude.json` |
| `codex` | `~/.codex` |
| `gemini`, `agy` | `~/.gemini` |
| `copilot`, `gh` | `~/.copilot`, `~/.config/gh` |

Dazu gibt der Loop diese Umgebungsvariablen weiter, sofern sie gesetzt sind: `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `CLAUDE_CODE_OAUTH_TOKEN`, `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `CODEX_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_GENAI_USE_VERTEXAI`, `GH_TOKEN`, `GITHUB_TOKEN`, `COPILOT_GITHUB_TOKEN` und die Proxy-Variablen. Im Befehl steht nur der Name (`-e NAME`), der Wert kommt aus der Umgebung; in der Prozessliste taucht er nicht auf.

* **macOS:** Claude Code legt die Anmeldung im Schlüsselbund ab, an den der Container nicht kommt. Mit `claude setup-token` einen Token erzeugen und `CLAUDE_CODE_OAUTH_TOKEN` in deiner Shell setzen (nicht im Projekt). Für Copilot gilt dasselbe mit `COPILOT_GITHUB_TOKEN` oder `GH_TOKEN`.
* Codex und Gemini legen die Anmeldung standardmäßig als Datei ab. Klappt sie im Container nicht, `CODEX_API_KEY` bzw. `GEMINI_API_KEY` setzen.

## Image

* **Standard `python:3.12-slim`:** genug für `python -m unittest` und für Endpunkt-Bauleiter. Für einen CLI-Bauleiter braucht es ein Image mit der CLI.
* **`sandbox/Dockerfile`** bringt Node 22, Python 3, Git, ripgrep, pytest und die CLIs `claude`, `codex`, `gemini` und `copilot` mit. Nur einzelne CLIs: `docker build --build-arg CLIS="@anthropic-ai/claude-code" -t claudegravity-sandbox sandbox/`. Antigravity (`agy`) gibt es nicht über npm; wer es im Container braucht, ergänzt es im eigenen Image.
* **Abhängigkeiten des Projekts** gehören in ein eigenes Image auf dieser Basis, denn der Prüfbefehl hat kein Netz:

  ```dockerfile
  FROM claudegravity-sandbox
  COPY requirements.txt /tmp/
  RUN python3 -m pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt
  ```

  Muss der Prüfbefehl doch etwas laden (z. B. `npm ci && npm test`), schaltet `--sandbox-net` das Netz für ihn ein.
* **Vor dem Bau prüft der Loop**, ob die Engine läuft ([CG-1701](fehlerbehebung.md#cg-1701)) und ob das Image die CLI des Bauleiters und das Programm des Prüfbefehls enthält ([CG-1702](fehlerbehebung.md#cg-1702)). Beim ersten Mal lädt die Engine das Image herunter, das kann dauern.

## Einstellungen

* `--sandbox an|docker|podman|aus` (auch `on`/`off`): `an` nimmt Docker, wenn es installiert ist, sonst Podman.
* `--sandbox-image <image>` und `--sandbox-net` wie oben.
* Über die Umgebung (`CLAUDEGRAVITY_SANDBOX=an`, `CLAUDEGRAVITY_SANDBOX_IMAGE=…`) oder das globale Profil dauerhaft einschalten. Aus dem Projekt-Profil wirken die drei Einstellungen nicht: Ein fremdes Repository soll die Sandbox weder abschalten noch ein Image wählen können, das deine Anmeldedaten bekommt.
* `claudegravity -c` setzt mit derselben Sandbox fort; `--dry-run` zeigt die Schalter im Befehl.

## Grenzen

* **Windows:** Nur der Prüfbefehl läuft im Container, ein CLI-Bauleiter weiter mit deinen Rechten (der Loop warnt). Für beides WSL nehmen.
* **Der Bauleiter hat Netz und seine eigenen Anmeldedaten.** Er kann den Arbeitsordner und seinen Token nach außen geben. Die Sandbox schützt den Rest deines Rechners, nicht das Projekt selbst.
* **Ein Container ist keine VM:** Der Kernel ist geteilt. Für Code, dem du gar nicht traust, eine VM nehmen.
* **Docker mit Root-Daemon:** Wer in der Gruppe `docker` ist, hat praktisch Root-Rechte. Rootless Podman oder rootless Docker sind die bessere Wahl.
* **Docker Desktop unter macOS:** Der Arbeitsordner muss in einem freigegebenen Ordner liegen (Standard: `/Users`); Dateizugriffe sind langsamer als nativ.
* Pfade mit Komma lassen sich nicht einbinden; Prüfbefehl bzw. Bauleiter-Aufruf scheitern dann mit dieser Meldung.

Mehr: [Sicherheit](sicherheit.md) (B8, B9), [CLI-Referenz](cli-referenz.md#sandbox), [Bau-Loop](bau-loop.md).
