---
Task: t477_better_control_for_paused_claude.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Fix Monitor TUI Focus and Interaction Model (t477)

## Context

The `ait monitor` TUI had critical UX problems making it unusable:
1. Focus disappeared every ~3 seconds because widget rebuilds destroyed focused cards
2. Tab cycled through every individual card instead of between the 3 main sections
3. No way to directly interact with previewed tmux sessions -- limited to confirm/later commands

## Solution: Zone-Based Navigation Model

Introduced 3 zones (attention, pane list, preview) with:
- **Tab/Shift+Tab** cycles between zones
- **Up/Down** navigates within a zone's cards
- **Preview zone** forwards ALL keystrokes (except Tab) directly to the tmux session
- **Fast preview refresh** (300ms timer) when preview zone is active for near-real-time display
- **Focus preservation** via `call_after_refresh` to restore focus after DOM rebuilds
- **Preview size cycling** (`z` key) through S/M/L sizes

## Files Modified

- `.aitask-scripts/monitor/tmux_monitor.py` -- Added `send_keys()` method for arbitrary key forwarding
- `.aitask-scripts/monitor/monitor_app.py` -- Major refactor of focus/navigation/interaction model

## Key Implementation Details

1. `Zone` enum + `ZONE_ORDER` for cycling
2. `PreviewPane(Static, can_focus=True)` replaces non-focusable Static
3. `_TEXTUAL_TO_TMUX` dict maps Textual key names to tmux send-keys arguments
4. `on_key` handler intercepts Tab/Shift+Tab globally, forwards all other keys in preview zone
5. `_restore_focus` deferred via `call_after_refresh` + zone-aware search order
6. `_fast_preview_refresh` separate lightweight timer (only captures focused pane)
7. `_manage_preview_timer` starts/stops fast timer on zone transitions
8. Removed `action_confirm` and `action_decide_later` -- replaced by direct interaction
9. `PREVIEW_SIZES` presets with `z` key to cycle

## Final Implementation Notes

- **Actual work done:** Implemented the full zone-based navigation model as planned. Added preview size cycling feature (not in original plan) per user request during review.
- **Deviations from plan:** Focus restoration required two fixes beyond the plan: (1) `call_after_refresh` instead of immediate call to handle Textual DOM timing, (2) zone-aware search order in `_restore_focus` to prevent cross-zone focus jumps when the same pane_id exists in both attention and pane-list sections.
- **Issues encountered:** Initial `_restore_focus` implementation ran before Textual processed DOM mutations, causing focus to be lost. Also, searching all cards without zone awareness caused focus to jump from pane-list to attention-section for idle agents.
- **Key decisions:** Preview zone forwards ALL keys except Tab (including q/j/s/r), requiring user to Tab out before using app commands. This maximizes interactivity with the previewed session.
