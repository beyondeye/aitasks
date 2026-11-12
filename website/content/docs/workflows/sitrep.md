---
title: "Sitrep"
linkTitle: "Sitrep"
weight: 84
description: "Keep one persisted todo list per repository, so finished agent windows can be closed without losing what they said was left to do"
depth: [intermediate]
---

Sitrep keeps one todo list per repository, filled from finished agents' wrap-ups, so you can close their windows without losing what they said was left to do: the follow-up tasks they created, "push main when CI is green", the next wave of a trail. The sitrep agent keeps the list current, turns closing notes into action and watch items, and answers your questions from the sources the items point at.

The sitrep agent is advisory. It never picks a task, pushes, commits or edits code, it changes only its own list, and it never types into another pane. The [sitrep TUI]({{< relref "/docs/tuis/sitrep" >}}) types into the sitrep agent only when you press one of its request keys, and launches `/aitask-pick` for an item's task only when you press `p`.

## Keeping the list

1. Open sitrep. From inside tmux, run:

   ```bash
   ait sitrep
   ```

   The first time, this opens a window named `agent-sitrep` in your current tmux session, with three panes: the sitrep agent at the top left, which you talk to; the [sitrep TUI]({{< relref "/docs/tuis/sitrep" >}}) below it, which shows the list and does the routine work on it; and a [minimonitor]({{< relref "/docs/tuis/minimonitor" >}}) column on the right. Running `ait sitrep` again from any window, or from a linked task worktree of the same repository, takes you to that same window: there is one sitrep per repository. If the agent or the TUI is missing from the window, `ait sitrep` adds it back. When the agent exits, the TUI and the minimonitor stay; press `A` in the TUI, or run `ait sitrep`, to start a new agent.

   From the TUIs, press `S`: in [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) it opens the sitrep window of the focused agent's repository, in a minimonitor that of the agent it follows, and in the TUI switcher (`j`) that of the selected session. Outside tmux, `ait sitrep` refuses; `ait codeagent invoke sitrep` starts the agent in the current terminal instead, without its own window or the one-per-repository check.

   The sitrep agent runs on Claude Code. Its code agent and model are the `sitrep` operation in [`ait codeagent`]({{< relref "/docs/commands/codeagent" >}}) and the Settings TUI.
