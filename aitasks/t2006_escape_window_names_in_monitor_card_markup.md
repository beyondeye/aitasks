---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitormini, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1326
followup_kind: upstream_defect
created_at: 2026-10-15 15:29
updated_at: 2026-10-15 15:41
---

## Origin

Spawned from t1351 during Step 8b review.

## Upstream defect

- .aitask-scripts/monitor/monitor_app.py:1763 — `ait monitor` card rows interpolate the raw tmux window name into Rich markup (also :1775, :1808, :1859), so a window named e.g. `agent-[/]x` raises MarkupError on render

## Diagnostic context

t1351 (minimonitor row-width audit) added a name matrix that includes markup-looking window names (`agent-[/]x[dim]` × 5). Before its fix, minimonitor's `_agent_card_text` raised `rich.errors.MarkupError: closing tag '[/]' … has nothing to close` for them, because the window name went into the row's markup unescaped. t1351 fixed minimonitor by clip-then-`escape()` of the name, title and command (`_row_name` / `_other_card_text` in `.aitask-scripts/monitor/minimonitor_app.py`, the same pattern `_own_header_text` already used for session names).

A probe against the full monitor during Step 8b reproduced the same defect there: `MonitorApp._format_agent_card_text` with `window_name="agent-[/]x"` produces

    ' [dim]☆[/] [bold magenta]●[/] [dim]≈[/] 1:agent-[/]x (0)  [bold magenta]PROMPT 999s[/]'

and `Text.from_markup` on it raises `MarkupError closing tag '[/]' at position 48 has nothing to close`. Window names are tmux-side user input (any user can rename a window), so this is reachable from an ordinary rename.

Raw interpolation sites in `monitor_app.py` found by grep: :1763, :1775 (frozen / parked rows), :1808 (live row), :1859 (`_format_other_card_text`). Check also any task-title interpolation in the same card builder and the `pane_label` at :2036 if it reaches markup.

## Suggested fix

`from rich.markup import escape` is already imported in `monitor_app.py`; wrap each user-derived field (`window_name`, task title, current command) in `escape()` at the interpolation site — after any truncation, never before, so budgets count rendered cells. Add a test that renders each row shape with a `[/]`-bearing window name and asserts the plain text contains it literally (mirror `AgentRowMatrixTests` in `tests/test_minimonitor_row_budget.py`).
