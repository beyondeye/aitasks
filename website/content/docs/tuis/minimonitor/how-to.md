---
title: "How-To Guides"
linkTitle: "How-To Guides"
weight: 10
description: "Task-oriented guides for using ait minimonitor"
maturity: [stable]
depth: [intermediate]
---

### How Minimonitor Is Auto-Spawned

Minimonitor is meant to be auto-spawned — you almost never start it yourself. Every ait TUI that launches a new code agent window also creates a minimonitor split next to it:

- [`ait board`]({{< relref "/docs/tuis/board" >}}) — when you pick a task and launch its agent (action menu or agent command screen).
- [`ait codebrowser`]({{< relref "/docs/tuis/codebrowser" >}}) — when you launch an agent from a code file or the history screen.
- [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}) — when you press **n** on an agent card to pick its next ready sibling task, which creates a new agent window.
- The TUI switcher's explore launch — when it creates an agent window for an explore target.

In every case the flow is the same: the launching TUI creates a new tmux window named `agent-...`, then the auto-spawn helper creates a horizontal right-split inside that window and runs `ait minimonitor` in it. The helper skips the split if the window name does not start with the configured agent prefix (default `agent-`) or if a monitor/minimonitor is already running in the window.

> **Auto-despawn:** minimonitor closes itself automatically when the agent pane it sits next to exits. On every refresh cycle it checks the panes in its own tmux window; the first refresh after the agent pane has gone (so there is no pane left other than minimonitor itself) triggers an `exit()` and the minimonitor pane closes. A 5-second grace period after startup prevents premature exit on cold launch. You never need to `ait minimonitor` after an agent finishes — a new one will spawn with the next agent you launch.

### How to Start Minimonitor Manually

Manual launch is an escape hatch for edge cases (an agent pane you started by hand, a killed sidebar you want to bring back). From inside a tmux session, run:

```bash
ait minimonitor
```

This starts minimonitor in the current tmux pane.

> **Single-instance guard:** `ait minimonitor` checks the current tmux **window** for any existing monitor or minimonitor process. If one is already running in the same window, the new invocation prints a short message and exits. The guard is per-window, so you can still have minimonitor split alongside each of several agent windows in the same session.

### How to Read the Agent List

Minimonitor shows a single scrollable list of **agent panes** (windows whose names match the configured agent prefix — default `agent-`). By default the list aggregates agents from every aitasks tmux session on the current tmux server; `── <session_name> ──` divider rows separate agents that belong to different sessions. TUIs, shells, and other panes are deliberately filtered out; for the full categorized view use [`ait monitor`]({{< relref "/docs/tuis/monitor" >}}).

Each card in the list shows:

