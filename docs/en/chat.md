# Chat interface

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/chat.md)

The easiest way to use the loop: a chat in the browser. You write the task, read plan and review, approve with a button or write what should be different, and watch the build. No flags needed.

```bash
claudegravity chat                      # in the project folder
claudegravity chat -p ~/projects/shop   # another project
```

The command starts a small server on your machine, prints the address and opens it in the browser. Ctrl+C in the terminal ends the chat; running tasks are paused and can be resumed later.

## How a conversation goes

1. **Write the task** and send it. The loop fills the roles as in the terminal (profile, strategy, detected AIs).
2. **Read plan and review.** The architect's plan and the reviewer's verdict appear as messages.
3. **Approve or change.** "Approve plan and build" starts the build. If you write a sentence instead, the architect revises the plan accordingly and the reviewer checks the new version before you are asked again.
4. **Watch.** Every build round, every proof command (red with its output) and the inspection appear in the thread. The header shows who is working.
5. **Result.** At the end, "Show changes" lists the changed files and the diff, new files with their content.

When the loop asks a question (write permission, a provider's limit, questions from the AI with "AI may ask questions first"), it appears with buttons above the input field. The browser tab title then gets a dot.

## What else the page does

| Area | Function |
| :--- | :--- |
| Left column | "New task", switch project (folder picker, recently used projects), all sessions of the project, including those from the terminal. |
| **Stop** | Pauses the run; the loop saves its state. A second click after eight seconds ends it hard. On Windows, Stop ends the run hard at once; the state up to the last step is kept. |
| **Resume** | Continues a paused or aborted session at the same point, with the same roles, models and endpoints. |
| **Details** | Phase, round, tokens, cost, changed files, diff, roles, `LOG.md`, the run's console output and the final report. |
| **Options** | Strategy, kind of task (template), proof command, "builder may write" (`--yolo`, preset in the chat), "approve plan without asking" (`--plan-auto`), "AI may ask questions first" (`--ask`), "merge into the base branch" (`--merge`). "More options" takes any flag from the [CLI reference](cli-referenz.md), e.g. `--builder codex --max-iterations 5`. |

Sessions running in a terminal are shown read-only; you answer their questions where the run was started. The page comes in German and English (`--lang en`), light and dark following the system setting, and fits a phone screen.

## Flags

| Flag | Description | Default |
| :--- | :--- | :--- |
| `chat` | Written as the task: start the chat interface. | |
| `--chat-port <port>` | Port of the chat interface; if taken, a free one. | `8766` |
| `-p <folder>` | Project the chat starts with; can be switched in the page. | current folder |

`CLAUDEGRAVITY_NO_BROWSER=1` keeps the browser from opening on its own (e.g. over SSH). To reach it from another device, forward the address over SSH: `ssh -L 8766:127.0.0.1:8766 machine`.

## How it works, and security

* The chat starts the loop as its own process; answers go to its standard input as lines. Everything the terminal does applies unchanged: separation of roles, read-only mode for architect, reviewer and inspection, proof command, test guard, sandbox.
* The conversation is built from `timeline.jsonl` in the session folder (see [Sessions & files](sessions-und-dateien.md)); the console output of a chat run is in `.dual-loop/sessions/<time>_chat.log`.
* The server listens on `127.0.0.1` only. Every request needs the random token from the address, the `Host` header is checked, there is no CORS permission and a strict Content Security Policy. Writing calls additionally require `Content-Type: application/json` and, if the browser sends an origin, its own. A foreign web page can therefore neither read nor start a run.
* Text from models and files is only ever inserted as text, never as HTML; links are opened to `http(s)` addresses only.
* Whoever has the address including the token can start tasks on your machine. Do not share it and do not show it in screen recordings. More in the [threat model](sicherheit.md).
