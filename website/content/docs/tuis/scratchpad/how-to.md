---
title: "How-To Guides"
linkTitle: "How-To"
weight: 20
description: "Taking notes beside a code agent, copying them into it, and keeping them across a re-pick"
maturity: [experimental]
depth: [intermediate]
---

## Take notes beside an agent

1. In [`ait minimonitor`]({{< relref "/docs/tuis/minimonitor" >}}), make sure the
   agent you want notes for is the **followed** agent — the one pinned at the top.
2. Press **o**. A scratchpad opens in a split of that agent's pane, below it by
   default, and the agent's window comes to the front.
3. Move tmux focus into the new pane — click it, or use your tmux pane keys
   (`Ctrl-b` + arrow by default) — and type.

The header reads `t<id> · saved` once the notes are loaded and owned by this pane.
From then on, saving is automatic; **ctrl+s** forces a save, and **ctrl+q** closes
the pad after one final save.

## Copy notes into the agent

Press **ctrl+c** in the scratchpad. With nothing selected it copies **all** of
your notes; select text first (with the mouse, or **shift** + arrow keys) to copy
only that part.

The copy goes to your system clipboard by two routes at once: an OSC 52 escape
sequence, and — inside tmux — a tmux paste buffer. Move focus to the agent's pane
and paste there with your terminal's paste key, or with tmux's paste (`Ctrl-b ]`
by default). **ctrl+x** cuts instead of copying, and reaches the same clipboard.

## Paste into the scratchpad

There are two pastes, and they read from different places:

- **Your terminal's paste** (for example `ctrl+shift+v`, or a middle click) inserts
  whatever is on the **system clipboard** — text you copied from a browser, an
  agent's output, another pane. Use this one for anything from outside the pad.
- **ctrl+v** inserts what you last copied or cut **inside this scratchpad**. It does
  not read the system clipboard.

tmux's own paste (`Ctrl-b ]`) also works, and inserts the current tmux paste
buffer.

## Keep notes across a re-pick

The notes belong to the task, not to the agent. You can kill the agent, freeze it,
or let it finish, and the notes stay on disk:

1. Close the agent however you like. If its scratchpad was open, it closes with
   the agent and makes a best-effort save on the way out — autosave has normally
   written everything already.
2. Later, pick the same task again (or run QA on it, or resume it) so that a new
   agent runs in an `agent-pick-<id>`, `agent-qa-<id>` or `agent-resume-<id>`
   window.
3. Press **o** in that agent's minimonitor. The same notes open.

The notes are deleted when the task is archived. Copy anything you want to keep
somewhere permanent before then — into the task's plan, for example.

## Use a scratchpad with a non-task agent

Press **o** on an agent that is not working on a task — an exploration agent, or
one you launched by hand. Minimonitor warns
`Not a task agent — notes will not be saved` and opens an **unsaved** pad, whose
header reads `scratch · NOT SAVED (no task)`. It is a plain editor: nothing you type
there is ever written to disk, and it is gone when the pane closes. Copy out what
you want to keep with **ctrl+c** first.

## Change where the scratchpad opens

Two keys in the `tmux:` block of `aitasks/metadata/project_config.yaml` place the
pane. Both are also editable in [`ait settings`]({{< relref "/docs/tuis/settings" >}})
→ Tmux tab.

```yaml
tmux:
  scratchpad_position: top   # above the agent; the default is bottom
  scratchpad_height: 16      # rows; the default is 12
```

An invalid value falls back to its default. The keys are read each time you press
**o**, so a change applies to the next scratchpad you open.

## When the header says read-only

`read-only: open elsewhere` means another editor already holds this task's notes —
usually one you launched by hand with `ait scratchpad --task <id>`. Minimonitor's
check for an open scratchpad only sees pads opened with **o**, so it cannot stop
**o** from opening a second editor beside a manual one; the second editor opens
read-only instead.

A read-only scratchpad is a snapshot of the notes taken when it opened. It never
saves, and it never becomes writable, even after the other editor closes. While it
is open it also keeps **o** from opening another pad for that task or that agent
— **o** just reports `A scratchpad is already open for t<id>`. To get back to an
editable pad:

1. Close the other editor with **ctrl+q**, and let its final save finish.
2. Close the read-only pad with **ctrl+q**. It closes at once — it has nothing to
   save.
3. Press **o** again in minimonitor — or, if the read-only pad was one you launched
   by hand, run the same `ait scratchpad --task <id>` command again.

If you reopen while the other editor's last save is still being written, the new
pad opens read-only again; close it and wait a moment before retrying.