- A prioritized mark: **★** when you have marked the agent, dim **☆** when you have not (see [How to Mark an Agent as Prioritized](#how-to-mark-an-agent-as-prioritized))
- A status dot: **green** when the agent has produced recent output, **yellow** when it is idle
- The agent window name (truncated to 20 characters on narrow layouts)
- An `IDLE <n>s` label when the pane has been quiet longer than `tmux.monitor.idle_threshold_seconds` (default 5 seconds)
- For agents whose window name carries a task ID, a second dimmed line showing the task's title

The header bar at the top of the pane shows either `multi: Ns · Ma  N idle` when the multi-session view is active, or `<session>  N agents  N idle` when the view is restricted to the attached session. See [How to Toggle the Multi-Session View](#how-to-toggle-the-multi-session-view) below.

### Mouse Support

Minimonitor supports full mouse interaction in addition to the keyboard shortcuts:

- **Click an agent card** — focus that card (alternative to **Up** / **Down**).
- **Scroll wheel** — scroll the agent list.
- **Click dialog buttons** — buttons in the task-info dialog and TUI switcher overlay are clickable.

All keyboard actions documented below remain available.

### How to Navigate the Agent List

- **Up** / **Down** — Move focus between agent cards within the list.
- The footer hint summarizes the navigation and action keys for the current layout.

When minimonitor is shown as a side split next to an agent, it auto-selects the card for that agent whenever the minimonitor pane regains terminal focus — so the focused card always reflects the neighbor you are working with, unless you explicitly moved focus somewhere else.

### How to Focus the Sibling Agent Pane

Minimonitor is designed to live beside an agent pane in the same tmux window. Pressing **Tab** moves **tmux focus** to that sibling pane (the first non-minimonitor pane in the same window), so your next keystrokes go directly to the agent. This is the fastest way to jump from glancing at the status sidebar to typing into the agent it sits next to.

If minimonitor is the only pane in its window (no sibling to target), Tab shows a notification and does nothing.

### How to Focus Minimonitor from the Agent Pane (native tmux)

**Tab** only goes one way: minimonitor → agent pane. There is no built-in shortcut for the opposite direction. Because minimonitor lives as a second pane inside the agent's tmux **window**, you move focus the other way (agent pane → minimonitor) with tmux's own pane-switching keys — the same keys you would use to move between any two panes in one window:

- **`Ctrl-b o`** — cycle tmux focus to the next pane in the window.
- **`Ctrl-b` + an arrow key** — move focus directionally to the adjacent pane.

This also saves you from clicking the minimonitor pane to activate it. `Ctrl-b` is the default tmux prefix; if you remapped your prefix, substitute your own. Once you are comfortable with these native shortcuts you can use them for **both** directions instead of Tab if you prefer.

This intra-window pane switching is specific to the minimonitor split — the other ait TUIs each occupy their own full tmux window, which you reach with the [TUI switcher](#how-to-jump-to-another-tui) (press **`j`**).

### How to Send Enter to the Sibling Agent

When a code agent is waiting for you to press Enter (for example, it just asked a clarifying question), you can unblock it without moving tmux focus:

1. Make sure minimonitor has terminal focus
2. Press **Enter**

Minimonitor sends a single `Enter` keystroke to the sibling pane via `tmux send-keys`. Tmux focus stays on minimonitor, so you can keep watching the agent status while it processes the input.

### How to Switch to the Selected Agent

To jump your tmux session focus to the **selected** card's agent (which may be in a different window from the minimonitor you're in):

1. Focus the agent's card with Up/Down
2. Press **s**

Minimonitor asks tmux to switch focus to the agent's window (preferring the companion pane when the card is next to its own minimonitor). A notification confirms the switch.

### How to Show Task Info for an Agent

For agent panes whose window name carries a task ID (e.g., `agent-t42-claudecode`), minimonitor can open the same task detail dialog used by the other TUIs:

1. Focus the agent's card with Up/Down
2. Press **i**

The task cache is refreshed and the task detail dialog appears with the task's metadata and content. If the focused card has no task ID in its window name, a warning notification is shown instead.

The agent minimonitor **follows** — the one pinned at the top under `── this agent ──` — is never selectable, so **i** cannot reach it. Press **I** (Shift+i) instead: it always opens the task detail dialog for the followed agent, whichever card happens to be highlighted. If this window has no agent to follow, a warning notification is shown instead.

### How to Pick a Task by Number

When an agent finishes it usually names the tasks it created, or the one to pick next, as bare numbers. Press **p** to act on one without leaving the window:

1. Press **p** and type the task number (`1310`, or `1310_2` for a child task — a leading `t` is accepted)
2. Press Enter; the task's details open, with **OK** / **Cancel** and a **kill followed agent** checkbox
3. Confirm, and the usual launch dialog appears so you can pick the coding agent, model, and where the new window goes

The checkbox is unchecked by default. Tick it to close down the agent this minimonitor follows once the new one has launched — the new agent always starts first, so the window teardown can never strand it. Leave it unticked to run both side by side.

Unlike **n**, which only offers the followed task's next *ready sibling*, **p** reaches any task. That includes tasks that are not cleanly pickable: if the target is not `Ready`, or is still waiting on an unfinished dependency, the dialog says so and the confirm button reads **Launch anyway** instead of **OK**. Minimonitor still lets you launch it — it just never does so silently. It also warns when an agent for that task is already running in this session.

If the number does not look like a task id, or no such task exists, a warning notification is shown and nothing is launched.

### How to Launch a Shadow Agent

Press **e** to launch a *shadow agent* next to the code agent you are following — an advisory companion that reads that agent's terminal output and helps you make sense of it. By default the shadow opens as a new pane in the **same tmux window** as the followed agent, so it sits right beside the work it is watching.

The shadow is read-only and advisory: it can explain what the agent is doing, help you answer a prompt the agent is stuck on, critically interrogate a plan before you approve it, or review the code the agent actually wrote — but it never types into the followed agent's pane. You stay the driver.

Like minimonitor itself, the shadow pane is a companion: it never appears in the agent list, and it closes automatically when the agent it shadows exits. Only one shadow runs per followed agent — if a shadow is already running for the agent you are following, a second **e** is refused with a notification.

For what the shadow can do and how to drive it once it is running, see the [Shadow Agent]({{< relref "/docs/workflows/shadow-agent" >}}) workflow guide.

### How to Pick Shadow Concerns

When the shadow agent interrogates a plan, reviews an implementation, or diagnoses errors, it emits a structured **concern block** alongside its prose. You can forward a subset of those concerns to the followed agent without retyping them:

1. Make sure a shadow is running for the agent (press **e** if not)
2. Press **c**

Minimonitor reads the shadow pane, parses its concern block, and opens a checklist modal of the concerns — each tagged with a priority (`high`, `medium`, or `low`) and the plan region it targets. Tick the ones you want, confirm, and minimonitor copies them — with a short preamble — to your clipboard, ready to paste into the followed agent. Nothing is written to the clipboard until you confirm, and minimonitor never types into the agent itself: you stay the driver.

For an implementation review, the modal splits the list into **Needs addressing** and **Informational**. The second section holds findings the shadow reports for your judgement without asking for a change; they are dimmed and **a** (select all) skips them, while **A** (copy all) still takes everything. A review with no informational findings shows no section headers at all. If some lines in the block could not be parsed, a warning above the list says how many, so a short list is never mistaken for a complete one. If *none* of them could be parsed, minimonitor says the shadow emitted a block that yielded nothing forwardable — rather than reporting no concerns at all.

If no shadow is running, pressing **c** tells you to launch one with **e**; if the shadow has not raised any concerns yet, minimonitor says so and does nothing.

> **Auto-offer:** when the shadow produces a fresh concern block, minimonitor proactively surfaces a `Shadow raised 2 concern(s) — press 'c' to pick` toast — once per block — so you don't have to poll the shadow pane for it. The count is of concerns needing attention; any informational ones are noted separately in the same toast.

> **Configuration:** two settings control the shadow, both editable in [`ait settings`]({{< relref "/docs/tuis/settings" >}}):
>
> - **Placement** — `tmux.shadow_same_window` (Tmux tab): `true` (default) splits the shadow into the followed agent's window; `false` opens it in its own window.
> - **Agent and model** — the `shadow` row on the Agent Defaults tab selects which coding agent and model the shadow runs as.

### How to Mark an Agent as Prioritized

When you are following many agents, some matter more than others. Press **Space** to toggle a **prioritized mark** on the selected agent. Marked agents show a bright **★**; unmarked agents show a dim **☆**, so the column is always present and rows never shift when you toggle one.

The marks are stored **per user, outside every repository**, in `~/.config/aitasks/agent_marks.json` (override the path with `AITASKS_AGENT_MARKS_FILE`). That means a mark you set here is visible from every other project's `minimonitor` and `monitor` — usually within one refresh cycle (about 3 seconds). Marks survive restarting the TUI.

Each mark is keyed by the pair *(project root, tmux window name)*, so two projects that happen to run identically-named agent windows never share a mark.

Marks are purely visual: they do not reorder the list or change any counter.

**Automatic cleanup.** You never have to unmark stale entries by hand:

- **Age** — a mark older than about 2 days is dropped automatically. Set `AITASKS_AGENT_MARK_TTL_DAYS` to change the window (a missing or invalid value falls back to the default, so a typo cannot wipe your marks).
- **Departed agents** — when a project's tmux session is visible and the marked window is gone, its mark is dropped. This check is deliberately conservative: if a project's session cannot be seen at all — it is not running, or lives on a different tmux server — its marks are always left alone. A project you simply have not opened today never loses its marks.

> **Note:** the followed agent pinned at the top of the pane is not markable; marks apply to the agents in the scrollable list. Prioritizing the agent you are already watching would not tell you anything.

### How to Jump to Another TUI

Press **j** to open the TUI switcher overlay. The overlay lists the TUIs integrated with the tmux workflow:

- **board** — `ait board`
- **monitor** — `ait monitor`
- **minimonitor** — `ait minimonitor` (the current TUI)
- **codebrowser** — `ait codebrowser`
- **settings** — `ait settings`
- **brainstorm** — `ait brainstorm`

Select a target and the switcher focuses the existing tmux window running that TUI or creates a new window and launches it.

<!-- SCREENSHOT: aitasks_tui_switcher_dialog.svg — the TUI switcher overlay as shown from minimonitor -->

### How the Agent List Refreshes

The agent list refreshes on its own every `tmux.monitor.refresh_seconds` seconds (default 3) — there is no manual refresh key. Actions that change the agent set (launching or killing an agent) schedule a refresh themselves, so the list catches up immediately rather than at the next tick.

### How to Toggle the Multi-Session View

By default, minimonitor aggregates agents from every aitasks tmux session on the current tmux server. Press **M** (uppercase, Shift+m) to toggle to a single-session view that shows only the agents in the tmux session this minimonitor is running in. Press **M** again to restore the aggregated view.

The toggle is in-memory only — it applies to the current minimonitor process and is not persisted to configuration. It is also independent of the main monitor's `M` toggle; switching modes in one TUI does not affect the other.

When the multi-session view is ON, agents are grouped under `── <session_name> ──` divider rows. The divider rows are display-only — they cannot be focused, and Up/Down navigation skips over them.

For the full cross-TUI story (auto-discovery, rendering details, cross-session focus from the main monitor), see [Multi-session view]({{< relref "/docs/tuis/monitor/reference" >}}#multi-session-view) in the monitor reference.

### How to Quit

Press **q** to quit minimonitor manually. The pane running minimonitor closes; the rest of your tmux session is unaffected. Because auto-despawn already closes minimonitor whenever its companion agent exits, manual quit is mainly useful when you want to reclaim the sidebar column while the agent is still running.

### Pairing Minimonitor with Monitor

Minimonitor and monitor are complementary and can run side by side. A productive layout looks like this:

- **Window 0 — `monitor`:** full dashboard via `ait monitor` (or `ait ide`), with pane list, preview, and all controls.
- **Window 1 — `agent-t42-...`:** a code agent window. Split horizontally so that the **left pane** runs the agent and the **right pane** runs minimonitor.
- **Window 2 — `agent-t43-...`:** another agent window with its own minimonitor split.
- **Window 3+ — other TUIs:** board, codebrowser, settings, brainstorm, all reachable from any monitor via `j`.

From any of the agent windows, Tab jumps into the code agent pane and j opens the TUI switcher to hop back to the full monitor dashboard. From monitor, `s` on an agent card brings you to the companion minimonitor alongside it. See [How to Switch tmux to the Focused Pane](../monitor/how-to/#how-to-switch-tmux-to-the-focused-pane) in the monitor docs for the reverse direction.

### Configuring Auto-Spawn

Auto-spawn (from board, codebrowser, monitor's next-sibling launch, and the TUI switcher's explore launch) is controlled by two keys in `aitasks/metadata/project_config.yaml`:

```yaml
tmux:
  minimonitor:
    auto_spawn: true   # set to false to disable automatic side splits
    width: 40          # width (in columns) of the minimonitor side pane
```

You can edit these directly, or use [`ait settings`]({{< relref "/docs/tuis/settings" >}}) → Tmux tab, which writes the same keys.

### Key Bindings Quick Reference

All actions below are also available via mouse — see [Mouse Support](#mouse-support).

| Key | Action |
|-----|--------|
| `Up` / `Down` | Move focus between agent cards |
| `Tab` | Move tmux focus to the sibling pane in this window |
| `Ctrl-b o` / `Ctrl-b` + arrow | *(native tmux, not a minimonitor key)* Move tmux focus between the panes in this window — works in both directions |
| `Enter` | Send an `Enter` keystroke to the sibling pane |
| `s` | Switch tmux focus to the selected agent's window |
| `i` | Show task info for the selected agent |
| `I` | Show task info for the followed agent (the one pinned at the top) |
| `k` | Kill the followed agent (with a confirmation dialog) |
| `n` | Launch the followed agent's next ready sibling task |
| `p` | Pick any task by typing its number, then launch it |
| `e` | Launch an advisory [shadow agent]({{< relref "/docs/workflows/shadow-agent" >}}) beside the followed agent |
| `E` | Launch a shadow agent, choosing the code agent and model first |
| `c` | Pick the shadow's concerns and copy the selected ones to the clipboard |
| `Space` | Toggle the prioritized mark (`★`) on the selected agent — shared across all your projects |
| `d` | Cycle the idle-detection compare mode (`≈` ANSI-stripped, `=` strict) |
| `j` | Open the TUI switcher |
| `m` | Switch to the full [monitor]({{< relref "/docs/tuis/monitor" >}}) with this agent focused |
| `M` | Toggle the multi-session view ON/OFF |
| `?` | Open the shortcut editor to rebind any of these keys |
| `q` | Quit minimonitor |

Minimonitor inherits config keys (`tmux.default_session`, `tmux.monitor.refresh_seconds`, `tmux.monitor.idle_threshold_seconds`, `tmux.monitor.capture_lines`, `tmux.monitor.agent_window_prefixes`, `tmux.monitor.tui_window_names`) from the same `project_config.yaml` section monitor uses — see the [monitor reference]({{< relref "/docs/tuis/monitor/reference" >}}#configuration) for the full list.

---

**Next:** [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}) — review diffs with task-aware annotations.
