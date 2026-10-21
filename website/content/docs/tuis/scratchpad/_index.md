---
title: "Scratchpad"
linkTitle: "Scratchpad"
weight: 18
description: "Notes editor that sits beside a code agent and keeps its notes per task"
maturity: [experimental]
depth: [main-concept]
---

The **scratchpad** is a small notes editor that opens in a pane right beside a
code agent. It is the place for the things you think of while an agent works: a
question to ask it next, a detail to check in the plan, a snippet you will paste
in later. For an agent working on a task, the notes belong to **that task** — they
are saved as you type, they are still there after you kill the agent and pick the
task again, and they are deleted when the task is archived.

> **Customizable keys:** the editor's own shortcuts (save, quit, copy) can be
> rebound in [Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}})
> under the `scratchpad` scope. Every letter key types into the notes, so this TUI
> has no `?` editor key of its own.

## Opening

You open a scratchpad from [`ait minimonitor`]({{< relref "/docs/tuis/minimonitor" >}}):
press **o** and a scratchpad opens in a vertical split of the **followed** agent's
pane, below it by default. What you get depends on the agent:

- **A task agent** — one whose window is `agent-pick-<id>`, `agent-qa-<id>` or
  `agent-resume-<id>` — gets that task's saved notes. Minimonitor confirms with
  `Opened scratchpad for t<id>`.
- **Any other agent** gets an **unsaved** pad: you can type in it, but nothing is
  ever written to disk. Minimonitor warns `Not a task agent — notes will not be saved`
  before opening it.

Only one scratchpad opens per task, and only one per agent pane — a second **o**
reports `A scratchpad is already open for t<id>` (or `for this agent`) instead.

You can also launch it by hand, for example outside tmux:

```bash
ait scratchpad --task 42     # task 42's saved notes
ait scratchpad --unsaved     # a throwaway pad
```

A pad launched this way is just an editor: it is not bound to any agent, even
with `--target` (which only labels its header). It saves and loads the same notes,
but the binding rules under [Lifecycle](#lifecycle) — closing with the agent,
staying out of the agent lists — apply only to pads opened with **o**. Close a
manual pad yourself with **ctrl+q**, and keep it out of `agent-…` windows, where
monitor and minimonitor would list it as an agent.

The scratchpad is not in the **j** TUI switcher: it belongs beside an agent, not in
a window of its own.

## Layout

The pane is a one-line header, the editor, and a footer with the editor's keys.
The header names the pad, its save state and, when it was opened from minimonitor,
the agent pane it is bound to:

```
t42 · saved · → %17
```

An unsaved pad is named `scratch` instead of `t<id>`. The save state is the field to
watch — `saved`, `unsaved changes`, `saving…`, or a `not saved — …` message when the
notes cannot be written. Every state is listed in the
[Reference](reference/#header-states).

## Saving

You do not need to save. The scratchpad saves about a second after you stop
typing, and while you keep typing it still starts a save within about three
seconds of your first unsaved change. **ctrl+s** saves at once, and **ctrl+q**
attempts one last save before it closes — if that save fails, it tells you so
as it exits.

When tmux closes the pane instead — the agent exiting, or a kill — the scratchpad
makes a best-effort save on the way out. What a hard kill can lose is stated
exactly:

> On a hard kill, changes not included in the latest successfully saved buffer
> may be lost, including edits queued during a pending save. Autosave targets
> starting within roughly three seconds when no save is pending; this is not a
> maximum loss window.

## Where notes live

A task's notes are one Markdown file, `.aitask-scratchpad/<id>/notes.md`, under
the project root. The directory is gitignored — `ait setup` adds
`.aitask-scratchpad/` to `.gitignore` — so notes are never committed and stay on
the machine where you wrote them.

## Lifecycle

- **Per task, not per agent.** Kill the agent, freeze it, or let it finish; when
  you pick, QA or resume the same task later and press **o**, the same notes come
  back.
- **Deleted at archival.** Archiving a task deletes its notes — and the notes of
  any task folded into it. A scratchpad still open on that task shows
  `not saved — task archived`.
The last three rules hold for a scratchpad opened with minimonitor's **o**, which
binds the pad to the agent it opened beside. A pad you
[launch by hand](#opening) has no such binding.

- **Closes with its agent.** The pane closes when the agent's pane exits, and also
  when you kill the agent with **k** in monitor or minimonitor, or drop its frozen
  record.
- **Survives freeze and restore.** Freezing the agent keeps its pane in place, so
  the scratchpad stays open beside the frozen-agent viewer and is still there
  after a restore.
- **Never an agent.** The scratchpad never appears in the monitor or minimonitor
  agent lists, and it is never mistaken for the agent it sits beside.

---

**Next:** [How-To Guides](how-to/) — taking notes, copying them into an agent, keeping them across a re-pick.  
**Reference:** [Reference](reference/) — keybindings, header states, command line, configuration.
