---
name: claudegravity
description: "Plan, review, build and accept a coding task with different AI providers (claude, agy/Gemini, codex, local Ollama or OpenAI-compatible servers) via claudegravity-loop, so no model grades its own plan or code. Use for 'claudegravity', 'mit loop bauen', cross-model plan review or independent code acceptance; not for trivial edits."
---

# ClaudeGravity

`claudegravity` (the `loop.py` runner from this repository) splits a task into four roles and keeps them on different providers:

| Role | Flag | Rule |
|---|---|---|
| 🏗️ Architekt (plan) | `--architekt <cli>` | read-only |
| 🧐 Prüfstatiker (plan review) | `--pruefstatiker <cli>` | never the Architekt's provider; read-only |
| 🔨 Bauleiter (build) | `--bauer <cli>` | the only role with write access (`--yolo` or the prompt before phase 3) |
| 🔎 Abnahme (code acceptance) | `--abnahme <cli>` | never the Bauleiter's provider+model; fresh read-only session |

Backends: `claude`, `agy`, `gemini`, `codex`, `copilot`, `ollama`, `lmstudio`, `endpoint` (`--endpoint <url>`), `architekt_ep`/`pruefstatiker_ep`/`bauer_ep`. Run `claudegravity --info` to see which are installed; listed is not the same as authenticated.

## Choose the roles

1. Find out what the user has: `claudegravity --info`. Prefer the user's explicit choices; do not swap providers or models silently.
2. Put the most capable available model on Architekt and Prüfstatiker (cheap in tokens), the cheapest adequate one on Bauleiter (80–90 % of tokens): `--strategy eco` or `--strategy local-free --bauer ollama|endpoint`. With a cloud CLI plus Ollama, `--strategy hybrid` sets this up by itself: the cloud CLI plans and accepts, Ollama reviews and builds, models are picked from the installed Ollama models.
3. The Abnahme defaults to the Prüfstatiker. With only one provider there is no independent acceptance; say so instead of claiming one.
4. Show the plan with `--dry-run` before a real run when the user has not fixed the roles.
5. Local Builders (Ollama, LM Studio, endpoints) build in stages by default (`--etappen auto`): the plan ends with `## Etappen`, one stage per round, each checked with `--proof`. Use `--etappen an` to force it for CLI Builders and `--etappen aus` to turn it off.

## Run

```bash
claudegravity "<task>" -p <project> \
  --architekt claude --pruefstatiker agy --bauer codex \
  --proof "python -m unittest discover -s tests"
```

- Always pass `--proof` with the repository's own test command. The loop runs it itself after every build round and does not trust the builder's "done".
- Add `--yolo` only when the user asked for unattended builds; it gives write access to the Bauleiter only.
- `--max-rounds` (plan review, default 2) and `--max-inspections` (acceptance, default 2) bound the cost. `-c` resumes.
- From an MCP client use the `claudegravity_optimize` tool to get the command, `claudegravity_run` to start it (`yolo` defaults to false). Both take the roles as parameters (`architekt`, `pruefstatiker`, `bauer`, `abnahme` and their `*_model`), plus `stages`, `approve_plan` and `merge`; `priority: "hybrid"` gives the cloud-plus-Ollama split. A background run always uses `--plan-auto` and only builds a plan the Prüfstatiker approved.

## Read the result

Everything is in `<project>/.dual-loop/sessions/<session>/`:

- `PLAN_vN.md`, `REVIEW_roundN.md`: plan versions and reviews (last line `VERDICT: APPROVED|REVISE|BLOCKED`; only that line counts).
- `INSPECTION_roundN.md`: acceptance of the finished code.
- `LOG.md`: verdicts, provider switches on rate limits, requested vs. reported model.
- `.done` exists only after proof and acceptance passed. `state.json` `phase = inspection_open` means acceptance still refuses; report the open findings instead of calling the task finished.

Report to the user: roles and models actually used, proof result, acceptance verdict and any open findings. Commits and pushes follow the user's own instructions; the loop never pushes.
