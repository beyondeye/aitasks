---
title: "Freeze and Restore Agents"
linkTitle: "Freeze and Restore Agents"
weight: 43
description: "Freeze finished agents to free their processes while keeping their output readable in place, then bring them back by restore or re-pick"
depth: [intermediate]
---

A working day with aitasks ends with more agents than you need. Ten or twenty
panes, each holding a code agent that has finished its task — and what you
actually want from most of them is the last screen: the workflow summary, the
list of tasks it spawned, the analysis it produced. The process behind that
screen is still running, still holding its context, still costing you memory and
a share of the machine.

**Freezing** ends the agent and keeps the screen. The agent's process — and the
context it was holding — goes away; its pane is taken over by the
[frozen-agent viewer]({{< relref "/docs/tuis/frozenagent" >}}), which replays
the captured output in place. What you trade a code agent for is that viewer:
a small terminal app that reads a file. The record of the agent — its task, its
session, its window — is kept so you can bring it back later.

## When to freeze

Three states an agent can be in, and they differ in what is running:

| | Live | Parked | Frozen |
|---|---|---|---|
| **Process** | running | running | ended |
| **Output** | live in its pane | live in its pane | captured and replayed by the viewer |
| **Costs you** | memory, context, a share of the machine | the same — parking changes nothing about the process | the agent process and its context are released; the viewer holds the pane, and the capture holds disk under `~/.config/aitasks/frozen/` |
| **In the monitors** | a normal card | `P`, hidden by the `P` filter, counted as `N parked` | `F`, hidden by the same filter, counted as `N frozen` |
| **How you come back** | it is already there | press `Space` to unpark | restore the session, or re-pick the task |

Parking is a signal to *you*: the agent keeps working and the monitors stop
showing it. Freezing is a decision about the *agent*: you are done with it as a
process, and you want its results readable. An agent you are still waiting on
gets parked; an agent that has delivered gets frozen.

## The daily loop

