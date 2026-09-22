---
priority: medium
effort: medium
depends: [t1377_3]
issue_type: enhancement
status: Ready
labels: [ait_settings, board_columns, tui]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-08-04 09:57
updated_at: 2026-08-04 09:57
boardidx: 9216
---

## Context

**Risk-mitigation follow-up for t1377** (timing: `after`, confirmed at t1377
planning). Addresses the goal-achievement risk that `ait settings` advertises a
stance the framework no longer holds.

The Settings TUI renders board columns read-only, labelled literally
"read-only — edit via board TUI" (`.aitask-scripts/settings/settings_app.py`,
Columns section). That label was **forced by capability**: column creation existed
only inside the board TUI, with no headless writer for
`aitasks/metadata/board_config.json`.

`t1377_3` removes that constraint by landing
`lib/board_columns.create_column(root, title, color)` — a Textual-free, root-scoped
writer that respects the project/user layer split. Once it exists, the settings
label is a stale claim rather than a real limitation: board, minimonitor and
settings would disagree about who may edit columns.

t1377_3 deliberately left the settings TUI unchanged (it was scoped to minimonitor)
and recorded the decision instead of widening. This task is where that decision is
revisited.

## Scope

Flip the Settings TUI's Columns section from read-only to editable on top of the
headless seam:

- add / edit (title, colour) / delete / reorder, reusing
  `lib/board_columns.py` (`create_column`, `generate_col_id`, `PALETTE_COLORS`) —
  **do not** re-implement slug generation or the palette;
- keep the board's own column UI as-is; both surfaces call the same seam;
- update the section label and any surrounding help text.

## Constraints

- **Layer discipline.** `columns` / `column_order` are **project-level** (tracked);
  `settings` is **user-level** (`board_config.local.json`, gitignored). Write only
  the project layer for column edits, exactly as `create_column` does. Writing a
  merged dict back to the project file leaks user settings into a tracked file.
- **No auto-commit from a TUI event handler.** Per
  `aidocs/framework/tui_conventions.md`, a runtime TUI may write project-level
  config but must never `git commit` / `./ait git push` from an event handler.
- **Single-source the key sets.** `_PROJECT_KEYS` / `_USER_KEYS` were triplicated
  across `aitask_board.py`, `settings_app.py` and `stats_config.py`; t1377_3
  consolidates them into `lib/board_columns.py`. Import, do not redefine.
- If, on inspection, the read-only stance turns out to be **deliberate product
  design** rather than a capability limit, the correct outcome is to keep it and
  update the label to say so — record that as the finding rather than forcing the
  change.

## Verification

- Column add / edit / delete / reorder from `ait settings` are reflected in
  `ait board` on next refresh.
- A round-trip test asserting `board_config.local.json` is untouched by a column
  edit and that no `settings` key appears in the project file.
- `bash tests/run_all_python_tests.sh` (read only the last line for the verdict).

## Dependency

Depends on **t1377_3**, which lands the headless writer this task builds on.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:33Z.47d40c05b2c23fd34a7d5748 from=t1794_9 from_verified=yes at=2026-09-22T06:09:33Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
