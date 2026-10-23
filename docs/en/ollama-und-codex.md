# Role examples with Ollama and Codex

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/ollama-und-codex.md)

This page plays through how to split the four roles between **Codex** (cloud, through your ChatGPT subscription) and **Ollama** (local, $0). The commands are derived from the options of `loop.py` and `mcp_server.py`, but have not yet been run against a real Codex and Ollama. Check every role assignment with `--dry-run` before the first real run.

**Rule of thumb:** Ollama is fast and free as long as the pieces are small. Codex pays off where few tokens decide a lot: the plan, the plan review and the acceptance check.

**Automatic:** `--strategy hybrid` sets up the split of Variant A by itself (cloud CLI plans and accepts, Ollama reviews and builds), picks the Ollama models from the installed ones and builds the plan in stages. The variants below show what happens and how to deviate from it.

## Contents

1. [Setting up Ollama and Codex](#1-setting-up-ollama-and-codex)
2. [What to know first](#2-what-to-know-first)
3. [The quickest way: `--strategy hybrid`](#the-quickest-way---strategy-hybrid)
4. [Variant A: Codex plans, Ollama reviews, another Ollama model builds, Codex accepts](#variant-a-codex-plans-ollama-reviews-another-ollama-model-builds-codex-accepts)
5. [Variant B: Ollama plans, Codex reviews, Ollama builds, Codex accepts](#variant-b-ollama-plans-codex-reviews-ollama-builds-codex-accepts)
6. [Variant C: Everything local, only the acceptance check uses Codex](#variant-c-everything-local-only-the-acceptance-check-uses-codex)
7. [Variant D: Hard task, Codex builds, Ollama accepts](#variant-d-hard-task-codex-builds-ollama-accepts)
8. [Variant E: Stages, the task in small pieces](#variant-e-stages-the-task-in-small-pieces)
9. [Which variant when?](#which-variant-when)
10. [Via MCP: setup and calls](#via-mcp-setup-and-calls)
11. [Ollama models for a Mac M4 with 48 GB](#ollama-models-for-a-mac-m4-with-48-gb)
12. [Troubleshooting checklist](#troubleshooting-checklist)

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
| An Ollama Builder sees no files | Endpoint Builders get the plan and, from the second round on, the current content of the files they wrote; in stage mode also the files the stage names. They rewrite each file in full. | Use [stage mode](#variant-e-stages-the-task-in-small-pieces) (on automatically for Ollama Builders). |
| Ollama runs no tests | The Builder only writes files. | Always pass `--proof "<test command>"`; the loop runs it itself. |
| Verdict only from `VERDICT:` | If the last line `VERDICT: APPROVED` is missing, the review does not count as approval. | For Reviewer and acceptance, choose models that follow format instructions (see [models](#ollama-models-for-a-mac-m4-with-48-gb)). |
| Two Ollama roles | The same backend with **different models** counts as a different identity. The same model reviews itself. If the model is missing, the loop picks one from the installed models and never gives Reviewer or acceptance the Builder's model. | Different models for Architect/Reviewer and for Builder/acceptance; without flags the loop takes care of it. |
| Acceptance | Defaults to the Reviewer, never the Builder. If the Reviewer is another Ollama model, **Ollama** accepts, not Codex. | Set Codex as acceptance explicitly with `--abnahme codex`. |
| Approval menu | After the review the loop asks for approval in the terminal, and before phase 3 for write permissions. | Start in a terminal. `--yolo` skips the permission question, `--plan-auto` the approval (then only a plan with `APPROVED` is built). |

The task itself is your strongest lever: write into the task text what the plan should look like, for example "Split the plan into numbered steps; each step changes at most one file and names its test". The Architect receives the text verbatim.

In all examples `~/Projekte/rechnung` is the project and `python3 -m unittest discover -s tests` the proof command. Replace both with your project and its own test command (e.g. `npm test`, `vendor/bin/phpunit`).

## The quickest way: `--strategy hybrid`

```bash
claudegravity "Add a CSV export for invoices" \
  -p ~/Projekte/rechnung \
  --strategy hybrid \
  --proof "python3 -m unittest discover -s tests" \
  --dry-run
```

This is what the loop sets up by itself (with the models from section 1 installed):

| Role | Automatic | Change with |
| :--- | :--- | :--- |
| 🏗️ Architect | first cloud CLI of `codex`, `claude`, `agy`, `gemini` | `--architekt` |
| 🧐 Reviewer | Ollama with a reasoning model, e.g. `gpt-oss:20b` | `--pruefstatiker`, `--pruefstatiker-model` |
| 🔨 Builder | Ollama with a code model, e.g. `qwen3-coder:30b` | `--bauer`, `--bauer-model` |
| 🔎 Acceptance | the Architect | `--abnahme`, `--abnahme-model` |
| 🧩 Stages | on: plan with `## Etappen`, each stage one build round with the proof command | `--etappen aus` |

The dry run shows the assignment and the complete command. Without `--dry-run` the real run starts. If you do not want to be asked at all, add `--plan-auto`: the loop then builds as soon as the Reviewer reports `APPROVED`, and stops otherwise.

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

This is the answer to "Ollama is faster with small pieces", and the loop does it by itself. Stage mode is on automatically for Ollama, LM Studio and endpoint Builders (`--etappen auto`), and with `--etappen an` also for Codex or Claude.

How it runs:

1. The Architect (e.g. Codex) is told to end the plan with `## Etappen`: 2 to 8 stages, each changing at most two files and testable afterwards.
2. The Reviewer checks plan and stages. After approval the loop lists the stages.
3. In each round the Ollama Builder gets only the current stage, the completed stages, the plan and the **current content** of the affected files and the files it already wrote.
4. The loop runs `--proof`. Green: next stage. Red: the output goes back to the Builder, up to 3 attempts per stage; then the loop stops and `claudegravity -c` continues.
5. After the last stage, Codex accepts the whole diff. If there are findings, the loop appends a rework stage.

```bash
claudegravity "CSV export for invoices with filters by period and customer" \
  -p ~/Projekte/rechnung \
  --architekt codex --architekt-effort medium \
  --pruefstatiker ollama --pruefstatiker-model gpt-oss:20b \
  --bauer ollama --bauer-model qwen3-coder:30b \
  --abnahme codex \
  --proof "python3 -m unittest discover -s tests" \
  --merge
```

Shorter, with the same roles: `--strategy hybrid --proof "…" --merge`.

**Instructions**

1. Without `--proof` every stage counts as done after one round. Always pass the project's test command.
2. If the project has no tests yet, `unittest discover` is red before the first stage. Add a small test first, or write into the task that stage 1 creates the tests.
3. In the approval menu, read the `## Etappen` section with `[4]`. Have stages that are too big cut smaller with `[2]`.
4. You do not need `-m`: without it the run gets 2 rounds per stage plus 2.
5. `LOG.md` in the session folder shows the progress (`Etappe n/N erledigt`); `state.json` remembers stage and state for `-c`.
6. Stages by hand, each as its own run, still work: one stage as the task, `--etappen aus`, `--merge`.

## Which variant when?

| Situation | Variant | Codex usage |
| :--- | :--- | :--- |
| Medium task in an existing project | A | plan + acceptance |
| New small project, the plan may be drafted locally | B | review + acceptance |
| Small fix with known files | C | acceptance only |
| Big rewrite, many files, tests inside the project | D | review + the whole build |
| Larger task, but build locally | E or `--strategy hybrid` | one plan in stages + one acceptance at the end |

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

**2. Have the command computed**: tool `claudegravity_optimize`, Variant A automatically:

```json
{
  "task": "Add a CSV export for invoices",
  "priority": "hybrid",
  "project_path": "/Users/<name>/Projekte/rechnung",
  "proof": "python3 -m unittest discover -s tests"
}
```

Result: `claudegravity '…' --strategy hybrid --proof '…' -p …`. The loop picks the Ollama models from the installed models at start; the optimizer shows "automatic" for them.

**3. A specific variant**: the tools take roles and models as parameters. Variant B:

```json
{
  "task": "Add a CSV export for invoices",
  "architekt": "ollama", "architekt_model": "qwen3:30b",
  "pruefstatiker": "codex",
  "bauer": "ollama", "bauer_model": "qwen3-coder:30b",
  "abnahme": "codex",
  "stages": "an",
  "proof": "python3 -m unittest discover -s tests"
}
```

More parameters: `abnahme_model`, `approve_plan` (`--plan-auto`) and `merge` (`--merge`). The optimizer shows model names only for Claude and Gemini; Codex uses its default model unless you set one.

With the skill [`skills/claudegravity`](../../skills/claudegravity/SKILL.md) the assistant already knows the role flags.

**4. `claudegravity_run`**: the same parameters. With `background: false` the tool returns the command with `cd` to copy. With `background: true` the loop starts without a terminal and with `--plan-auto`: it only builds if the Reviewer reports `APPROVED`. Ollama Builders do not need `yolo` for that; a Codex Builder (Variant D) does.

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
