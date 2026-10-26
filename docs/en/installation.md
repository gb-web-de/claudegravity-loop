# Installation

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/installation.md)

ClaudeGravity consists of two entry scripts (`loop.py` and `mcp_server.py`) and the package folder `claudegravity/`, which `loop.py` loads from its own directory. Keep the folder next to `loop.py`; symlinks to `loop.py` work. Everything uses only the standard library. A `pip install` is **not needed**: no dependencies, no virtual environment, nothing to compile. If you prefer to manage commands with pipx or uv, you can still install ClaudeGravity as a package (see [below](#with-pipx-or-uv)). Without any Python, use the [ready-made program](#ready-made-program-no-python-needed) from the release.

## Ready-made program (no Python needed)

Every [release](https://github.com/gb-web-de/claudegravity-loop/releases) contains ClaudeGravity as a standalone program that brings its own Python. One command downloads it, checks the SHA-256 sum, sets up `claudegravity`, `claudegravity-loop` and `claudegravity-mcp` and registers the MCP server and the skill in every client it finds:

```bash
# macOS (Apple Silicon and Intel) and Linux (x64 and arm64, e.g. Raspberry Pi)
curl -fsSL https://github.com/gb-web-de/claudegravity-loop/releases/latest/download/claudegravity-install.sh | sh
```

```powershell
# Windows (PowerShell)
irm https://github.com/gb-web-de/claudegravity-loop/releases/latest/download/claudegravity-install.ps1 | iex
```

Then open a new terminal and run `claudegravity --info`. Arguments go to the installer, e.g. `curl … | sh -s -- --project ~/projects/shop` (default project for desktop apps) or `--no-path`. Pick a specific version with `CLAUDEGRAVITY_VERSION=v1.6.0`.

| Release file | For |
| :--- | :--- |
| `claudegravity-macos-arm64.tar.gz` | macOS with Apple Silicon (M1 to M4) |
| `claudegravity-macos-x86_64.tar.gz` | macOS with an Intel processor |
| `claudegravity-linux-x86_64.tar.gz` | Linux x64 with glibc 2.35 or newer (Ubuntu 22.04, Debian 12 …) |
| `claudegravity-linux-arm64.tar.gz` | Linux arm64, e.g. Raspberry Pi 4/5 with a 64-bit system |
| `claudegravity-windows-x86_64.zip` | Windows 10/11 (on ARM devices through the built-in emulation) |
| `claudegravity.mcpb` | Claude Desktop, see [extension](mcp-server.md#claude-desktop-one-click-extension) |
| `claudegravity_loop-<version>-py3-none-any.whl` | Python 3.10+ with pipx or uv, see [below](#with-pipx-or-uv) |
| `SHA256SUMS` | Checksums of all files |

* **By hand:** unpack the archive and run `./claudegravity/claudegravity install` (Windows: `claudegravity\claudegravity.exe install`). The program copies itself to `~/.local/bin` or `%LOCALAPPDATA%\ClaudeGravity\bin` and extends the `PATH`; it also runs straight from the folder without installing.
* **One program for everything:** `claudegravity "Task"` starts the loop, `claudegravity mcp` the MCP server (that is how the installer registers it), `claudegravity install` installs. You still need the AI CLIs (`claude`, `codex`, `gemini`, `ollama` …).
* **Not signed:** downloaded through a browser, macOS blocks the first start ("Apple could not verify …"). Run `xattr -d com.apple.quarantine claudegravity/claudegravity` or choose "Open Anyway" under *System Settings → Privacy & Security*. Windows SmartScreen shows "Windows protected your PC": *More info → Run anyway*. The one-command install downloads without a browser and is normally not affected.
* **Update:** run the same command again. **Remove:** `claudegravity install --uninstall` (program, commands, MCP entries and skill).

## Requirements

| Component | Required? | Purpose |
| :--- | :--- | :--- |
| **Python 3.10+** | Yes (not for the [ready-made program](#ready-made-program-no-python-needed)) | Runtime for `loop.py` and `mcp_server.py` (`str \| None` type annotations are used, so at least 3.10). |
| **At least one AI CLI** or an **OpenAI-compatible endpoint** | Yes | Without a backend no role can be filled. See [Backends](backends.md). |
| **Two different backends** | Recommended | The four-eyes principle only works if Architect and Reviewer are different models. With only one CLI, the model reviews itself. |
| `git` | Optional | For cloning and updating. |

Supported CLIs (searched for automatically on the `PATH`): `claude`, `agy`, `gemini`, `codex`, `copilot` (or `gh`), `ollama`. The CLIs are signed in with your existing subscriptions – ClaudeGravity itself needs no API keys.

> [!TIP]
> **Everything in one step:** After cloning, run `./install.sh` (Linux/macOS), `install.bat` (CMD) or `.\install.ps1` (PowerShell). This registers the MCP server and the skill in all clients found (Claude Code, Claude Desktop, Gemini CLI, Antigravity, Codex, Copilot CLI, Cursor, Windsurf, VS Code) and makes `claudegravity`, `claudegravity-loop` and `claudegravity-mcp` callable globally. `--project <path>` sets a default project for desktop apps (`CLAUDEGRAVITY_PROJECT`), `--status` shows the current state, `--dry-run` simulates, `--uninstall` removes everything again. The manual steps below are then not needed. Only Claude Desktop? Then the [`.mcpb` extension](mcp-server.md#claude-desktop-one-click-extension) is enough.

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

* **Update:** `git pull` in the repository folder (with pipx/uv: `pipx upgrade claudegravity-loop` or `uv tool upgrade claudegravity-loop`; ready-made program: run the [one-command installer](#ready-made-program-no-python-needed) again).
* **Uninstall:** ready-made program with `claudegravity install --uninstall`, otherwise remove the symlinks in `~/.local/bin` or the `PATH` entry and delete the folder. Project-specific data lives in `.dual-loop/` and `logs/` of the respective target project.

## Next

* [Quick start](schnellstart.md)
* [Register the MCP server in Claude Code & co.](mcp-server.md)
