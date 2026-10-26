# GitHub: from issue to pull request

[← Back to overview](../../README.md) · [Documentation index](README.md) · 🇩🇪 [Deutsch](../de/github.md)

`--from-issue` takes a GitHub issue as the task, `--open-pr` opens a pull request with `Closes #12` after a successful acceptance check. As a GitHub Action this runs without your computer: add the label `claudegravity` or comment `/claudegravity`, and the loop plans, reviews, builds and opens the pull request.

## In the terminal

```bash
claudegravity --from-issue 12 --open-pr --proof "python -m pytest -q"
claudegravity --from-issue gb-web-de/claudegravity-loop#12 --pr-draft
claudegravity "Please without new dependencies" --from-issue https://github.com/o/r/issues/12 --open-pr
```

* **Issue reference:** `12`, `#12`, `owner/repo#12` or the URL. Without a repository the loop uses the project's `origin` (in GitHub Actions otherwise `GITHUB_REPOSITORY`).
* **What the loop reads:** title, body, labels and the latest 10 comments (up to 1,500 characters each), at most 12,000 characters in total. A note to the models is added: the text comes from third parties, and instructions in it to read credentials or publish anything are not followed. Your own task text on the command line follows as an "additional instruction" (`Zusätzlicher Auftrag`).
* **Session and branch:** the session is named `<time>_issue-12_<title>`, the build runs on `loop/<session>` as always.
* **Access:** first the GitHub CLI `gh` with its sign-in (`gh auth login`), otherwise the REST API with `GH_TOKEN` or `GITHUB_TOKEN`. For GitHub Enterprise set `GITHUB_API_URL`. `CLAUDEGRAVITY_GH=off` uses only the API, `CLAUDEGRAVITY_GH=/path/to/gh` a specific `gh`. The token is never stored, logged or given to a model.
* `--dry-run` already reads the issue and shows the command with `--from-issue`.

## Pull request

With `--open-pr`, a successful finish (proof command green, acceptance check `APPROVED`) continues like this:

1. The workspace is committed to `loop/<session>` as always. Nothing is merged, not even with `--merge`.
2. `git push -u origin loop/<session>`.
3. Pull request against the original branch (if the project was on a detached HEAD, against the default branch). The title is the issue title; the body contains `Closes #12`, the four roles with their models, the proof command, the metrics and the approved plan as a collapsible section.
4. The URL is then stored in `state.json` (`pull_request`), `LOG.md`, `events.jsonl` (event `pull_request`) and `.done`.

* `--pr-draft` opens the pull request as a draft.
* If the branch already has a pull request (e.g. after `claudegravity -c`), the loop uses its URL.
* There is no pull request without a Git workspace (`--no-worktree` or no Git), without new commits, or if the run did not complete. If the push or the pull request fails, the loop reports [CG-1602](fehlerbehebung.md#cg-1602); the branch stays available locally.
* In [candidate mode](bau-loop.md#candidate-mode-best-of-n) the winner's branch gets the pull request.
* `open_pr` and `pr_draft` only apply from the command line, the environment (`CLAUDEGRAVITY_OPEN_PR=1`) or the global profile, not from the project profile: a foreign repository should not decide on its own that something gets published.
* The MCP server knows the same switches as `issue` and `open_pr` ([MCP server](mcp-server.md)).

## GitHub Action

The repository is an action itself. This workflow starts the loop when someone with write access adds the label `claudegravity` or a member comments `/claudegravity`:

```yaml
# .github/workflows/claudegravity.yml
name: claudegravity
on:
  issues:
    types: [labeled]
  issue_comment:
    types: [created]

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  loop:
    if: >-
      (github.event_name == 'issues' && github.event.label.name == 'claudegravity') ||
      (github.event_name == 'issue_comment' && !github.event.issue.pull_request &&
       startsWith(github.event.comment.body, '/claudegravity') &&
       contains(fromJSON('["OWNER", "MEMBER", "COLLABORATOR"]'), github.event.comment.author_association))
    runs-on: ubuntu-latest
    timeout-minutes: 60
    concurrency:
      group: claudegravity-${{ github.event.issue.number }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      # Project dependencies for the proof command, e.g.:
      # - run: pip install -r requirements.txt
      - uses: gb-web-de/claudegravity-loop@main
        with:
          proof: python -m pytest -q
          args: --architekt claude --pruefstatiker gemini --abnahme gemini --budget-max 2m
          lang: en
        env:
          GH_TOKEN: ${{ github.token }}
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

Setup:

1. **Secrets** under *Settings → Secrets and variables → Actions*: `CLAUDE_CODE_OAUTH_TOKEN` (create it with `claude setup-token` from your Claude subscription) and `GEMINI_API_KEY` for the Gemini CLI as Reviewer and acceptance check. Install other CLIs via the `cli` input and sign them in as their own docs describe. Credentials belong in secrets only, never in the repository.
2. **Allow pull requests from Actions:** *Settings → Actions → General → Workflow permissions* → "Allow GitHub Actions to create and approve pull requests".
3. Create the **label** `claudegravity`.

Action inputs:

| Input | Default | Meaning |
| :--- | :--- | :--- |
| `issue` | issue of the event | Number, `owner/repo#12` or URL |
| `args` | – | More options for `claudegravity` (roles, strategy, budget …), split without a shell |
| `proof` | – | Proof command the loop runs itself |
| `draft` | `false` | Open the pull request as a draft |
| `comment` | `true` | Comment the result on the issue (link to the PR, or the reason and a link to the run) |
| `lang` | `de` | Language of the output, the pull request and the comment (`de`, `en`) |
| `cli` | `@anthropic-ai/claude-code @google/gemini-cli` | npm packages of the AI CLIs; empty installs none |
| `python-version` | `3.12` | Python for the loop |
| `working-directory` | `.` | Project folder in the checkout |

Outputs: `pull-request` (URL), `success` (`true`/`false`) and `session`. The job summary shows the result, the reason, the pull request and the report from `.done` or `AUDIT.md`.

The action runs `claudegravity --from-issue … --open-pr --plan-auto --yolo`: only a plan approved by the Reviewer is built, and the Builder has full rights in the runner.

### What to watch out for

* **Who may start it:** the Builder runs with `--yolo` and sees the runner's environment including secrets. So only let people you trust trigger the workflow: only users with at least triage access can add labels, and the comment start checks `author_association`. Never react to `issues: opened` in public repositories, or any stranger decides the task. More in [Security](sicherheit.md) (T15).
* **CI on the pull request:** pull requests and pushes made with the `GITHUB_TOKEN` do not start further workflows (a GitHub rule). If your CI should run on the pull request, set `GH_TOKEN` to a GitHub App token or a fine-grained PAT with *Contents* and *Pull requests: Read and write*.
* **Costs:** `timeout-minutes` and `--budget-max` in `args` limit the run.
* Try it locally without a run: `CG_ISSUE=12 CG_ARGS="--dry-run" python3 tools/github_action.py`.
