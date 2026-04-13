---
Task: t534_full_monitor_from_minimonitor.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# t534 — Minimonitor shortcut to full monitor with companion agent focused

## Context

Minimonitor runs in the same tmux window as one agent (its "companion"). Today,
switching to the full monitor and focusing that companion agent costs several
keystrokes: `j` (tui switcher) → select monitor → Up/Down to find the right
agent card. The task is to add a single keybinding (`m`) in minimonitor that
jumps straight to the full monitor window with the companion agent already
focused.

## Design

**Cross-process hand-off via tmux session env var.** Minimonitor writes the
companion's tmux window name to `AITASK_MONITOR_FOCUS_WINDOW` on the session,
then selects (or creates) the `monitor` window. The monitor TUI reads that
env var on each refresh; on a successful match, it sets the focused pane and
clears the env var. If no match yet (e.g. fresh monitor startup race), the
env var is left in place and retried on the next refresh.

Window **name** is used (not window index) because names are stable across
tmux renumber-windows and uniquely identify agent windows (`agent-*`).

Works for both cases:
- **Monitor not running** — `ait monitor` is launched in a new window; on the
  first refresh it reads the env var and auto-focuses the target card.
- **Monitor already running** — `select-window` switches to it; its next
  refresh cycle picks up the env var and moves focus.

## Files to modify

### 1. `.aitask-scripts/monitor/minimonitor_app.py`

- **Track own window name** — add `self._own_window_name: str | None = None`
  in `__init__`, and extend the `tmux display-message` calls in `on_mount()`
  and `_update_own_window_info()` to fetch `#{window_name}` alongside
  `window_id` and `window_index`. Store in `_own_window_name`.
- **Add binding `m`**: `Binding("m", "switch_to_monitor", "Full Monitor", show=False)`.
- **Update `#mini-key-hints`** text to include `m:full`.
- **New action `action_switch_to_monitor()`:**
  - Guard: if no `TMUX` env, `_own_window_name` is None, or `_session` is
    missing → `notify("Not inside tmux", severity="warning")` and return.
  - `tmux set-environment -t <session> AITASK_MONITOR_FOCUS_WINDOW <name>`
  - Query `tmux list-windows -t <session> -F '#{window_name}'` to check if
    `monitor` window exists.
  - If exists: `tmux select-window -t <session>:monitor`
  - If not: `tmux new-window -t <session>: -n monitor "ait monitor"`
  - On subprocess error → `notify(..., severity="error")`.

### 2. `.aitask-scripts/monitor/monitor_app.py`

- **New helper `_consume_focus_request()`** on `MonitorApp`. Takes no args,
  returns `str | None`:
  - Run `tmux show-environment -t <session> AITASK_MONITOR_FOCUS_WINDOW`.
  - Non-zero exit / empty stdout / value starts with `-` → return `None`.
  - Parse `VAR=value` → return the value (without clearing yet).
- **New helper `_clear_focus_request()`** — `tmux set-environment -t <session>
  -u AITASK_MONITOR_FOCUS_WINDOW`.
- **Hook into `_refresh_data()`** — after `capture_all()` and the stale-pane
  cleanup, before `_maybe_auto_switch`:
  ```python
  target_name = self._consume_focus_request()
  if target_name:
      for pid, snap in self._snapshots.items():
          if (snap.pane.category == PaneCategory.AGENT
                  and snap.pane.window_name == target_name):
              self._focused_pane_id = pid
              saved_pane_id = pid
              saved_zone = Zone.PANE_LIST
              self._clear_focus_request()
              break
  ```
  If no match, leave the env var in place for the next refresh tick.

No change is needed to `_restore_focus` — it already walks the card list and
focuses the card whose `pane_id` matches `saved_pane_id`.

## Edge cases

- **Companion pane filtered** — `_is_companion_process` removes minimonitor
  panes from the agent list; the agent pane in the same window stays with
  the same `window_name`, so lookup still succeeds.
- **Startup race** — if monitor's first refresh runs before the target pane
  is captured, `_consume_focus_request` returns the value but no match is
  found, so the env var stays set and the next refresh retries.
- **Stale env var** — tmux session env vars only live for the session
  lifetime, so stale state is bounded.
- **`m` pressed before `on_mount` finishes** — `_own_window_name` is `None`,
  the action notifies and bails out.

## Verification

Interactive (tmux TUI feature):

1. Start a tmux session with an agent window — minimonitor spawns in a side
   pane.
2. Press `m` in the minimonitor. Expected: the tmux window switches to a
   `monitor` window (newly created if not present), and the card for the
   originating agent is pre-selected with Content Preview showing its output.
3. Press `m` from another agent window's minimonitor while monitor is already
   running. Expected: switch + re-focus within ~3s (one refresh cycle).
4. Kill the monitor window, press `m` — new monitor launches with correct
   focus.

Syntax check: `python -m py_compile .aitask-scripts/monitor/minimonitor_app.py
.aitask-scripts/monitor/monitor_app.py`.

## Step 9 — Post-Implementation

Standard task-workflow Step 9: user review → commit → archive → push. No
branch/worktree (fast profile). No `verify_build` configured.

## Post-Review Changes

### Change Request 1 (2026-04-13 14:55)
- **Requested by user:** `m:full` shortcut hint did not appear at the bottom
  of the minimonitor.
- **Root cause:** First attempt extended the existing 2-line hint and added
  extra spacing on the second line, pushing total content past the ~40-col
  minimonitor width. The line wrapped and `m:full` was clipped.
- **Changes made:** Restored original 2-line column alignment and moved the
  new shortcut to its own third line: `m:full monitor`. The `dock: bottom;
  height: auto;` hint container grows to accommodate the third line.
- **Files affected:** `.aitask-scripts/monitor/minimonitor_app.py` (compose).

## Final Implementation Notes

- **Actual work done:** Added an `m` keybinding to minimonitor that hands
  off the companion agent's tmux window name to the full monitor via the
  tmux session env var `AITASK_MONITOR_FOCUS_WINDOW`, then selects (or
  launches) the `monitor` window. The full monitor consumes the env var
  on each refresh, finds the matching agent pane by `window_name`, sets
  it as the focused pane, and clears the env var on a successful match.
- **Deviations from plan:** None of substance. Minor: hint text layout
  changed during user review (see Change Request 1).
- **Issues encountered:** First hint text edit overflowed the narrow
  minimonitor column and the new shortcut was clipped. Resolved by moving
  the new shortcut to its own third hint line, leaving the existing
  2-line column alignment untouched.
- **Key decisions:**
  - **Cross-process hand-off mechanism:** chose tmux session env vars over
    a marker file because tmux env vars are session-scoped (auto-cleared
    on session kill), avoid filesystem cleanup, and need no extra IPC code.
  - **Match by `window_name` instead of `window_index`:** names are stable
    across tmux `renumber-windows` and uniquely identify agent windows.
  - **Env var only cleared on successful pane match:** lets the next
    refresh retry the lookup if the target pane wasn't yet captured on
    the first refresh after a fresh `ait monitor` startup.
  - **Three-line hint layout:** simpler and safer than packing the new
    shortcut into the existing 2-line column-aligned grid, where it
    overflowed the narrow column.
