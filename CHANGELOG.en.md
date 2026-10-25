# Changelog

🇩🇪 [Deutsch](CHANGELOG.md) · Versions follow [Semantic Versioning](https://semver.org/). The version lives in `claudegravity/__init__.py`, the MCP server and all plugin manifests (raise them together, `tests/test_plugins.py` checks this). `claudegravity --version` shows it.

## [Unreleased]

### Added
- `tools/realrun.py`: checks every installed backend with real models (answer, read-only mode holds, `--resume` continues the session, with `--full` a complete run as Builder).
- Benchmark with ten tasks; a run only counts if the unchanged original tests are green. `--baseline <cli>` compares with a single CLI without the loop, plus `--repeat` and `--tasks-dir`.
- `claudegravity --version`.
- Test guard (`--test-guard warn|strict|off`): after a green proof command it detects deleted test files, new skip/only markers and fewer test cases or assertions; audit CG-1504.
- The benchmark builds directly in the throwaway folder (`--no-worktree`) so the original tests see the result.

### Changed
- Copilot runs via the new Copilot CLI (`copilot -s`, prompt via stdin, own session with `--resume`, read-only mode via `--deny-tool`) and is a full Builder. `gh copilot suggest` is no longer supported.

### Fixed
- A missing Copilot CLI behind `gh` counted as ready because `gh copilot` exits with 0.
- `gh` without a downloaded Copilot CLI is no longer detected as Copilot; automatic role selection used to pick it as Reviewer.
- Roles with Copilot via `gh` aborted with "Agent-CLI 'gh' ist nicht verfügbar".

## [1.0.0] – 2026-10-25

First recorded state.

- Four roles with separate providers: Architect, Reviewer, Builder, Acceptance; verdicts only via the last `VERDICT:` line.
- Backends `claude`, `agy`, `gemini`, `codex`, `copilot`, `ollama` and OpenAI-compatible endpoints; strategies `balanced`, `best-code`, `eco`, `local-free`, `hybrid`.
- Stage mode, Builder session across rounds, search/replace blocks for endpoints, plan excerpt per stage.
- Setup with `claudegravity init`, profiles and templates, `--print-effective-config`, dry run with cost estimate, budget limits, escalation to the cloud.
- Security: read-only roles monitored, write targets only inside the project, redacted logs, threat model.
- MCP server for desktop apps and CLIs, plugins for Claude Code, Codex, Antigravity, Copilot CLI, Cursor and Gemini CLI.
- Worktree per session, resume after abort, error codes CG-xxxx, event log `events.jsonl`, smoke matrix on Linux, macOS and Windows.
