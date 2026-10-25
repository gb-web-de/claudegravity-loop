# Backends: CLIs, local models & your own servers

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/backends.md)

Every role can be assigned to any detected backend. `claudegravity --info` shows which backends are available on your machine.

## Detected backends

| Key (for `--architekt`, `--pruefstatiker`, `--bauer`) | Detection | How ClaudeGravity calls it | Token tracking |
| :--- | :--- | :--- | :--- |
| `claude` | `claude` in `PATH` | `claude -p <prompt> --output-format json` | exact (incl. cost from `total_cost_usd`) |
| `agy` | `agy` in `PATH` | `agy -p <prompt> --output-format json` | exact (incl. thinking tokens) |
| `gemini` | `gemini` in `PATH` | `gemini -p <prompt>` | estimated (characters / 4) |
| `codex` | `codex` in `PATH` | `codex exec -s <sandbox> <prompt>` | estimated |
| `copilot` | `copilot` or `gh` in `PATH` | `copilot suggest -t shell …` or `gh copilot suggest …` | estimated |
| `ollama-cli` | `ollama` in `PATH` | `ollama run <modell> <prompt>` | estimated |
| `ollama` | Server responds on `http://localhost:11434` or on the address in `OLLAMA_HOST` | OpenAI API (`/v1/chat/completions`) | from `usage`, otherwise estimated |
| `lmstudio` | Server responds on `http://localhost:1234` | OpenAI API | from `usage`, otherwise estimated |
| `endpoint` | `--endpoint` or environment variable set | OpenAI API | from `usage`, otherwise estimated |
| `architekt_ep`, `pruefstatiker_ep`, `bauer_ep` | `--architekt-endpoint` / `--pruefstatiker-endpoint` / `--bauer-endpoint` | OpenAI API | from `usage` |

Local servers are checked with a short GET (0.3 s, 1.5 s for an `OLLAMA_HOST` on the network). If Ollama or LM Studio only starts after ClaudeGravity has started, it is not detected.

## Local models

### Ollama

```bash
ollama run qwen2.5-coder:32b      # load the model, server runs on port 11434
claudegravity "Build a REST interface" --strategy local-free --bauer ollama --bauer-model qwen2.5-coder:32b
```

Without `--bauer-model`, the Ollama server Builder uses `qwen2.5-coder:latest`.

### LM Studio

In LM Studio choose *Local Server → Start Server*. Then:

```bash
claudegravity "Write unit tests" --strategy local-free --bauer lmstudio
```

## Your own servers on the network / intranet

Any OpenAI-compatible server (vLLM, Ollama, Open WebUI, LiteLLM, e.g. `https://ki.firma.intern/v1`) works. The URL is normalized: `https://host`, `https://host/v1` and `https://host/v1/chat/completions` are equivalent.

### Via the command line

```bash
claudegravity "Create unit tests for the API gateway" \
  --strategy local-free \
  --endpoint http://192.168.1.50:11434/v1 \
  --bauer endpoint --bauer-model qwen2.5-coder:7b
```

### A separate server per role

```bash
claudegravity "Auth refactoring" \
  --architekt claude \
  --pruefstatiker-endpoint https://review.intern/v1 --pruefstatiker pruefstatiker_ep \
  --bauer-endpoint http://localhost:11434/v1 --bauer bauer_ep --bauer-model qwen2.5-coder:32b
```

### Permanently via environment variable

| Variable | Meaning |
| :--- | :--- |
| `CLAUDEGRAVITY_ENDPOINT` | Default endpoint (highest priority after `--endpoint`) |
| `OPENAI_BASE_URL` | Alternative, used if `CLAUDEGRAVITY_ENDPOINT` is missing |
| `AI_ENDPOINT` | Another alternative |
| `CLAUDEGRAVITY_API_KEY` / `OPENAI_API_KEY` | Bearer token for protected endpoints (`--api-key` takes precedence; `OPENAI_API_KEY` is read first) |

Linux / macOS (`~/.bashrc` or `~/.zshrc`):
```bash
export CLAUDEGRAVITY_ENDPOINT="http://192.168.1.50:11434/v1"
```

Windows PowerShell (profile, e.g. `$PROFILE`):
```powershell
$env:CLAUDEGRAVITY_ENDPOINT = "http://192.168.1.50:11434/v1"
```

Windows, permanently for the user:
```cmd
setx CLAUDEGRAVITY_ENDPOINT "http://192.168.1.50:11434/v1"
```

> [!CAUTION]
> Pass an API key via environment variable rather than `--api-key`: command lines end up in the shell history and are visible to other processes.

### Ollama & co. from the local network

A model server does not have to run on the same machine. A machine on your home network (e.g. a Raspberry Pi or a PC with a graphics card) can build for all other devices.

**1. Make the server reachable on the network.** Out of the box, Ollama only listens on `127.0.0.1`.

| System | Setting |
| :--- | :--- |
| Linux (systemd) | `sudo systemctl edit ollama`, add `[Service]` and `Environment="OLLAMA_HOST=0.0.0.0:11434"` there, then `sudo systemctl restart ollama` |
| macOS | `launchctl setenv OLLAMA_HOST "0.0.0.0:11434"`, then restart the Ollama app |
| Windows | Set the user environment variable `OLLAMA_HOST` = `0.0.0.0:11434`, restart Ollama |
| LM Studio | Enable *Developer → Server Settings → Serve on Local Network* (port 1234) |

Open the port in the firewall for the home network only, e.g. `sudo ufw allow from 192.168.0.0/16 to any port 11434`.

**2. Check from your own machine.** Give the server a fixed IP in your router or use its name on the home network (e.g. `server.local` or `server.fritz.box`).

