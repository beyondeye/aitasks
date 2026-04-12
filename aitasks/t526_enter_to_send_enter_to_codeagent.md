---
priority: medium
effort: low
depends: [524]
issue_type: feature
status: Implementing
labels: [aitask_monitormini]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-12 10:49
updated_at: 2026-04-12 11:01
---

In `ait minimonitor`, add an `Enter` keyboard shortcut that sends an `Enter` keystroke to the **sibling codeagent pane that sits next to the minimonitor in the same tmux window** — i.e. the same target pane that t524's `Tab` binding switches focus to. The Enter is NOT routed to whichever MiniPaneCard happens to be focused in the minimonitor's card list. The card selection in the minimonitor is irrelevant to this action; the target is always the physically adjacent pane.

This is a follow-up to t524 (Tab to switch focus to the sibling codeagent pane). Before implementing, read the archived plan/notes for t524 (`aiplans/archived/p524_*.md`) — in particular the "Final Implementation Notes → Notes for follow-up task" section, which records the gotchas learned while wiring up Tab. Reuse the same "find the non-minimonitor pane in the current tmux window" logic that t524 introduces in `_focus_sibling_pane()` (consider refactoring that helper into a shared `_find_sibling_pane_id()` method so both handlers share it without duplication).

Implementation sketch:
- Add `Binding("enter", "send_enter_to_sibling", ...)` and handle it in `on_key` (same Binding + no-op action + on_key pattern used by Tab in t524, to sidestep Textual's default activation handling).
- When triggered, resolve the sibling pane id via the shared helper, then run `tmux send-keys -t <sibling_pane_id> Enter`.
- The binding must NOT fire when a modal screen is active (e.g. `TaskDetailDialog`) — carry the same modal guard used for Tab. Put the new `enter` branch after the modal-screen check in `on_key`.
- Reference for the keystroke mechanic (but NOT the targeting logic): `monitor_app.py:751-755`, which sends Enter to a focused agent pane. In the minimonitor case the target is fixed (the sibling), not derived from card focus.

Key files:
- `.aitask-scripts/monitor/minimonitor_app.py` — the minimonitor TUI (add new binding + handler, reuse/extract t524's sibling-pane helper)
- `.aitask-scripts/monitor/monitor_app.py:751-755` — reference for the send-keys mechanic only

Update the custom multi-line footer introduced in t524 to include an `enter:send` (or similar) hint — there is room for one more entry at the end of the second line.
