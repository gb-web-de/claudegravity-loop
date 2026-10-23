# Quick start

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/schnellstart.md)

Prerequisite: ClaudeGravity is [installed](installation.md) and at least one AI CLI is signed in.

## 1. Set up

```bash
cd ~/Projekte/mein-projekt
claudegravity init
```

Setup detects the operating system, AI CLIs and local models and asks three things, each with a suggestion (Enter accepts it):

1. **Goal:** fast (`balanced`), cheap (`hybrid` when a cloud CLI and a local model are available, otherwise `local-free` or `eco`) or maximum quality (`best-code`).
2. **Proof command:** guessed from the project (`vendor/bin/phpunit` for `composer.json`, `npm test` for `package.json`, `python3 -m unittest …` for `tests/` and so on).
3. **Location:** project profile `.dual-loop/profile.json` or global profile `~/.config/claudegravity/profile.json`.

At the end you get the profile and the two commands to start. Everything can be changed in the profile later, see [Settings precedence](cli-referenz.md#settings-precedence).

To only see what is detected, without saving anything:

```bash
claudegravity --info
```

The output shows the operating system and Python version, all detected CLIs and endpoints (e.g. `[x] Claude Code (claude / claude)`) and the default assignment of the three roles.

## 2. Look first, then start (dry run)

```bash
claudegravity --dry-run "Create a Python script for weather queries with error handling"
```

The dry run shows which CLI and which model each role gets, estimates the usage and prints the ready-made start command. **No file** is created.

The **cost estimate** gives a best, expected and worst case. It is based on the key figures of the project's last 20 sessions (from `.done` and `AUDIT.md`), preferring the same strategy once there are at least two such sessions. Without history it only shows a rule of thumb for build rounds. USD only appear if providers reported costs; there is no price table. It also adds tips, such as a matching `--budget-max`, a local build strategy or `--proof` when there was a lot of rework.

## 3. First task

```bash
cd ~/Projekte/mein-projekt
claudegravity "Create a Python script for weather queries with error handling"
```

If there is no profile yet, the first run asks in the terminal: show a dry run (default, followed by "So starten? [j/N]"), start setup, start right away, or start right away and stop asking (writes `"guide": false` to the global profile; once only: `--no-guide`). At start the loop also warns about risky settings, such as `--yolo` without Git, a missing `--proof`, `--no-inspect` or an API key sent over unencrypted `http://`.

Or with a target folder, without changing into it first:

```bash
claudegravity "Create a Python script for weather queries" -p ~/Projekte/mein-projekt
```

## What happens next

1. **🏗️ Architect** writes `PLAN_v1.md` into a new session folder under `.dual-loop/sessions/`.
2. **🧐 Reviewer** checks the plan and answers with `VERDICT: APPROVED` or `VERDICT: REVISE`. On `REVISE`, the Architect revises the plan (up to 2 review rounds).
3. **You decide** in the menu:
   ```
   [1] Approve  -> Plan genehmigen & weiter zur Implementierung
   [2] Changes  -> Änderungen/Feedback anbringen
   [3] Swap     -> Rollen tauschen (Architekt <-> Prüfstatiker)
   [4] Anzeigen -> Plan direkt hier im Terminal lesen
   [5] Beenden  -> Abbrechen (Fortsetzen später mit --resume möglich)
   ```
   (Meaning: [1] approve the plan and continue to implementation; [2] add changes/feedback; [3] swap roles (Architect <-> Reviewer); [4] show – read the plan right here in the terminal; [5] quit – abort (can be resumed later with `--resume`).)

   **[Enter]** is enough to approve.
4. **Permission prompt:** Without `--yolo`, ClaudeGravity asks whether the Builder gets full write and tool permissions.
5. **🔨 Builder** implements the plan in up to 10 rounds (`-m` changes this) and finally creates `.dual-loop/sessions/<session>/.done`. ClaudeGravity additionally writes the token and cost report into this file.

Details on each step: [Workflow & roles](ablauf-und-rollen.md).

## Typical combinations

```bash
# Allow follow-up questions, then build without prompts
claudegravity "Build a customer portal" -i --yolo

# Economical: strong plan, a cheap model builds
claudegravity "Add logging" --strategy eco

# €0 in the build loop with local Ollama
claudegravity "Build a REST interface" --strategy local-free

# Resume an interrupted session
claudegravity -c
```

## Next

* [Strategies](strategien.md) – which preset for what
* [Backends](backends.md) – Ollama, LM Studio, intranet servers
* [CLI reference](cli-referenz.md) – all flags
