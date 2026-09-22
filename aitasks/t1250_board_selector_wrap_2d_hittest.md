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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:08:41Z.a0f0005f4c539a5a4928cdba from=t1794_9 from_verified=yes at=2026-09-22T06:08:41Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
>
> | t1794 split the board mono-file `.aitask-scripts/board/aitask_board.py`
> | (children t1794_1..8 landed; the last extraction is commit 387d8cb20). Any
> | `aitask_board.py:NN` anchor in your body or plan is STALE: aitask_board.py is
> | now ~6.8k lines (was ~13.7k) and most classes moved. Re-derive by symbol
> | (grep the class/function name), not by line number.
> | 
> | Where symbols live now (.aitask-scripts/board/):
> | - aitask_board.py: KanbanApp (incl. action_* handlers, _do_archive,
> |   action_work_report, sync), Kanban/InFlight/Topic columns, board-only modals
> |   (delete/archive/rename/commit/settings/cross-repo/gate choice), key map,
> |   command palette provider
> | - board_task_manager.py: TaskManager (paths injected as required kw-only
> |   tasks_dir / metadata_file / gates_registry_file; no module-global reads)
> | - board_task_model.py: Task, MoveResult, MergeResult
> | - board_workflow_phase.py: workflow-phase / in-flight derivation
> | - board_widgets.py: TaskCard, ColumnHeader, PickerItem, badge/marker helpers,
> |   LoadingOverlay
> | - board_detail_screen.py: TaskDetailScreen + its field widgets and pickers
> | - board_column_dialogs.py: ColumnEdit/Select/Manage/MultiSelect screens,
> |   ColorSwatch, column confirm dialogs
> | - board_trail_view.py: pure trail rendering - trail cards/columns, trail
> |   modals (TrailDetailScreen, TrailSelectScreen, summary), TRAIL_CSS
> | - board_trail_screen.py: TrailScreenMixin (all By-Trail actions),
> |   TRAIL_BINDINGS, TrailHost protocol, TRAIL_ACTION_CAPABILITIES
> | - trails_app.py: the new stand-alone `ait trails` TUI, hosting the same mixin
> | 
> | Rules a change to these files must keep (full text: contracts C1-C3 in
> | aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; note that the
> | line ranges in that plan's "Target file map" are PRE-split mono-file anchors,
> | not current ones):
> | 1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
> | 2. No board/*.py other than aitask_board.py reads TASKS_DIR / METADATA_FILE /
> |    etc. at import time - moved code receives paths by parameter.
> | 3. No board/*.py imports aitask_board.
> | All three are test-enforced (tests/test_board_package_contract.py,
> | tests/test_board_fixture_harness.py). Test patch targets follow the symbol:
> | patch board_task_manager.X (etc.), not aitask_board.X, for moved code.
> | 
> | Advisory, not an instruction: tree-relative claims above are as of the base
> | SHA this note records.
> | 
> | Your body (aitasks/t1250_board_selector_wrap_2d_hittest.md) cites symbols you name -> current module: KanbanApp -> aitask_board.py.
