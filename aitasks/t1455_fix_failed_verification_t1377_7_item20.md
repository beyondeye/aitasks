---
priority: medium
effort: medium
depends: [t1377_6]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1243
followup_kind: verification_failure
created_at: 2026-08-07 13:08
updated_at: 2026-08-13 23:07
---

## Failed verification item from t1377_6

> [t1377_6] Read the updated board and minimonitor doc pages against the shipped behaviour and confirm no statement is stale

### Source

- **Manual-verification task:** `aitasks/t1377/t1377_7_manual_verification_column_features.md` (item #20)
- **Origin feature task:** t1377_6
- **Origin archived plan:** `aiplans/archived/p1377/p1377_6_column_features_documentation.md`

### Commits that introduced the failing behavior

- e8e782300 documentation: Document the board column dialog, merge and minimonitor move (t1377_6)

### Files touched by those commits

- website/content/docs/tuis/board/how-to.md
- website/content/docs/tuis/board/reference.md
- website/content/docs/tuis/minimonitor/how-to.md

### Stale statements found (all in `website/content/docs/tuis/board/how-to.md`)

`minimonitor/how-to.md` was checked line by line against live behaviour and
is **accurate** — lines 135, 140 and 273 all match what ships. The board
page has three wrong statements:

1. **Line 91 — `| Delete column | **e** → focus the column → **Delete** →
   confirm |`.** This path does not work: pressing the dialog's `Delete`
   button always reports `Select a column to delete` and deletes nothing.
   There is no other delete path inside the dialog, so the row documents an
   operation the dialog cannot perform. See **t1454** for the underlying
   defect — this doc row should be corrected in step with that fix (or the
   fix lands first and the row becomes true).

2. **Line 90 — `| Edit column | **e** → focus the column → **Enter** (or
   **Edit**) |`.** The `Enter` path works; the parenthesised `(or **Edit**)`
   button alternative does not (same root cause, `Select a column to edit`).

3. **Line 85 — "reachable … from the command palette
   (**Ctrl+Backslash**)".** The palette opens with **Ctrl+P**; the board's
   own footer reads `^p palette`, and `Ctrl+Backslash` was verified live to
   do nothing.

### Also noticed (pre-existing, not introduced by t1377_6)

- **Line 102** — "Collapse/expand state is saved in `board_config.json`".
  It is saved in **`board_config.local.json`**: `collapsed_columns` lives
  under `settings`, and `settings` is a USER key
  (`board_columns.py:144` / `aitask_board.py` `_USER_KEYS`), so the layered
  save routes it to the gitignored local file. Verified live: collapsing a
  column left `board_config.json` byte-identical and wrote
  `board_config.local.json`. Introduced by `633f73bc13` (2026-04-19), so it
  is out of t1377_6's scope but worth fixing on the same pass.

### Next steps

Correct the statements above. Items 1 and 2 depend on how **t1454** is
resolved — sequence them together.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:56Z.c6311e93c28b6df0e4cd9d76 from=t1794_9 from_verified=yes at=2026-09-22T06:09:56Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
