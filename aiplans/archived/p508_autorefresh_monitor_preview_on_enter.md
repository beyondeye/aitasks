---
Task: t508_autorefresh_monitor_preview_on_enter.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

In the monitor TUI (`ait monitor`), pressing Enter in the PANE_LIST zone sends an Enter key to the focused agent's tmux pane. After sending, `self.call_later(self._fast_preview_refresh)` schedules a preview refresh on the next event loop tick — essentially immediate. The problem: the agent hasn't processed the Enter yet, so the preview shows stale content. The user can't tell whether the Enter was actually sent.

## Approach: Delayed one-shot refresh with dedup

Replace the immediate `call_later` with a delayed one-shot timer (~300ms), and track the timer to cancel/replace if another key is sent before it fires. This avoids stacking multiple delayed refreshes on rapid keystrokes.

**Why not integrate with the existing periodic timer?** The `_preview_timer` (0.3s interval) only runs in PREVIEW zone, not PANE_LIST. Repurposing it would complicate zone management for minimal benefit. A separate one-shot timer is simpler, testable, and still works with the existing mechanism — the periodic timer continues to handle PREVIEW zone as before.

## File to modify

`.aitask-scripts/monitor/monitor_app.py`

## Steps

- [x] 1. Add `_delayed_refresh_timer` instance variable in `__init__`
- [x] 2. Add `_schedule_delayed_refresh` and `_fire_delayed_refresh` methods
- [x] 3. Replace `call_later` with `_schedule_delayed_refresh` for Enter in PANE_LIST
- [x] 4. Step 9: Post-Implementation (archival, push)

## Verification

1. Run `ait monitor` inside a tmux session with at least one agent pane
2. Navigate to pane list (Tab to PANE_LIST zone)
3. Press Enter — should see the preview update ~300ms later reflecting the agent's response to Enter
4. Press Enter rapidly multiple times — should not stack refresh calls, only the last one fires
5. Switch to PREVIEW zone (Tab) and type — existing immediate+periodic refresh should still work as before

## Final Implementation Notes
- **Actual work done:** Added `_schedule_delayed_refresh()` method with dedup timer and wired it into the Enter-in-PANE_LIST handler, replacing the immediate `call_later` call. Three changes total in `monitor_app.py`.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Kept the PREVIEW zone key forwarding using `call_later` (immediate) since the 0.3s periodic `_preview_timer` already covers that zone. Only the PANE_LIST Enter needed the delayed approach.
