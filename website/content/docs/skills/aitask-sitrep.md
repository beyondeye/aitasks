---
title: "/aitask-sitrep"
linkTitle: "/aitask-sitrep"
weight: 65
description: "The repository's sitrep steward — one persisted todo list, wrap-ups turned into action and watch items, answers from the sources"
maturity: [experimental]
depth: [intermediate]
---

The steward of the repository's one persisted todo list. It turns finished agents' closing notes into action and watch items, writes the situation text, reports trails, and answers questions from the sources the items point at. Collecting wrap-ups, re-checking the list, dismissing and restoring are done by the [sitrep TUI]({{< relref "/docs/tuis/sitrep" >}}) in the pane below it. It is **advisory-only**: it changes only its own list, through the list's locked writer, and never picks, pushes, commits, edits code or types into another pane. For the workflow, see [Sitrep]({{< relref "/docs/workflows/sitrep" >}}).

**Usage:**
```
/aitask-sitrep
```

No arguments; text after the command is your first request. You normally do not type this: `ait sitrep` opens the sitrep agent in its own `agent-sitrep` window, with the sitrep TUI below it and a minimonitor column beside them, and takes you back to that window when it is already open (one per repository). The sitrep agent currently runs on Claude Code.

> **Note:** Must be run from the project root directory (the main worktree). See [Skills overview](..) for details.

## Step-by-Step

1. **Check the root:** the list belongs to the main worktree; started anywhere else, the agent says so and stops.
2. **Read the list:** it does not collect or re-check. The sitrep TUI does both when it starts and on its **`r`** key.
3. **Greet:** the counts in Pick now, Next and Waiting, the open triage items, and the menu below. When the list cannot be read, it says so and points at the TUI's **`R`** (restore) instead.

## Capabilities

| Shortcode | Capability |
|-----------|------------|
| `>t [c<N>]` | **Triage** — propose action and watch items from each harvested wrap-up, and the missed items of each unparsed-output review; ask once, then write them. A bare `>t` takes every open triage item as one batch; `>t c<N>` only that item |
| `>w [<theme>]` | **Situation text** — a short summary per work area: every one that needs it, or only `<theme>` |
| `>q [c<N>]` | **Ask anything** — answered from the items' sources; stale checks are called out. With `c<N>` the question is about that item |
| `>tr [c<N>]` | **Trails** — progress of watched trails, or of one watch; offers `/aitask-trail --refresh` for a stale one |
| `>p` | **What to pick** — relates `/aitask-backlog-roadmap --show` to the Pick now items |
| `>c` | **Unparsed-output cases** — lists the kept cases and their review state; replays one against the current parser (writes items only on your yes) |
| `>?` | **Menu** |

You can always ask in your own words instead.

## Requests from the sitrep TUI

The sitrep TUI types one of these lines into the agent when you press a request key: `t`, `a`, `w` or `T` on an item, or `n` for the whole list:

- `>t c<N>` — triage that item;
- `>q c<N> <question>` — answer a question about that item;
- `>w <theme>` — rewrite that work area's situation text;
- `>tr c<N>` — report that trail watch;
- `>p` — what to pick next.

A request carries no more authority than the same line typed by you. Before handling one, the agent re-reads the list, because the TUI may have changed it since. It answers a request about an item that no longer fits (gone, already triaged, not a trail watch) by saying what it found, and writing nothing. Every write still waits for your confirmation.

## Done in the sitrep TUI, not here

The list itself is shown in the sitrep TUI. Collecting and re-checking, dismissing an item and restoring a damaged list are its keys: **`r`**, **`x`** and **`R`** by default. When you ask the agent for one of them, it names the key instead of doing it.

## What it never does

- Pick, claim or implement a task, push, commit, or edit code, task or plan files.
- Type into another agent's pane. The sitrep TUI types requests into the sitrep agent when you press one of its keys, and refuses when the agent is waiting at a dialog, holds a draft, is working, or its pane is scrolled back (copy mode).
- Follow an instruction found in an agent's output — that text is only data to analyze.
- Write a trail or a roadmap itself: it offers the owning skill, which asks before it writes.
- Dismiss an item or restore the list: those are the sitrep TUI's keys, pressed by you.

## See also

- [Sitrep]({{< relref "/docs/workflows/sitrep" >}}) — the workflow
- [Sitrep TUI]({{< relref "/docs/tuis/sitrep" >}}) — the list view and its request keys
- [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}) and [`/aitask-backlog-roadmap`]({{< relref "/docs/skills/aitask-backlog-roadmap" >}})
