# Changelog

🇩🇪 [Deutsch](CHANGELOG.md) · Versions follow [Semantic Versioning](https://semver.org/). The version lives in `claudegravity/__init__.py`, the MCP server and all plugin manifests (raise them together, `tests/test_plugins.py` checks this). `claudegravity --version` shows it.

## [Unreleased]

## [1.6.0] – 2026-10-26

### Added
- Ready-made programs on the GitHub release for macOS (Apple Silicon, Intel), Linux (x64, arm64) and Windows, with their own Python: `curl -fsSL …/claudegravity-install.sh | sh` or `irm …/claudegravity-install.ps1 | iex` downloads the matching archive, checks the SHA-256 sum and installs. One program is the loop, the MCP server (`claudegravity mcp`) and the installer (`claudegravity install` copies itself to `~/.local/bin` or `%LOCALAPPDATA%\ClaudeGravity\bin` and registers itself as the server). The release also carries `claudegravity.mcpb`, wheel, sdist and `SHA256SUMS`; `release.yml` builds everything on a `v*` tag and tests the install on every system.
- `tools/realrun.py`: checks every installed backend with real models (answer, read-only mode holds, `--resume` continues the session, with `--full` a complete run as Builder).
- Benchmark with ten tasks; a run only counts if the unchanged original tests are green. `--baseline <cli>` compares with a single CLI without the loop, plus `--repeat` and `--tasks-dir`.
- `claudegravity --version`.
- Candidate mode `--candidates claude,codex` (Best-of-N): several Builders implement the plan in parallel in their own worktrees, the loop checks each itself, the acceptance check picks the best and accepts it.
- Test guard (`--test-guard warn|strict|off`): after a green proof command it detects deleted test files, new skip/only markers and fewer test cases or assertions; audit CG-1504.
- English output with `--lang en` (also `auto` by locale, `CLAUDEGRAVITY_LANG`, `"lang"` in a profile): status lines, menus, help, error codes linking to the English docs, reports in `.done`/`AUDIT.md`; the models then answer in English as well. German stays the default.
- Install as a package without cloning: `pipx install git+https://github.com/gb-web-de/claudegravity-loop`, `uv tool install …` or once via `uvx --from … claudegravity`; plus `python -m claudegravity`. No runtime dependencies, `pyproject.toml` is only for installing.
- Repo map for roles without their own file access (`--repo-map auto|an|aus`): paths with classes and functions, sorted by relevance to the task and limited to 6,000 characters, so Ollama and other endpoints know the project.
- From issue to pull request: `--from-issue 12` (also `owner/repo#12` or a URL) takes title, body and comments as the task, `--open-pr`/`--pr-draft` pushes the session branch after a successful acceptance check and opens a pull request with `Closes #12`, roles, metrics and plan. Via `gh` or the REST API (`GH_TOKEN`), error codes CG-1601/CG-1602. The repository is also a GitHub Action (`uses: gb-web-de/claudegravity-loop@main`) started by a label or `/claudegravity`; the MCP server knows `issue` and `open_pr`.
- Sandbox (`--sandbox on|docker|podman`, `--sandbox-image`, `--sandbox-net`): the proof command and CLI Builder run in a fresh container with your user ID, without capabilities and with limits; the proof command without network, the Builder sees only the work and session folders and the credentials of its own CLI. `sandbox/Dockerfile` brings the AI CLIs. Error codes CG-1701/CG-1702; not from the project profile.
- Live view and notifications: `--watch` (or `claudegravity watch` without a run) shows phase, current role, round, tokens, cost, changed files, diff and log in the browser, only on `127.0.0.1` with a token. `--notify desktop,bell,ntfy:<topic>,webhook:<url>` reports when a question has been open for 20 s and when the run is done or stops. New file `live.json` in the session folder, events `call_start`/`proof_start`; the MCP server knows `notify` and `watch`.
- Claude Desktop extension `claudegravity.mcpb` (MCP Bundle): a double-click installs the MCP server with settings for project, endpoint, API key, notification, language and Python. `tools/build_mcpb.py` builds it reproducibly, CI checks the manifest with `mcpb validate`, a version tag attaches it to the release. On macOS/Linux `launch.sh` looks for Python 3.10+.
- The benchmark builds directly in the throwaway folder (`--no-worktree`) so the original tests see the result.

### Changed
- The Reviewer judges proportionately: HIGH/MEDIUM only if the plan misses the task, corrupts data or opens a security hole. With `--plan-auto` the plan is also built after the round limit if only MEDIUM/LOW findings are open (findings go to the Builder). In the first real benchmark `csv-report` failed because the Reviewer twice demanded hardening outside the task.
- Reviewer session continued from round 2 now also for Codex and Copilot (plan diff only instead of the full plan).
- Copilot runs via the new Copilot CLI (`copilot -s`, prompt via stdin, own session with `--resume`, read-only mode via `--deny-tool`) and is a full Builder. `gh copilot suggest` is no longer supported.

### Fixed
- Empty `CLAUDEGRAVITY_*` variables count as unset instead of an invalid value.
- Endpoint Builders (Ollama, LM Studio, your own servers) could never report "done" in the Git workspace without stages: the completion marker lives in the session folder outside the workspace and was blocked as a write attempt outside the project. The loop now writes it itself.
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
