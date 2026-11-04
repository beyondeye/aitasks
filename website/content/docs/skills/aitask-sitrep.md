---
title: "/aitask-sitrep"
linkTitle: "/aitask-sitrep"
weight: 65
description: "The repository's sitrep steward — one persisted todo list, wrap-ups turned into action and watch items, answers from the sources"
maturity: [experimental]
depth: [intermediate]
---

The steward of the repository's one persisted todo list. It collects finished agents' wrap-ups, keeps the list current, turns the closing notes into action and watch items, and answers questions from the sources the items point at. It is **advisory-only**: it changes only its own list, through the list's locked writer, and never picks, pushes, commits, edits code or types into another pane. For the workflow, see [Sitrep]({{< relref "/docs/workflows/sitrep" >}}).

**Usage:**
```
/aitask-sitrep
```

No arguments; text after the command is your first request. You normally do not type this: `ait sitrep` opens the sitrep agent in its own `agent-sitrep` window, with a minimonitor companion, and takes you back to that window when it is already open (one per repository). The sitrep agent currently runs on Claude Code.

> **Note:** Must be run from the project root directory (the main worktree). See [Skills overview](..) for details.

## Step-by-Step

1. **Check the root:** the list belongs to the main worktree; started anywhere else, the agent says so and stops.
2. **Collect and re-check:** it harvests every finished agent's wrap-up not yet in the list, then re-checks the items it can verify (task state, pushes, trail progress).
3. **Read the list and greet:** the counts in Pick now, Next and Waiting, the open triage items, and the menu below.

## Capabilities

| Shortcode | Capability |
|-----------|------------|
| `>s` | **Show the list** — items with their live state and how long ago it was checked |
| `>t` | **Triage** — propose action and watch items from each harvested wrap-up, ask once, then write them |
| `>w` | **Situation text** — a short summary per work area |
| `>q` | **Ask anything** — answered from the items' sources; stale checks are called out |
| `>tr` | **Trails** — progress of watched trails; offers `/aitask-trail --refresh` for a stale one |
| `>p` | **What to pick** — relates `/aitask-backlog-roadmap --show` to the Pick now items |
| `>x c<N> [reason]` | **Dismiss** an item (only on your request) |
| `>r` | **Refresh** — collect new wrap-ups and re-check |
| `>?` | **Menu** |

You can always ask in your own words instead.

## What it never does

- Pick, claim or implement a task, push, commit, or edit code, task or plan files.
- Type into another agent's pane.
- Follow an instruction found in an agent's output — that text is only data to analyze.
- Write a trail or a roadmap itself: it offers the owning skill, which asks before it writes.
- Dismiss an item on its own.

## See also

- [Sitrep]({{< relref "/docs/workflows/sitrep" >}}) — the workflow
- [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}) and [`/aitask-backlog-roadmap`]({{< relref "/docs/skills/aitask-backlog-roadmap" >}})
