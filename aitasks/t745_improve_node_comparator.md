---
priority: high
effort: high
depends: []
issue_type: enhancement
status: Ready
labels: [ait_brainstorm]
children_to_implement: [t745_5]
created_at: 2026-05-04 18:51
updated_at: 2026-05-05 08:52
boardidx: 80
boardcol: manual_verifications
---

in ait brainstorm in the compare tab we can compare proposals from two nodes. we want to improve how compare work. there are several issues: once a comparison is generated apparently it remains there: if there are shortcut to generate a new one and override current, they are not shown. there is a general issue with shortcuts in ait brainstorm: shortcuts for switching between tab should not be shown in footer: in the footer we should show the currently context-aware shortcuts active. also about the comparison itself: we have the list of dimensions and the corresponding value for the two nodes being compared: we print the full value even if the value matches between the two nodes (see brainstorm-635, for the two currently existing nodes). also when two dimensions are actually different we should show WHAT is actually different using some diff engine (like the existing diff tui). also we currently cannot open actual diff view of the two compared nodes proposal: no diff tui integration yet. this is the time to add the integration. this is a complex task that need to be split in child tasks

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:35Z.a2c3596b7dad283a475ddaa6 from=t1794_9 from_verified=yes at=2026-09-22T06:10:35Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your plan aiplans/p745_improve_node_comparator.md cites stale anchors: aitask_board.py:3333 - re-verify it against the current modules before implementing.
