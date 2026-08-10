---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini, tui]
gates: [risk_evaluated]
anchor: 1479
followup_kind: upstream_defect
created_at: 2026-08-10 23:30
updated_at: 2026-08-10 23:30
---

## Origin

Spawned from t1479 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_launch_utils.py:1587-1588 — tmux.minimonitor.width is
  read with int() and no minimum/sanity validation, so a configured width of 10 (or 1)
  is accepted and every row of the pane is built against a geometry no content can fit`
  — the same unvalidated value is re-read at
  `.aitask-scripts/monitor/minimonitor_app.py:2599`
  (`target_width = int(mm_cfg["width"]) if ... else 40`).

Both read sites accept any integer: a negative or absurdly small value is passed
straight through to the pane geometry (`resize_pane(own_pane, x=target_width)`) and to
every row budget derived from it. `int()` on a non-numeric value raises, so a typo in
`project_config.yaml` can also take the spawner down rather than degrade to the default.

## Diagnostic context

t1479 merged minimonitor's gate-summary and workflow-phase rows onto one line and
introduced `_row_budget()` / `_detail_budget()` as the single site for the pane's
column arithmetic (`target_width − padding [− indent]`). The first draft clamped the
detail budget to a minimum of 8 cells; review caught that this **overstates** capacity
at small configured widths (at width 10 the real indented capacity is 6, so an 8-cell
`2/2 pass` row would be accepted and would wrap). That was fixed in t1479 by returning
real geometry clamped at 0 — the detail row now sheds and clips correctly at any width.

What t1479 deliberately did **not** touch is the config seam. A detail-row budget is
the wrong place to reject an absurd configured width: the same value governs row 1
(mark × shadow × compare-mode × status × name — see t1351) and the title row, and the
spawner uses it for the tmux pane size before the app ever starts.

## Suggested fix

Validate once, where the value is read: clamp or reject a `tmux.minimonitor.width`
below a stated minimum (the card's own arithmetic suggests ~20 cells as the floor at
which a row can still say anything), fall back to the default of 40 on a
non-integer/absent value instead of raising, and warn the user. Apply it at both read
sites through one shared helper so the spawner and the app cannot disagree about the
pane width. Cover with a test at the config seam, and re-use t1479's
`tests/test_minimonitor_gate_phase_row.py::MergedRowLadderTests` narrow-width cases as
the downstream evidence that the row budgets behave once the width is sane.
