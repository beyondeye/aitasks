---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Ready
labels: [aitask_board, tui, python, script-performance]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-08-04 09:44
updated_at: 2026-08-04 09:44
---

## Context

`KanbanApp._column_widgets()` (`.aitask-scripts/board/aitask_board.py:7138-7147`)
issues **four separate full-DOM class queries per call**:

```python
return (list(self.query(KanbanColumn))
        + list(self.query(InFlightColumn))
        + list(self.query(TopicColumn))
        + list(self.query(TrailColumn)))
```

Textual 8.2.7's `query()` walks the entire tree wherever it is rooted, so this
costs **~25 ms on a 200-card board** — measured in t1243_4, against ~7 ms for a
single `query(TaskCard)` and ~13 ms for the whole unscoped filter pass. In the
normal kanban view **three of the four return empty** (`InFlightColumn`,
`TopicColumn`, `TrailColumn` only exist in derived views), so most of that cost
is structurally wasted.

Reported by **t1243_4**, restated by **t1243_5**, and named as a suspect by
**t1395** — which then **disproved that suspicion**.

## What t1395 established (read this before assuming anything)

t1395 measured `_column_widgets()` at **0 calls on both move axes** (lateral and
vertical, 200 cards, 5 runs). It is **not** on the board's move path. The claim
that it is "reached from the post-move refocus path via `_card_fully_visible` /
`_viewport_anchor`" — carried by t1243_4, t1243_5, t1399 and t1395's own task
file — is **false against current code**.

Verified reachability (exhaustive call-site trace, then confirmed by counter):

| entry point | path |
|---|---|
| `action_nav_up` (`:7287`) / `action_nav_down` (`:7304`) | → `_reanchor_to_viewport` (`:7214`) → `_card_fully_visible` (`:7224`) / `_viewport_anchor` (`:7226`) → `_column_widget` (`:7157`) → `_column_widgets` |
| `action_nav_left` / `action_nav_right` → `_nav_lateral` (`:7343`) | → `_card_fully_visible` / `_viewport_anchor` (`:7359-7360`) → same, **plus** `_get_visible_col_ids` (`:7270`) → `_column_widgets` directly (`:7348`) |
| `action_focus_board` (`:7118`) | → `_get_visible_col_ids` → `_column_widgets` |

So this is a **plain-arrow navigation** cost — every cursor movement around the
board — and nothing in the t1243 workstream ever measured that path.
`aiplans/archived/p1395_board_residual_move_layout_cost.md` and the
`### RECORDED RESULT — t1395 …` section of
`aiplans/p1243_board_task_groups_and_fast_reordering.md` hold the evidence.

## Problem

**There is no measurement of the nav path at all.** t1243_1's pre-registered
harness (`tests/test_board_movement.py`) presses only `shift+`/`ctrl+` keys; its
two axes are lateral and vertical *moves*. The only figure that exists for
`_column_widgets()` is t1243_4's ~25 ms micro-measurement of the helper in
isolation — not its share of a nav keypress, and not how many times a single
arrow press calls it.

## Goal

**Measure first, then decide. This task asserts no performance target up front**
— same posture as t1395. If it becomes an optimisation, the target is set from
its own measurement.

1. Extend the harness with a **navigation axis** (plain `up`/`down` and
   `left`/`right` ping-pong) and record: median/p90 keypress latency, the
   harness floor, and `_column_widgets` / `_column_widget` /
   `_get_visible_col_ids` call counts and self time per keypress.
2. Attribute the nav keypress the way t1395 attributed the move keypress, then
   quantify what removing the three always-empty queries would actually buy.
3. Recommend: reducible (with the expected win) or not worth it (with the
   evidence). "No follow-up warranted", stated with numbers, is a success.

## ⚠️ Harness trap — read before touching `_bench_axes`

`_bench_axes(cards)` (`tests/test_board_movement.py`) returns **all** axes, and
`test_bench_baseline` consumes it with `axes=None` for its `full` and
`no_af_git` configurations:

```python
chosen = {k: v for k, v in all_axes.items() if axes is None or k in axes}
```

Adding a third axis to `_bench_axes` would therefore **silently add it to the
pre-registered baseline**, changing what t1243_14 compares against 2173.2 /
1162.4 ms. The nav axis must be **opt-in** — either a separate axis dict or an
explicit `axes=[...]` on every existing caller. Verify by re-running
`test_bench_baseline` and confirming its banner is structurally unchanged (same
configs, same span list, same verdict lines), exactly as t1395 did.

t1395's opt-in attribution tier (`Probe.TREE` / `_install_attribution`,
`test_bench_attribution`) is the pattern to copy — `col_widgets` is **already**
an instrumented span there, so the counter exists; it currently reads 0 because
nothing presses an arrow key.

## Candidate fix (do not pre-commit — measure first)

Collapse the four queries into one. Textual supports a comma-separated selector
union, and all four classes are `VerticalScroll` subclasses, so a single
`self.query(...)` (or one walk filtered by `isinstance`) should replace the four.
The helper's docstring says it exists as the "single source for the column-class
union so `_get_visible_col_ids` and `_column_widget` cannot drift apart when a
new column class is added" — **preserve that property**; a fix that hardcodes a
selector string reintroduces exactly the drift the helper was written to prevent.

## Method constraints (inherited from t1243_1 — non-negotiable)

- Use the existing harness and its per-sample validity invariants. Do not invent
  a second measurement method.
- **Attribution is by ABLATION**; span shares under-attribute and are
  diagnostics only.
- **Within-run ablation only**, never cross-run absolutes. Report the harness
  floor alongside any absolute.
- **Repeat ≥ 5 runs** of the configuration being judged — a single run
  adjudicates nothing on this box (t1395 saw 1079.5-1505.0 ms across 5 runs of
  identical code). Record ambient load before and after each run.
- Run nothing else while a bench is in flight; check for concurrent agents first.
- Any new attribution span must join the active-span stack so non-overlap stays
  *proved*, not assumed.

## Coordination

- **t1395** (archived) produced the reachability proof and the attribution tier
  this task extends. Its
  `test_column_widgets_is_unreachable_from_the_move_path` pins the 0-call
  result on the *move* axes — that test must keep passing; this task adds nav
  coverage, it does not relax that pin.
- **t1402** (`board_focus_query_storm_on_move`) explicitly excludes this defect
  and targets `_focused_card` / the bindings sweep instead. The two touch
  different helpers but the **same harness file**, so avoid running them
  concurrently.
- **t1399** (`board_vertical_move_stale_dirty_marker`) previously carried this
  defect as a secondary bullet on the now-disproved move-path premise; that
  bullet now points here.
- **No dependency on t1243_14.** Unlike t1402, this task changes *navigation*
  cost, not move cost, so it cannot disturb t1243_14's move-axis retrospective —
  provided the harness trap above is respected.
