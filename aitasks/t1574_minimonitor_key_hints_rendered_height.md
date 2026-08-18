---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [minimonitor, tui, layout]
gates: [risk_evaluated]
anchor: 1566
followup_kind: upstream_defect
created_at: 2026-08-18 16:52
updated_at: 2026-08-18 16:52
---

## Origin

Spawned from t1566 during Step 8b review. Pre-existing; not caused by t1566 and
not fixable by its caps.

## Upstream defect

- `.aitask-scripts/monitor/minimonitor_app.py:489 — _KEY_HINTS_ROWS is a newline
  count, not a rendered height, so below ~24 columns _refresh_short_mode
  under-measures the docked hints (22 rendered rows at width 18 against a
  believed 10) and the pane-list floor breaks there;
  tests/test_minimonitor_top_chrome_render.py:456 only pins the equality at 40
  columns`

## Diagnostic context

t1566 made the minimonitor's own-agent panel width-independent and proved the
pane-list floor holds at 40 columns down to pane height 14. Sweeping the same
fixture across narrower panes showed the floor still breaking at width 18 — but
**not** because of the own panel, which holds its 7-row cap with no scrollbar at
22, 26, 30 and 40 columns. Measured at width 18: `#mini-key-hints` composites
**22 rows** while `_refresh_short_mode`'s predicate believes `_KEY_HINTS_ROWS`
== 10, so it never engages short mode and the pane list is squeezed to a
1-row-overlapping region.

The constant is derived as `KEY_HINTS_TEXT.count("\n") + 1` — a count of
authored lines, which equals the rendered height only while no hint line wraps.
`test_key_hints_occupy_one_row_per_line` pins that equality, but only at 40
columns, so the divergence at narrow widths is invisible to the suite.

This is the same defect class the constant's own comment warns about ("a line
long enough to wrap invalidates this loudly instead of silently shifting the
threshold") — the guard just does not cover the axis that actually breaks it,
which is pane width rather than hint-text length.

## Suggested fix

Measure the hints' desired height at the current width instead of counting
newlines — e.g. have `_refresh_short_mode` read the widget's own rendered
height, or compute the wrapped line count against `self.size.width`. Beware the
feedback loop the current design deliberately avoids: the predicate must not
consume the hints' *current* height (which short mode itself changes), so a
width-aware **desired** height is the value to derive. Extend
`test_key_hints_occupy_one_row_per_line` into a width sweep, and add the floor
case at widths 18/22 that fails today.
