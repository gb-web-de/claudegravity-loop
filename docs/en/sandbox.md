# Sandbox: proof command and Builder in a container

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/sandbox.md)

Without a sandbox, the proof command and a CLI Builder run with your user rights: model code sees your home folder with SSH keys, browser profiles and other projects. With `--sandbox on` the loop starts both in a fresh container (Docker or Podman) that only sees the work folder. This shrinks threats T8 and T9 of the [threat model](sicherheit.md).

## Quick start

```bash
# Proof command in the container; enough for endpoint Builders (Ollama, LM Studio, your own servers)
claudegravity "Task" --strategy local-free --sandbox on --proof "python -m unittest"

# The CLI Builder in the container too: build the image with the AI CLIs once
docker build -t claudegravity-sandbox sandbox/
claudegravity "Task" --bauer claude --sandbox on --sandbox-image claudegravity-sandbox --proof "python -m pytest -q"
```

Without a clone of the repository (e.g. after `pipx install`) build the image straight from GitHub: `docker build -t claudegravity-sandbox "https://github.com/gb-web-de/claudegravity-loop.git#main:sandbox"`.

## What runs in the container

| Part | In the container | Network | Sees |
| :--- | :--- | :--- | :--- |
| Proof command (`--proof`) | yes | off (on with `--sandbox-net`) | the work folder |
| CLI Builder (`claude`, `codex`, `gemini`, `copilot`, `agy`) | yes, on Linux and macOS | on, it needs its model | work folder, session folder and the credentials of this one CLI |
| Endpoint Builder | not needed: it writes nothing itself, the loop creates its files via `resolve_project_target()` | – | – |
| Architect, Reviewer, acceptance check | no, they run read-only anyway | – | – |
| Candidates (`--candidates`) | each candidate as above; the main run checks them in the container | as above | as above |

The run header shows the setup, e.g. `[*] Sandbox : 🐳 docker (claudegravity-sandbox): proof command and CLI Builder, proof command without network`.

## How the container is set up

* A fresh container per call (`--rm`, name `claudegravity-…`); after a timeout the loop removes it.
* Your user ID (`--user uid:gid`, with Podman `--userns keep-id`), so new files belong to you.
* No capabilities (`--cap-drop ALL`), `no-new-privileges`, limits of 512 processes, 4 GB memory and 2 CPUs.
* `HOME` and `/tmp` are empty (tmpfs). From your home folder only the credentials of the CLI that is building come in.
* The work folder sits at the same path inside the container (on Windows `/work`), so paths in the plan, output and error messages match.
* If a `.git` folder lies directly in the work folder (with `--no-worktree`), the loop covers it with an empty folder in the container, because `.git/config` can contain tokens. In the Git workspace (default) there is only the file `.git`; Git commands do not work in the container then, because the main repository is not mounted. The loop does the committing itself.

## Credentials

Only the folders of the CLI that builds are mounted, and writable, because the CLIs refresh their tokens:

| CLI | from your home folder |
| :--- | :--- |
| `claude` | `~/.claude`, `~/.claude.json` |
| `codex` | `~/.codex` |
| `gemini`, `agy` | `~/.gemini` |
| `copilot`, `gh` | `~/.copilot`, `~/.config/gh` |

The loop also passes these environment variables if they are set: `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `CLAUDE_CODE_OAUTH_TOKEN`, `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `CODEX_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_GENAI_USE_VERTEXAI`, `GH_TOKEN`, `GITHUB_TOKEN`, `COPILOT_GITHUB_TOKEN` and the proxy variables. The command only contains the name (`-e NAME`), the value comes from the environment; it does not show up in the process list.

* **macOS:** Claude Code keeps its sign-in in the Keychain, which the container cannot reach. Create a token with `claude setup-token` and set `CLAUDE_CODE_OAUTH_TOKEN` in your shell (not in the project). The same goes for Copilot with `COPILOT_GITHUB_TOKEN` or `GH_TOKEN`.
* Codex and Gemini store their sign-in as a file by default. If it does not work in the container, set `CODEX_API_KEY` or `GEMINI_API_KEY`.

## Image

* **Default `python:3.12-slim`:** enough for `python -m unittest` and for endpoint Builders. A CLI Builder needs an image with its CLI.
* **`sandbox/Dockerfile`** brings Node 22, Python 3, Git, ripgrep, pytest and the CLIs `claude`, `codex`, `gemini` and `copilot`. Only some CLIs: `docker build --build-arg CLIS="@anthropic-ai/claude-code" -t claudegravity-sandbox sandbox/`. Antigravity (`agy`) is not available via npm; if you need it in the container, add it in your own image.
* **The project's dependencies** belong in your own image on top of it, because the proof command has no network:

  ```dockerfile
  FROM claudegravity-sandbox
  COPY requirements.txt /tmp/
  RUN python3 -m pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt
  ```

  If the proof command has to download something after all (e.g. `npm ci && npm test`), `--sandbox-net` turns the network on for it.
* **Before the build the loop checks** that the engine is running ([CG-1701](fehlerbehebung.md#cg-1701)) and that the image contains the Builder's CLI and the proof command's program ([CG-1702](fehlerbehebung.md#cg-1702)). The first time, the engine downloads the image, which can take a while.

## Settings

* `--sandbox on|docker|podman|off` (also `an`/`aus`): `on` picks Docker if it is installed, otherwise Podman.
* `--sandbox-image <image>` and `--sandbox-net` as above.
* Turn it on permanently via the environment (`CLAUDEGRAVITY_SANDBOX=on`, `CLAUDEGRAVITY_SANDBOX_IMAGE=…`) or the global profile. The three settings have no effect from the project profile: a foreign repository should neither switch the sandbox off nor pick an image that receives your credentials.
* `claudegravity -c` continues with the same sandbox; `--dry-run` shows the switches in the command.

## Limits

* **Windows:** only the proof command runs in the container, a CLI Builder still runs with your rights (the loop warns). Use WSL for both.
* **The Builder has network access and its own credentials.** It can send the work folder and its token elsewhere. The sandbox protects the rest of your machine, not the project itself.
* **A container is not a VM:** the kernel is shared. For code you do not trust at all, use a VM.
* **Docker with a root daemon:** anyone in the `docker` group effectively has root rights. Rootless Podman or rootless Docker is the better choice.
* **Docker Desktop on macOS:** the work folder must be in a shared folder (default: `/Users`); file access is slower than native.
* Paths with a comma cannot be mounted; the proof command or Builder call then fails with this message.

More: [Security](sicherheit.md) (T8, T9), [CLI reference](cli-referenz.md#sandbox), [Build loop](bau-loop.md).
