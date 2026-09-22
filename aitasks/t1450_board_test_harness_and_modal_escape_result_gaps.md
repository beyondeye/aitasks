---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui, testing]
gates: [risk_evaluated]
anchor: 1243
followup_kind: upstream_defect
created_at: 2026-08-07 11:26
updated_at: 2026-08-13 23:07
---

## Origin

Spawned from t1377_5 during Step 8b review. Both defects were hit directly while
building the board column-management dialog; neither is caused by that task.

## Upstream defect

- `tests/lib/board_fixture.py:561-583 (PristineTreeMixin) — restores only
  **/*.md, while snapshot() in the same module treats
  metadata/board_config*.json as part of the tree. Any test class that mutates
  COLUMNS leaks board config into the next test, and the leak is
  self-concealing: with the column already dropped from config, merge_columns
  refuses it as unknown_column and writes nothing, while a "the source column
  was removed" assertion still passes — because the previous test removed it.
  Cost t1377_5 a vacuous pair of assertions. Worked around locally with a
  _PristineConfigMixin in tests/test_board_column_dialog.py rather than editing
  a harness 31 modules share.`
- `.aitask-scripts/board/aitask_board.py:8223-8230 (action_focus_board) — the
  app's priority=True escape binding closes ANY active modal with a bare
  self.screen.dismiss(), discarding the dismiss result. Every modal whose
  dismiss value carries meaning silently loses it when closed with Escape; it
  is benign only because every other board modal happens to treat None as
  "cancelled". The handle_escape hook checked one line above is the escape
  valve and had no implementers until t1377_5. A modal author has no way to
  discover this except by hitting it.`

## Diagnostic context

**Defect 1** surfaced as a single failing test in t1377_5 whose delete-then-merge
ordering left `c1` absent from `board_config.json`. Because `merge_columns`
validates ids before writing, the merge was *refused* rather than failing — so
the two assertions checking that the source column had been removed passed
vacuously, and only the third (destination membership) failed. Running the merge
test alone passed; running it after the delete test failed. The asymmetry between
`PristineTreeMixin` (`*.md` only) and `snapshot()` (`*.md` + `board_config*.json`)
in the same module is the root cause.

**Defect 2** surfaced only in a real terminal. Every unit test passed while the
board behind the dialog kept rendering a merged-away column: the dialog defers
`refresh_board()` to close and signals "something changed" through its dismiss
value, but Escape never reached the modal's own `action_cancel` — the app's
priority binding closed it with `dismiss()` and the flag became `None`. A probe
confirmed `screen.dismiss(True)` fires the callback while `pilot.press("escape")`
does not.

## Suggested fix

1. Make `PristineTreeMixin` restore the same allowlist `snapshot()` uses (add
   `metadata/board_config*.json`), then drop the local `_PristineConfigMixin`
   workaround in `tests/test_board_column_dialog.py`. Re-run the board test
   modules — most do not mutate config, so this should be a no-op for them.
2. Either have `action_focus_board` delegate to the screen's own `action_cancel`
   when one exists (preserving each modal's dismiss contract), or document
   `handle_escape` where modal authors will actually see it — e.g. in
   `aidocs/framework/tui_conventions.md` alongside the footer/binding rules.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1816** id=2026-09-17T10:04:33Z.45be26fc301cadcd09e89b4e from=t1816 from_verified=yes at=2026-09-17T10:04:33Z base=aab0d57067adfae49af46312c376529721b2c6e3 base_branch=main dirty=yes host=omg16
>
> | Context from t1816 (committed 454329428), for coordinating your tui_conventions.md edit:
> | 
> | - aidocs/framework/tui_conventions.md now has a section "Modal dismissal: subclass `GuardedModalScreen`, never bare `ModalScreen`" (placed before "Modals pushed by multiple Apps must carry their own DEFAULT_CSS"). It only covers WHICH screen a dismiss pops: Textual's dismiss() pops whatever is on top, so a stale Escape cascades. Its last paragraph defers "what result a modal returns when closed by Escape or an app-level binding" to t1450. Please put your dismiss-result rule next to it rather than contradicting it.
> | - New helper: .aitask-scripts/lib/guarded_dismiss.py (GuardedDismissMixin / GuardedModalScreen). It makes dismiss() a no-op, with no result callback, unless the screen is app.screen.
> | - Board modals are NOT converted yet; t1830 (guard_dismiss_remaining_tuis) will move aitask_board.py screens onto GuardedModalScreen. Relevant to your fix: under the guard, a bare `self.screen.dismiss()` from the App (action_focus_board) still works, because self.screen is the active screen by definition. But dismissing any screen that is not on top becomes a silent no-op, so do not rely on popping a non-top modal.

> **✉ note:t1794_9** id=2026-09-22T06:09:52Z.48b55281431acc40dca910bf from=t1794_9 from_verified=yes at=2026-09-22T06:09:51Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1450_board_test_harness_and_modal_escape_result_gaps.md) cites stale line anchors: aitask_board.py:8223-8230.
