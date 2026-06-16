---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitormini, tui, agent_chooser]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-16 17:22
updated_at: 2026-06-16 17:32
---

## Problem

In the minimonitor companion pane (~40 cols wide), pressing `n` to start the
next sibling task opens the shared **`AgentCommandScreen`** ("Pick Task t<N>")
modal, which overflows the narrow pane. Observed in tmux session
`aitasks_go`, window `agent-pick-5_4`, minimonitor pane (40 cols): the
`Cancel` button is truncated to `Can`, the command preview is clipped to
`claude --model claud…`, and the tmux `(S)ession` / `(W)indow` `Select`
boxes are cut off at the dialog border.

## Root cause

The `n` flow chains two dialogs:

1. `NextSiblingDialog` / `ChooseSiblingModal`
   (`.aitask-scripts/monitor/monitor_shared.py`) — these **already implement a
   `narrow=True` mode** (widen the dialog to `width: 90%; min-width: 30` and
   stack the buttons vertically). The minimonitor passes `narrow=True` to both
   (`minimonitor_app.py:868`, `:893`).
2. `_launch_pick_for_own` (`.aitask-scripts/monitor/minimonitor_app.py:896`)
   then pushes **`AgentCommandScreen`**
   (`.aitask-scripts/lib/agent_command_screen.py:132`), which has **no narrow
   mode**. Its `DEFAULT_CSS` uses `width: 80%` with horizontal rows
   (`#profile_row`, `#agent_row`, the Direct/tmux `TabbedContent`, the tmux
   `.tmux-field-row` rows with `width: 12` labels + `1fr` selects, and the
   side-by-side `.agent-cmd-buttons` / `.agent-cmd-copy-row` button rows). At
   80% of 40 cols (~26 usable columns) every horizontal row overflows.

## Blast radius

`AgentCommandScreen` has 12 call sites (board ×5, codebrowser ×3, monitor full
×2, syncer ×1, minimonitor ×1 — see `minimonitor_app.py:926`). Only the
minimonitor renders it in a ~40-col pane; all other callers run in full-width
TUI windows. A new `narrow: bool = False` constructor parameter therefore
leaves the 11 wide callers untouched, mirroring the existing sibling-dialog
pattern.

## Proposed fix

Mirror the established `narrow` pattern from `NextSiblingDialog`:

1. Add a `narrow: bool = False` parameter to `AgentCommandScreen.__init__`
   (`lib/agent_command_screen.py`); when set, `self.add_class("narrow")` in
   `compose`.
2. Add `.narrow` CSS variants to `DEFAULT_CSS` that:
   - widen the dialog (`#agent_cmd_dialog`) to ~95–100% with a sensible
     `min-width`, so content has room;
   - stack the horizontal button rows vertically and make buttons `width: 1fr`
     (`.agent-cmd-buttons`, `.agent-cmd-copy-row`, `#agent_row`,
     `#profile_row`);
   - reflow the tmux `.tmux-field-row` / new-session / new-window / split rows
     so the `width: 12` labels do not eat half the pane (e.g. stack label above
     the `Select`/`Input`, or shrink the label column).
3. Pass `narrow=True` from `_launch_pick_for_own` in
   `minimonitor_app.py:926` (the only narrow caller).

## Acceptance criteria

- Pressing `n` in the minimonitor opens a "Pick Task" dialog that fits within
  the ~40-col companion pane with no truncated buttons, clipped command text,
  or cut-off `Select` boxes.
- The Direct and tmux tabs, the Session/Window selectors, the command `Input`,
  and the `Run` / `Cancel` buttons are all fully visible and operable at 40
  cols.
- The 11 full-width callers (board, codebrowser, monitor, syncer) render
  unchanged (`narrow` defaults to `False`).
- Add a unit/snapshot test mirroring
  `tests/test_agent_command_dialog_default_session.py` that constructs the
  dialog with `narrow=True` and asserts the narrow CSS class / sizing applies.

## Notes

- Follow `aidocs/framework/tui_conventions.md` for Textual modal conventions.
- Source of truth is the Claude Code implementation; no cross-agent skill port
  is needed (this is TUI Python code, not a skill).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T14:31:47Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-16T14:31:48Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-16T14:36:40Z status=pass attempt=1 type=human
