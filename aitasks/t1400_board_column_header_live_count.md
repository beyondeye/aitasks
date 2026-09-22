---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
anchor: 1243
followup_kind: risk_mitigation
created_at: 2026-08-03 22:43
updated_at: 2026-08-13 23:07
boardidx: 5120
---

## Origin

Risk-mitigation ("after") follow-up for t1243_5, created at Step 8d after
implementation landed.

## Risk addressed

> Two invariants the recompose used to maintain for free — `ColumnHeader.task_count`
> and the dirty `*` — become explicit obligations of the movement path, and a
> future third one could be missed the same way · severity: medium

`addresses`: code-health — recompose-maintained invariants become explicit
caller obligations.

## Goal

Make `ColumnHeader` derive its task count from the manager at render time
instead of baking it in at construction, so no movement path has to remember to
call `_sync_header_count`.

Today (`.aitask-scripts/board/aitask_board.py`):

- `ColumnHeader.__init__` stores `task_count`, and `compose` renders
  `f"{self.col_title} ({self.task_count})"`. The value is frozen at construction.
- `KanbanColumn.compose` computes it via
  `len(self.manager.get_column_tasks(self.col_id))`.
- Before t1243_5 every move recomposed the column, so the header was rebuilt for
  free. t1243_5's transplant does not, so it added `KanbanApp._sync_header_count`,
  called explicitly from the lateral path (and deliberately not from the to-edge
  path, where the count cannot change).

That is a remembered step, and the next in-place path that changes a column's
membership — **t1243_11's group block moves are the obvious candidate** — has to
remember it too or ship a stale header.

## Suggested direction

Have the header read the count from the manager when it renders (a Textual
reactive, or simply computing it in `compose` from `col_id` + manager) so the
only thing a caller must do is trigger a repaint. Then `_sync_header_count`
either disappears or shrinks to that repaint.

**Verify at render level, not on the attribute** —
`tests/test_board_dom_transplant.py::LateralTransplantTests::test_both_column_headers_repaint_their_counts`
already asserts the rendered header text and pairs it with an untouched-column
control; keep that contract and make it pass without the explicit sync call.

Do not regress: a same-column move must still not disturb the count, and an
untouched column's header must not be rewritten.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:22Z.9754d6434c7c13d5f540ebed from=t1794_9 from_verified=yes at=2026-09-22T06:09:22Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1400_board_column_header_live_count.md) cites symbols you name -> current module: ColumnHeader -> board_widgets.py, KanbanApp -> aitask_board.py.
