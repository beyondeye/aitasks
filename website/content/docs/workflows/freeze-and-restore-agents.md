---
title: "Freeze and Restore Agents"
linkTitle: "Freeze and Restore Agents"
weight: 43
description: "Freeze finished agents to free their processes while keeping their output readable in place, then bring them back by restore or re-pick"
depth: [intermediate]
---

Freezing ends a code agent that has finished its task and keeps its output
readable in the same pane, so the agent stops using memory and a share of the
machine. You can bring it back later by restoring its session or by re-picking
its task.

## When to freeze

An agent can be live, parked or frozen:

| | Live | Parked | Frozen |
|---|---|---|---|
| **Process** | running | running | ended |
| **Output** | live in its pane | live in its pane | captured and replayed by the viewer |
| **Costs you** | memory, context, a share of the machine | the same; parking does not touch the process | the agent process and its context are released; the viewer holds the pane, and the capture uses some disk |
| **In the monitors** | a normal card | hidden by the `P` filter | hidden by the `P` filter |
| **How you come back** | it is already there | press `Space` once | restore the session, or re-pick the task |

Park an agent you are still waiting on, and freeze one that has delivered.
Parking is one of the agent's
[marks]({{< relref "/docs/tuis/monitor/reference" >}}#pane-interaction):
**Space** cycles the mark from unmarked to prioritized to parked and back to
unmarked.
Freezing keeps an agent's mark, and **Space** still cycles it, but it never
brings a frozen agent back. The mark and filter keys, and the counters for
parked and frozen agents, are in
the [monitor reference]({{< relref "/docs/tuis/monitor/reference" >}}).

## Freeze an agent and bring it back

1. Freeze an agent that has finished. Press **f** in
   [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) on the focused card, or
   in [`ait minimonitor`]({{< relref "/docs/tuis/minimonitor" >}}) on the
   followed agent, and confirm at `Freeze this agent?`. The
   [frozen-agent viewer]({{< relref "/docs/tuis/frozenagent" >}}) takes over the
   same pane in the same window and keeps the window's name, so your layout does
   not change.
2. Read the output when you get to it. The pane is already the viewer.
   Press **G** for the closing summary, and copy a selection with **y** or
   **ctrl+c**. The copy reaches your system clipboard even from a pane you
   cannot see. The keys for search, plain text, Markdown and selecting lines
   are listed in the
   [viewer's keybindings]({{< relref "/docs/tuis/frozenagent/reference" >}}#keybindings). The
   [how-to]({{< relref "/docs/tuis/frozenagent/how-to" >}}#copy-a-spawned-task-list-out-of-a-frozen-transcript)
   shows how to copy a spawned-task list out of a transcript.
3. Copy what you want to keep before you bring the agent back. A restore or
   re-pick that the resumed agent confirms deletes the capture.
4. Choose how to bring it back. Re-picking the task usually costs less than
   restoring it:
   - **R** (restore) relaunches the agent with its recorded session. Use it when
     you want the agent's context back: a long investigation, a half-finished
     conversation. It needs a recorded session id and the CLI that ran it. An
     OpenCode agent cannot resume a session, so it can only be re-picked; which
     other agents qualify is in
     [Which CLI owns the session]({{< relref "/docs/development/framework-session" >}}#which-cli-owns-the-session).
   - **P** (re-pick) starts the task over with a fresh agent, which reads the
     task file instead of replaying a long transcript. It costs fewer tokens and
     less time, and when the task file already says everything that matters it
     loses nothing. It needs a task id on the record.
5. Press the key in the viewer. **R** and **P** belong to the viewer. From
   `ait monitor`, press **s** to switch to the frozen agent's window; from
   `ait minimonitor`, press **Tab** to move to the pane beside it. The monitors'
   own keys keep their usual meaning on a frozen agent.
6. Drop the agent when you are done with it. **k** deletes the record and its
   capture and closes the viewer's pane. It confirms first, because it is the one
   action that leaves you with neither the agent nor its output.

The restored or re-picked agent runs in the viewer's pane.

## Before shutting down

1. Press **Z** in `ait monitor` or `ait minimonitor`. It freezes every agent on
   the machine, in every project, parked agents included. The confirmation names
   the real count, so the number is often larger than what you see on screen.
2. Shut down or reboot.
3. When the machine is back up, run `ait ide` in any project. Before it attaches,
   it lists the frozen agents whose viewer is gone, for every project, and asks
   once per project what to do:
   - **V** (the default): bring the viewers back. The agents stay frozen.
   - **R**: bring the viewers back, then restore every agent that can resume.
   - **P**: bring the viewers back, then re-pick every agent that has a task.
   - **S**: change nothing. The agents stay listed in `ait frozenagent`.

   All the questions come first; then everything runs.

This project's agents land in the session `ait ide` opens. Another project's
agents land in that project's own tmux session, and `ait ide` names those
sessions when it is done. Which projects it acts on, and the
`--no-frozen-check` option that turns the check off, are in
[The `ait ide` frozen-agent check]({{< relref "/docs/tuis/frozenagent/reference" >}}#the-ait-ide-frozen-agent-check).

To bring agents back one at a time instead, run `ait frozenagent`. It lists every
frozen record across all projects, and **R** and **P** act on the highlighted
row.

## What "unverified" means

A restore succeeds in one of two ways. It is verified when the resumed agent
confirms it is the same session, and the capture is then deleted. It is
unverified when the agent is running but nothing confirmed it resumed the same
session, so the capture is kept instead of deleted. You see it when the
[session hook]({{< relref "/docs/commands/setup-install" >}}#session-hooks) was
declined at `ait setup`, when the agent's CLI reports no session at startup, or
for a Codex agent whose session cannot be read from its process. Raising
[`frozen.restore_ack_grace`]({{< relref "/docs/tuis/frozenagent/reference" >}}#configuration)
helps only an agent that confirms itself slowly. Every message the viewer shows
is listed in [States shown]({{< relref "/docs/tuis/frozenagent/reference" >}}#states-shown),
and how a restore is confirmed is in
[Restore verification]({{< relref "/docs/development/framework-session" >}}#restore-verification).

## When something goes wrong

The viewer's messages for these cases are listed in
[States shown]({{< relref "/docs/tuis/frozenagent/reference" >}}#states-shown).

- A failed restore keeps the capture, and a new viewer takes the pane again.
  Its header gives the reason.
- A record that cannot be resumed has no session id, an agent that cannot
  resume, or a CLI that is unknown or is not the one the restore would launch.
  The viewer says so and starts nothing. You can still re-pick the task with
  **P**.
- A refusal that names another window means an earlier restore's agent is
  still running there. Close that window first, then try again.
- A session name held by another project stops a restore that would have to
  create that session. Give the two projects different `tmux.default_session`
  values; see
  [Bring an agent back]({{< relref "/docs/tuis/frozenagent/how-to" >}}#bring-an-agent-back).
- A restore that did not start, for example because tmux could not be queried
  to find where the agent should land, left the record unchanged, so you can
  try again.
- A record that stays stuck, such as a restore still in progress when the
  viewer stops watching it, a viewer whose pane died, or an agent that came
  back but still shows as frozen, is settled by a reconcile pass. An open `ait monitor` or
  `ait minimonitor` runs one regularly. To run it yourself:

  ```bash
  ./.aitask-scripts/aitask_frozen.sh reconcile
  ```

  The script's other commands are in
  [The freeze engine]({{< relref "/docs/development/framework-session" >}}#the-freeze-engine).

## Limits

- Frozen records do not expire. A record lives until you drop it or a
  confirmed restore consumes it. A record whose capture file has gone missing is
  removed, because there is nothing left to read or restore. `ait frozenagent`
  with no arguments lists every record on the machine, which is also how you
  find what still takes up disk space.
- The capture is the tail of the scrollback. `frozen.capture_max_lines`
  (50000 by default) sets how far back a freeze reaches. The capture of a pane
  with more history than that leaves out its earliest output.

## See also

- [Frozen Agent]({{< relref "/docs/tuis/frozenagent" >}}): the viewer TUI, its
  keys and its messages.
- [Framework session]({{< relref "/docs/concepts/framework-session" >}}): the
  record behind all of this. What identifies an agent, what the states mean and
  where the store lives are in
  [Framework Session Store]({{< relref "/docs/development/framework-session" >}}).
- [Session hooks]({{< relref "/docs/commands/setup-install" >}}#session-hooks):
  what `ait setup` installs to make a confirmed restore possible.
- [Crash Recovery]({{< relref "/docs/workflows/crash-recovery" >}}): what to do
  when an agent died instead of being frozen.
