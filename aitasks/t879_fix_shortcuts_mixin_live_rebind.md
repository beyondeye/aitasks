---
priority: low
effort: medium
depends: []
issue_type: bug
status: Postponed
labels: [custom_shortcuts]
followup_kind: upstream_defect
created_at: 2026-05-31 16:28
updated_at: 2026-08-13 23:07
boardcol: now
boardidx: 50
---

## Origin

Spawned from t876 during Step 8b review.

## Upstream defect

`.aitask-scripts/lib/shortcuts_mixin.py:41` — the mixin's
`self.BINDINGS = register_app_bindings(self._shortcuts_scope, self.BINDINGS)`
reassignment runs in `ShortcutsMixin.__init__` **after** `super().__init__()`,
but Textual 8.2.7 builds the live key-dispatch map (`self._bindings`) from the
**class-level** merged map (`_merged_bindings`, computed in `__init_subclass__`
and copied at `DOMNode.__init__:218`) — which happens *before* the mixin
reassigns `self.BINDINGS`. As a result the reassignment never reaches
`key_to_bindings`, so a user override saved via the `?` editor / Settings tab is
recorded in the registry and shown in the editor but does **not** actually rebind
the live key for any mixin-only scope (e.g. `board`, `board.detail`,
`shared.agent_cmd`).

## Diagnostic context

Verified empirically in Textual 8.2.7 with two minimal cases while implementing
t876:
- `App`/`ModalScreen` + `ShortcutsMixin` with **literal** class `BINDINGS` and an
  override in `userconfig.yaml`: live `_bindings.key_to_bindings` kept the
  **default** key (`a`), not the override (`z`). Appending to `self.BINDINGS` in
  `__init__` was likewise ignored.
- A class-body `BINDINGS = register_app_bindings(scope, [...])` (the pattern used
  by `brainstorm_dag_display.py:450`, and adopted by t876 for the switcher
  overlay): the override **was** baked into the live map (`w`), because
  `_merge_bindings` reads `cls.__dict__["BINDINGS"]` at class-creation time.

So today only class-body-registered scopes (`brainstorm.dag`, `shared.tui_switcher`)
honor overrides at runtime; mixin-only scopes do not.

## Suggested fix

Make `ShortcutsMixin` apply overrides in a way Textual picks up — e.g. rebuild
`self._bindings` from the resolved `BINDINGS` at the end of `__init__` (or in
`on_mount`), or have the mixin write the resolved list to the class `BINDINGS`
before Textual merges. Verify against the real `KanbanApp`/`AgentCommandScreen`
(not just synthetic classes) and add a test that asserts a saved override changes
`key_to_bindings` for a mixin-based scope.

## IMPORTANT — check concurrent work first

While t876 was implemented, a concurrent session had uncommitted edits to
`.aitask-scripts/lib/shortcuts_mixin.py` (+69 lines). That work may already
address this defect — confirm the committed state of `shortcuts_mixin.py` before
starting; this task may be a no-op or need re-scoping.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:33Z.7c26476141792d849a403f95 from=t1794_9 from_verified=yes at=2026-09-22T06:10:33Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t879_fix_shortcuts_mixin_live_rebind.md) cites symbols you name -> current module: KanbanApp -> aitask_board.py.
