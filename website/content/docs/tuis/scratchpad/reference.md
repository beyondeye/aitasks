---
title: "Feature Reference"
linkTitle: "Reference"
weight: 30
description: "Keybindings, header states, command line, configuration and storage for ait scratchpad"
maturity: [experimental]
depth: [advanced]
---

## Keybindings

| Key | Action | Notes |
|-----|--------|-------|
| `ctrl+s` | Save now | In a pad that cannot save, it shows the current state instead |
| `ctrl+q` | Save and quit | Attempts one final save, reports a failure as it exits, then closes. A read-only or unsaved pad closes at once. The command palette's Quit does the same |
| `ctrl+c` | Copy | The selection, or **all** the notes when nothing is selected. Goes to the system clipboard by OSC 52 and, inside tmux, to a tmux paste buffer |
| `ctrl+x` | Cut | The selection, or the current line when nothing is selected. Same clipboard routes as `ctrl+c` |
| `ctrl+v` | Paste | What was last copied or cut **in this pad** — not the system clipboard. Use your terminal's paste for that |
| `ctrl+z` / `ctrl+y` | Undo / redo | |

Every other key belongs to the editor: letters type, and arrows, **shift** + arrows
(select), **Home**/**End** and the rest behave as in any text field.

`ctrl+s`, `ctrl+q` and `ctrl+c` can be rebound in
[Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}) under the
`scratchpad` scope. The remaining keys are the text editor's own and are not in
that scope. The scratchpad has no `?` shortcut-editor key, because `?` types a `?`.

## Header states

The header is `<name> · <state>`, followed by ` · → <pane>` when the pad is bound
to an agent pane. `<name>` is `t<id>` for a task pad and `scratch` for an unsaved
one.

| State | Meaning |
|-------|---------|
| `opening…` | Loading the notes; the editor is read-only until they are in |
| `saved` | Everything you typed is on disk |
| `unsaved changes` | You have typed since the last save; autosave is due shortly |
| `saving…` | A save is being written |
| `save failed — retrying in <n>s` | The last save did not complete; it is retried automatically |
| `save stuck — waiting for the previous write to finish` | A save ran past its time limit and could not be confirmed stopped. No new save starts until it has |
| `saving before quit…` | `ctrl+q` is making its final save |
| `autosave stopped — error` | Autosave hit an internal error and has stopped. Copy your notes out with `ctrl+c` |
| `NOT SAVED (no task)` | An unsaved pad — nothing typed here is written anywhere |
| `read-only: open elsewhere` | Another editor holds this task's notes; this pad is a snapshot that never saves — see [When the header says read-only](../how-to/#when-the-header-says-read-only) |
| `not saved — task archived` | The task was archived and its notes deleted; nothing more is saved |
| `not saved — no active task` | No active task file exists for this id, so there is nowhere to save |
| `not saved — store unavailable` | The notes store could not be opened |

In every `not saved — …` state you can still type and copy, but nothing is written.

## Command line

```bash
ait scratchpad --task <id> [--target <pane>]   # a task's saved notes (42 or 42_3; a leading t is accepted)
ait scratchpad --unsaved [--target <pane>]     # a throwaway pad
```

Exactly one of `--task` and `--unsaved` is required. `--target` only labels the
header with the pane the pad belongs to; it binds nothing — see
[Lifecycle rules](#lifecycle-rules) for what a hand-launched pad does not get. Minimonitor's **o**
runs this command for you.

| Exit code | Cause |
|-----------|-------|
| `0` | Normal quit |
| `1` | Missing Python packages — run `ait setup` |
| `2` | Bad arguments, or `ait scratchpad: invalid task id: <id>` |

## Configuration

Two keys under the `tmux:` block of `aitasks/metadata/project_config.yaml` place
the pane that minimonitor's **o** opens. Both are editable in
[`ait settings`]({{< relref "/docs/tuis/settings" >}}) → Tmux tab and are read on
each **o** press.

| Key | Default | Effect |
|-----|---------|--------|
| `tmux.scratchpad_position` | `bottom` | `top` or `bottom`: above or below the followed agent's pane. Any other value means `bottom` |
| `tmux.scratchpad_height` | `12` | Initial height of the pane, in rows. A value that is not a whole number of at least 1 means `12` |

## Storage

- A task's notes are the file `.aitask-scratchpad/<id>/notes.md` under the project
  root. The environment variable `AITASK_SCRATCHPAD_DIR` moves the root.
- `.aitask-scratchpad/` is gitignored — `ait setup` adds it to `.gitignore` — so
  notes are never committed and never leave the machine.
- Archiving a task deletes its notes directory, and the notes of every task folded
  into it.
- An unsaved pad writes nothing at all.

## Autosave timing

A save is due one second after your last change, or three seconds after your
first unsaved change, whichever comes first — continuous typing postpones the
first, never the second. Saves run one at a time: a change made while a save is
running waits for the next one. A failed save is retried two seconds after it
returned. A save still running after 30 seconds is stopped and retried.

When tmux closes the pane (the agent exits, or the pane is killed), the scratchpad
starts a best-effort save of what you typed before it goes.

> On a hard kill, changes not included in the latest successfully saved buffer
> may be lost, including edits queued during a pending save. Autosave targets
> starting within roughly three seconds when no save is pending; this is not a
> maximum loss window.

The notes store also waits up to 5 seconds for its own lock before giving up on a
save. That figure bounds only the lock wait; it is not a limit on how long a save
takes.

## Lifecycle rules

- **One pad per task, one per agent.** Minimonitor's **o** refuses when a pad is
  already open for the same task's notes or bound to the same agent pane:
  `A scratchpad is already open for t<id>` (or `for this agent`). If it cannot
  check, it refuses too: `Could not verify whether a scratchpad is already open — not opening`.
- **The check sees only pads opened with o.** An editor launched by hand carries
  no binding, so **o** can open a second editor beside it. That second editor opens
  read-only.
- **An open pad blocks o whether or not it can save.** A read-only pad is a
  snapshot taken when it opened: it does not refresh, never saves, and never becomes
  writable. Close it with `ctrl+q` (it closes at once) before opening another.
- **Binding comes only from o.** The three rules below hold for a pad opened with
  minimonitor's **o**, which binds it to the agent pane. `ait scratchpad` run by
  hand binds nothing, even with `--target`: such a pad does not close with any
  agent (close it with `ctrl+q`), and in an `agent-…` window monitor and
  minimonitor list it as an agent.
- **Closes with its agent** — when the agent's pane exits, when the agent is killed
  with **k** in monitor or minimonitor, and when its frozen record is dropped. If
  minimonitor could not arrange that, it says so when opening:
  `Scratchpad opened; auto-cleanup on agent exit could not be wired — close the scratchpad by hand when the agent exits`.
- **Stays open across freeze and restore**, and when another agent in the same
  window exits.
- **Never listed as an agent** in monitor or minimonitor.

## See also

- [Minimonitor]({{< relref "/docs/tuis/minimonitor" >}}) — where **o** opens a
  scratchpad ([How to Open a Scratchpad]({{< relref "/docs/tuis/minimonitor/how-to" >}}#how-to-open-a-scratchpad)).
- [Frozen Agent]({{< relref "/docs/tuis/frozenagent" >}}) — what stands in for a
  frozen agent while its scratchpad stays open.
- [Monitor reference]({{< relref "/docs/tuis/monitor/reference" >}}#configuration)
  — the full `tmux:` configuration block.
