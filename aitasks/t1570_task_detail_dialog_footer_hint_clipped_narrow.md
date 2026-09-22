---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, aitask_monitormini]
gates: [risk_evaluated]
anchor: 1563
followup_kind: upstream_defect
created_at: 2026-08-18 14:01
updated_at: 2026-08-18 14:01
---

## Origin

Spawned from t1563 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_shared.py:1334 — TaskDetailDialog (the
  read-only i/I surface, pushed from minimonitor_app.py:3741) clips its footer
  to "q/Esc: close  p: switch" at 40 columns. Same root cause as the hint
  defect fixed in t1563 (a 33-column string in a 30-column `height: 1` footer),
  but in the base class, which has no `.narrow` variant and is shared with the
  full monitor — so it was left out of t1563's scope. Verified on a composited
  frame at 40x24 and 40x20; correct at 80x24.`

## Diagnostic context

t1563 fixed a same-edge dock overlap in `TaskPickConfirmDialog` and, while
building a render-level guard for the resulting footer, found that
`_task_info` in `tests/test_minimonitor_pick_by_number.py` hard-coded
`plan_content=None` — so **no** test had ever rendered the long footer form.
With plan content the confirm dialog's hint
(`q/Esc: cancel  p: switch plan/task`, 34 cols) clipped to `p: switch` in the
30-column narrow footer at every narrow size. t1563 fixed that by shortening
the narrow-only wording to `p: plan/task` (27 of 30 cols).

The base `TaskDetailDialog` carries the same pattern with
`q/Esc: close  p: switch plan/task` (33 cols) and was measured to clip
identically — but it has no `_narrow` flag to branch on, and it serves both
`ait monitor` (wide, correct today) and `ait minimonitor` (narrow, clipped).
Fixing it needs a decision t1563 did not own.

Measured (`app.run_test`, composited frame):

```
(40, 24)  footer row: '  q/Esc: close  p: switch         '   complete hint: False
(40, 20)  footer row: '  q/Esc: close  p: switch         '   complete hint: False
(80, 24)  footer row: '  q/Esc: close  p: switch plan/task'   complete hint: True
```

## Suggested fix

Give `TaskDetailDialog` a width-aware footer rather than a `_narrow`
constructor flag — the base has no such flag and both call sites would have to
learn to pass one. Either shorten unconditionally to `p: plan/task` (fits both
variants, matches what t1563 shipped for the confirm dialog), or set a
`.narrow` class from `on_resize` the way `aitask_board.py`'s
`_apply_filter_reflow` does and branch in CSS/compose.

Guard it the way t1563 did: assert the hint on the strip at `footer.y`, with an
`assertNotIn("p: switch", row)` half — the truncated form is a prefix of the
correct one, so a test asserting only the close hint passes on the broken row.
`tests/test_minimonitor_pick_by_number.py`'s `BottomDockGeometryTests`
(`test_narrow_footer_hint_is_complete_with_plan_content`) is the model.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:59Z.1c94f521acc067cb97ba4ad4 from=t1794_9 from_verified=yes at=2026-09-22T06:09:59Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
