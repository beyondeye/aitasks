---
title: "Updating Model Lists"
linkTitle: "Updating Model Lists"
weight: 65
description: "Refresh the supported AI code-agent model lists used by ait codeagent, the Settings TUI, and verified-score stats"
---

Each project keeps its own copy of the supported AI code-agent model lists in `aitasks/metadata/models_<agent>.json`. Refresh these files when vendors release new coding-capable models, rename existing ones, or deprecate old variants.

## Why refresh

The local `aitasks/metadata/models_<agent>.json` files drive:

- [`ait codeagent`]({{< relref "/docs/commands/codeagent" >}}) — model selection per skill/operation.
- [Settings TUI]({{< relref "/docs/tuis/settings" >}}) — the Agent Defaults and Models tabs.
- [Verified scores]({{< relref "/docs/skills/verified-scores" >}}) — per-skill, per-model satisfaction ratings.

Refreshing periodically keeps these surfaces accurate as vendor offerings change.

## One-shot refresh of all agents

The [`/aitask-refresh-code-models`]({{< relref "/docs/skills/aitask-refresh-code-models" >}}) skill walks through all four agents in a single run:

- **claudecode**, **codex**, **geminicli** — discovered via web research (`WebSearch` + `WebFetch` against vendor documentation URLs).
- **opencode** — discovered via CLI (`bash .aitask-scripts/aitask_opencode_models.sh`), because the available OpenCode models depend on which providers the user has connected locally.

The skill preserves existing `verified` scores and never auto-removes models — deprecated entries are flagged for explicit user approval. Run it from the project root:

```
/aitask-refresh-code-models
```

## OpenCode-only quick path

When you only need to refresh the OpenCode list (e.g., after connecting a new provider locally), call the helper directly:

```bash
bash .aitask-scripts/aitask_opencode_models.sh            # discover and update
bash .aitask-scripts/aitask_opencode_models.sh --dry-run  # show diff only
bash .aitask-scripts/aitask_opencode_models.sh --sync-seed
```

The helper preserves `verified` scores and the `unavailable` status marker on models the local CLI cannot currently see.

## Adding a single known model

When you already know a model's `cli_id` (e.g., a vendor just announced a specific variant), skip web research and use [`/aitask-add-model`]({{< relref "/docs/skills/aitask-add-model" >}}):

```
/aitask-add-model --agent claudecode --name opus4_7_1m --cli-id 'claude-opus-4-7[1m]' --notes "1M context"
```

Add `--promote --promote-ops <ops>` to also set the new model as the default for the specified ops. See the skill page for the full flag list and the manual-review file list emitted after a promote.

## Where the files live

| File | Purpose | Branch |
|------|---------|--------|
| `aitasks/metadata/models_<agent>.json` | Runtime model list — read by `ait codeagent`, Settings TUI, and stats. | Task-data branch (committed via `./ait git`). |
| `seed/models_<agent>.json` | Template for new projects bootstrapped with `ait setup`. | Source-repo branch (committed via plain `git`). Only present in the framework source repo. |

`<agent>` is one of: `claudecode`, `codex`, `geminicli`, `opencode`.

## Commit conventions

The two file locations live on different branches, so they need separate commits:

- **Metadata** (`aitasks/metadata/...`) — `./ait git add` + `./ait git commit`. See the [Git branching model]({{< relref "/docs/concepts/git-branching-model" >}}) for why task data lives on a separate branch.
- **Seed** (`seed/...`) — plain `git add` + `git commit`. Seed files exist only in the framework source repo and never need `./ait git`.

Both `/aitask-refresh-code-models` and `/aitask-add-model` handle this split automatically; the convention matters only if you are editing the JSON files by hand.

## Related

- [`/aitask-refresh-code-models`]({{< relref "/docs/skills/aitask-refresh-code-models" >}}) — full refresh skill reference.
- [`/aitask-add-model`]({{< relref "/docs/skills/aitask-add-model" >}}) — single-model registration.
- [Settings TUI]({{< relref "/docs/tuis/settings" >}}) — Models tab (read-only view of the lists).
- [Verified scores]({{< relref "/docs/skills/verified-scores" >}}) — how ratings accumulate.
- [`ait codeagent`]({{< relref "/docs/commands/codeagent" >}}) — model picker that consumes these files.
