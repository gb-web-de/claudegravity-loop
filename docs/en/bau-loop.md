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
5. With **endpoint Builders** (Ollama server, LM Studio, custom servers, Copilot), ClaudeGravity reads the `filepath:` code blocks from the response and writes the files itself (format: see [Backends](backends.md#how-endpoint-builders-write-files)). Written files are listed.
6. Check for `.done` again. Without `.done`, the proof command still runs; if it is red, its output goes into the next round. Then a pause of `--delay` seconds (default 3) and the next round.

An error in a round (e.g. a CLI crash) doesn't end the loop: it is reported and the next round starts.

## End of the loop

| Trigger | Result |
| :--- | :--- |
| `.done` found, proof command green, acceptance check passed | `phase = completed`, the audit report is written to `.done` and displayed. |
| Acceptance check still rejected after `--max-inspections` rounds | `phase = inspection_open`, findings in `INSPECTION_round*.md`. The worktree is not merged. Continue with `claudegravity -c -m <new maximum>`. |
| `.done` in the project root folder | Moved into the session folder and handled as above. |
| `--max-iterations` reached (default 10) | State saved, audit report in `AUDIT.md` (no `.done`, otherwise the task would count as finished when resuming). Continue with `claudegravity -c -m <new maximum>`. |
| `Ctrl+C` | The current round is ended cleanly, the state is kept. |
| Rate limit | Menu Switch / Wait / Quit, or automatic switch with `--auto-switch` (see [Workflow & roles](ablauf-und-rollen.md#limits--auto-switch)). |

## When is the Builder "done"?

The Builder signals with `.done` that it is finished. The task **is** only finished when

1. the proof command (`--proof`) is green – ClaudeGravity runs it itself and doesn't trust the Builder's success message, and
2. the **acceptance check** (`--abnahme`) agrees: a different provider gets, in a fresh read-only session, the plan, the proof command result and the diff since build start (`git diff` against the base commit plus new files, truncated to 60,000 characters). It also checks whether the tests verify the requirement rather than just what the implementation currently does.

If either of them rejects the signal, ClaudeGravity deletes `.done` and passes the findings to the Builder in the next round. Every acceptance check is stored as `INSPECTION_roundN.md` in the session folder and in `LOG.md`. Without Git, the acceptance check gets no diff and reads the files named in the plan itself. How to safeguard the tests is described in [Tests](tests.md).

## Useful flags for phase 3

| Flag | Effect |
| :--- | :--- |
| `-m`, `--max-iterations <n>` | Maximum rounds |
| `-d`, `--delay <s>` | Pause between rounds, `0` for no pause |
| `--yolo` | Skip the permission prompt (Builder only) |
| `--proof "<command>"` | Proof command that ClaudeGravity runs itself |
| `--abnahme`, `--abnahme-model`, `--max-inspections`, `--no-inspect` | Control the acceptance check |
| `--auto-switch` | Automatically switch backend on limit |
| `--bauer`, `--bauer-model`, `--bauer-effort`, `--bauer-endpoint` | Set the Builder |

Full list: [CLI reference](cli-referenz.md).
