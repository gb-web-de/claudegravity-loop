# Installation

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/installation.md)

ClaudeGravity consists of two entry scripts (`loop.py` and `mcp_server.py`) and the package folder `claudegravity/`, which `loop.py` loads from its own directory. Keep the folder next to `loop.py`; symlinks to `loop.py` work. Everything uses only the standard library. A `pip install` is **not needed**: no dependencies, no virtual environment, nothing to compile. If you prefer to manage commands with pipx or uv, you can still install ClaudeGravity as a package (see [below](#with-pipx-or-uv)).

## Requirements

| Component | Required? | Purpose |
| :--- | :--- | :--- |
| **Python 3.10+** | Yes | Runtime for `loop.py` and `mcp_server.py` (`str \| None` type annotations are used, so at least 3.10). |
| **At least one AI CLI** or an **OpenAI-compatible endpoint** | Yes | Without a backend no role can be filled. See [Backends](backends.md). |
| **Two different backends** | Recommended | The four-eyes principle only works if Architect and Reviewer are different models. With only one CLI, the model reviews itself. |
| `git` | Optional | For cloning and updating. |

Supported CLIs (searched for automatically on the `PATH`): `claude`, `agy`, `gemini`, `codex`, `copilot` (or `gh`), `ollama`. The CLIs are signed in with your existing subscriptions – ClaudeGravity itself needs no API keys.

> [!TIP]
> **Everything in one step:** After cloning, run `./install.sh` (Linux/macOS), `install.bat` (CMD) or `.\install.ps1` (PowerShell). This registers the MCP server and the skill in all clients found (Claude Code, Claude Desktop, Gemini CLI, Antigravity, Codex, Copilot CLI, Cursor, Windsurf, VS Code) and makes `claudegravity`, `claudegravity-loop` and `claudegravity-mcp` callable globally. `--project <path>` sets a default project for desktop apps (`CLAUDEGRAVITY_PROJECT`), `--status` shows the current state, `--dry-run` simulates, `--uninstall` removes everything again. The manual steps below are then not needed.

## With pipx or uv

Without a clone, straight from GitHub; this creates `claudegravity`, `claudegravity-loop` and `claudegravity-mcp` (the package is not on PyPI yet):

```bash
pipx install git+https://github.com/gb-web-de/claudegravity-loop
# or
uv tool install git+https://github.com/gb-web-de/claudegravity-loop
# try it once without installing anything:
uvx --from git+https://github.com/gb-web-de/claudegravity-loop claudegravity --dry-run "Your task"
```

From a clone, `pipx install .` or `uv tool install .` works too; `python -m claudegravity` is the same entry point as `loop.py`. Update with `pipx upgrade claudegravity-loop` or `uv tool upgrade claudegravity-loop`. For MCP clients the command is then `claudegravity-mcp` (instead of `python3 /path/mcp_server.py`). The plugins and `install.py` still expect a clone.

## 🍏 macOS & 🐧 Linux

1. Clone the repository and make the scripts executable:
   ```bash
   git clone https://github.com/gb-web-de/claudegravity-loop.git ~/Projekte/claudegravity-loop
   cd ~/Projekte/claudegravity-loop
   chmod +x loop.py mcp_server.py
   ```
2. Create global commands via symlinks:
   ```bash
   mkdir -p ~/.local/bin
   ln -sf ~/Projekte/claudegravity-loop/loop.py       ~/.local/bin/claudegravity
   ln -sf ~/Projekte/claudegravity-loop/loop.py       ~/.local/bin/claudegravity-loop
   ln -sf ~/Projekte/claudegravity-loop/mcp_server.py ~/.local/bin/claudegravity-mcp
   ```
3. If `~/.local/bin` is not yet on the `PATH`, add it to `~/.bashrc` or `~/.zshrc` and reload the shell:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

The symlinks point to the clone, so a `git pull` in the repository automatically updates the global commands.

## 🪟 Windows (CMD or PowerShell)

1. Clone the repository (or download and extract the ZIP):
   ```cmd
   git clone https://github.com/gb-web-de/claudegravity-loop.git C:\claudegravity
   ```
2. The folder contains ready-made launchers:

   | File | Shell | Starts |
   | :--- | :--- | :--- |
   | `claudegravity.bat` | CMD | `loop.py` |
   | `claudegravity.ps1` | PowerShell | `loop.py` |
   | `claudegravity-mcp.bat` | CMD | `mcp_server.py` |

   The launchers set UTF-8 (`chcp 65001` or `[Console]::OutputEncoding`, `PYTHONIOENCODING=utf-8`) so that umlauts and emojis display correctly, and look for `python` and then the `py -3` launcher.
3. *(Optional)* Add `C:\claudegravity` to the `PATH` environment variable so that `claudegravity` works in every folder.

> [!NOTE]
> If PowerShell blocks the script, this helps for the current user:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Verifying the installation

```bash
claudegravity --info        # detected CLIs, endpoints and default assignment
claudegravity-mcp --info    # the same from the MCP server's point of view
```

On Windows, use `claudegravity.bat --info` or `.\claudegravity.ps1 --info` accordingly.

## Updating & uninstalling

* **Update:** `git pull` in the repository folder (with pipx/uv: `pipx upgrade claudegravity-loop` or `uv tool upgrade claudegravity-loop`).
* **Uninstall:** Remove the symlinks in `~/.local/bin` or the `PATH` entry and delete the folder. Project-specific data lives in `.dual-loop/` and `logs/` of the respective target project.

## Next

* [Quick start](schnellstart.md)
* [Register the MCP server in Claude Code & co.](mcp-server.md)
