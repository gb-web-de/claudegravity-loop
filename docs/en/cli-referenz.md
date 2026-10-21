# CLI reference (`claudegravity` / `loop.py`)

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/cli-referenz.md)

```text
claudegravity [AUFGABE] [OPTIONEN]
```

All German and English spellings of a flag are equivalent (e.g. `--bauer` = `--builder`).

## General

| Flag | Aliases | Description | Default |
| :--- | :--- | :--- | :--- |
| `AUFGABE` | *(positional argument)* | The coding task in quotes. Without a task, an interrupted session is offered; otherwise the help is shown. | – |
| `-p`, `--project` | | Target project (absolute or relative). | `.` |
| `-m`, `--max-iterations` | | Maximum rounds in the build loop (phase 3). | `10` |
| `-d`, `--delay` | | Pause between build rounds in seconds. | `3` |
| `-c`, `--resume` | `--continue` | Resume the last session in the project. | off |
| `-i`, `--ask` | `--interview`, `--clarify` | Question mode: Architect and Reviewer may ask follow-up questions. | off |
| `--yolo` | `--auto-approve` | Full write and tool permissions for the **Builder** without asking. Architect, Reviewer and Acceptance check stay read-only. | off |
| `--max-rounds` | | Maximum review rounds for the plan. | `2` |
| `--auto-switch` | `--fallback` | Automatically switch to the alternative AI when a limit is hit. | off |
| `--swap` | `--swap-roles`, `--reverse` | Swap the default roles: Antigravity/Gemini plans, Claude reviews. | off |
| `--strategy` | `--preset` | `balanced`, `best-code` (`quality`), `eco` (`economy`, `cost`), `local-free` (`free`, `local`). See [Strategies](strategien.md). | `balanced` |
| `--dry-run` | | Show the assignment, cost analysis and start command without running or creating anything. | off |
| `--info` | `--check` | Show detected CLIs/endpoints and the default assignment. | off |

## Roles

| Flag | Aliases | Description |
| :--- | :--- | :--- |
| `--architekt <key>` | `--planner` | Backend for phase 1. |
| `--pruefstatiker <key>` | `--reviewer` | Backend for phase 2. |
| `--bauer <key>` | `--builder` | Backend for phase 3 (default: same as Architect). |

Valid keys: `claude`, `agy`, `gemini`, `codex`, `copilot`, `ollama`, `ollama-cli`, `lmstudio`, `endpoint`, `architekt_ep`, `pruefstatiker_ep`, `bauer_ep` – if detected. An unrecognized key silently falls back to the default choice. Details: [Backends](backends.md).

## Acceptance check & proof command

| Flag | Aliases | Description | Default |
| :--- | :--- | :--- | :--- |
| `--proof "<command>"` | `--pruefbefehl` | Command that ClaudeGravity runs itself after every build round (without a shell). Red: `.done` is rejected and the output goes to the Builder. | – |
| `--abnahme <key>` | `--inspector` | Backend for the acceptance check of the finished code. Never the Builder itself. | Reviewer |
| `--abnahme-model <name>` | `--inspector-model` | Model for the acceptance check. | – |
| `--abnahme-effort <level>` | `--inspector-effort` | Effort for the acceptance check. | – |
| `--max-inspections <n>` | | Acceptance check rounds per run; after that the task stays open (`phase = inspection_open`). | `2` |
| `--no-inspect` | `--ohne-abnahme` | Skip the acceptance check (noted in `LOG.md`). | on |

## Models

| Flag | Aliases | Description |
| :--- | :--- | :--- |
| `--architekt-model <name>` | `--planner-model` | e.g. `sonnet`, `opus`, `gemini-2.5-pro` |
| `--pruefstatiker-model <name>` | `--reviewer-model` | e.g. `gemini-2.5-pro`, `sonnet` |
| `--bauer-model <name>` | `--builder-model` | e.g. `claude-3-5-haiku`, `gemini-2.5-flash`, `qwen2.5-coder:32b` |

The model name is passed as `--model <name>` to the CLI, or as `model` to the endpoint.

## Reasoning effort

Values: `low`, `medium`, `high`, `xhigh`, `max`.

| Flag | Aliases | Applies to |
| :--- | :--- | :--- |
| `--effort` | | Architect and Reviewer (if not set individually) |
| `--architekt-effort` | `--planner-effort` | Architect |
| `--pruefstatiker-effort` | `--reviewer-effort` | Reviewer |
| `--bauer-effort` | `--builder-effort` | Builder |

Effort is passed on to `agy` (`--effort`) and `codex` (`-c model_reasoning_effort`, `max` becomes `xhigh`).

## Endpoints

| Flag | Aliases | Description |
| :--- | :--- | :--- |
| `--endpoint <url>` | `--api-base` | OpenAI-compatible endpoint, available as key `endpoint`. |
| `--api-key <key>` | | Bearer token for the endpoint (better via environment variable, see [Backends](backends.md)). |
| `--architekt-endpoint <url>` | | Dedicated endpoint, available as `architekt_ep`. |
| `--pruefstatiker-endpoint <url>` | | Dedicated endpoint, available as `pruefstatiker_ep`. |
| `--bauer-endpoint <url>` | | Dedicated endpoint, available as `bauer_ep`. |
| `--timeout <sec>` | | Seconds per round for endpoints. Default: 900 on the home network, 180 otherwise. Also `CLAUDEGRAVITY_TIMEOUT`. |

## Git workspace

| Flag | Aliases | Description | Default |
| :--- | :--- | :--- | :--- |
| `--no-worktree` | `--no-workspace` | Don't create a separate Git worktree per session; build directly in the project folder. | Worktree on (only in Git repositories) |
| `--merge` | `--worktree-merge` | Merge the session branch into the original branch after successful completion (`.done`, acceptance check passed). | off |

Details: [Sessions & files](sessions-und-dateien.md#git-workspace-per-session).

## Privacy

| Flag | Description |
| :--- | :--- |
| `--no-shield` | Turn off the privacy shield (also `CLAUDEGRAVITY_SHIELD=off`). See [Sessions & files](sessions-und-dateien.md#privacy-shield). |

## Settings precedence

1. Explicit flag in this invocation
2. Saved value from `state.json` (with `-c`)
3. Default value of the selected preset
4. CLI default of the backend

## Examples

```bash
# Configure everything separately
claudegravity "Security audit and auth refactoring" \
  --architekt claude --architekt-model opus \
  --pruefstatiker agy --pruefstatiker-model gemini-2.5-pro --pruefstatiker-effort max \
  --bauer-endpoint http://192.168.1.50:11434/v1 --bauer bauer_ep --bauer-model qwen2.5-coder:7b

# Long task: more rounds, no pause, fallback on limit
claudegravity "Large refactoring" -m 25 -d 0 --auto-switch --yolo

# Resume a different project
claudegravity -c -p ~/Projekte/kundenportal
```
