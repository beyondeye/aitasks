---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-07-21 19:16
updated_at: 2026-07-22 10:52
---

In `ait board`, a column with no task cards cannot be focused. Because the
column-reordering shortcuts (`ctrl+left` / `ctrl+right`) resolve their target
column from the focused card, an empty column can never be moved.

## Symptom

1. Create/keep a board column with zero tasks in it.
2. Try to reach it with left/right arrow navigation — focus jumps straight over
   it to the next non-empty column.
3. `ctrl+left` / `ctrl+right` therefore cannot reorder that column at all.

## Root cause

All in `.aitask-scripts/board/aitask_board.py`:

- `refresh_board` (~4879-4886) mounts **every** configured column regardless of
  task count, so the empty column *is* on screen — it just has no focusable
  descendant.
- `KanbanColumn.compose` (~1663-1677) yields a `ColumnHeader` (a plain `Static`,
  `can_focus` defaults to False) plus one `TaskCard` per task. When collapsed it
  yields a `CollapsedColumnPlaceholder` (~1074-1087) which **is** focusable — so
  the collapsed-empty case works while the expanded-empty case does not.
- `_nav_lateral` (~5401-5429) walks columns and only stops on one that has a
  collapsed placeholder or at least one card; otherwise it advances
  (`new_idx += direction`), deliberately skipping empty expanded columns.
- `_shift_column` (~6217-6234), backing `action_move_col_right` /
  `action_move_col_left`, starts with `focused = self._focused_card()` and
  returns early when there is none — it ignores the already-generalized
  `_get_focused_col_id()` helper (~5391-5399) that resolves a column id from a
  card *or* a collapsed placeholder.
- `action_toggle_column_collapsed` (~6315-6328) has the same shape but already
  falls back to `_focused_collapsed_placeholder()`; it still fails for an
  empty **expanded** column for the same "nothing focusable" reason.
- `refresh_board` only accepts `refocus_filename`, so after moving an empty
  column there is no way to restore focus to it — a column-identity refocus
  path is needed.

## Suggested direction (to be confirmed at planning time)

- Add a focusable placeholder for empty *expanded* columns, mirroring
  `CollapsedColumnPlaceholder` (e.g. an `EmptyColumnPlaceholder` carrying
  `column_id`), and make `_get_focused_col_id()` / `_focused_card()`-dependent
  navigation aware of it.
- Stop `_nav_lateral` from skipping a column that now has a focusable
  placeholder; keep vertical nav a no-op on it (as it already is for the
  collapsed placeholder).
- Rewrite `_shift_column` (and the `toggle_column_collapsed` path) to resolve
  the column via `_get_focused_col_id()` instead of `_focused_card()`.
- Extend `refresh_board` with a column-identity refocus (e.g.
  `refocus_col_id`) so the moved empty column keeps focus after the swap.
- Re-check `check_action` (~4758) footer-visibility rules so `move_col_*` /
  `toggle_column_collapsed` stay shown when only a placeholder is focused.

## Acceptance criteria

- An empty, expanded board column can be reached with left/right arrow
  navigation and shows a visible focus indication.
- `ctrl+left` / `ctrl+right` reorder an empty column, the new order persists to
  board metadata, and focus stays on that column after the refresh.
- `Shift+X` (toggle collapse) works on an empty expanded column.
- Existing behaviour for non-empty and collapsed columns is unchanged
  (including the vertical-nav no-op on placeholders).
- Regression tests added under `tests/` following the existing Textual-pilot
  board test style (`tests/test_board_footer_visibility.py`,
  `tests/test_board_detail_arrow_nav.py`), covering: focusing an empty column,
  moving it in both directions, and the boundary cases (leftmost/rightmost).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-22T07:52:17Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-22T08:17:53Z status=pass attempt=1 type=human
