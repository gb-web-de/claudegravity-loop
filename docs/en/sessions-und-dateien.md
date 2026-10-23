# Sessions, files & project context

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/sessions-und-dateien.md)

## What ClaudeGravity creates in the target project

```text
<projekt>/
├── .dual-loop/                      # git-ignored
│   ├── profile.json                 # optional project profile (see CLI reference)
│   └── sessions/
│       └── 20261017_153000_Baue_ein_Kundenportal/
│           ├── state.json           # progress, roles, models, metrics
│           ├── PLAN_v1.md           # the Architect's first draft
│           ├── REVIEW_round1.md     # the Reviewer's verdict
│           ├── PLAN_v2.md           # revised version
│           ├── PLAN_v3_manual.md    # version edited in the editor
│           ├── INSPECTION_round1.md # the acceptance check's verdict on the finished code
│           ├── LOG.md               # history of plan, review, acceptance check, limit switches, retries
│           ├── audit-events.jsonl   # security events (see permission audit)
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

`state.json` is written atomically (first `state.json.tmp`, then renamed); the previous state stays as `state.json.bak`. If `state.json` is damaged after a crash, `-c` resumes from `state.json.bak` and repeats at most the last round. Plan and review are never recreated on resume once the plan was approved; if the completion signal was already there, the loop goes straight to the acceptance check.

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

### Key figures (KPI)

Before the audit report there is a key figures block in a fixed format, so sessions can be compared:

```markdown
### 📈 Kennzahlen (ClaudeGravity KPI v1)
* **Ergebnis:** erfolgreich · Strategie `hybrid` · Dauer 12 min 30 s
* **Kosten je Aufgabe:** 0.1900 USD · **davon Abnahme:** 0.0900 USD (gemeldet von: Claude Code)
* **Runden:** Plan-Review 2 · Bau 3 (bis Erfolg: 3) · Etappen 2 · Abnahme 2
* **Nacharbeit:** 2 von 3 Bau-Runden (Quote 67 %); Prüfbefehl rot 1/2, Abnahme verweigert 1
```

Below it, the same values follow as one JSON line in a ` ```json ` block (`version`, `success`, `duration_s`, `build_rounds`, `rework_rate`, `cost_usd_task`, `cost_usd_by_role`, `tokens_by_role` and so on) that scripts can read.

* **Costs** come only from what providers report (Claude Code, API endpoints with `usage.cost` such as OpenRouter). Subscription CLIs and local models report no costs; there is no price table, and the tokens per role are included so you can do the math yourself. The unit is USD, as reported by the providers.
* **Rework** counts build rounds that followed a red proof command or a rejected acceptance check, at most all build rounds after the first.
* **Build rounds to success** only exist for completed sessions.

## Project context: `CLAUDE.md` & `knowledge/`

When planning, ClaudeGravity reads from the target project:

1. **All** existing rule files from `CLAUDE.md`, `AGENTS.md`, `.claude/rules.md` (in full; identical content only once).
2. From `knowledge/`, the files whose name or beginning contains a word of the task (4 letters or more), with the first 500 characters. The rest only as file names, so the Architect can read them itself if needed. Secret files such as `.env` or `*.key` are skipped.

This context goes only to the Architect. That keeps the prompt small.

## Privacy shield

Before a prompt goes to a cloud model (Claude, Antigravity, Gemini, Codex, Copilot or an endpoint outside the home network), ClaudeGravity replaces any credentials found in it with `[GESCHWÄRZT: …]` and reports this with 🛡️. Detected are private keys, API keys and tokens (Anthropic, OpenAI, GitHub, Google, AWS, Slack, Stripe, JWT), assignments like `PASSWORD=…` or `token: …`, passwords in URLs, valid IBANs and credit card numbers. Prompts to Ollama, LM Studio and servers on the home network stay unchanged.

The shield only protects the prompt that ClaudeGravity sends itself. If a CLI like Claude Code reads files on its own during the build loop, its own rules apply. Turn it off with `--no-shield` or `CLAUDEGRAVITY_SHIELD=off`.

### Logs, warnings and safe environment variables

Independently of the shield, ClaudeGravity masks the same patterns in `LOG.md`, `audit-events.jsonl` and the build logs under `logs/`. Plans, reviews and acceptance checks in the session folder stay unchanged, because the next steps reuse them verbatim; the session folder is git-ignored.

If the task itself contains credentials, the loop says so at start; with the shield off it also names the cloud models that receive them in plain text. If a model answer contains credentials, an audit event is raised (see below).

Credentials do not belong in the task, a profile or the repository, but in environment variables: `CLAUDEGRAVITY_API_KEY` for your own endpoints, and your project's own variables for the project (e.g. `.env`, which endpoint builders may not write). In the task, the variable name is enough, for example "read the key from `STRIPE_KEY`".

## Permission audit

Architect, reviewer and acceptance check run with read-only flags (Claude: only the Read, Glob and Grep tools, Codex: `-s read-only`). Since not every CLI has such a flag (Antigravity, Gemini, Copilot), the loop also checks: it compares the Git state of the working folder before and after every call of a read-only role. If a file changes, it reports this with 🛑 and records it. It does not undo anything, because you might have been working in the project at the same time.

| Event | When |
| :--- | :--- |
| Blocked write attempt | An endpoint builder tries to write outside the project, into `.git/`, into secret files or into `.dual-loop/profile.json`. |
| Change by read-only role | The working folder changed during plan, review or acceptance check (Git projects only). |
| Possible credentials in model answer | An answer contains patterns such as API keys, tokens or passwords. |

Every event is written to `LOG.md` and as a JSON line to `audit-events.jsonl` in the session folder; the count per kind appears in the audit block of `.done`.

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
