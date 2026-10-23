# Strategy presets

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/strategien.md)

Instead of configuring each role individually, you pick a preset with `--strategy <name>` (alias `--preset`). It sets **defaults** for effort and the Builder model; anything you specify explicitly (`--bauer-model`, `--architekt-effort`, …) takes precedence.

## Overview

| Preset | Aliases | Architect effort | Reviewer effort | Builder effort | Builder model (default) | Use case |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `balanced` *(default)* | – | `high` only with `agy` | `high` only with `agy` | CLI default | same as Architect | Everyday work |
| `best-code` | `quality` | `high` | `high` | `high` | same as Architect | Core systems, security, large refactorings |
| `eco` | `economy`, `cost` | `medium` | `medium` | `low` | `claude-3-5-haiku` (with `claude`), `gemini-2.5-flash` (with `agy`/`gemini`), otherwise CLI default | Up to ~70% token savings |
| `local-free` | `free`, `local` | `high` | `high` | `low` | Ollama: picked automatically from the installed models; endpoint: `qwen2.5-coder:32b`; otherwise `local-model` | €0 API cost in the build loop |
| `hybrid` | `mixed` | CLI default | – | – | Ollama: automatic | Cloud plans and accepts, local model reviews and builds in stages |

> [!NOTE]
> `--effort` values are passed on to `agy` (`--effort`) and `codex` (`model_reasoning_effort`). For `claude` and other CLIs they only show up in the audit report.

## `best-code`

All three phases run on frontier models with high thinking effort. Highest quality and the most thorough tests, but also the highest consumption.

```bash
claudegravity "Security audit and auth refactoring" --strategy best-code
```

## `eco`

Planning and review stay strong (they use little anyway). A fast, economical model takes over the expensive build loop.

```bash
claudegravity "Add structured logging" --strategy eco
```

## `local-free`

Cloud models plan and review; a local or intranet model builds. Endpoints on your own network (`localhost`, private IPs such as `192.168.*`, `10.*`, `172.16–31.*` and hostnames such as `nas`, `server.local` or `pi.fritz.box`) are booked at €0 in the audit.

ClaudeGravity looks for Builder candidates in this order: `--bauer-endpoint` → Ollama server (`localhost:11434` or `OLLAMA_HOST`) → LM Studio (`localhost:1234`) → `--endpoint`/`CLAUDEGRAVITY_ENDPOINT` → `ollama` CLI.

The candidate found remains the Builder after the plan is approved. Use `--bauer` to set it explicitly. The Acceptance check (`--abnahme`) is then done by a cloud model (by default the Reviewer), because the local model should not sign off on its own code.

```bash
# Ollama locally
claudegravity "Build a REST interface" --strategy local-free --bauer ollama

# Your own server on the network
claudegravity "Refactor the module" --strategy local-free \
  --endpoint http://192.168.1.50:11434/v1 --bauer endpoint --bauer-model qwen2.5-coder:7b
```

## `hybrid`

The split for a cloud CLI plus a local model, without setting each role by hand:

| Role | Filled with |
| :--- | :--- |
| 🏗️ Architect | first detected cloud CLI in the order `codex`, `claude`, `agy`, `gemini` |
| 🧐 Reviewer | local model (Ollama server, LM Studio, endpoint), reasoning model picked automatically |
| 🔨 Builder | the same local backend, code model picked automatically and never the same as the Reviewer's |
| 🔎 Acceptance | the Architect (cloud), so never the Builder |

[Stage mode](bau-loop.md#stage-mode) is on as well: the Architect cuts the plan into stages, the local model builds them one by one and gets the current state of the affected files each time. Every role you set yourself (`--architekt claude`, `--bauer-model …`) stays as you set it. If a cloud CLI or a local model is missing, ClaudeGravity says so and uses the normal assignment.

```bash
claudegravity "CSV export for invoices" --strategy hybrid --proof "python3 -m unittest discover -s tests"
```

Examples and model recommendations: [Ollama & Codex](ollama-und-codex.md).

## Escalating to the cloud

With `--escalate` (`--eskalation`) a local Builder gets a fallback: if it fails several build rounds in a row, a cloud CLI takes over the build once.

```bash
claudegravity "CSV export" --strategy local-free --proof "make test" --escalate auto --yolo
```

* **Triggers** (default: 2 in a row, `--escalate-after N`): proof command red, stage not green, completion signal rejected by the proof command or the acceptance check, call failed, or an endpoint Builder delivers no files. A successful round resets the counter.
* **Target:** `auto` takes the Architect's CLI first, otherwise the next detected cloud CLI. Or you name it (`--escalate claude`). Never the acceptance check, because the new Builder must not accept its own work; with `hybrid` and only one cloud CLI this therefore needs a different `--abnahme`.
* **Write access:** CLIs such as Claude Code, Codex or Gemini only build with write access (`--yolo` or yes at the permission prompt). Without it the loop says so once and the local model keeps building.
* **Traceable:** The switch is recorded in `LOG.md`, in `state.json` (`escalation`) and in the key figures block of `.done` or `AUDIT.md`, with round, old and new Builder and reason. It happens at most once per session; the Builder receives the last feedback.
* The dry run shows where it would escalate. Without `--escalate` the loop never moves to the cloud on its own.

## Checking presets

Combine any preset with `--dry-run` to see the concrete assignment on your machine:

```bash
claudegravity --dry-run "New feature" --strategy eco
```

## Letting MCP choose the strategy

The [MCP server](mcp-server.md) maps the goals `best-code`, `lowest-cost` (→ `eco`), `local-free`, `hybrid` and `balanced` to these presets and generates the matching command.
