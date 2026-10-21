# Quick start

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/schnellstart.md)

Prerequisite: ClaudeGravity is [installed](installation.md) and at least one AI CLI is signed in.

## 1. Check what is available

```bash
claudegravity --info
```

The output shows the operating system and Python version, all detected CLIs and endpoints (e.g. `[x] Claude Code (claude / claude)`) and the default assignment of the three roles.

## 2. Look first, then start (dry run)

```bash
claudegravity --dry-run "Create a Python script for weather queries with error handling"
```

The dry run shows which CLI and which model each role gets, and prints the ready-made start command. **No file** is created.

## 3. First task

```bash
cd ~/Projekte/mein-projekt
claudegravity "Create a Python script for weather queries with error handling"
```

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
