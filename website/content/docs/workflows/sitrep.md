---
title: "Sitrep"
linkTitle: "Sitrep"
weight: 84
description: "Keep one persisted todo list per repository, so finished agent windows can be closed without losing what they said was left to do"
depth: [intermediate]
---

A finished agent's last screen often holds the only record of what is left: the follow-up tasks it created, "push main when CI is green", the next wave of a trail. Keeping its window open just to remember that does not scale — after a few agents you no longer know which window said what, and closing one loses the information.

**Sitrep** is a steward agent that keeps **one persisted todo list for the repository**. Finished agents' wrap-ups are collected into it automatically, so their windows can be closed. Sitrep keeps the list current, turns the closing notes into concrete action and watch items, and answers your questions about what is going on — from the sources, not from memory.

Sitrep is **advisory only**. It never picks a task, pushes, commits, edits code, or types into another agent's pane. It changes only its own list, and only through the list's locked writer.

## Opening sitrep

Run, from inside tmux:

```bash
ait sitrep
```

The first time, this opens a new window named `agent-sitrep` in your current tmux session, with the sitrep agent on the left and a [minimonitor]({{< relref "/docs/tuis/minimonitor" >}}) companion beside it. Running it again — from any window, or from a linked task worktree of the same repository — takes you to that same window: there is **one sitrep per repository**.

Outside tmux, `ait sitrep` refuses. `ait codeagent invoke sitrep` starts the agent in the current terminal instead, without its own window or the one-per-repository check.

The sitrep agent currently runs on Claude Code. Its code agent and model are the `sitrep` operation in [`ait codeagent`]({{< relref "/docs/commands/codeagent" >}}) and the Settings TUI.

## What happens when it starts

1. It collects every finished agent's wrap-up that is not in the list yet (the same harvest that runs automatically when an agent is frozen or finishes a task workflow).
2. It re-checks every item it can verify: whether a task is still open, picked, archived or folded; whether a commit has reached the remote; how far a trail has progressed.
3. It greets you with the list's shape — how many items are in **Pick now**, **Next** and **Waiting**, how many wrap-ups are waiting for triage — and its shortcodes.

## The list

Each item is a **task**, an **action**, a **question** or a **watch**, and is **open**, **done**, **dismissed** or **unknown**. *Unknown* means the state could not be verified (for example a task in a linked project that is not registered) — it is never treated as done.

For tasks, pushes and trails, sitrep shows the item's live state as the re-check last found it, with how long ago that was. It never copies a task's content into the list; when you want details, it reads the task, plan or retained output the item points at.

## Triage: turning wrap-ups into items

Every finished agent run arrives as a triage item — "Triage wrap-up of t42 …". Ask sitrep to triage (`>t`) and it reads each run's closing message and proposes the items worth tracking:

- **actions** — push a branch, deploy, tell someone, run something by hand. A push with a known commit is tracked against the remote and closes itself once the commit lands.
- **watches** — CI, an external event, an [implementation trail]({{< relref "/docs/workflows/implementation-trails" >}}) the run pointed at. A trail watch reports the trail's next wave and whether the trail is stale.

It shows all proposals in one list and asks once before writing anything. A trail that several wrap-ups point at gets one watch, linked to all of them. Follow-up tasks a run created are already in the list as task items, so they are not proposed again.

## Asking questions

Ask in your own words — "is main pushed?", "what did the t2175 runs leave open?", "what is this trail waiting for?". Sitrep answers from the sources the items point at: task and plan files, the agents' retained closing output, commits, trails. When an answer relies on an item that was last checked more than an hour ago, it says so and offers to refresh. Every question and answer is kept in a dated log next to the list.

## Trails and what to pick next

- **Trails.** Sitrep reports a trail's progress and, when the trail is stale, offers to refresh it with [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}) — on your yes, and that skill asks again before it writes a new version.
- **What to pick.** Sitrep relates the Pick now items to the backlog ranking of [`/aitask-backlog-roadmap`]({{< relref "/docs/skills/aitask-backlog-roadmap" >}}). It never ranks tasks itself and never picks one: it names the `/aitask-pick` command for you to run in another agent window.

## Dismissing items

Ask sitrep to dismiss an item you do not want to track (`>x c4 not needed`). Only you dismiss: sitrep may suggest it, never do it on its own. A dismissed item stays dismissed — later harvests and re-checks never bring it back.

## Shortcodes

| Code | What it does |
|---|---|
| `>s` | Show the list |
| `>t` | Triage the harvested wrap-ups into action and watch items |
| `>w` | Rewrite the short situation text per work area |
| `>q` | Ask anything (or just ask in your own words) |
| `>tr` | Report trail progress, and offer to refresh a stale trail |
| `>p` | What to pick next |
| `>x c<N> [reason]` | Dismiss an item |
| `>r` | Collect new wrap-ups and re-check the list |
| `>?` | Show the menu again |

## Where the list lives

The list is stored per repository in `.aitask-sitrep/`, which is git-ignored and never committed. It is not rebuildable — your dismissals, the agent's derived items and the Q&A log exist nowhere else — so it is written only by one locked writer with a rolling backup. If a file is ever damaged, sitrep says so and offers to restore it from that backup.

Sitrep's own window is never collected into the list: its screen only shows the list back to you.

## See also

- [`/aitask-sitrep`]({{< relref "/docs/skills/aitask-sitrep" >}}) — the skill reference
- [Freeze and Restore Agents]({{< relref "/docs/workflows/freeze-and-restore-agents" >}}) — freezing finished agents, whose wrap-ups sitrep collects
- [Implementation Trails]({{< relref "/docs/workflows/implementation-trails" >}})
