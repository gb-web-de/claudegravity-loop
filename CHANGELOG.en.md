# Changelog

🇩🇪 [Deutsch](CHANGELOG.md) · Versions follow [Semantic Versioning](https://semver.org/). The version lives in `claudegravity/__init__.py`, the MCP server and all plugin manifests (raise them together, `tests/test_plugins.py` checks this). `claudegravity --version` shows it.

## [Unreleased]

### Added
- `tools/realrun.py`: checks every installed backend with real models (answer, read-only mode holds, `--resume` continues the session, with `--full` a complete run as Builder).
- Benchmark with ten tasks; a run only counts if the unchanged original tests are green. `--baseline <cli>` compares with a single CLI without the loop, plus `--repeat` and `--tasks-dir`.
- `claudegravity --version`.
- Candidate mode `--candidates claude,codex` (Best-of-N): several Builders implement the plan in parallel in their own worktrees, the loop checks each itself, the acceptance check picks the best and accepts it.
- Test guard (`--test-guard warn|strict|off`): after a green proof command it detects deleted test files, new skip/only markers and fewer test cases or assertions; audit CG-1504.
- English output with `--lang en` (also `auto` by locale, `CLAUDEGRAVITY_LANG`, `"lang"` in a profile): status lines, menus, help, error codes linking to the English docs, reports in `.done`/`AUDIT.md`; the models then answer in English as well. German stays the default.
- Install as a package without cloning: `pipx install git+https://github.com/gb-web-de/claudegravity-loop`, `uv tool install …` or once via `uvx --from … claudegravity`; plus `python -m claudegravity`. No runtime dependencies, `pyproject.toml` is only for installing.
- Repo map for roles without their own file access (`--repo-map auto|an|aus`): paths with classes and functions, sorted by relevance to the task and limited to 6,000 characters, so Ollama and other endpoints know the project.
- The benchmark builds directly in the throwaway folder (`--no-worktree`) so the original tests see the result.

### Changed
- The Reviewer judges proportionately: HIGH/MEDIUM only if the plan misses the task, corrupts data or opens a security hole. With `--plan-auto` the plan is also built after the round limit if only MEDIUM/LOW findings are open (findings go to the Builder). In the first real benchmark `csv-report` failed because the Reviewer twice demanded hardening outside the task.
- Reviewer session continued from round 2 now also for Codex and Copilot (plan diff only instead of the full plan).
- Copilot runs via the new Copilot CLI (`copilot -s`, prompt via stdin, own session with `--resume`, read-only mode via `--deny-tool`) and is a full Builder. `gh copilot suggest` is no longer supported.

### Fixed
- A missing Copilot CLI behind `gh` counted as ready because `gh copilot` exits with 0.
- `gh` without a downloaded Copilot CLI is no longer detected as Copilot; automatic role selection used to pick it as Reviewer.
- Roles with Copilot via `gh` aborted with "Agent-CLI 'gh' ist nicht verfügbar".

## [1.5.0] – 2026-10-25

First recorded state. Package, MCP server (previously 1.4.0) and plugin manifests (previously 1.0.0) share one version from here on.

- Four roles with separate providers: Architect, Reviewer, Builder, Acceptance; verdicts only via the last `VERDICT:` line.
- Backends `claude`, `agy`, `gemini`, `codex`, `copilot`, `ollama` and OpenAI-compatible endpoints; strategies `balanced`, `best-code`, `eco`, `local-free`, `hybrid`.
- Stage mode, Builder session across rounds, search/replace blocks for endpoints, plan excerpt per stage.
- Setup with `claudegravity init`, profiles and templates, `--print-effective-config`, dry run with cost estimate, budget limits, escalation to the cloud.
- Security: read-only roles monitored, write targets only inside the project, redacted logs, threat model.
- MCP server for desktop apps and CLIs, plugins for Claude Code, Codex, Antigravity, Copilot CLI, Cursor and Gemini CLI.
- Worktree per session, resume after abort, error codes CG-xxxx, event log `events.jsonl`, smoke matrix on Linux, macOS and Windows.
