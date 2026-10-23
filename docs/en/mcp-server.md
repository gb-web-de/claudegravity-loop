# MCP Server & Optimizer (`mcp_server.py`)

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/mcp-server.md)

`mcp_server.py` is a standalone **Model Context Protocol** server (JSON-RPC 2.0 over stdio, protocol version `2024-11-05`) with no dependencies. It lets an AI assistant such as Claude Code, Antigravity or Cursor work out the right ClaudeGravity configuration for a task and start it. The same logic can also be used directly in the terminal.

## Registering

### Claude Code

```bash
# Linux / macOS
claude mcp add claudegravity -- python3 ~/Projekte/claudegravity-loop/mcp_server.py

# Windows
claude mcp add claudegravity -- python C:\claudegravity\mcp_server.py
```

With `--scope user` the server is available in all projects. Check with: `claude mcp list`.

### Other MCP clients (Antigravity, Cursor, Claude Desktop, …)

Most clients use the same JSON format in their MCP configuration file:

```json
{
  "mcpServers": {
    "claudegravity": {
      "command": "python3",
      "args": ["/home/<user>/Projekte/claudegravity-loop/mcp_server.py"],
      "env": {
        "CLAUDEGRAVITY_ENDPOINT": "http://192.168.1.50:11434/v1"
      }
    }
  }
}
```

On Windows use `"command": "python"` and a path like `"C:\\claudegravity\\mcp_server.py"`, or use `claudegravity-mcp.bat` directly. The `env` block is optional.

## Provided tools

### `claudegravity_optimize`

Analyzes the task and returns the role assignment, a cost/quality assessment and the ready-made command for Bash, CMD and PowerShell. Runs nothing.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `task` | string | *(required)* | Task description |
| `priority` | `best-code` \| `lowest-cost` \| `local-free` \| `hybrid` \| `balanced` | `balanced` | Goal; `lowest-cost` corresponds to `--strategy eco`, `hybrid` to the `hybrid` strategy (cloud plans and accepts, Ollama reviews and builds in stages) |
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
| `background` | boolean | `false` | `true`: starts the loop as a background process in the project folder and reports the PID and log file; always sets `--plan-auto`. `false`: only returns the command for starting it manually. |

> [!WARNING]
> There is no terminal in the background: the plan is only built if the Reviewer reports `APPROVED` (`--plan-auto`), and the permission prompt before phase 3 is skipped. A CLI Builder such as Claude or Codex can then only write with `yolo: true`; local Builders (Ollama, endpoints) do not need that, because ClaudeGravity writes their files itself. Results are in the project's `.dual-loop/sessions/`; the run's terminal output goes to `.dual-loop/sessions/<time>_background.log`. `loop.py` is started directly with the MCP server's Python.

### `claudegravity_status`

Shows the state of a project's latest session, meant for checking on a background run: task, phase, build round (with stage), tokens, reported cost, abort reason, whether the completion file exists, and the end of `LOG.md` and of the background log. Read-only, starts nothing.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `project_path` | string | `.` | Target project |
| `log_lines` | integer | `15` | Lines from the end of the logs (`0` = none) |

### `claudegravity_info`

Shows the operating system, Python version, detected CLIs and endpoints, plus strategy recommendations. No parameters.

## How the optimizer decides

1. **Detect backends** the same way as `loop.py` (CLIs on the `PATH`, Ollama/LM Studio on localhost, `CLAUDEGRAVITY_ENDPOINT`/`OPENAI_BASE_URL`/`AI_ENDPOINT`).
2. **Pairing:** Architect `claude`, Reviewer `agy` (otherwise `gemini`, otherwise `claude` as well).
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
| `--priority` | `best-code`, `quality`, `eco`, `lowest-cost`, `cost`, `local-free`, `free`, `local`, `hybrid`, `mixed`, `balanced` | `balanced` |
| `--endpoint <url>` | Endpoint for the Builder | – |
| `-p`, `--project` | Target project | `.` |
| `-i`, `--ask` | Question mode in the command | off |
| `--yolo` | `--yolo` in the command | off |
| `-m`, `--max-iterations` | Rounds in the command | `10` |
| `--info` | System check | off |
| `--mcp` | Start as an MCP server (same behavior as without arguments) | – |

## Protocol details

Supported methods: `initialize`, `notifications/initialized`, `ping`, `tools/list`, `tools/call`. Each line on stdin is one JSON-RPC message; responses are written line by line to stdout. Unknown methods return a JSON-RPC error.

Manual test:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp_server.py
```
