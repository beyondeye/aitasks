---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_board, tui]
gates: [risk_evaluated]
anchor: 1210
followup_kind: risk_mitigation
created_at: 2026-07-26 11:46
updated_at: 2026-08-13 23:06
boardidx: 39936
---

## Origin

Risk-mitigation ("after") follow-up for t1247, created at Step 8d after
implementation landed.

## Risk addressed

**Goal-achievement — selector still clips below ~90 cols.** From t1247's plan
`## Risk` section, verbatim:

> Terminals narrower than the selector itself still clip (documented limit
> above); a user on a very narrow terminal may consider the bug unfixed ·
> severity: low · → mitigation: board_selector_wrap_2d_hittest

t1247 made `#view_col` auto-width so the filter row is never truncated by a new
base filter or a key rebind, and added an `on_resize` reflow that drops the
search box onto its own line below ~120 columns. What it did **not** fix: when
the terminal is narrower than the rendered selector itself (~90 cells), the
selector line still clips, because it is a single-line `Static`.

## Goal

Make `ViewSelector` hit-testing two-dimensional so the filter row can **wrap**
onto multiple lines instead of clipping on very narrow terminals.

Why this is not a one-line CSS change: `ViewSelector._click_targets` is a list of
1-D `(start_col, end_col, target_id)` tuples, and `ViewSelector.on_click`
(`.aitask-scripts/board/aitask_board.py`) reads only `event.x` — it ignores
`event.y` entirely. If the line were simply allowed to wrap, every segment past
the first row would dispatch to the wrong filter. Enabling wrap therefore
requires the hit-testing to change first.

### Scope

1. Extend the click-target model to `(row, start_col, end_col, target_id)` (or
   equivalent), produced by the same single `ViewSelector._build()` pass that
   t1247 introduced — keep one arithmetic site for layout and hit-testing.
   `_build()` currently returns `(markup, targets, width)`; it will need to know
   the available width to decide wrap points.
2. Honour `event.y` in `on_click`, accounting for `#view_selector`'s
   `padding: 0 1` on the x axis as today.
3. Let `#view_selector` wrap (drop `height: 1`) and have
   `KanbanApp._apply_filter_reflow` account for the wrapped height.
4. Decide the wrap policy: wrap only when the terminal cannot fit one line
   (preserving today's single-line look at normal widths), rather than wrapping
   opportunistically.

### Constraints

- Do **not** reintroduce a hardcoded column count. `content_width()` and the
  reflow threshold must keep deriving from the rendered labels — that is the
  invariant t1247 established and `tests/test_board_filter_row_layout.py`
  guards.
- Keyboard bindings (`a`/`l`/`f`/`i`/`y`/`z`, `g`, `t`) already work at any
  width; this task is about click targeting and visibility only.

## Verification

- Extend `tests/test_board_filter_row_layout.py` (or add a sibling file):
  - Boot `KanbanApp` at a width below the selector's `content_width()` and
    assert no segment is clipped — every click target lies within the drawn
    region on its own row.
  - Assert click dispatch lands on the correct base filter for a segment on the
    **second** row, which is precisely the case 1-D hit-testing gets wrong. Pin
    it with a negative control that would pass under the 1-D model.
  - Assert the single-line layout is unchanged at normal widths (no regression
    to `test_filter_row_not_truncated` or the reflow threshold tests).
- Run isolated and in the full suite — `t1179` records that
  `tests/run_all_python_tests.sh` is order-dependent.
- Manual: `ait board` in a ~70-column terminal; confirm the filter row wraps
  legibly and each segment clicks correctly on both rows.