**Freeze what has finished.** Press **f** in
[`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) on the focused card, or in
[`ait minimonitor`]({{< relref "/docs/tuis/minimonitor" >}}) on the followed
agent. A dialog confirms (`Freeze this agent?`) and explains the trade. Nothing
about your layout changes: the viewer takes over the same pane in the same
window, keeping the window's name, so an agent pane with a minimonitor companion
beside it still looks exactly like that.

**Read it whenever you get to it.** The pane is the viewer, so there is nothing
to launch — press **G** for the closing summary, **r** for plain text, **m** to
render the capture as Markdown. Search with **/** and **n**, select with
**shift+↑** / **shift+↓** or the mouse, and copy with **y**, which reaches your
system clipboard even from a pane you cannot currently see. The
[how-to]({{< relref "/docs/tuis/frozenagent/how-to" >}}) walks through pulling a
spawned-task list out of a transcript.

**Come back by the cheaper route.** Two ways back, and the obvious one is
usually not the cheaper one:

- **R — restore** relaunches the agent with its recorded session. Worth it when
  the agent's *context* is what you want back: a long investigation, a
  half-finished conversation.
- **p — re-pick** starts the task over with a fresh agent, which reads the task
  file instead of replaying a long transcript. That is cheaper in tokens and in
  time, and for a task whose file already says everything that matters it loses
  nothing.

Each route needs something the other does not, and a record may carry only one:
re-pick needs a **task id**, restore needs a recorded **session id**. An agent
whose CLI cannot resume a session — OpenCode today — can only be re-picked.

**A successful, verified restore or re-pick deletes the capture.** Once the
resumed agent identifies itself the transcript has served its purpose and the
record drops it. Choosing restore or re-pick is therefore not a way to keep the
output: copy what you want with **y** first.

**Drop when you are done.** **k** deletes the record and its capture and closes
the stand-in pane. It confirms first, because that is the one action that leaves
you with neither the agent nor its output.

## Before shutting down

**Z** freezes every agent on the machine — every project, parked agents
included, not just the ones in the list you are looking at. The confirmation
names the real count, which is why that number is usually larger than what is on
screen. It is the key for shutting the machine down with your work recoverable.

Afterwards, bring agents back one at a time from `ait frozenagent` list mode —
it lists every frozen record across all projects, and **R** / **p** act on the
highlighted row — or all at once:

```bash
./.aitask-scripts/aitask_frozen.sh restore --all           # resume each session
./.aitask-scripts/aitask_frozen.sh restore --all --repick  # re-pick each task instead
```

Restore-All works through the records sequentially, and one record's failure
never stops the batch: with three frozen agents and one missing binary, the other
two come back. A record with no recorded session id, or one whose CLI cannot
resume, is reported as a failure by the first form and keeps its capture — those
are the ones to bring back by re-picking.

Agents whose windows survived come back in them. Agents whose windows are gone —
after a tmux restart, say — come back in **new windows under their recorded
names**; if a name is already taken, the next one gets a `-2` suffix. A project
with no tmux session at all gets one created the way `ait ide` would. The full
set of landing places is in
[Where the agent comes back]({{< relref "/docs/tuis/frozenagent/how-to" >}}#bring-an-agent-back).

## What "unverified" means

A restore succeeds in one of two ways, and they are not the same outcome:

| Outcome | What happened | The capture |
|---|---|---|
| `restored` | the resumed agent's session hook reported the record and the expected session id back to the store | **deleted** |
| `restored, unverified — capture kept` | the agent is running, nothing confirmed it is the same session, and the framework confirmed it on the process alone | **kept** |

Both are successes. The second is not a fault, and it is the safer of the two:
precisely because nobody confirmed the session, the transcript is kept rather
than deleted.

You will see it whenever no [session hook]({{< relref "/docs/commands/setup-install" >}}#session-hooks)
reports back — the hook was declined at `ait setup`, or the agent is an
interactive Codex session (Codex fires the hook only under `codex exec`), or the
CLI reports no session at startup.

`frozen.restore_ack_grace` sets how long the restore waits for that
acknowledgement. It is a **waiting period, not an outcome lever**: an agent that
never acknowledges ends unverified however high you set it. See the
[reference]({{< relref "/docs/tuis/frozenagent/reference" >}}#configuration).

## When something goes wrong

**A failed restore costs you nothing.** The viewer comes back in its pane and the
capture is intact. The header reports what happened —
`restore failed: <reason> — capture kept` — and the viewer shows the store's
memory of it the next time you open the record.

**`restore did not start` is the other shape of failure.** Nothing was
dispatched: the record has no session id to resume, the agent does not support
resuming, or tmux could not be queried to find out where the agent should land.
Re-pick is the way forward for the first two.

**A stand-in that died is respawned.** So is a freeze or a restore whose
coordinator was killed part-way: records in a transitional state are settled from
what tmux can actually be seen to hold. That settling — **reconcile** — runs
after every freeze and restore, and on the maintenance tick of any open
`ait monitor` or `ait minimonitor`. To run it yourself:

```bash
./.aitask-scripts/aitask_frozen.sh reconcile
```

There is no `ait frozen` command; the viewer is `ait frozenagent`, and the engine
is the script above.

**A session name held by another project** stops a restore that would have had to
create that session, rather than borrowing it. That case and the closed-window
routes are covered in
[Where the agent comes back]({{< relref "/docs/tuis/frozenagent/how-to" >}}#bring-an-agent-back).

## Marks and frozen agents

Freezing does not disturb the mark you put on an agent. A frozen card shows its
★ or `P` *plus* a cyan `F`, so the mark column never shifts, and `Space` still
cycles the mark of a frozen agent.

The `P` filter hides parked and frozen agents together — it is one filter over
both kinds of set-aside agent, not two. The counters stay separate: `N parked`
and `N frozen` (`Np` and `Nf` in minimonitor's narrow header), both reported
whether or not the rows are hidden, and an agent that is both frozen and marked
parked is counted once, as frozen.

## Limits

- **Frozen records do not expire.** There is no age-based cleanup: a record lives
  until you drop it or a verified restore consumes it. A record whose capture
  file has gone missing is retired, since there is nothing left to read or
  restore from.
- **Disk.** Each record keeps `capture.ansi` and `capture.txt` under
  `~/.config/aitasks/frozen/<id>/`. `ait frozenagent` with no arguments lists
  every record on the machine, which is also the way to find what is still
  taking up space.
- **The capture is the tail of the scrollback.** `frozen.capture_max_lines`
  (50000 by default) is a *depth*, not a total: the freeze reaches that many
  lines back through the pane's history and runs to the bottom of the visible
  pane, so a stored capture holds roughly the cap plus a pane height. A pane with
  more history than the cap has already lost its earliest output before the
  freeze runs.

## See also

- [Frozen Agent]({{< relref "/docs/tuis/frozenagent" >}}) — the viewer TUI, its
  keys and its messages.
- [Framework session]({{< relref "/docs/concepts/framework-session" >}}) — the
  record behind all of this: what identifies an agent, what the states mean, and
  where the store lives.
- [Session hooks]({{< relref "/docs/commands/setup-install" >}}#session-hooks) —
  what `ait setup` installs to make a verified restore possible.
- [Crash Recovery]({{< relref "/docs/workflows/crash-recovery" >}}) — what to do
  when an agent died instead of being frozen.
