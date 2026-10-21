# Sessions, files & project context

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/sessions-und-dateien.md)

## What ClaudeGravity creates in the target project

```text
<projekt>/
├── .dual-loop/                      # git-ignored, contains only sessions/
│   └── sessions/
│       └── 20261017_153000_Baue_ein_Kundenportal/
│           ├── state.json           # progress, roles, models, metrics
│           ├── PLAN_v1.md           # the Architect's first draft
│           ├── REVIEW_round1.md     # the Reviewer's verdict
│           ├── PLAN_v2.md           # revised version
│           ├── PLAN_v3_manual.md    # version edited in the editor
│           ├── INSPECTION_round1.md # the acceptance check's verdict on the finished code
│           ├── LOG.md               # history of plan, review, acceptance check, limit switches
│           ├── workspace/           # the session's Git worktree (branch loop/<session>)
│           ├── AUDIT.md             # audit report if the run ends without a completion signal
│           └── .done                # completion signal + audit report
└── logs/
    └── loop_<session>.log           # Builder output per round
```

* The folder name is `<timestamp>_<first 30 characters of the task>`.
* Every task gets its own folder. Plans, reviews and logs of different tasks don't mix.
* The newest plan version (`PLAN_v*.md`) is the plan the Builder works with.
* Older files `PLAN.md`, `REVIEW.md` and `PLAN-REVIEW-LOG.md` directly in `.dual-loop/` come from earlier versions and are deleted on startup.

Add `.dual-loop/`, `logs/` and `.done` to your project's `.gitignore` if they shouldn't go into the repository.

## Git workspace per session

If the project is a Git repository, the Builder doesn't build directly in the project folder but in its own worktree under `<session>/workspace` on the branch `loop/<session-id>`. The branch is created from the current `HEAD`. This leaves your working directory untouched.

* After successful completion, ClaudeGravity commits pending changes to the session branch and removes the worktree. The branch is kept, so you can review it and merge it yourself.
* With `--merge`, the branch is automatically merged into the original branch after `.done` and a passed acceptance check, provided the project is still on that branch.
* If the acceptance check rejects the completion signal, the worktree is kept and `claudegravity -c` continues there.
* With `--no-worktree`, the Builder works directly in the project folder. Without Git there is no worktree.

## `state.json`

Holds everything needed to resume, including:

| Field | Content |
| :--- | :--- |
| `task` | Original task |
| `phase` | `plan`, `review`, `build`, `inspection_open` or `completed` |
| `user_approved`, `plan_approved` | Approval by you or by the Reviewer |
| `approved_plan_sha256`, `approved_plan_file` | Content the approval applies to |
| `build_base`, `build_plan_sha256` | Base commit and plan at build start (for the acceptance check diff) |
| `proof`, `inspector_binary`, `inspector_model`, `inspection_rounds`, `pending_feedback` | Proof command, acceptance check and pending feedback for the Builder |
| `last_iteration`, `max_iterations` | Progress in the build loop |
| `planner_model`, `reviewer_model`, `builder_model`, `*_effort` | Selected models and effort |
| `swap_roles`, `yolo_enabled`, `auto_switch`, `ask_mode`, `strategy` | Active modes |
| `metrics` | Collected token and cost figures |

## Resuming (`-c` / `--resume`)

```bash
cd ~/Projekte/mein-projekt
claudegravity -c
```

ClaudeGravity takes the newest session, loads the task, plan and settings, and continues from there:

* If the plan wasn't approved yet, it goes back to review and the approval menu.
* If it was approved, the build loop starts at `last_iteration + 1`.
* If `--max-iterations` was reached, `claudegravity -c -m 20` adds more rounds (the count continues up to the new maximum).

If you run `claudegravity` **without a task** and the last session isn't finished, ClaudeGravity asks whether to resume it.

## Completion signal & audit report (`.done`)

The Builder creates `.dual-loop/sessions/<session>/.done` once everything is implemented and tested. ClaudeGravity adds a report to it:

```markdown
### 📊 Ressourcen-Verbrauch & Kosten (ClaudeGravity Audit)
* **Gesamt-Tokens:** 182,340 Tokens
  * **Input-Tokens:** 150,120
  * **Output-Tokens:** 32,220
* **Entstandene Kosten (geschätzt):** ~$0.8421 USD
* **Aufschlüsselung nach Rolle, Agent, Modell & Effort:**
  * **🏗️ Architekt (Planung & Entwurf) (Claude Code)**
    * **Modell:** `claude-sonnet-…`
    ...
```

If the run ends without a completion signal (round limit), the report goes into `AUDIT.md` instead of `.done`, so the task isn't treated as finished when resuming. Roles without API costs (subscription, local) appear as „Abo-Inklusivkontingent“ (included in subscription). For CLIs that don't report usage, token counts are rough estimates (characters / 4).

## Project context: `CLAUDE.md` & `knowledge/`

When planning, ClaudeGravity reads from the target project:

1. **All** existing rule files from `CLAUDE.md`, `AGENTS.md`, `.claude/rules.md` (in full; identical content only once).
2. From `knowledge/`, the files whose name or beginning contains a word of the task (4 letters or more), with the first 500 characters. The rest only as file names, so the Architect can read them itself if needed. Secret files such as `.env` or `*.key` are skipped.

This context goes only to the Architect. That keeps the prompt small.

## Privacy shield

Before a prompt goes to a cloud model (Claude, Antigravity, Gemini, Codex, Copilot or an endpoint outside the home network), ClaudeGravity replaces any credentials found in it with `[GESCHWÄRZT: …]` and reports this with 🛡️. Detected are private keys, API keys and tokens (Anthropic, OpenAI, GitHub, Google, AWS, Slack, Stripe, JWT), assignments like `PASSWORD=…` or `token: …`, passwords in URLs, valid IBANs and credit card numbers. Prompts to Ollama, LM Studio and servers on the home network stay unchanged.

The shield only protects the prompt that ClaudeGravity sends itself. If a CLI like Claude Code reads files on its own during the build loop, its own rules apply. Turn it off with `--no-shield` or `CLAUDEGRAVITY_SHIELD=off`.

## Mirrored projects (`projects/`)

The ClaudeGravity repository contains the `projects/` folder for projects organized like in the Claude UI: each subproject with its own `CLAUDE.md` and an optional `knowledge/` folder. Example:

```text
projects/demo/
├── CLAUDE.md
└── knowledge/
    └── api_guidelines.md
```

```bash
claudegravity "Add a greeting function" -p projects/demo
```
