# Strategy presets

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/strategien.md)

Instead of configuring each role individually, you pick a preset with `--strategy <name>` (alias `--preset`). It sets **defaults** for effort and the Builder model; anything you specify explicitly (`--bauer-model`, `--architekt-effort`, …) takes precedence.

## Overview

| Preset | Aliases | Architect effort | Reviewer effort | Builder effort | Builder model (default) | Use case |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `balanced` *(default)* | – | `high` only with `agy` | `high` only with `agy` | CLI default | same as Architect | Everyday work |
| `best-code` | `quality` | `high` | `high` | `high` | same as Architect | Core systems, security, large refactorings |
| `eco` | `economy`, `cost` | `medium` | `medium` | `low` | `claude-3-5-haiku` (with `claude`), otherwise `gemini-2.5-flash` | Up to ~70% token savings |
| `local-free` | `free`, `local` | `high` | `high` | `low` | `qwen2.5-coder:32b` (endpoint), `qwen2.5-coder:latest` (Ollama), otherwise `local-model` | €0 API cost in the build loop |

> [!NOTE]
> `--effort` values are currently only passed on to `agy` (Antigravity) as `--effort`. For `claude` and other CLIs they only show up in the audit report.

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

## Checking presets

Combine any preset with `--dry-run` to see the concrete assignment on your machine:

```bash
claudegravity --dry-run "New feature" --strategy eco
```

## Letting MCP choose the strategy

The [MCP server](mcp-server.md) maps the goals `best-code`, `lowest-cost` (→ `eco`), `local-free` and `balanced` to these presets and generates the matching command.
