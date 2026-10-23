# Troubleshooting & known limitations

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/fehlerbehebung.md)

## Common problems

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| `claudegravity: command not found` | Symlink missing or `~/.local/bin` not in `PATH` | Check [Installation](installation.md) steps 2–3; open a new shell. |
| `Python 3.10+ wurde nicht im System-PATH gefunden` (Windows) | Python missing or not in `PATH` | Install Python from python.org and enable "Add Python to PATH". |
| Broken umlauts/emojis (Windows) | Console not set to UTF-8 | Use `claudegravity.bat` or `.ps1` instead of `python loop.py`. |
| `Agent-CLI '…' ist nicht verfügbar` | Role assigned to an undetected backend | Check `claudegravity --info`, install/sign in to the CLI. |
| Architect and Reviewer are the same model | Only one backend installed | Install a second CLI or set an endpoint as Reviewer. |
| Ollama / LM Studio not detected | Server was not running at startup, or a different port | Start the server first; for a different port use `--bauer-endpoint http://localhost:<port>/v1 --bauer bauer_ep`. |
| `Verbindungsfehler zu …` | Endpoint unreachable | Check the URL in a browser/with `curl`, check VPN/proxy. |
| `API-Fehler … HTTP 401` | Key missing or wrong | Set `CLAUDEGRAVITY_API_KEY` or pass `--api-key`. |
| "Model tried to create a file" | Architect tried to write despite the planning phase | Automatically retried once; avoid `--yolo` if needed. |
| Build loop ends after 10 rounds without `.done` | Round limit reached | `claudegravity -c -m 20`. |
| Endpoint Builder doesn't change any files | Response contains no `filepath:` blocks | Choose a bigger/better model; for the format see [Backends](backends.md#how-endpoint-builders-write-files). |
| Hanging prompt in the background (MCP `background: true`) | Interactive menu without a terminal | Start the run in a terminal or use `--yolo` and review the plan beforehand. |

## Cancelling

`Ctrl+C` cleanly ends the current round; the state is preserved. Resume with `claudegravity -c`.

## Known limitations

These points reflect the current state of the code:

* **Effort only for Antigravity and Codex:** `--effort` and the role-specific effort flags are passed to `agy` and `codex`. For other CLIs they only appear in the audit report.
* **Resuming the reviewer session only with Claude:** From review round 2 on, only a Claude reviewer receives the plan diff instead of the whole plan. Other reviewers receive the full plan.
* **Copilot:** Is called via `copilot suggest -t shell` and is therefore better suited to shell suggestions than to planning or building.
* **Cost detection for endpoints:** `localhost`, private IPs and hostnames on the home network (without a dot or ending in `.local`, `.lan`, `.fritz.box`, `.home.arpa`, `.internal`) count as free. An intranet server with a public domain name appears in the audit as "API".
