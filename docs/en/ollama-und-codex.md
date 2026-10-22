# Role examples with Ollama and Codex

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/ollama-und-codex.md)

This page plays through how to split the four roles between **Codex** (cloud, through your ChatGPT subscription) and **Ollama** (local, $0). The commands are derived from the options of `loop.py` and `mcp_server.py`, but have not yet been run against a real Codex and Ollama. Check every role assignment with `--dry-run` before the first real run.

**Rule of thumb:** Ollama is fast and free as long as the pieces are small. Codex pays off where few tokens decide a lot: the plan, the plan review and the acceptance check.

## Contents

1. [Setting up Ollama and Codex](#1-setting-up-ollama-and-codex)
2. [What to know first](#2-what-to-know-first)
3. [Variant A: Codex plans, Ollama reviews, another Ollama model builds, Codex accepts](#variant-a-codex-plans-ollama-reviews-another-ollama-model-builds-codex-accepts)
4. [Variant B: Ollama plans, Codex reviews, Ollama builds, Codex accepts](#variant-b-ollama-plans-codex-reviews-ollama-builds-codex-accepts)
5. [Variant C: Everything local, only the acceptance check uses Codex](#variant-c-everything-local-only-the-acceptance-check-uses-codex)
6. [Variant D: Hard task, Codex builds, Ollama accepts](#variant-d-hard-task-codex-builds-ollama-accepts)
7. [Variant E: Stages, the task in small pieces](#variant-e-stages-the-task-in-small-pieces)
8. [Which variant when?](#which-variant-when)
9. [Via MCP: setup and calls](#via-mcp-setup-and-calls)
10. [Ollama models for a Mac M4 with 48 GB](#ollama-models-for-a-mac-m4-with-48-gb)
11. [Troubleshooting checklist](#troubleshooting-checklist)

## 1. Setting up Ollama and Codex

### Ollama (macOS)

```bash
brew install ollama            # or the app from https://ollama.com/download
ollama serve                   # only needed without the app; the app starts the server itself

ollama pull qwen3-coder:30b    # Builder
ollama pull gpt-oss:20b        # Reviewer / acceptance
ollama pull qwen3:30b          # Architect
curl http://localhost:11434/api/tags   # lists the models with their exact names
```

Settings that matter for the loop (for the app via `launchctl`; quit and restart Ollama afterwards):

```bash
launchctl setenv OLLAMA_CONTEXT_LENGTH 32768   # plan + files fit into the context
launchctl setenv OLLAMA_KEEP_ALIVE 30m         # model stays loaded between rounds
launchctl setenv OLLAMA_MAX_LOADED_MODELS 2    # e.g. reviewer and builder at the same time
launchctl setenv OLLAMA_FLASH_ATTENTION 1      # less memory for the context
```

If you run `ollama serve` in a terminal, set the same variables with `export` beforehand. `ollama ps` shows whether the context applies (column `CONTEXT` in newer versions).

> [!IMPORTANT]
> ClaudeGravity talks to Ollama through the OpenAI interface (`/v1/chat/completions`). The context length cannot be set per request there. Without `OLLAMA_CONTEXT_LENGTH`, Ollama uses its default, which depending on the version is only a few thousand tokens. Ollama then silently cuts off the plan or the diff.

Ollama must be running **before** ClaudeGravity starts, otherwise it is not detected. If Ollama runs on another machine in your home network, set `OLLAMA_HOST=<machine>:11434`; everything else is under [Backends](backends.md#ollama--co-from-the-local-network).

### Codex CLI

```bash
npm install -g @openai/codex   # or: brew install --cask codex
codex login                    # sign in with your ChatGPT account (subscription), no API key needed
codex exec -s read-only "Reply with OK only"   # checks sign-in and sandbox
```

ClaudeGravity calls Codex as `codex exec -s <sandbox> --json` and sends the prompt via stdin. Architect, Reviewer and acceptance get `-s read-only`; only a Codex Builder gets `-s workspace-write`, and only after you answer "J" before phase 3 or with `--yolo`. `--architekt-effort`, `--pruefstatiker-effort`, `--bauer-effort` and `--abnahme-effort` are passed to Codex as `model_reasoning_effort` (`max` becomes `xhigh`). Set a model with `--architekt-model` etc.; without one, Codex uses its default model.

> [!NOTE]
> `codex exec` only works inside a Git repository, so create your project with `git init`. That fits anyway, because ClaudeGravity creates its own Git workspace per session.

### Check

```bash
claudegravity --info
```

The list must contain `codex` and `ollama` (usually also `ollama-cli`). If `ollama` is missing, the server is not answering on `http://localhost:11434` or on the address from `OLLAMA_HOST`.

## 2. What to know first

These points decide whether a split with Ollama works:

| Point | What happens | What you do |
| :--- | :--- | :--- |
| `--bauer ollama` etc. | The key `ollama` is the Ollama **server** (OpenAI API). If it is missing from `--info`, the loop silently picks another backend. | `--dry-run` before every run. |
| Ollama sees no files | An Ollama Reviewer only gets the task and the plan, an Ollama acceptance check only the diff (up to 60,000 characters). Codex, by contrast, reads the project itself. | Use Ollama where the text is enough, Codex where the project has to be known. |
| An Ollama Builder has no memory | Every build round gets the whole plan and the feedback from the proof command, but neither its earlier answers nor the current state of the files. It rewrites each file in full. | Cut tasks small enough for one round. For more: [Variant E](#variant-e-stages-the-task-in-small-pieces). |
| Ollama runs no tests | The Builder only writes files. | Always pass `--proof "<test command>"`; the loop runs it itself. |
| Verdict only from `VERDICT:` | If the last line `VERDICT: APPROVED` is missing, the review does not count as approval. | For Reviewer and acceptance, choose models that follow format instructions (see [models](#ollama-models-for-a-mac-m4-with-48-gb)). |
| Two Ollama roles | The same backend with **different models** counts as a different identity. The same model reviews itself. | Always pick different models for Architect/Reviewer and for Builder/acceptance. |
| Acceptance | Defaults to the Reviewer, never the Builder. If the Reviewer is another Ollama model, **Ollama** accepts, not Codex. | Set Codex as acceptance explicitly with `--abnahme codex`. |
| Approval menu | After the review the loop asks for approval in the terminal, and before phase 3 for write permissions. | Start in a terminal. `--yolo` only skips the permission question. |

The task itself is your strongest lever: write into the task text what the plan should look like, for example "Split the plan into numbered steps; each step changes at most one file and names its test". The Architect receives the text verbatim.

In all examples `~/Projekte/rechnung` is the project and `python3 -m unittest discover -s tests` the proof command. Replace both with your project and its own test command (e.g. `npm test`, `vendor/bin/phpunit`).

## Variant A: Codex plans, Ollama reviews, another Ollama model builds, Codex accepts

| Role | Backend | Model |
| :--- | :--- | :--- |
| 🏗️ Architect | Codex | default, effort `high` |
| 🧐 Reviewer | Ollama | `gpt-oss:20b` |
| 🔨 Builder | Ollama | `qwen3-coder:30b` |
| 🔎 Acceptance | Codex | default, effort `high` |

Codex knows the project and writes a plan in small steps. A local reasoning model checks the plan for gaps for free. A fast code model builds. At the end Codex reviews the diff with access to the project.

```bash
claudegravity "Add a CSV export for invoices. Split the plan into numbered steps; each step changes at most one file and names the function and its test." \
  -p ~/Projekte/rechnung \
  --architekt codex --architekt-effort high \
  --pruefstatiker ollama --pruefstatiker-model gpt-oss:20b \
  --bauer ollama --bauer-model qwen3-coder:30b \
  --abnahme codex --abnahme-effort high \
  --proof "python3 -m unittest discover -s tests" \
  -m 6 --dry-run
```

Without `--dry-run` the real run starts.

> [!NOTE]
> For the real run, use the same command without `--dry-run`. The "Generierter Shell-Befehl" at the end of the dry run currently drops `--architekt`, `--pruefstatiker`, `--bauer` and the effort flags, so it is incomplete for these variants. Also, without `--abnahme` the dry run sometimes shows Codex as acceptance although in the real run another Ollama model would accept. So always set `--abnahme` explicitly.

**Instructions**

1. Check the dry run: Reviewer and Builder show `Ollama (Lokal: http://localhost:11434)` with two different models, the acceptance shows `Codex CLI`.
2. After phase 2, read the plan with `[4]` in the approval menu. If a step touches more than one file or lacks a test, ask for changes with `[2]`. Codex revises, Ollama reviews again.
3. The answer to the permission question before phase 3 does not matter: Ollama does not write files itself, the loop does that through `filepath:` blocks.
4. If Codex refuses acceptance, the Builder gets the findings as feedback. After `--max-inspections` (default 2) the task stays open; `claudegravity -c` continues from there.
5. If the task is too big for one build round (the proof stays red, files contradict each other), stop and switch to [Variant E](#variant-e-stages-the-task-in-small-pieces).

## Variant B: Ollama plans, Codex reviews, Ollama builds, Codex accepts

| Role | Backend | Model |
| :--- | :--- | :--- |
| 🏗️ Architect | Ollama | `qwen3:30b` |
| 🧐 Reviewer | Codex | default, effort `high` |
| 🔨 Builder | Ollama | `qwen3-coder:30b` |
| 🔎 Acceptance | Codex | same as the Reviewer (default) |

The plan costs nothing. Codex reviews it with access to the project and catches the typical mistakes of small models (invented files, missing edge cases). Without further flags the acceptance falls to the Reviewer, Codex, because it is not the Builder.

```bash
claudegravity "Add a CSV export for invoices. Plan in numbered steps, each step at most one file." \
  -p ~/Projekte/rechnung \
  --architekt ollama --architekt-model qwen3:30b \
  --pruefstatiker codex --pruefstatiker-effort high \
  --bauer ollama --bauer-model qwen3-coder:30b \
  --proof "python3 -m unittest discover -s tests" \
  --max-rounds 3 -m 6
```

**Instructions**

1. The local Architect only knows the task text and the loaded `CLAUDE.md`/`AGENTS.md`/`knowledge/` files, not the code. Put important file names and interfaces into the task or into `CLAUDE.md`.
2. `--max-rounds 3` gives the small Architect one more round to work in the findings from Codex.
3. If Codex still says `REVISE` after all rounds, choose `[3] Swap` in the approval menu: Codex then plans and Ollama reviews, which is Variant A.
4. If you want the acceptance check to be more thorough than the review, set `--abnahme codex --abnahme-effort xhigh`.

## Variant C: Everything local, only the acceptance check uses Codex

| Role | Backend | Model |
| :--- | :--- | :--- |
| 🏗️ Architect | Ollama | `qwen3:30b` |
| 🧐 Reviewer | Ollama | `gpt-oss:20b` |
| 🔨 Builder | Ollama | `qwen3-coder:30b` |
| 🔎 Acceptance | Codex | default, effort `high` |

The cheapest way: Codex is called exactly once per acceptance round. Planner and Reviewer are two different local models; that is more independent than self-review, but less independent than two providers. Codex is the only check here that reads the project itself.

```bash
claudegravity "Add the missing validation of the invoice number in src/rechnung.py and test it." \
  -p ~/Projekte/rechnung \
  --architekt ollama --architekt-model qwen3:30b \
  --pruefstatiker ollama --pruefstatiker-model gpt-oss:20b \
  --bauer ollama --bauer-model qwen3-coder:30b \
  --abnahme codex --abnahme-effort high \
  --proof "python3 -m unittest discover -s tests" \
  -m 5
```

**Instructions**

1. Only for small, clearly bounded tasks with file names in the task text.
2. Three models of roughly 14 to 19 GB each do not fit into memory at the same time. Ollama reloads when the role changes; each switch costs a few seconds. With `OLLAMA_MAX_LOADED_MODELS 2`, Reviewer and Builder often both stay loaded.
3. Do not drop `--abnahme codex`, otherwise `gpt-oss:20b` does the acceptance and no model with project access sees the code.

## Variant D: Hard task, Codex builds, Ollama accepts

| Role | Backend | Model |
| :--- | :--- | :--- |
| 🏗️ Architect | Ollama | `qwen3:30b` |
| 🧐 Reviewer | Codex | default, effort `high` |
| 🔨 Builder | Codex | default, effort `medium` |
| 🔎 Acceptance | Ollama | `gpt-oss:20b` |

For tasks that change several files at once or need to run tests inside the project. Codex builds with `-s workspace-write`, sees the state of the files, runs commands itself and keeps track between rounds. Ollama does the draft and the acceptance, the roles that only need text. This uses more of your Codex quota than A to C.

```bash
claudegravity "Move invoice storage from JSON files to SQLite, including a migration of the existing data." \
  -p ~/Projekte/rechnung \
  --architekt ollama --architekt-model qwen3:30b \
  --pruefstatiker codex --pruefstatiker-effort high \
  --bauer codex --bauer-effort medium \
  --abnahme ollama --abnahme-model gpt-oss:20b \
  --proof "python3 -m unittest discover -s tests" \
  -m 8
```

**Instructions**

1. Answer the permission question before phase 3 with "J" (or pass `--yolo`), otherwise Codex may not write.
2. Codex builds in the session copy (Git workspace), not in your working folder. With `--merge` the result is merged into your branch after `.done`; otherwise you merge the session branch yourself.
3. The Ollama acceptance sees the diff up to 60,000 characters (about 15,000 tokens). With `OLLAMA_CONTEXT_LENGTH 32768` that fits; for bigger rewrites prefer `--abnahme codex --abnahme-model <another model>` or a smaller task.
4. Here Codex reviews the plan and also builds it. That is allowed (the Architect is Ollama), but the only outside check of the code is the Ollama acceptance plus the proof command. Good tests matter most here.

## Variant E: Stages, the task in small pieces

This is the answer to "Ollama is faster with small pieces". The loop does not split a task by itself, and an Ollama Builder does not see in round 2 what it wrote in round 1. So Codex cuts the task into stages once, and each stage runs as its own short loop on top of the previous stage.

**Step 1: let Codex cut the stages** (read-only, without the loop):

```bash
cd ~/Projekte/rechnung
codex exec -s read-only --output-last-message etappen.txt \
  "Split this task into 3 to 8 stages that can be implemented one after another. Each stage changes at most two files and is testable afterwards. Output only the stages, one per line, without numbers and without blank lines. Task: CSV export for invoices with filters by period and customer."
cat etappen.txt   # read, shorten, reorder: you decide
```

**Step 2: build the stages one after another**, each with Variant A:

```bash
GOAL="CSV export for invoices with filters by period and customer"
while IFS= read -r stage <&3; do
  [ -z "$stage" ] && continue
  echo "=== Stage: $stage"
  claudegravity "Overall goal: $GOAL. Implement ONLY this stage now: $stage" \
    -p ~/Projekte/rechnung \
    --architekt codex --architekt-effort medium \
    --pruefstatiker ollama --pruefstatiker-model gpt-oss:20b \
    --bauer ollama --bauer-model qwen3-coder:30b \
    --abnahme codex \
    --proof "python3 -m unittest discover -s tests" \
    --merge -m 3
done 3< etappen.txt
```

**Instructions**

1. `3< etappen.txt` and `<&3` are deliberate: the loop reads the stages through a separate channel, so the approval menu keeps reading from your keyboard.
2. `--merge` is required: only then does each accepted stage land in your branch, and the next stage builds on it.
3. The loop does not stop the shell loop by itself. If a stage is not accepted, choose `[5] Beenden` in the approval menu of the next stage or press Ctrl+C, then continue the open stage with `claudegravity -c -p ~/Projekte/rechnung`.
4. Here Codex needs a small plan and an acceptance check per stage. For even less Codex usage, use Variant C instead of A in step 2.
5. On Windows (PowerShell) the loop looks like this: `foreach ($stage in Get-Content etappen.txt) { if ($stage) { .\claudegravity.ps1 "Overall goal: $GOAL. Implement ONLY this stage now: $stage" <other flags as above> } }`.

## Which variant when?

| Situation | Variant | Codex usage |
| :--- | :--- | :--- |
| Medium task in an existing project | A | plan + acceptance |
| New small project, the plan may be drafted locally | B | review + acceptance |
| Small fix with known files | C | acceptance only |
| Big rewrite, many files, tests inside the project | D | review + the whole build |
| Larger task, but build locally | E | stages + plan and acceptance per stage |

## Via MCP: setup and calls

With the [MCP server](mcp-server.md) an assistant (Claude Code or Codex itself) can prepare ClaudeGravity for you. First, Ollama and Codex must be set up as in [section 1](#1-setting-up-ollama-and-codex) and `claudegravity --info` must show both.

### Setup in Codex

```bash
codex mcp add claudegravity -- python3 ~/Projekte/claudegravity-loop/mcp_server.py
codex mcp list
```

Or directly in `~/.codex/config.toml`:

```toml
[mcp_servers.claudegravity]
command = "python3"
args = ["/Users/<name>/Projekte/claudegravity-loop/mcp_server.py"]
env = { PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", OLLAMA_HOST = "localhost:11434" }
```

### Setup in Claude Code

```bash
claude mcp add claudegravity --scope user -- python3 ~/Projekte/claudegravity-loop/mcp_server.py
claude mcp list
```

> [!TIP]
> An MCP server inherits the `PATH` of the program that starts it. On macOS that often lacks `/opt/homebrew/bin`. The server then finds neither `codex` nor `ollama`, and `claudegravity_info` does not list them. Set `PATH` in the `env` block as shown above.

### Calls

**1. Check what the server sees**: tool `claudegravity_info`, no parameters. Expected: `Codex CLI (codex)`, `Ollama CLI (ollama-cli)` and `Ollama (Lokal: …) (ollama)`.

**2. Have the command computed**: tool `claudegravity_optimize`:

```json
{
  "task": "Add a CSV export for invoices",
  "priority": "local-free",
  "project_path": "/Users/<name>/Projekte/rechnung",
  "proof": "python3 -m unittest discover -s tests",
  "max_iterations": 6
}
```

If no CLIs other than Codex and Ollama are installed, this yields `claudegravity '…' --strategy local-free --bauer-model qwen2.5-coder:latest --proof '…' -m 6 -p …`. In the run this becomes roughly Variant A: Codex plans, `ollama run qwen2.5-coder:latest` reviews, the Ollama server builds with `qwen2.5-coder:latest`, Codex accepts. If `claude` is installed as well, Claude plans instead of Codex.

> [!WARNING]
> The MCP tools have no role or model parameters. The model names `claudegravity_optimize` shows for Architect and Reviewer (e.g. `gemini-2.5-pro`) are defaults for Claude/Gemini and do not apply to Codex and Ollama. You have to fetch the Builder value `qwen2.5-coder:latest` beforehand with `ollama pull qwen2.5-coder`. For Variants A to E with your own models, use the command from this page.

**3. Start a variant through the assistant**: since the tools take no roles, give the assistant the finished command. Example prompt in Codex or Claude Code:

```text
In the terminal, start claudegravity using Variant A from docs/en/ollama-und-codex.md
for the project ~/Projekte/rechnung with the task "CSV export for invoices".
Run the same command with --dry-run first and show me the role assignment.
```

With the skill [`skills/claudegravity`](../../skills/claudegravity/SKILL.md) the assistant already knows the role flags.

**4. `claudegravity_run`**: with `background: false` the tool only returns the command with `cd` to copy. `background: true` is not suitable for these variants: the approval menu and the permission question need a terminal.

**Testing without a client** (one JSON-RPC line via stdin):

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"claudegravity_optimize","arguments":{"task":"CSV export","priority":"local-free","proof":"python3 -m unittest discover -s tests"}}}' \
  | python3 ~/Projekte/claudegravity-loop/mcp_server.py
```

## Ollama models for a Mac M4 with 48 GB

A Mac with 48 GB shares its memory between system and graphics. By default macOS gives the GPU about three quarters of it, roughly 36 GB. Context (KV cache) and system load come off that. Realistic is **one model up to about 20 GB plus a second one up to about 14 GB at the same time**. A 70B model (about 40 GB at Q4) does not fit sensibly.

The sizes are for the default quantization of the Ollama library (mostly `Q4_K_M`, `MXFP4` for `gpt-oss`) and are download sizes; the context comes on top at runtime. As of this page: October 2026. New models appear all the time; check [ollama.com/library](https://ollama.com/library) for successors.

| Role | Recommendation | Size | Why | Alternative |
| :--- | :--- | :--- | :--- | :--- |
| 🔨 Builder | `qwen3-coder:30b` | ~19 GB | Mixture-of-experts with about 3B active parameters: as fast as a small model, code quality of a big one. Ideal for small pieces. | `qwen2.5-coder:32b` (~20 GB, dense, slower, very stable output format), `devstral:24b` (~14 GB) |
| 🔨 Builder, very small pieces | `qwen2.5-coder:14b` | ~9 GB | Leaves room for a big reviewer next to it. | `qwen2.5-coder:7b` (~4.7 GB) for single files |
| 🧐 Reviewer | `gpt-oss:20b` | ~14 GB | Thinks before answering (reasoning), follows format rules such as `VERDICT:` well. | `qwen3:14b` (~9 GB), `deepseek-r1:14b` (~9 GB) |
| 🏗️ Architect | `qwen3:30b` | ~19 GB | Fast MoE model with a thinking mode, good at structured plans. | `qwen3:32b` (~20 GB, more thorough, slower), `gpt-oss:20b` |
| 🔎 Acceptance (Variant D) | `gpt-oss:20b` | ~14 GB | Same as Reviewer; the diff needs at least 32k context. | `qwen3:30b` |

**Proven pairs that stay loaded together** (with `OLLAMA_MAX_LOADED_MODELS 2` and 32k context):

| Pair | Together | Fits |
| :--- | :--- | :--- |
| `gpt-oss:20b` + `qwen3-coder:30b` | ~33 GB | Variant A, E (reviewer + builder) |
| `qwen3:30b` + `qwen3-coder:30b` | ~38 GB | Variant B; tight, Ollama may reload when roles change |
| `gpt-oss:20b` + `qwen2.5-coder:14b` | ~23 GB | Variant A/E with plenty of room for a large context |

If you want to give the GPU more memory, you can raise the limit, e.g. `sudo sysctl iogpu.wired_limit_mb=40960` (valid until reboot). The system then keeps only 8 GB; close other large programs first.

## Troubleshooting checklist

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Dry run shows a different backend for `--bauer ollama` | The Ollama server was not running at start | Start Ollama, `curl http://localhost:11434/api/tags`, restart |
| Review ends without approval, "kein lesbares VERDICT" | The local model does not follow the answer format | Another reviewer model (`gpt-oss:20b`, `qwen3:14b`) |
| Builder writes half files or forgets parts | Context too small or task too big | Raise `OLLAMA_CONTEXT_LENGTH`, Variant E |
| Timeout after 900 s | Big model, long plan | `--timeout 1800` or a smaller model |
| `Codex Fehler: … not inside a trusted directory` or similar | The project is not a Git repository | `git init` in the project |
| Codex Builder changes nothing | Permission question answered with "n" | Continue with `claudegravity -c --yolo` |
| Codex limit reached | Subscription quota used up | Wait in the limit menu, or `--auto-switch`: another installed CLI steps in, never the provider of the counterpart role |

More problems: [Troubleshooting](fehlerbehebung.md).
