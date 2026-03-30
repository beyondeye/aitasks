---
Task: t490_switching_pane_lose_focus_to_specific_agent.md
Worktree: (current directory)
Branch: main
Base branch: main
---

## Context

In the `ait monitor` TUI, pressing Tab cycles between the agent list pane and the preview pane. When switching back to the agent list, focus always resets to the first agent instead of restoring the previously selected agent. This is a UX bug — the user's selection should be preserved across zone switches.

## Root Cause

`_focus_first_in_zone()` at line 699 of `monitor_app.py` unconditionally calls `cards[0].focus()` when the active zone is `PANE_LIST`. The `_focused_pane_id` instance variable already tracks the selected agent correctly, but it's not consulted during zone switching.

## Plan

- [x] **Change `_focus_first_in_zone()`** in `.aitask-scripts/monitor/monitor_app.py` (lines 699-709): When switching to `Zone.PANE_LIST`, find the card matching `self._focused_pane_id` and focus it. Fall back to first card only if no previous selection exists or the card was removed.

## Verification

1. Run `ait monitor` in a tmux session with multiple agent windows
2. Select an agent other than the first one (arrow keys)
3. Press Tab to switch to preview pane
4. Press Tab again to return to agent list
5. Verify the previously selected agent is still focused (not the first one)

## Final Implementation Notes
- **Actual work done:** Modified `_focus_first_in_zone()` to look up the card matching `_focused_pane_id` before falling back to the first card. Exactly as planned.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Reused existing `_focused_pane_id` state variable rather than introducing new tracking — it was already correctly maintained by `on_descendant_focus()`.
