---
title: "Sitrep"
linkTitle: "Sitrep"
weight: 84
description: "Keep one persisted todo list per repository, so finished agent windows can be closed without losing what they said was left to do"
depth: [intermediate]
---

A finished agent's last screen often holds the only record of what is left: the follow-up tasks it created, "push main when CI is green", the next wave of a trail. Keeping its window open just to remember that does not scale — after a few agents you no longer know which window said what, and closing one loses the information.

**Sitrep** is a steward agent that keeps **one persisted todo list for the repository**. Finished agents' wrap-ups are collected into it automatically, so their windows can be closed. Sitrep keeps the list current, turns the closing notes into concrete action and watch items, and answers your questions about what is going on — from the sources, not from memory.

Sitrep is **advisory only**. It never picks a task, pushes, commits or edits code. It changes only its own list, and only through the list's locked writer. The sitrep agent never types into another pane. The [sitrep TUI]({{< relref "/docs/tuis/sitrep" >}}), the list view beside it, types into the sitrep agent only when you press one of the TUI's request keys.

## Opening sitrep

Run, from inside tmux:

```bash
ait sitrep
```

The first time, this opens a new window named `agent-sitrep` in your current tmux session, with three panes:

- the **sitrep agent** at the top left, which you talk to;
- the **[sitrep TUI]({{< relref "/docs/tuis/sitrep" >}})** below it, which shows the list and does the routine work on it;
- a **[minimonitor]({{< relref "/docs/tuis/minimonitor" >}})** column on the right.

Running it again from any window, or from a linked task worktree of the same repository, takes you to that same window: there is **one sitrep per repository**. When the agent or the TUI is missing from the window, `ait sitrep` adds the missing one back. When the agent exits, the TUI and the minimonitor stay; press **`A`** in the TUI, or run `ait sitrep`, to start a new agent above the TUI.

From the TUIs, press **`S`**: in [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) it opens the sitrep window of the focused agent's repository, in a [minimonitor]({{< relref "/docs/tuis/minimonitor" >}}) that of the agent it follows, and in the TUI switcher (`j`) that of the selected session.

Outside tmux, `ait sitrep` refuses. `ait codeagent invoke sitrep` starts the agent in the current terminal instead, without its own window or the one-per-repository check.

The sitrep agent currently runs on Claude Code. Its code agent and model are the `sitrep` operation in [`ait codeagent`]({{< relref "/docs/commands/codeagent" >}}) and the Settings TUI.

## What happens when it starts

1. The sitrep TUI collects every finished agent's wrap-up that is not in the list yet (the same harvest that runs automatically when an agent is frozen or finishes a task workflow).
2. It then re-checks every item it can verify: whether a task is still open, picked, archived or folded; whether a commit has reached the remote; how far a trail has progressed. Press **`r`** in the TUI to collect and re-check again at any time.
3. The sitrep agent reads the list and greets you with its shape (how many items are in **Pick now**, **Next** and **Waiting**, how many wrap-ups are waiting for triage) and its shortcodes.

## The list

Each item is a **task**, an **action**, a **question** or a **watch**, and is **open**, **done**, **dismissed** or **unknown**. *Unknown* means the state could not be verified (for example a task in a linked project that is not registered) — it is never treated as done.

For tasks, pushes and trails, sitrep shows the item's live state as the re-check last found it, with how long ago that was. It never copies a task's content into the list; when you want details, it reads the task, plan or retained output the item points at.

