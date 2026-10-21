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
| `priority` | `best-code` \| `lowest-cost` \| `local-free` \| `balanced` | `balanced` | Goal; `lowest-cost` corresponds to `--strategy eco` |
| `endpoint` | string | – | OpenAI-compatible endpoint for the Builder |
| `project_path` | string | `.` | Target project |
| `ask_mode` | boolean | `false` | Question mode (`-i`) |
| `yolo` | boolean | `false` | Append `--yolo` |
| `max_iterations` | integer | `10` | `-m` |
| `proof` | string | – | Check command (`--proof`) that the loop runs itself after every build round |

### `claudegravity_run`

Computes the same command and starts it.

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `task`, `priority`, `endpoint`, `project_path`, `ask_mode`, `max_iterations`, `proof` | | as above | |
| `yolo` | boolean | `false` | Full permissions for the Builder. Only set this when explicitly requested; without `yolo` a Claude Builder cannot write anything in the background. |
| `background` | boolean | `false` | `true`: starts the loop as a background process in the project folder and reports the PID. `false`: only returns the command for starting it manually. |

> [!WARNING]
> No interactive menus (plan approval, permission prompt) run in the background. The process is started without a terminal; check the results in the project's `.dual-loop/sessions/` and `logs/`. The command calls `claudegravity`, which therefore has to be on the `PATH`.

### `claudegravity_info`

Shows the operating system, Python version, detected CLIs and endpoints, plus strategy recommendations. No parameters.

## How the optimizer decides

1. **Detect backends** the same way as `loop.py` (CLIs on the `PATH`, Ollama/LM Studio on localhost, `CLAUDEGRAVITY_ENDPOINT`/`OPENAI_BASE_URL`/`AI_ENDPOINT`).
2. **Pairing:** Architect `claude`, Reviewer `agy` (otherwise `gemini`, otherwise `claude` as well).
3. **Complexity** via keyword search in the task: refactoring, security/auth and architecture/migration/schema → `hoch` (high); small fixes/typos → `niedrig` (low); otherwise `mittel` (medium).
4. **Priority → preset** (see [Strategies](strategien.md)); for `lowest-cost` and `local-free`, `--bauer-model` is set.
5. For **architecture tasks**, `-i` (question mode) is added automatically.

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
| `--priority` | `best-code`, `quality`, `eco`, `lowest-cost`, `cost`, `local-free`, `free`, `local`, `balanced` | `balanced` |
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
