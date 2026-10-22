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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2128** id=2026-10-22T21:19:11Z.f6edc91cd2264bb371411a09 from=t2128 from_verified=yes at=2026-10-22T21:19:11Z base=12ca117857305a6f6149e71c5f9d94b54b7525e9 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2128 (minimonitor phase glyph + colour), as of commit 12ca11785 — line references are tree-relative to that commit:
> | 
> | - .aitask-scripts/monitor/minimonitor_app.py now has a second configured-width budget consumer besides `_row_budget` / `_detail_budget`: `_own_phase_budget(target_width) = max(0, target_width - _ROW_PADDING - _DETAIL_INDENT)` for the docked own-agent card's phase row (no scrollbar term — the panel is overflow-y hidden). It feeds `_own_phase_text` -> `format_phase_markup`; the budget block comment at the top of the module documents it.
> | - The list-row phase now leads with a 2-cell glyph that is counted against `_detail_budget` before the shed ladder runs; the worst realistic row `◌ unknown (rec off) · 0/4 1p 1f 1s` is exactly 34 cells at width 40, so there is no slack left at the default width.
> | - If this task re-bases budgets on the actual pane width or validates/clamps the configured width, `_own_phase_budget` is presumably in scope too. The composited regression for it is OwnPanelSizingTests.test_the_longest_phase_stays_on_one_row_at_every_width in tests/test_minimonitor_top_chrome_render.py.
