# MCP Server & Optimizer (`mcp_server.py`)

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/mcp-server.md)

`mcp_server.py` is a standalone **Model Context Protocol** server (JSON-RPC 2.0 over stdio, protocol versions `2025-06-18`, `2025-03-26` and `2024-11-05`) with no dependencies. It lets an AI assistant such as Claude Code, Antigravity or Cursor work out the right ClaudeGravity configuration for a task and start it. The same logic can also be used directly in the terminal.

## Registering

### Easiest: the installer

```bash
./install.sh                                    # Linux/macOS; Windows: install.bat or .\install.ps1
./install.sh --project ~/Projekte/my-project    # also set a default project for desktop apps
./install.sh --only claude-desktop,codex        # only certain clients
```

The installer registers the server in every client it finds (Claude Code, Claude Desktop, Gemini CLI, Antigravity, Codex, Copilot CLI, Cursor, Windsurf, VS Code), always with the **absolute path** of the Python it was started with. `--project` sets `CLAUDEGRAVITY_PROJECT` in the server environment (see [Desktop apps](#desktop-apps-claude-desktop-cursor-)). Restart the client afterwards.

### By hand

```bash
# Claude Code (all projects)
claude mcp add --scope user claudegravity -- "$(command -v python3)" ~/Projekte/claudegravity-loop/mcp_server.py

# Codex CLI
codex mcp add claudegravity -- "$(command -v python3)" ~/Projekte/claudegravity-loop/mcp_server.py

# Windows (PowerShell)
claude mcp add --scope user claudegravity -- (Get-Command python).Source C:\claudegravity\mcp_server.py
```

Check with `claude mcp list` or `codex mcp list`. For JSON clients (Claude Desktop, Cursor, Gemini CLI, Antigravity, Windsurf):

```json
{
  "mcpServers": {
    "claudegravity": {
      "command": "/opt/homebrew/bin/python3",
      "args": ["/Users/<user>/Projekte/claudegravity-loop/mcp_server.py"],
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "CLAUDEGRAVITY_PROJECT": "/Users/<user>/Projekte/my-project"
      }
    }
  }
}
```

| Client | Configuration file |
| :--- | :--- |
| Claude Desktop | macOS `~/Library/Application Support/Claude/claude_desktop_config.json`, Windows `%APPDATA%\Claude\claude_desktop_config.json` |
| Cursor | `~/.cursor/mcp.json` |
| Gemini CLI | `~/.gemini/settings.json` |
| Antigravity (app) | `~/.gemini/antigravity/mcp_config.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| Codex CLI and Codex app | `~/.codex/config.toml` (shared by both), section `[mcp_servers.claudegravity]` with `command`, `args`, `env` |

On Windows, double the backslashes in JSON (`"C:\\claudegravity\\mcp_server.py"`) or use `claudegravity-mcp.bat` as `command`. `CLAUDEGRAVITY_PROJECT`, `CLAUDEGRAVITY_HOST` and other variables such as `CLAUDEGRAVITY_ENDPOINT` are optional.

### The calling client leads the loop

On `initialize` the server remembers which client started it (`clientInfo.name`) and uses that client's CLI as the **Architect**: from Codex (CLI or app) `codex` plans, from the Antigravity app `agy`, from Claude Code or Claude Desktop `claude`, from the Gemini CLI `gemini`. The Reviewer is never the same provider; if needed it falls back to Ollama or another cloud CLI. With `priority: "auto"` (the default) this becomes the `hybrid` strategy as soon as Ollama, LM Studio or an endpoint is reachable: the client plans and accepts, **Ollama reviews and builds** in stages for free. Without a local model, `balanced` applies.

This needs the client's CLI to be installed (`codex`, `agy`, `claude`); otherwise the recommendation says so and chooses as before. The installer also writes the client as `CLAUDEGRAVITY_HOST` into the configuration, in case an app reports an unknown name. `CLAUDEGRAVITY_HOST=aus` turns this off; explicit roles (`architekt` etc.) always win.

Ollama itself is not an MCP client: the Ollama app does not call MCP servers; in the loop it is the Reviewer and Builder. The loop picks the models from the installed ones (`/api/tags`), or you set them with `pruefstatiker_model` and `bauer_model`.

### Desktop apps (Claude Desktop, Cursor, …)

Desktop apps start the server differently from a terminal. The server handles that as follows:

* **No shell PATH:** On macOS a desktop app usually only sees `/usr/bin:/bin`. At startup the server adds existing folders such as the CLI folders of the Codex, Antigravity and Ollama apps under `/Applications`, `/opt/homebrew/bin`, `/usr/local/bin`, `~/.local/bin`, `~/.npm-global/bin`, `~/.bun/bin`, `~/.volta/bin`, `~/.cargo/bin` and nvm's `bin` folders (on Windows `%APPDATA%\npm` and `%LOCALAPPDATA%\Programs\Ollama`), so `claude`, `codex`, `gemini` or `ollama` are found. If a CLI lives somewhere else, add its folder under `env` → `PATH`. `claudegravity_info` shows which folders were added.
* **Wrong working directory:** There the server usually runs in `/` or the home folder. A relative `project_path` is then rejected; pass an absolute path or set `CLAUDEGRAVITY_PROJECT`, which applies when `project_path` is missing or `.`. `~` is expanded.
* **Python too old:** `command` must point to Python 3.10+ (on macOS `/usr/bin/python3` is often 3.9). Otherwise the server stops with a clear message in the client log.
* **No terminal:** Start runs from desktop apps with `claudegravity_run` and `background: true`, follow them with `claudegravity_status` and stop them with `claudegravity_stop` if needed.

## Provided tools

### `claudegravity_optimize`

Analyzes the task and returns the role assignment, a cost/quality assessment and the ready-made command for Bash, CMD and PowerShell. Runs nothing.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `task` | string | *(required)* | Task description |
| `priority` | `auto` \| `best-code` \| `lowest-cost` \| `local-free` \| `hybrid` \| `balanced` | `auto` | Goal; `auto` becomes `hybrid` when a local model is reachable, otherwise `balanced`; `lowest-cost` corresponds to `--strategy eco`, `hybrid` to the `hybrid` strategy (cloud plans and accepts, Ollama reviews and builds in stages) |
| `endpoint` | string | – | OpenAI-compatible endpoint for the Builder |
| `project_path` | string | `.` | Target project |
| `ask_mode` | boolean | `false` | Question mode (`-i`) |
| `yolo` | boolean | `false` | Append `--yolo` |
| `max_iterations` | integer | `10` | `-m` |
| `proof` | string | – | Check command (`--proof`) that the loop runs itself after every build round |
| `architekt`, `pruefstatiker`, `bauer`, `abnahme` | string | – | Backend per role, like `--architekt` etc. (e.g. `codex`, `ollama`). Overrides the optimizer's choice. |
| `architekt_model`, `pruefstatiker_model`, `bauer_model`, `abnahme_model` | string | – | Model per role. If it is missing for `ollama`, the loop picks one from the installed models. |
| `stages` | `auto` \| `an` \| `aus` | `auto` | Stage mode (`--etappen`) |
| `approve_plan` | boolean | `false` | `--plan-auto`: accept the plan without asking as soon as the Reviewer reports `APPROVED` |
| `merge` | boolean | `false` | `--merge`: merge the result into the original branch after acceptance |

### `claudegravity_run`

Computes the same command and starts it.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `task`, `priority`, `endpoint`, `project_path`, `ask_mode`, `max_iterations`, `proof`, roles, `stages`, `approve_plan`, `merge` | | as above | |
| `yolo` | boolean | `false` | Full permissions for the Builder. Only set this when explicitly requested; without `yolo` a Claude Builder cannot write anything in the background. |
| `background` | boolean | `false` | `true`: starts the loop as its own process in the project folder (without a console window on Windows) and reports the PID and log file; always sets `--plan-auto` and drops `-i`. If a background run is already active in the project, no second one is started. `false`: only returns the command for starting it in a terminal (Bash or PowerShell, with the server's Python). |

> [!WARNING]
> There is no terminal in the background: the plan is only built if the Reviewer reports `APPROVED` (`--plan-auto`), and the permission prompt before phase 3 is skipped. A CLI Builder such as Claude or Codex can then only write with `yolo: true`; local Builders (Ollama, endpoints) do not need that, because ClaudeGravity writes their files itself. Results are in the project's `.dual-loop/sessions/`; the run's terminal output goes to `.dual-loop/sessions/<time>_background.log`. `loop.py` is started directly with the MCP server's Python; PID and start time are stored in `.dual-loop/sessions/<time>_background.json`.

### `claudegravity_status`

Shows the state of a project's latest session, meant for checking on a background run: task, phase, build round (with stage), tokens, reported cost, abort reason, whether the completion file exists, whether the background run is still running (with exit code, as long as the same server started it), and the end of `LOG.md` and of the background log. Read-only, starts nothing.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `project_path` | string | `.` | Target project |
| `log_lines` | integer | `15` | Lines from the end of the logs (`0` = none) |

### `claudegravity_stop`

Stops the project's latest background run, including the CLIs it started (POSIX: `SIGTERM` to the process group, Windows: `taskkill /T`). Only PIDs from the server's own `_background.json` are stopped. The state stays in the session and can be resumed with `claudegravity -c`.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `project_path` | string | `.` | Target project |

### `claudegravity_info`

Shows the operating system, the server's Python, working directory, `CLAUDEGRAVITY_PROJECT`, the PATH folders added at startup, detected CLIs and endpoints, plus strategy recommendations. No parameters. The first thing to check when a desktop app finds no CLIs.

## How the optimizer decides

1. **Detect backends** the same way as `loop.py` (CLIs on the `PATH`, Ollama/LM Studio on localhost, `CLAUDEGRAVITY_ENDPOINT`/`OPENAI_BASE_URL`/`AI_ENDPOINT`).
2. **Pairing:** The Architect is the calling client (see above), otherwise `claude`; Reviewer `agy` (otherwise `gemini`, otherwise a provider other than the Architect).
3. **Complexity** via keyword search in the task: refactoring, security/auth and architecture/migration/schema → `hoch` (high); small fixes/typos → `niedrig` (low); otherwise `mittel` (medium).
4. **Priority → preset** (see [Strategies](strategien.md)); `--bauer-model` is set for `lowest-cost` (Claude/Gemini only) and for `local-free` with an endpoint. For Ollama the loop picks the model itself from the installed models. With `hybrid`, the first cloud CLI (`codex`, `claude`, `agy`, `gemini`) plans and the local model reviews and builds.
5. **Explicit roles** (`architekt`, `bauer_model`, …) override the choice and end up as flags in the command. The optimizer shows model names only for Claude and Gemini; other CLIs use their CLI default.
6. For **architecture tasks**, `-i` (question mode) is added automatically.

## Directly in the terminal (without an MCP client)

```bash
claudegravity-mcp --optimize "Build a microservice backend" --priority local-free --endpoint http://192.168.1.50:11434/v1
claudegravity-mcp "Fix the login bug" --priority lowest-cost   # task also as a positional argument
claudegravity-mcp --info
claudegravity-mcp                                              # no arguments: starts the stdio server
```

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--optimize`, `-o <task>` | Analyze the task and print a recommendation | – |
| `--priority` | `auto`, `best-code`, `quality`, `eco`, `lowest-cost`, `cost`, `local-free`, `free`, `local`, `hybrid`, `mixed`, `balanced` | `auto` |
| `--endpoint <url>` | Endpoint for the Builder | – |
| `-p`, `--project` | Target project | `.` |
| `-i`, `--ask` | Question mode in the command | off |
| `--yolo` | `--yolo` in the command | off |
| `-m`, `--max-iterations` | Rounds in the command | `10` |
| `--info` | System check | off |
| `--mcp` | Start as an MCP server (same behavior as without arguments) | – |

## Protocol details

Supported methods: `initialize`, `ping`, `tools/list`, `tools/call`; `resources/list`, `resources/templates/list` and `prompts/list` return empty lists. Notifications (messages without an `id`, e.g. `notifications/initialized` or `notifications/cancelled`) never get a response. Each line on stdin is one JSON-RPC message; responses are written line by line to stdout. Unknown methods return a JSON-RPC error.

The server negotiates the protocol version (the client's if known, otherwise `2025-06-18`), sends short `instructions` for the model on `initialize` and marks the tools with `annotations` (`readOnlyHint` for optimize, status and info). While it runs, stray output on stdout goes to stderr so it cannot break the protocol; stderr ends up in the client's log (for Claude Desktop under `~/Library/Logs/Claude/mcp-server-claudegravity.log`).

Manual test:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp_server.py
```
