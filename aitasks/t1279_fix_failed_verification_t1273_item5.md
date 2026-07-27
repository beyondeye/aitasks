---
priority: medium
effort: medium
depends: [1268]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1210
created_at: 2026-07-28 01:18
updated_at: 2026-07-28 01:18
---

## Failed verification item from t1268

> Press `R` twice in quick succession — the second press is a no-op, and `R Agent Refresh` disappears from the footer while the launch is pending

### Source

- **Manual-verification task:** `aitasks/t1273_manual_verification_bytrail_refresh_semantics_followup.md` (item #5)
- **Origin feature task:** t1268
- **Origin archived plan:** `aiplans/archived/p1268_bytrail_refresh_semantics_and_key_footer_contract.md`

### Commits that introduced the failing behavior

- ceb07381d bug: Fix By-Trail refresh semantics and key/footer contract (t1268)

### Files touched by those commits

- .aitask-scripts/board/aitask_board.py
- tests/test_board_bytrail_view.py

### Observed failure

The **footer half passes**: while a confirmed launch is pending
(`_trail_launch_pending` True during the off-thread baseline read),
`trail_refresh_agent` drops out of `screen.active_bindings` and `R Agent
Refresh` disappears from the footer, returning once the launch completes and
the watch is installed.

The **"second press is a no-op" half fails**. Pressing `R` opens
`AgentCommandScreen`, and that screen binds the same key to Run:

    agent_command_screen.py:339-340
        Binding("r", "run", "Run", show=False),
        Binding("R", "run", "Run", show=False),

So the second `R` never reaches the board's guard in
`action_trail_refresh_agent` (`aitask_board.py:5990`) — it is consumed by the
modal and **confirms the dialog**, launching the agent on the currently
selected tab (Tmux by default).

### Reproduction

1. Live tmux board, By-Trail with an active trail: `R`, `R`. The dialog closed
   and `claude --model claude-opus-5 /aitask-trail --refresh art:<handle>`
   started in a new tmux window `agent-trail-<suffix>` — a real agent, launched
   without the user ever reviewing the dialog.
2. Headless on the real `KanbanApp` with `launch_in_tmux` stubbed: after the
   second `R`, `screen` is back to the board and `launch_in_tmux` has been
   called exactly once.

### Impact

No double-spawn (one agent, not two), so the `_trail_launch_pending` guard is
not defeated — but an accidental double-tap of `R` silently launches a
heavyweight model-authored refresh with no confirmation step. The dialog's
purpose is to be reviewed before running.

### Possible directions

- Do not bind the launching key itself to Run inside `AgentCommandScreen`
  (require Enter / an explicit Run button), or
- ignore a repeat of the key that opened the dialog for a short debounce window
  after mount, or
- restate the checklist expectation if the current behaviour is intended — but
  then the t1268 "second press is a no-op" claim needs correcting.

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1273 item #5.