The sitrep TUI shows the list grouped as **Now** (the agent's *Pick now*), **Next** and **Waiting**, with one "What to do" line per item; **`d`** also shows the done and dismissed items. **Enter** opens an item's details and the sources it points at. See [How to Read the List]({{< relref "/docs/tuis/sitrep/how-to" >}}#how-to-read-the-list).

## Triage: turning wrap-ups into items

Every finished agent run arrives as a triage item — "Triage wrap-up of t42 …". Press **`t`** on it in the sitrep TUI to triage that one run, or type `>t` to the agent to triage every open wrap-up at once. The agent reads each run's closing message and proposes the items worth tracking:

- **actions** — push a branch, deploy, tell someone, run something by hand. A push with a known commit is tracked against the remote and closes itself once the commit lands.
- **watches** — CI, an external event, an [implementation trail]({{< relref "/docs/workflows/implementation-trails" >}}) the run pointed at. A trail watch reports the trail's next wave and whether the trail is stale.

It shows all proposals in one list and asks once before writing anything. A trail that several wrap-ups point at gets one watch, linked to all of them. Follow-up tasks a run created are already in the list as task items, so they are not proposed again.

## Output the harvest could not read

Sometimes an agent's wrap-up cannot be read reliably: the banner is cut off or rendered without its fence, a follow-up id is malformed, the closing message is too long, or a run's workflow ended but no banner followed. Then the harvest still writes every item it did find, and it also **keeps the agent's whole output** in the list's store, together with what went wrong and where. It adds one item, "Analyze unparsed agent output …", for sitrep. An agent that was simply frozen mid-work, with no banner at all, is not such a case.

During triage (`t` on the review item in the TUI, or `>t`), sitrep reads the kept output around each problem, proposes the follow-up tasks and actions the harvest missed, and records what it found. Closing or dismissing that item never deletes the kept output: the cases form a local record that parser fixes can be checked against.

```bash
ait sitrep case list                  # every kept case and its review state
ait sitrep case show <case>           # where it came from, what went wrong, what was found
ait sitrep case read <case> --lines 40-60
ait sitrep case replay <case>         # what the current parser would now find (writes nothing)
ait sitrep case export <case> --out <dir>   # a test fixture, once a parser fix resolves it
```

The kept output stays in the git-ignored store and is never pruned automatically. An exported fixture is a verbatim capture: remove other projects' content and conversation text before committing it.

## Asking questions

Press **`a`** on an item in the sitrep TUI to ask about it, or ask the agent in your own words — "is main pushed?", "what did the t2175 runs leave open?", "what is this trail waiting for?". Sitrep answers from the sources the items point at: task and plan files, the agents' retained closing output, commits, trails. When an answer relies on an item that was last checked more than an hour ago, it says so and suggests the TUI's **`r`** to re-check it. Every question and answer is kept in a dated log next to the list.

## Trails and what to pick next

- **Trails.** Sitrep reports a trail's progress and, when the trail is stale, offers to refresh it with [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}) — on your yes, and that skill asks again before it writes a new version.
- **What to pick.** Sitrep relates the Pick now items to the backlog ranking of [`/aitask-backlog-roadmap`]({{< relref "/docs/skills/aitask-backlog-roadmap" >}}). It never ranks tasks itself and never picks one: it names the `/aitask-pick` command for you to run in another agent window.

## Dismissing items

Press **`x`** on an item in the sitrep TUI to dismiss it, and give a reason. Only you dismiss: the agent may suggest it, and when you ask it to, it names the key. A dismissed item stays dismissed — later harvests and re-checks never bring it back.

## Shortcodes

You type these to the sitrep agent. The request keys of the [sitrep TUI]({{< relref "/docs/tuis/sitrep" >}}) type the same codes for you, for the item you have selected.

| Code | What it does | TUI key |
|---|---|---|
| `>t [c<N>]` | Triage the harvested wrap-ups into action and watch items: all open ones, or only item `c<N>` | `t` |
| `>w [<theme>]` | Rewrite the short situation text: every work area that needs it, or only one | `w` |
| `>q [c<N>]` | Ask anything, optionally about one item (or just ask in your own words) | `a` |
| `>tr [c<N>]` | Report trail progress, and offer to refresh a stale trail | `T` |
| `>p` | What to pick next | `n` |
| `>c` | List the kept unparsed-output cases, or replay one against the current parser | — |
| `>?` | Show the menu again | — |

Showing the list, collecting and re-checking, dismissing and restoring are keys of the sitrep TUI (`r`, `x`, `R`), not shortcodes.

## Closing a finished agent

In [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) or a [minimonitor]({{< relref "/docs/tuis/minimonitor" >}}), press **`h`** on a finished agent:

1. The agent's terminal output is collected into the list first — the whole screen of a live agent, or the kept capture of a [frozen]({{< relref "/docs/workflows/freeze-and-restore-agents" >}}) one.
2. A dialog shows what was captured: each new or already-known item, any warnings about a wrap-up that looked incomplete, and the outcome. There are three outcomes:
   - **Harvested** — the output was read and its items are in the list.
   - **Harvested — output kept for sitrep review** — part of the output could not be read reliably, so the whole output was saved in the store with a review item (see [Output the harvest could not read](#output-the-harvest-could-not-read)). Closing is safe.
   - **Harvest failed** — nothing was certified, so the agent and its output are kept and no close is offered.
3. Only then does it offer to close the agent: **Close agent** for a live agent, **Drop** for a frozen one (which also deletes its kept capture), or **Keep**.

If the output could not be captured or collected, the dialog says why and offers no close — the agent stays. The close also applies only to the agent that was harvested: if the pane was frozen, restored or restarted while the dialog was open, nothing is closed and you are asked to press `h` again. A live sitrep window is never harvested; `h` on it just offers to close it.

**Close agent** closes only the agent's own pane and its shadow or notes panes. Other panes in the window stay, and a [minimonitor]({{< relref "/docs/tuis/minimonitor" >}}) companion closes itself once it is alone in the window.

While the monitor is open it also collects, every few minutes, any frozen agent whose capture is not in the list yet, so those agents can be dropped. The monitor's title bar shows `sitrep N now` while the list has open **Pick now** items.

## Where the list lives

The list is stored per repository in `.aitask-sitrep/`, which is git-ignored and never committed. Kept unparsed output lives there too, in `raw/`, with its case records in `cases/`. It is not rebuildable — your dismissals, the agent's derived items and the Q&A log exist nowhere else — so it is written only by one locked writer with a rolling backup. If a file is ever damaged, the sitrep TUI shows a red banner, keeps showing the last good view, and **`R`** restores the file from that backup.

Sitrep's own window is never collected into the list: its screen only shows the list back to you.

## See also

- [Sitrep TUI]({{< relref "/docs/tuis/sitrep" >}}) — the list view, its keys and its requests to the agent
- [`/aitask-sitrep`]({{< relref "/docs/skills/aitask-sitrep" >}}) — the skill reference
- [Freeze and Restore Agents]({{< relref "/docs/workflows/freeze-and-restore-agents" >}}) — freezing finished agents, whose wrap-ups sitrep collects
- [Implementation Trails]({{< relref "/docs/workflows/implementation-trails" >}})
