# Plugins for Claude Code, Codex, Antigravity & co.

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/plugins.md)

The repository is a plugin itself. One command in each client loads the [MCP server](mcp-server.md) with all its tools (`claudegravity_optimize`, `claudegravity_run`, `claudegravity_status`, `claudegravity_stop`, `claudegravity_info`), the `claudegravity` skill and three commands. No path has to be entered by hand, and the client becomes the Architekt automatically.

| Command | What it does |
| :--- | :--- |
| `loop_run <task>` | Pick the roles, start in the background after your OK, report the result |
| `loop_optimize <task>` | Show the best role split and the ready `claudegravity` command without starting |
| `loop_status` | State of the last run in the current project, stop it on request |

As with the loop, the only requirement is **Python 3.10+** as `python3` on the PATH. You still need the role CLIs (`claude`, `agy`, `codex`, `ollama`, …) as usual.

## Install

| Client | Command | Use afterwards |
| :--- | :--- | :--- |
| **Claude Code** | `/plugin marketplace add gb-web-de/claudegravity-loop` and `/plugin install claudegravity@claudegravity` (or `python3 install.py`) | `/loop_run …`, `/loop_optimize …`, `/loop_status` (or `/claudegravity:loop_…`) |
| **Codex** (CLI and app) | `codex plugin marketplace add gb-web-de/claudegravity-loop`, then install it under Plugins in Codex | skill `claudegravity` or `@claudegravity` |
| **Antigravity** (`agy`, app, IDE) | `agy plugin install https://github.com/gb-web-de/claudegravity-loop` | skill `claudegravity`, tools in the agent |
| **GitHub Copilot CLI** | `copilot plugin marketplace add gb-web-de/claudegravity-loop` and `copilot plugin install claudegravity@claudegravity` | skill `claudegravity` |
| **Cursor** | add the repository as a plugin source or team marketplace (`.cursor-plugin/marketplace.json`) | `/loop_run`, `/loop_optimize`, `/loop_status` |
| **Gemini CLI** | `gemini extensions install https://github.com/gb-web-de/claudegravity-loop` | `/claudegravity:loop_run …`, `/claudegravity:loop_optimize …`, `/claudegravity:loop_status` |

For Claude Desktop there is the [`.mcpb` extension](mcp-server.md#claude-desktop-one-click-extension) (a double-click is enough). VS Code and Windsurf have no matching plugin format; there the [installer](mcp-server.md#easiest-the-installer) registers the MCP server.

**Test locally** (without GitHub): give the checkout's path instead of `gb-web-de/claudegravity-loop`, e.g. `/plugin marketplace add ~/Projekte/claudegravity-loop` or `agy plugin install ~/Projekte/claudegravity-loop`.

**Plugin or installer, not both:** both register a server named `claudegravity`. When switching to the plugin, remove the old entry with `python3 install.py --uninstall --only <client>`.

## Files in the repository

Each client reads only its own files. All of them start the same server, `mcp_server.py`, from the plugin folder.

| File | Client | Plugin folder in the MCP entry |
| :--- | :--- | :--- |
| `.claude-plugin/plugin.json` | Claude Code (MCP server, skill from `skills/`, commands from `commands/*.md`) | `${CLAUDE_PLUGIN_ROOT}` |
| `.claude-plugin/marketplace.json` | Claude Code, Copilot CLI and Codex (marketplace with the repository as its only plugin) | – |
| `plugin.json` + `mcp.json` | open standard [Agent Plugins](https://agent-plugins.org) (Codex, Copilot CLI); `plugin.json` is also the Antigravity manifest | `${PLUGIN_ROOT}` |
| `mcp_config.json` | Antigravity | `${PLUGIN_ROOT}` |
| `.cursor-plugin/plugin.json`, `.cursor-plugin/mcp.json`, `.cursor-plugin/marketplace.json` | Cursor | `${CURSOR_PLUGIN_ROOT}` |
| `gemini-extension.json` + `commands/claudegravity/*.toml` | Gemini CLI | `${extensionPath}` |
| `commands/*.md` | commands for Claude Code and Cursor | – |
| `skills/claudegravity/SKILL.md` | skill for all clients | – |

Each entry sets `CLAUDEGRAVITY_HOST` to match the client (`claude`, `agy`, `gemini`) where the format allows it; otherwise the server recognises the client from `clientInfo` (see [The calling client leads the loop](mcp-server.md#the-calling-client-leads-the-loop)).

**Changing commands:** `commands/*.md` is the source; the TOML files for Gemini CLI hold the same text with `{{args}}` instead of `$ARGUMENTS`. `tests/test_plugins.py` checks that both stay in sync, that all manifests carry the same name and version, and that every MCP entry starts `mcp_server.py`. For a new version, raise `version` in `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json` and `gemini-extension.json` together. Claude Code checks the plugin with `claude plugin validate .`.

## Known limits

- So far only Claude Code has been tested (installed from the local marketplace, server connected). Codex, Antigravity, Copilot CLI, Cursor and Gemini CLI follow their documentation as of October 2026 and have not been tried in the real client yet.
- If a client does not know the plugin variable in the MCP entry, the server does not start. Use the [installer](mcp-server.md#easiest-the-installer) for that client instead.
- On Windows, Python is often called `python` or `py` instead of `python3`. Without `python3`, register the server with the installer, which uses the absolute path of its Python.
- Desktop apps do not start the server in the project folder. That is why the commands always pass the absolute `project_path`.
