# Tests

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/tests.md)

Tests run through all three phases. This page describes how ClaudeGravity handles tests in your project and how to test ClaudeGravity itself.

## Tests in the workflow

| Phase | What happens with tests |
| :--- | :--- |
| 🏗️ **Architect** | The plan must contain **test criteria** (alongside affected files, architecture and edge cases). |
| 🧐 **Reviewer** | Explicitly checks the plan for **missing tests** and requests them with `VERDICT: REVISE`. |
| 🔨 **Builder** | Should run tests every round and only create `.done` once everything is tested. |

With `--proof "<test command>"` ClaudeGravity runs the test command **itself** after every build round or stage; a completion signal only counts once it is green and the acceptance check agrees. Without `--proof` the loop relies on builder, plan and acceptance check (see [Build loop](bau-loop.md)).

## Making tests reliable

* **Write the test command into the project's `CLAUDE.md`**, e.g. `Tests: python -m pytest -q`. The file is passed as context to the Architect, who carries the command over into the plan (see [Sessions & files](sessions-und-dateien.md#project-context-claudemd--knowledge)).
* **Define a completion criterion**, e.g. "Only create `.done` once `pytest` passes without errors."
* **Check in the approval menu** ([4] Show) whether the plan names concrete tests. If not: [2] Changes → [3] Feedback, e.g. "Add unit tests for all edge cases."
* **With `--strategy best-code`** all phases get high effort, which pays off for test-heavy tasks.
* **Verify yourself after the run**: run the test suite locally once before you commit.

### Endpoint Builders and tests

Ollama, LM Studio and custom server Builders **cannot run commands**. They only write files via `filepath:` blocks. With `--proof` the loop runs the tests for them and returns the output in the next round; without `--proof` no tests run.

## Testing ClaudeGravity itself

The unit tests only need Python and no AI:

```bash
python3 -m unittest discover -s tests
```

| Suite | Checks |
| :--- | :--- |
| `test_adapters.py` | Contract of all backend adapters: plain and garbage output, errors, rate limits, time limits, HTTP errors |
| `test_resume.py` | Atomic session state, damaged `state.json`, crash via SIGKILL during the build and after the completion signal |
| `test_smoke.py` | Full run with a fake server for `balanced` and `local-free` |
| `test_review_safety.py`, `test_stages.py` | End to end with fake CLIs or fake endpoints, acceptance check, stages |
| `test_config.py`, `test_templates.py`, `test_wizard.py` | Profiles, environment, templates, setup |
| `test_retry.py`, `test_audit.py`, `test_errors.py`, `test_kpi.py` | Retries, audit, error codes, key figures |
| `test_budget.py`, `test_estimate.py` | Budget limits, cost estimate from earlier sessions |
| `test_progress.py` | Status line after every AI call, abort reason at the round limit |
| `test_benchmark.py` | Benchmark pack: tasks red at first, reference solution green, flow in fake mode |
| `test_events.py` | Structured event log `events.jsonl` |
| `test_builder_resume.py` | Continuing the Builder session: short prompt, `codex exec resume`, fallback to a fresh session, Builder switch |
| `test_edit_blocks.py` | Search/replace blocks from endpoints: several pairs, not found/ambiguous, blocked paths, feedback |
| `test_escalation.py` | Escalation from a local Builder to the cloud: target choice, write access, end to end |

### Smoke matrix

The CI job `smoke` (`.github/workflows/tests.yml`) runs on Linux, macOS and Windows, each with `balanced` and `local-free`. A fake server plays all roles via the OpenAI-compatible API; the loop builds, runs `--proof` and does the acceptance check. Stdout, session folder, build logs and `summary.json` with the key figures are attached to the run as artifact `smoke-<os>-<strategy>`. Locally:

```bash
python3 tests/smoke/run_smoke.py --strategy local-free --out smoke-artifacts
```

Real CLIs (`claude`, `codex`, `agy` …) do not run in CI, because no subscriptions are signed in there.

### Golden fixtures

`tests/test_golden.py` compares central outputs with reference files in `tests/golden/`: key figures block, error catalog, `--print-effective-config` with profile, template and environment, a dry run with `local-free` and the complete smoke run (files in the session folder, `LOG.md`, key figures). Paths, times and ports are normalized first. If a commit changes one of these outputs, CI fails and shows the difference. If the change is intended:

```bash
UPDATE_GOLDEN=1 python3 -m unittest tests.test_golden
```

and commit the changed files in `tests/golden/`.

### Lint

CI checks the code with [Ruff](https://docs.astral.sh/ruff/) (rules in `ruff.toml`: syntax, Pyflakes, Bugbear, simplifications). Ruff is only a tool for development and CI; the loop itself still needs nothing but the standard library. CI checks the formatting with `ruff format --check .`. Locally: `uvx ruff check . && uvx ruff format --check .` (or inside a venv: `pip install ruff`, then `ruff format .` and `ruff check .`).

The code lives in the package `claudegravity/` (one module per concern); `loop.py` is only the entry point. A test that replaces a function patches the module where it is called, for example `mock.patch.object(loop.runner, "interruptible_sleep")`; a patch on `loop.<name>` does not reach it.

Without AI calls and without changing files:

```bash
# Detection of CLIs and endpoints
claudegravity --info

# Role and model assignment for a preset
claudegravity --dry-run "Test task" --strategy local-free

# Optimizer
claudegravity-mcp --optimize "Fix the login bug" --priority lowest-cost

# MCP server responds to tools/list
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp_server.py
```

A real run without risk is best done in the demo project:

```bash
claudegravity "Add a greeting function with a test" -p projects/demo -m 3
```

## Benchmark pack

`tools/benchmark/benchmark.py` runs fixed tasks with several strategies and compares the key figures. This shows, on your machine and with your subscriptions, which setup succeeds how often and what it costs.

```bash
# real models: every task with two strategies (everything after -- goes to claudegravity)
python3 tools/benchmark/benchmark.py --strategies balanced,hybrid --out bench -- --yolo

# one task only, your own roles
python3 tools/benchmark/benchmark.py --tasks median-bug --strategies eco -- --bauer codex --yolo

# without models: only checks the flow (a fake server returns the reference solution)
python3 tools/benchmark/benchmark.py --fake
```

* **Tasks** live under `tools/benchmark/tasks/<name>/`: `task.txt`, `project/` (starting state with tests that are red at first) and `solution/` (only for `--fake`). Included are `fizzbuzz` (new function), `median-bug` (bug fix) and `slugify` (feature with umlauts). A task of your own is another folder following this pattern. The task texts are German, like the loop's prompts.
* **Flow:** Every run gets a fresh copy of `project/` as a Git repository in a throwaway folder and starts with `--plan-auto`, `--log-format json` and `--proof "python -m unittest discover -s tests"`. CLI Builders need write access (`-- --yolo`); your own project stays untouched.
* **Result:** A table per task and strategy (result, build rounds, tokens, reported costs, duration) plus a total per strategy. With `--out` also `results.json`, `results.md` and the output of every run. Exit code 0 only if all runs succeed.
* `--timeout` limits every run (default 1800 s). Costs only appear if providers report them.
