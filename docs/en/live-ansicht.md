# Live view and notifications

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/live-ansicht.md)

A run easily takes half an hour. So you do not have to sit at the terminal, the loop shows its state in the browser and tells you when it is waiting for you or done.

```bash
# Live view next to the run and a desktop notification when it waits or is done
claudegravity "Task" --watch --notify desktop

# Live view without a run of its own, e.g. for a background run from the MCP server
claudegravity watch -p ~/projects/shop

# To your phone via ntfy
claudegravity "Task" --notify ntfy:my-secret-topic-4711
```

## Live view

`--watch` starts a small page at `http://127.0.0.1:8765/?t=…` next to the run and opens it in the browser. `claudegravity watch` does the same without a run, until Ctrl+C, and shows all sessions of the project (selection at the top right). The page refreshes every two seconds and shows:

* task, phase and whether the run is still going; which role is working right now and since when, or that the proof command is running;
* a yellow notice when the loop waits for an answer in the terminal (e.g. plan approval or permission prompt);
* build round, stage, tokens, reported cost, strategy, branch and proof command;
* provider, model, calls, tokens and cost per role;
* changed files with added and removed lines, the full diff at the push of a button;
* the end of `LOG.md`, after the run the report from `.done` or `AUDIT.md` and the link to the pull request.

The page uses the language of the run (`--lang`) and follows the light or dark system theme.

| Option | Meaning |
| :--- | :--- |
| `--watch` (`--live`) | Live view next to the run. The address is in the run header and in `live.json`. |
| `--watch-port <port>` | Port (default 8765). If it is taken, the loop picks a free one and shows the address. |
| `claudegravity watch` | Live view without a run for the project in `-p` (default: current folder). |

The loop only opens the browser if there is a graphical desktop (macOS, Windows, Linux with `DISPLAY` or `WAYLAND_DISPLAY`); `CLAUDEGRAVITY_NO_BROWSER=1` prevents it entirely. Over SSH, forward the port: `ssh -L 8765:127.0.0.1:8765 server`.

**Protection:** the server only listens on `127.0.0.1`, every request needs the random token from the address, and the `Host` header must be `127.0.0.1` or `localhost` (against DNS rebinding). The page loads nothing from outside and sets a strict Content Security Policy. Anyone who knows the address including the token sees task, log and diff; do not share it.

## Notifications

`--notify` takes one or more channels, separated by commas:

| Channel | What happens |
| :--- | :--- |
| `desktop` | System notification: macOS via `osascript`, Linux via `notify-send` (package `libnotify-bin` or `libnotify`), Windows as a balloon tip via PowerShell. |
| `bell` | Terminal bell (`\a`); many terminals then show a badge or flash. |
| `ntfy:<topic>` | Push to your phone with the [ntfy](https://ntfy.sh) app: a topic on `ntfy.sh` or the full URL of your own server, e.g. `ntfy:https://ntfy.example.org/loop`. A token for protected topics comes from `CLAUDEGRAVITY_NTFY_TOKEN` (or `NTFY_TOKEN`). |
| `webhook:<url>` | JSON via POST to the URL, with `text` and `content` (for Slack, Mattermost, Discord and similar) plus `title`, `message`, `event` and `url`. |

What is reported:

* **Waiting for you:** if a question in the terminal stays unanswered for 20 seconds, "⏳ Waiting for you: …" goes out. Set the delay with `CLAUDEGRAVITY_NOTIFY_WAIT=<seconds>`.
* **Done:** "✅ Done: <task>", with the pull request if one was opened (tap to open with ntfy).
* **Without completion:** "🛑 Ended without completion: <task> · <reason>" (round limit, budget, Ctrl+C) or "🛑 Error CG-xxxx" when the run stops with an error code.

Turn it on permanently via the environment (`CLAUDEGRAVITY_NOTIFY=desktop`) or the global profile (`"notify": "desktop"`). `notify` has no effect from the project profile, so a foreign repository cannot send notifications to addresses of its choice. In candidate mode only the main run notifies.

**What goes out:** the first characters of the task, the abort reason and the link to the pull request, redacted as in `LOG.md`. Anyone who knows a topic on `ntfy.sh` can read it: pick a hard-to-guess topic or your own server. Webhook URLs and topics are secrets; in the run header, with `--dry-run` and `--print-effective-config` they are shortened. If sending fails, the loop says so once and carries on.

## For scripts: live.json

The running process writes `live.json` to the session folder: process ID, current call (`activity`), open question (`waiting`), pull request, address of the live view and whether the run has ended (`ended`). The events `call_start` and `proof_start` also appear in `events.jsonl` with `--log-format json` ([Sessions & files](sessions-und-dateien.md#structured-event-log)). The MCP server knows `notify` and `watch` and shows the address in `claudegravity_status` ([MCP server](mcp-server.md)).