```bash
curl http://<server>:11434/api/tags     # Ollama: installed models with exact names
curl http://<server>:11434/v1/models    # OpenAI-compatible list (Ollama, LM Studio, LiteLLM)
```

**3. Use it in ClaudeGravity.** If you set `OLLAMA_HOST=<server>:11434` on your machine (the same variable as for the Ollama CLI), ClaudeGravity detects the server as `ollama`. Otherwise you specify it yourself, with the model name exactly as `/api/tags` reports it:

```bash
claudegravity "Write unit tests" --strategy local-free \
  --bauer-endpoint http://<server>:11434/v1 --bauer bauer_ep --bauer-model qwen2.5-coder:7b
```

To make it permanent, use `export CLAUDEGRAVITY_ENDPOINT="http://<server>:11434/v1"` and `--bauer endpoint`.

**Gateways with a key** (LiteLLM, your own router, Open WebUI) need a bearer token in `CLAUDEGRAVITY_API_KEY`. In Open WebUI the OpenAI address is `/api/chat/completions`; specify the full URL there: `--endpoint https://<server>/api/chat/completions`. The model names are provided by `/api/models`.

> [!WARNING]
> Ollama and LM Studio have no authentication. Never forward port 11434 or 1234 to the outside in your router. Use a VPN for access on the go.

> [!NOTE]
> Small models on weak hardware (e.g. 7B on a CPU) take several minutes for a longer file. Endpoints on the home network therefore get 900 seconds per round, cloud endpoints 180. If that is not enough: `--timeout 1800` or `CLAUDEGRAVITY_TIMEOUT=1800`. `localhost`, private IPs and hostnames without a dot or ending in `.local`, `.lan`, `.fritz.box`, `.home.arpa`, `.internal` count as home network; they appear in the audit at €0.
>
> CLIs (`claude`, `codex`, `agy` …) have their own time limit of 3600 seconds per call, so a hung process cannot block the loop forever. Change it with `CLAUDEGRAVITY_CLI_TIMEOUT=<seconds>`, `0` turns it off. An exceeded CLI time limit is not retried automatically.

### Model names with Antigravity (`agy`)

From version 1.4 on, the Antigravity CLI expects model names with the effort level built in, e.g. `Gemini 3.8 Flash (Medium)` or `Gemini 4 Argon (High)`. `agy` prints the list itself when a name does not fit. ClaudeGravity translates short names such as `--bauer-model gemini-3.8-flash --bauer-effort low` into `Gemini 3.8 Flash (Low)` and then leaves out `--effort`. Without an effort it uses `(Medium)`; `xhigh` and `max` become `(High)`. If `agy` still rejects the name, the loop reads the list from the error message, picks the matching entry and retries the call once. If nothing matches, the role continues with the CLI's default model. When no model is chosen (shown as `CLI-Default`), the loop passes neither `--model` nor an empty `--effort`.

Reading roles run `agy` with `--mode plan`. If `agy` tries to start a command such as `pytest` there, it is refused without approval and `agy` ends the turn without any answer text (while still reporting success). The reviewer and the acceptance check are therefore asked not to start commands; the loop runs the proof command itself. If an empty answer still comes back, the loop asks once in the same conversation (`--conversation <id>`) for the result.

### How endpoint builders write files

Endpoints have no file access. ClaudeGravity asks them to output new files completely:

````
```filepath: src/app.py
<complete file content>
```
````

Existing files can be changed more cheaply with search/replace blocks. This saves output tokens; local models in particular are slow at output and hit their output limit on large files:

````
```edit: src/app.py
<<<<<<< SUCHEN
    return a - b
=======
    return a + b
>>>>>>> ERSETZEN
```
````

A block may hold several pairs; `SEARCH`/`REPLACE` works too. Each search text must occur exactly once in the file. If a pair doesn't fit (not found, ambiguous, file missing), the whole file stays unchanged and the Builder gets the error back in the next round together with the current file content.

Headings such as `### Datei: src/app.py` directly before a code block are recognized as well. The blocks are written relative to the project folder. Paths outside the project (`../`, absolute paths, `~`) and secret files (`.env`, `.ssh/`, `.git/`, `*.key`, `*.pem`, `credentials.json` …) are blocked and reported with `[!] Blockiert`. Endpoint Builders receive the approved plan as text, because they cannot open the plan file themselves. They report completion the same way, via a block with the `.done` path.

The request uses `temperature: 0.2` and a timeout of 900 seconds per round on the home network, 180 seconds otherwise (`--timeout`). HTTP 429 is treated as a rate limit.

## Permissions & YOLO

With `--yolo` (or "J" at the permissions prompt before phase 3) these flags are set:

| CLI | Flags |
| :--- | :--- |
| `claude`, `agy` | `--dangerously-skip-permissions` |
| `gemini` | `-y` |
| `codex` | `-s workspace-write` |
| Endpoints, `ollama`, `copilot` | none (ClaudeGravity writes the files itself) |

**Only the Builder** gets these flags. Architect, Reviewer and the Acceptance check (`--abnahme`) always run read-only, even with `--yolo`:

| CLI | Flags for read-only roles |
| :--- | :--- |
| `claude` | `--permission-mode dontAsk --tools Read,Glob,Grep --allowedTools Read,Glob,Grep --strict-mcp-config` (no shell, no writing, no MCP servers) |
| `codex` | `-s read-only` |
| `agy`, `gemini` | no permission flags (tools that require confirmation are denied without a terminal) |

For `claude`, `codex`, `gemini` and `ollama`, prompts are passed via stdin, not on the command line. This keeps the task and plan out of the process list and prevents them from being truncated at the length limit (~32 KB) on Windows.

> [!WARNING]
> In YOLO mode the Builder may change files and run commands without asking. Only use it in projects under version control.
