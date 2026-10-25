# Build loop (phase 3)

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/bau-loop.md)

The build loop only starts once you have confirmed the plan in the approval menu (see [Workflow & roles](ablauf-und-rollen.md)). This is where ClaudeGravity uses roughly 80–90 % of all tokens, so a cheaper or local model pays off here (see [Strategies](strategien.md)).

## Who builds?

* Default: the same CLI as the Architect who wrote the approved plan (after a swap, that is the new Architect).
* With `--bauer <key>` (alias `--builder`), any other backend, e.g. `--bauer ollama` or `--bauer bauer_ep`.
* Model and effort: `--bauer-model`, `--bauer-effort` or the preset's defaults.

## Permission prompt before the start

Without `--yolo`, ClaudeGravity asks:

```
Soll 🔨 Bauleiter (Claude Code) volle Schreib-/Tool-Rechte erhalten (--dangerously-skip-permissions)? [J/n]:
```

* **[Enter] / J:** The permission flags are set and remembered in `state.json` (see [Backends](backends.md#permissions--yolo)).
* **n:** Restricted mode. The CLI then asks for confirmation on every tool call itself. Since ClaudeGravity doesn't start the CLIs interactively, the Builder often gets stuck in this mode.

## What happens in a round

1. ClaudeGravity checks whether `.dual-loop/sessions/<session>/.done` already exists. If so, the acceptance check follows (see below).
2. `last_iteration` and metrics are saved to `state.json`. This allows resuming exactly here after an interruption.
3. The Builder gets a short prompt: path to the approved plan version, the task, the instruction "create/modify files, run tests", the proof command and the exact path for the completion signal. **No chat history** is sent, only the plan and, if applicable, the feedback from the last round (red proof command or acceptance check findings).
4. The response is printed in the terminal and appended to `logs/loop_<session>.log`.
5. With **endpoint Builders** (Ollama server, LM Studio, custom servers), ClaudeGravity reads the `filepath:` code blocks from the response and writes the files itself (format: see [Backends](backends.md#how-endpoint-builders-write-files)). Written files are listed.
6. Check for `.done` again. Without `.done`, the proof command still runs; if it is red, its output goes into the next round. Then a pause of `--delay` seconds (default 3) and the next round.

An error in a round (e.g. a CLI crash) doesn't end the loop: it is reported and the next round starts.

### Continuing the Builder session

If the Builder is `claude` or `codex`, ClaudeGravity continues the same session from the second round on (`claude --resume <id>` or `codex exec resume <id>`). The Builder still has the task, the plan and the files it already read in its context and only receives the feedback from the last round (end of the proof output or the acceptance findings) and the next step. Over several rounds this saves most of the input tokens and the time to read the project again.

* If the session can't be continued (e.g. deleted or expired), the same round starts in a fresh session with the full instructions.
* After a switch because of a limit or an escalation, the new Builder always starts fresh.
* The session ID is stored in `state.json` (`builder_session`), so `claudegravity -c` continues it too. Continued rounds are counted as `builder_resumed` in the metrics.
* `--builder-fresh` (alias `--bauer-neu`) turns this off: a new session every round, as before.
* Endpoint Builders have no session; they still get the plan and the file contents every round.

## Stage mode

Small local models work faster and more reliably with small pieces. In stage mode (`--etappen an`, or `auto` for Builders without their own file access such as Ollama, LM Studio and endpoints), phase 3 runs like this:

1. The Architect is told to end the plan with a `## Etappen` section: 2 to 8 numbered stages, each changing at most two files and testable afterwards. The Reviewer checks the stages along with the plan.
2. After approval, ClaudeGravity reads the stages from the plan and lists them.
3. In each round the Builder gets **only the current stage**, the list of completed stages, the plan and the **current content** of the files the stage names or that it wrote earlier (up to 40,000 characters). This way an Ollama model also sees what was created in the earlier rounds. If the plan is longer than 6,000 characters, only an excerpt goes along: the head, the sections on goals, acceptance criteria, tests, risks and interfaces, and the sections that name a file of the stage; the `## Etappen` section is left out because the stage is included anyway. Parts that stay the same (task, plan, format) come first and changing parts (stage, file contents, feedback) last, so prompt caching at the provider and in Ollama can work.
4. Then ClaudeGravity runs `--proof`. Green: the stage is done and noted in `LOG.md`. Red: the output goes into the next round of the same stage. After 3 red attempts the loop stops (`phase = stage_open`); `claudegravity -c` continues from there.
5. After the last stage, the proof command and the acceptance check follow as described below. If the acceptance check refuses, ClaudeGravity appends a rework stage with the findings. A `.done` from the Builder does not count in this mode; the task is closed after the last stage.

If the `## Etappen` section is missing or has fewer than two stages, the Builder builds the whole plan as before. Without `--proof` every stage counts as done after one round, so always pass a proof command in stage mode. A proof command that is red without tests (e.g. `unittest` in a project without tests) already blocks the first stage: add a test first, or let the first stage write one.

Even outside stage mode, endpoint Builders get the current content of the files they already wrote from the second round on.

## End of the loop

| Trigger | Result |
| :--- | :--- |
| `.done` found, proof command green, acceptance check passed | `phase = completed`, the audit report is written to `.done` and displayed. |
| Acceptance check still rejected after `--max-inspections` rounds | `phase = inspection_open`, findings in `INSPECTION_round*.md`. The worktree is not merged. Continue with `claudegravity -c -m <new maximum>`. |
| `.done` in the project root folder | Moved into the session folder and handled as above. |
| Stage not green after 3 attempts | `phase = stage_open`, state and completed stages stay in `state.json`. Continue with `claudegravity -c`. |
| `--max-iterations` reached (default 10, in stage mode 2 per stage + 2) | State saved, audit report in `AUDIT.md` (no `.done`, otherwise the task would count as finished when resuming). Continue with `claudegravity -c -m <new maximum>`. |
| `Ctrl+C` | The current round is ended cleanly, the state is kept. |
| Rate limit | Menu Switch / Wait / Quit, or automatic switch with `--auto-switch` (see [Workflow & roles](ablauf-und-rollen.md#limits--auto-switch)). |

## When is the Builder "done"?

The Builder signals with `.done` that it is finished. The task **is** only finished when

1. the proof command (`--proof`) is green – ClaudeGravity runs it itself and doesn't trust the Builder's success message, and
2. the **acceptance check** (`--abnahme`) agrees: a different provider gets, in a fresh read-only session, the plan, the proof command result and the diff since build start (`git diff` against the base commit plus new files, truncated to 60,000 characters). It also checks whether the tests verify the requirement rather than just what the implementation currently does.

If either of them rejects the signal, ClaudeGravity deletes `.done` and passes the findings to the Builder in the next round. Every acceptance check is stored as `INSPECTION_roundN.md` in the session folder and in `LOG.md`. Without Git, the acceptance check gets no diff and reads the files named in the plan itself. How to safeguard the tests is described in [Tests](tests.md).

### Test guard

A green proof command proves little if the Builder weakened the tests beforehand. After every green `--proof`, ClaudeGravity compares the test files with the base commit and looks for deleted test files, new skip or only markers (`@unittest.skip`, `pytest.mark.skip/xfail`, `it.skip`, `describe.only`, `xit`, `markTestSkipped`, `@Disabled`, `t.Skip` …) and for fewer test cases or assertions than before. Findings appear in the terminal, as audit event CG-1504 in `LOG.md` and `audit-events.jsonl`, and in the key figure counter `tests_weakened`.

| `--test-guard` | Behaviour |
| :--- | :--- |
| `warn` (default) | The findings go into the acceptance prompt; the acceptance check decides whether the change is justified. |
| `strict` | The completion report is rejected right away, the Builder gets the findings as feedback. |
| `off` | No check. |

Without a Git base commit (no repository) the guard checks nothing.

## Useful flags for phase 3

| Flag | Effect |
| :--- | :--- |
| `-m`, `--max-iterations <n>` | Maximum rounds |
| `--etappen auto\|an\|aus` | Stage mode (see above) |
| `-d`, `--delay <s>` | Pause between rounds, `0` for no pause |
| `--yolo` | Skip the permission prompt (Builder only) |
| `--proof "<command>"` | Proof command that ClaudeGravity runs itself |
| `--abnahme`, `--abnahme-model`, `--max-inspections`, `--no-inspect` | Control the acceptance check |
| `--auto-switch` | Automatically switch backend on limit |
| `--bauer`, `--bauer-model`, `--bauer-effort`, `--bauer-endpoint` | Set the Builder |

Full list: [CLI reference](cli-referenz.md).
