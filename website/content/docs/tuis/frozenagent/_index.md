---
title: "Frozen Agent"
linkTitle: "Frozen Agent"
weight: 16
description: "Viewer TUI that stands in for a frozen code agent's pane and restores it"
maturity: [experimental]
depth: [main-concept]
---

A **frozen** code agent is one whose process has ended while its terminal output
was kept. Freezing frees everything a running agent costs — its process, its
context, its share of the machine — but keeps the part you usually wanted: the
task-workflow summary, the list of tasks it spawned, the analysis it produced.

The `ait frozenagent` TUI is what stands in for that agent. It takes over the
agent's own pane in the agent's own tmux window, replays the captured output in
place, and offers the three ways back: **restore** the session, **re-pick** the
task, or **drop** the record for good.

> **Customizable keys:** every shortcut here can be rebound. Press `?` in this
> TUI for the in-place editor, or open
> [Settings → Shortcuts]({{< relref "/docs/tuis/settings#shortcuts-s" >}}).

## Launching

You rarely launch the viewer yourself. When an agent is frozen — with **f** in
[`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) or
[`ait minimonitor`]({{< relref "/docs/tuis/minimonitor" >}}) — the freeze
replaces the agent's process with a viewer bound to that record, so the pane
keeps its place in the window and the window keeps its name.

Two forms are available by hand:

```bash
ait frozenagent              # list mode: every frozen record, across all projects
ait frozenagent --record <id>  # viewer mode: one record
```

Those are the only accepted forms. Anything else prints
`usage: ait frozenagent [--record <id>]` and exits `2`.

You can also reach list mode from any other TUI: press **j** for the TUI
switcher, then **f**. The switcher's bottom hint row does not advertise **f** —
that row is already at the width a standard terminal can show — but the key
works.

## Layout

The header is a single line of seven fields, separated by ` · `:

```
myproject · agent-pick-1705 · t1705 Frozen code agents · claudecode/opus5 · frozen 2026-09-09T18:30:23Z · 412 lines · frozen
```

project · window · task · agent · when it was frozen · how many lines were
captured · the record's state. A task the record cannot name shows `(no task)`,
and an unknown agent shows `(agent unknown)`.

The header also carries a suffix when the capture is degraded or the view is
switched:

| Suffix | Meaning |
|---|---|
| `\[plain]` | ANSI replay is toggled off; you are reading stripped text |
| `\[colour unavailable — showing plain text]` | the colour capture could not be read, so plain text is all there is |
| `· capture missing` | the capture file is gone; the record can still be restored, re-picked or dropped |
| `· colour data missing` | the stripped text survives but the colour capture does not |

Below the header is the log area holding the captured output, and a search box
that stays hidden until you open it.

## Viewing

- **r** toggles between the ANSI replay and plain stripped text. When the colour
  capture is unreadable the viewer starts in plain mode and says so.
- **m** opens the capture as Markdown — the selected range if you have one, the
  whole capture otherwise. **Escape** closes it.
- **g** and **G** jump to the top and the bottom.

If the capture file itself is gone, the body reads
`(capture file missing — the record can still be restored, re-picked or dropped)`
and every action stays available.

## Searching

Press **/** to open the search box, type, and press **Enter**. Matching lines are
highlighted; **n** moves to the next hit. The search is a case-insensitive
substring and it wraps — you are told when it does (`Search wrapped to top`), and
told when there is nothing (`Not found: <term>`). **Escape** closes the box.

## Selecting and copying

Two ways to select:

- **Keyboard** — **shift+↑** / **shift+↓** extend a line range from the cursor.
  The range stays visible after you navigate away, and **Escape** clears it
  (when the search box is not open — Escape closes that first).
- **Mouse** — drag to select, as in any terminal app.

**y** copies the keyboard range if you have one, otherwise the mouse selection,
and reports how many lines it took. The text goes to the system clipboard by two
routes at once: an OSC 52 escape sequence, and — inside tmux — a tmux paste
buffer that is forwarded to every attached client. The second route is what makes
a copy work from a pane you cannot see.

## Restore, re-pick and drop

Three ways out of a frozen record, none of which is reversible in the same way:

- **R — restore.** Relaunches the agent with its recorded session, in the pane
  the viewer is occupying.
- **p — re-pick.** Starts the task fresh instead of replaying the old session.
  Often the cheaper choice: a new agent reads the task file rather than a long
  transcript. Only available when the record names a task — otherwise the viewer
  says `This record has no task id — restore instead`.
- **k — drop.** Deletes the record *and* its capture, and closes the stand-in
  pane, leaving nothing running. It confirms first:
  `Remove the frozen record and its capture? This cannot be undone.` with a
  **Remove** button. **R** and **p** do not confirm, because a failed attempt
  leaves the viewer and the capture where they were.

**The capture is not preserved by choosing restore or re-pick.** Once the resumed
agent identifies itself, the record deletes the transcript — the `restored`
outcome below. The capture survives only when the attempt fails, or when it
succeeds unverified (`restored, unverified — capture kept`). If you want to keep
part of the output, copy it with **y** before you press **R** or **p**.

While a restore is in flight the header reads `dispatching…`; a drop reads
`dropping…`. When it settles you get one of:

| Result | What it means |
|---|---|
| `restored` | the resumed agent confirmed itself; the capture is deleted |
| `restored, unverified — capture kept` | the agent is running but nothing confirmed it was the same session, so **the capture is kept**. A success, not a fault |
| `restore failed: <reason> — capture kept` | the attempt failed and the viewer is back; the capture is intact |
| `restore ended — capture kept` | the attempt ended without a recorded reason; the capture is intact |
| `restore did not start — run 'ait frozenagent' or reconcile` | nothing was dispatched |
| `restore still <state> after the grace — run reconcile; capture kept` | still in transition; only a reconcile pass can settle it |
| `dropped — capture removed` | the record and its capture are gone |
| `drop failed — record kept` | nothing was deleted |

A viewer that comes back after a failed restore shows what the store remembers:
`last restore failed: <reason> — capture kept`.

## List mode

`ait frozenagent` with no arguments lists every frozen record on the machine,
across every project, under the header `frozen records: <n>`:

| project | window | task | agent | frozen | lines |
|---|---|---|---|---|---|

Fields the record does not carry show `—`. **Enter** opens the highlighted record
in the viewer; **R**, **p** and **k** act on the highlighted row, and more than
one can be in flight at once. Opening a record from the list deliberately does
*not* make that pane the record's stand-in — it is a reader, not a replacement.

---

**Next:** [How-To Guides](how-to/) — reading, copying and reviving a frozen agent.  
**Reference:** [Reference](reference/) — keybindings, header fields, states, exit codes.
