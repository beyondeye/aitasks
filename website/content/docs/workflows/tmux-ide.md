---
title: "The tmux IDE workflow"
linkTitle: "tmux IDE workflow"
weight: 5
description: "Daily end-to-end developer workflow using ait ide, the monitor TUI, and the TUI switcher"
---

This page walks through a day in the life of an aitasks user — starting the IDE, picking a task, watching a code agent run, reviewing the diff, and committing. Everything happens inside a single tmux session managed by `ait ide`, with the **`j`** key as the one keystroke that moves between TUIs.

## Before you start

- **tmux 3.x or newer** installed. See the [Terminal Setup page](../../installation/terminal-setup/) for details.
- **ait** installed and `ait setup` run in your project. See [Getting Started](../../getting-started/) if you haven't done that yet.
- **Code agents configured** — open `ait settings` → **Code Agents** tab and pick your default agent + model.

## 1. Start the IDE

Open a terminal, go to your project, and run:

```bash
cd /path/to/your/project
ait ide
```

`ait ide` attaches to (or creates) the project's tmux session and opens a `monitor` window running [`ait monitor`](../../tuis/monitor/) — the dashboard for everything happening inside the session. You land directly on the monitor view: a list of agent windows on the left, a preview pane on the right, and a footer showing the active key bindings.

<!-- TODO screenshot: aitasks_monitor_main_view.svg — the monitor dashboard immediately after running ait ide -->

From this point on every aitasks TUI is one keystroke away. `ait ide` is the only shell command you need — everything else is reachable via the TUI switcher.

## 2. Jump to the board with `j`

Press **`j`** anywhere in the monitor. The **TUI switcher** dialog appears, listing the main TUIs (`board`, `monitor`, `codebrowser`, `settings`) plus any running code agent windows and brainstorm sessions grouped underneath. Select **board** and the switcher opens (or focuses) the `ait board` window inside the same tmux session.

<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg — the TUI switcher dialog opened from the monitor -->

The board is your kanban view of the task list. Navigate with the arrow keys, press **Enter** to open a task detail panel, and **Shift+arrows** to move a task between columns.

## 3. Pick a task

With a task highlighted on the board, press **`p`** to pick it. The board invokes the `aitask-pick` skill inside your configured code agent and launches the agent in a new tmux window. The task's status flips to **Implementing** and it appears in the monitor's agent list.

If you prefer to start the pick skill directly from a code agent prompt, open any tmux window and run `/aitask-pick` (or `$aitask-pick` in Codex CLI) in the agent's REPL — the effect is the same.

## 4. Watch the agent run

Press **`j`** → **monitor** to return to the dashboard. The agent you just launched shows up in the agent list with an idle-or-busy indicator. Select it to see the live tmux pane contents in the preview panel on the right.

To drop straight into the agent's own tmux window and interact with it, press **`j`** again — the new window appears under the **Code Agents** group in the switcher — and select it. The agent window opens with `ait minimonitor` running as a narrow side panel alongside the agent pane, so you keep the live agent list visible while the agent works.

## 5. Review the changes

When the agent finishes, it will prompt you for review through the `aitask-pick` workflow. Press **`j`** → **codebrowser** to open `ait codebrowser` and walk through the diff file by file. Approve the changes or jump back to the agent window to request adjustments — `aitask-pick` loops between implementation and review until you accept.

## 6. Commit and iterate

Once you approve the changes, the `aitask-pick` skill handles the rest automatically: it commits the code (with proper `<issue_type>: <description> (tNN)` formatting), updates the plan file, runs `aitask_archive.sh` to move the task and plan into their archive directories, and pushes the result. The agent window closes itself and you land back in the monitor with a fresh view.

From there you're ready for the next task. Press **`j`** → **board**, pick another task, repeat.

## Key bindings at a glance

| Key | Action | Where |
|-----|--------|-------|
| `j` | Open the TUI switcher | Board, monitor, minimonitor, codebrowser, settings, brainstorm |
| `p` | Pick highlighted task | Board |
| `Enter` | Open task detail / confirm | Board, monitor, codebrowser |
| Arrow keys | Navigate list | All main TUIs |
| `Shift+arrows` | Move task between columns | Board |
| `q` | Quit current TUI | All main TUIs |

The switcher's destinations are the main TUIs (`board`, `monitor`, `codebrowser`, `settings`), any running code agent windows (grouped under **Code Agents**), and any running brainstorm sessions. `minimonitor` is not a destination — it runs automatically as a side panel inside each code agent window.

See each TUI's documentation for its full key binding reference: [Board](../../tuis/board/), [Monitor](../../tuis/monitor/), [Code Browser](../../tuis/codebrowser/), [Settings](../../tuis/settings/).

## Related

- [Terminal Setup](../../installation/terminal-setup/) — terminal emulator choice, tmux install, and the `ait ide` command reference.
- [Getting Started](../../getting-started/) — the shorter first-task walkthrough.
- [Monitor TUI](../../tuis/monitor/) — full details of `ait monitor`, the agent list, and the TUI switcher.
- [One gotcha: `ait ide` is one view of a shared session](../../installation/terminal-setup/#one-gotcha-ait-ide-is-one-view-of-a-shared-session) — why two `ait ide` windows share state, and how to run parallel IDEs per project.
- [Concepts: The IDE model]({{< relref "/docs/concepts/ide-model" >}}) — the conceptual overview of how `ait ide` is structured.
