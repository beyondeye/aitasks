---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_monitormini, tui, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-18 10:34
updated_at: 2026-10-18 16:59
completed_at: 2026-10-18 16:59
---

## Symptom

After restarting `ait ide` from scratch and restoring frozen agents, each restored
window's minimonitor companion ends up ~135 columns wide instead of the configured 40
(observed on aitasks windows `agent-pick-2018`, `-2023`, `-2024` and
`thinking_back:agent-pick-118`: panes 134 | 135 in a 270-col window).

## How the geometry gets there (trigger, not the bug)

- `ait ide` runs `offer_frozen_agents` BEFORE `tmux attach`, so the restored
  windows are created in a detached session. With tmux `default-size 80x24` and
  `aggressive-resize on`, each window is 80x24 when
  `maybe_spawn_minimonitor` → `_companion_check_and_split`
  (`.aitask-scripts/lib/agent_launch_utils.py` ~2524) runs
  `split-window -h -l 40`, which gives 39 | 40.
- A window is resized only when a client first views it. Growing 80→270, tmux
  spreads the extra columns evenly over both panes: 39+95 = 134, 40+95 = 135.
- Windows never opened yet stay at 80x24 with a 39 | 40 split, and they jump to
  134 | 135 when first viewed. Ordinary agent launches are split while the
  window already has its full size, so they look right at spawn.

## Root cause: the t978 width pin never fires

The minimonitor is supposed to undo exactly this drift.
`MiniMonitorApp.on_resize` → `_maybe_pin_width`
(`.aitask-scripts/monitor/minimonitor_app.py` ~1483 / ~1536-1555) resizes its own
pane back to `target_width` whenever it is wider than the target. It reads
**`self.size.width`**, and under Textual 8.2.7 (the pinned
`textual>=8.2.7,<9`) `App.size` inside `on_resize` is still the PREVIOUS size.
The new size is only on `event.size`.

Reproduced in an isolated tmux server (`tmux -L <probe> -f /dev/null`) with an
instrumented minimonitor (wrapping `on_resize` / `_maybe_pin_width`):

- grow 270→300 with the companion at 40: logged `event.size=55 self.size=40`.
  The early return `self.size.width <= self._target_width` fires, there is no
  `resize-pane`, and the companion stays at 55.
- shrink 270→200: the companion went to **5** cols and the pin logged `size=40`.
- A manual `resize-pane -t <companion> -x 40` works, so the tmux side is fine.

So the pin is broken for **every** minimonitor: frozen restores, any companion
split into a never-viewed window, and plain terminal resizes. No test exercises
`_maybe_pin_width` (`grep pin_width tests/` finds nothing), which is how this
went unnoticed.

## Fix scope

1. Feed the pin the new size: pass `event.size.width` from `on_resize` into
   `_maybe_pin_width` (or have it read the pane's real width), not `self.size`.
   Keep the existing self-termination argument (the follow-up Resize lands at
   the target and returns early) and the gateway call
   (`self._monitor.resize_pane`, subprocess path, per the monitor_core.py
   ~2370 docstring).
2. Decide, and state in the plan, whether the pin should also restore the target
   width after a window **shrink** that left the companion narrower than the
   target (the 5-col case above) when the window is wide enough. The current
   docstring only clamps when wider than the target. Respect manual pane drags:
   a Resize caused only by the user dragging the border should not snap back
   if that is the current intended behaviour. Check t978's plan
   (`aiplans/archived/`) for the original intent.
3. Regression tests:
   - a unit/pilot test where `on_resize` receives an event whose size differs
     from a stale `self.size`, asserting `resize_pane` is called with the target;
   - a live tmux test (isolated socket, like the `*_live.py` tests, mind the
     serial carve-out rules in CLAUDE.md) that splits a companion with
     `-l 40` into an 80-col window, grows the window to ~270, and asserts the
     companion is back at 40. Add a pre-fix control showing it stays at ~135.
4. Optional, decide in planning: if the pin is reliable, the restore-before-attach
   path in `ait ide` needs no change. Note this explicitly rather than adding a
   second mechanism (e.g. a tmux `window-resized` hook).

## Related, not folded

- t1481 (validate `tmux.minimonitor.width`) touches the same `target_width`
  value but is a config-validation fix.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-18T09:32:41Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-18T13:56:54Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-18T13:59:05Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:da83f95ba2c902de

> **✅ gate:risk_evaluated** run=2026-10-18T13:59:05Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2050/risk_evaluated_2026-10-18T13:59:05Z-risk_evaluated-a1.log`