2. Let it start. The sitrep TUI reads every finished agent's wrap-up that the list does not hold yet and adds what it finds to the list; this is the **harvest**. A harvest also runs when an agent is frozen or finishes a task workflow. The TUI then re-checks every item it can verify: whether a task is still open, picked, archived or folded, whether a commit has reached the remote, and how far a trail has progressed. The sitrep agent greets you with the number of items in Pick now, Next and Waiting, the wrap-ups waiting for triage, and its shortcodes. You type shortcodes such as `>t`, `>q` and `>tr` to the agent, and the TUI's request keys type the same codes for you, for the selected item; every shortcode is listed under [Capabilities]({{< relref "/docs/skills/aitask-sitrep" >}}#capabilities). Press `r` in the TUI to harvest and re-check again at any time.
3. Read the list. The TUI groups the items as Now (the agent's Pick now), Next and Waiting, with one "What to do" line each. `d` also shows the done and dismissed items, and `Enter` opens an item's details and the sources it points at. An item is a task, an action, a question or a watch. For tasks, pushes and trails, the list shows the live state as the last re-check found it, and how long ago that was. An item whose state could not be verified, such as a task in a linked project that is not registered, is shown as unknown and never treated as done. The list never copies a task's content; ask for details and sitrep reads the task, plan or retained output the item points at. See [How to Read the List]({{< relref "/docs/tuis/sitrep/how-to" >}}#how-to-read-the-list).
4. Triage the wrap-ups. Every finished agent run arrives as a "Triage wrap-up of t42 …" item. Press `t` on it in the TUI to triage that one run, or type `>t` to the agent to triage every open wrap-up at once. The agent reads each run's closing message and proposes the items worth tracking:
   - **actions**: push a branch, deploy, tell someone, run something by hand. A push with a known commit is tracked against the remote and closes itself once the commit lands.
   - **watches**: CI, an external event, or an [implementation trail]({{< relref "/docs/workflows/implementation-trails" >}}) the run pointed at. A trail watch reports the trail's next wave and whether the trail is stale.

   It shows all proposals in one list and asks once before writing anything. A trail that several wrap-ups point at gets one watch, linked to all of them. Follow-up tasks a run created are already in the list as task items, so they are not proposed again. An "Analyze unparsed agent output …" item is triaged the same way; see [Output the harvest could not read](#output-the-harvest-could-not-read).
5. Ask. Press `a` on an item to ask about it, or ask the agent in your own words: "is main pushed?", "what did the t2175 runs leave open?", "what is this trail waiting for?". Sitrep answers from the sources the items point at: task and plan files, the agents' retained closing output, commits and trails. When an answer relies on an item that was last checked more than an hour ago, it says so and suggests `r`. Every question and answer is kept in a dated log next to the list, which `l` opens in the TUI.

   For a stale trail, sitrep offers to refresh it with [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}); on your yes, that skill asks again before it writes a new version. For what to pick next, it relates the Pick now items to the ranking of [`/aitask-backlog-roadmap`]({{< relref "/docs/skills/aitask-backlog-roadmap" >}}). The sitrep agent never ranks or picks a task itself; it names the `/aitask-pick` command for you to run in another agent window, and pressing `p` on the item in the TUI opens a dialog that launches it for you.
6. Dismiss what you will not do. Press `x` on an item in the TUI and give a reason. Only you dismiss: the agent may suggest it, and when you ask it to dismiss, it names the key. A dismissed item stays dismissed; later harvests and re-checks never bring it back.
7. Close finished agents with `h`. In [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) or a minimonitor, press `h` on a finished agent. Its output is harvested into the list first: the whole screen of a live agent, or the kept capture of a [frozen]({{< relref "/docs/workflows/freeze-and-restore-agents" >}}) one. A dialog then shows each new or already-known item, any warnings about a wrap-up that looked incomplete, and the outcome. Closing is offered when the output was read, when part of it could not be read reliably and the whole output was kept for a sitrep review (see [Output the harvest could not read](#output-the-harvest-could-not-read)), and when it held nothing new. When the output could not be captured or harvested, the dialog says why, the agent and its output are kept, and no close is offered.

   Where closing is offered, the dialog offers **Close agent** for a live agent, **Drop** for a frozen one (which also deletes its kept capture), and **Keep**. **Close agent** closes only the agent's own pane and its [shadow]({{< relref "/docs/workflows/shadow-agent" >}}) and [scratchpad]({{< relref "/docs/tuis/scratchpad" >}}) panes; other panes in the window stay, and a minimonitor companion closes itself once it is alone in the window. If the agent was frozen, restored or restarted while the dialog was open, nothing is closed and you are asked to press `h` again. On a live sitrep window, `h` harvests nothing and only offers to close it.

While `ait monitor` or a minimonitor is open, it also harvests, about every 10 minutes, every frozen agent's capture that no list holds, so those agents can be dropped. The full monitor's title bar shows `sitrep N now` while the list has open Pick now items.

## Output the harvest could not read

Sometimes an agent's wrap-up cannot be read reliably, for example because its closing banner is cut off. The closing banner is the short block, starting `✔ aitask workflow complete` or `■ aitask workflow stopped`, that a task workflow prints as its last output. The harvest then still writes every item it found, keeps the agent's whole output with a note of what went wrong and where, and adds one "Analyze unparsed agent output …" item. An agent frozen mid-work, with no closing banner at all, is not such a case. Every cause is listed under [Unparsed-output cases]({{< relref "/docs/tuis/sitrep/reference" >}}#unparsed-output-cases).

1. Triage the item: `t` on it in the TUI, or `>t`. Sitrep reads the kept output around each problem, proposes the follow-up tasks and actions the harvest missed, and records what it found.
2. To look at the kept output yourself, run `ait sitrep case list` for every kept case and its review state, then `ait sitrep case replay <case>` to see what the current parser would find in it now; replay writes nothing. The other case commands are in the [sitrep TUI reference]({{< relref "/docs/tuis/sitrep/reference" >}}#unparsed-output-cases).

Closing or dismissing the item never deletes the kept output, and nothing deletes it automatically.

## Where the list lives

The list belongs to the repository's main working copy; a linked task worktree uses the same list. It stays on this machine and is never committed. It cannot be rebuilt: your dismissals, the agent's derived items and the Q&A log exist nowhere else. If one of its files is damaged, the sitrep TUI shows a red warning naming the file, keeps showing the last good view, and `R` restores the file from its backup. Sitrep's own window is never harvested into the list, because its screen only shows the list back to you. The files and folders are listed under [Where the list is stored]({{< relref "/docs/tuis/sitrep/reference" >}}#where-the-list-is-stored).

## See also

- [Sitrep TUI]({{< relref "/docs/tuis/sitrep" >}}): the list view, its keys and its requests to the agent
- [`/aitask-sitrep`]({{< relref "/docs/skills/aitask-sitrep" >}}): the skill reference
- [Freeze and Restore Agents]({{< relref "/docs/workflows/freeze-and-restore-agents" >}}): freezing finished agents, whose wrap-ups sitrep harvests
- [Implementation Trails]({{< relref "/docs/workflows/implementation-trails" >}})
