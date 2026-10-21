# Tests

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/tests.md)

Tests run through all three phases. This page describes how ClaudeGravity handles tests in your project and how to test ClaudeGravity itself.

## Tests in the workflow

| Phase | What happens with tests |
| :--- | :--- |
| 🏗️ **Architect** | The plan must contain **test criteria** (alongside affected files, architecture and edge cases). |
| 🧐 **Reviewer** | Explicitly checks the plan for **missing tests** and requests them with `VERDICT: REVISE`. |
| 🔨 **Builder** | Should run tests every round and only create `.done` once everything is tested. |

ClaudeGravity itself does **not** run any tests and does not check whether they pass. It relies on the Builder and on the approved plan.

## Making tests reliable

* **Write the test command into the project's `CLAUDE.md`**, e.g. `Tests: python -m pytest -q`. The file is passed as context to the Architect, who carries the command over into the plan (see [Sessions & files](sessions-und-dateien.md#project-context-claudemd--knowledge)).
* **Define a completion criterion**, e.g. "Only create `.done` once `pytest` passes without errors."
* **Check in the approval menu** ([4] Show) whether the plan names concrete tests. If not: [2] Changes → [3] Feedback, e.g. "Add unit tests for all edge cases."
* **With `--strategy best-code`** all phases get high effort, which pays off for test-heavy tasks.
* **Verify yourself after the run**: run the test suite locally once before you commit.

### Endpoint Builders and tests

Ollama, LM Studio and custom server Builders **cannot run commands**. They only write files via `filepath:` blocks. In this case tests do not run automatically. For tasks where tests must run inside the loop, choose a CLI as Builder (`claude`, `agy`, `gemini`), or run the tests yourself after the run.

## Testing ClaudeGravity itself

The unit tests only need Python and no AI:

```bash
python3 -m unittest discover -s tests
```

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
