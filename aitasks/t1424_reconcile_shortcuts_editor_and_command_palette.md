---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [tui, textual, shortcuts]
gates: [risk_evaluated]
anchor: 1418
followup_kind: risk_mitigation
created_at: 2026-08-05 10:52
updated_at: 2026-08-13 23:07
---

## Origin

Risk-mitigation ("after") follow-up for t1418, created at Step 8d after implementation landed.

## Risk addressed

> Discovery-surface overlap between the `?` shortcuts editor and the `ctrl+p` command
> palette: neither surface shows the whole operation set, so a user cannot learn
> everything the board can do from either one.

## Goal

Reconcile the two discovery surfaces so there is a single answer to "what can this
TUI do, and which key does it".

The two are **not** duplicates today — that was checked while planning t1418:

- `ctrl+p` (`KanbanCommandProvider`, `.aitask-scripts/board/aitask_board.py:5782`)
  exposes 9 board commands **plus** Textual's built-ins (theme, screenshot, quit).
  Four of its nine have **no key binding at all** and therefore appear nowhere else:
  Add Column, Edit Column, Delete Column, Expand Column, and Clear Selection.
- `?` (`ShortcutsMixin`, `.aitask-scripts/lib/shortcuts_mixin.py`) lists and
  **rebinds** keys, so by construction it can only reach operations that already
  have one — the five above are invisible to it.

So each surface is missing something the other has, and the footer (even multi-row
after t1418) only ever shows *bound, shown* actions.

Directions to weigh (decide in planning, do not assume):

- Give the palette's binding-less commands real bindings so `?` and the footer can
  see them — simplest, but spends scarce keys on rare operations.
- Let the `?` editor list binding-less palette commands as unbound rows, with the
  option to assign a key. Keeps the palette as the execution surface and makes `?`
  the complete inventory.
- Have the palette read from the keybinding registry so every bound action is also
  palette-searchable, making `ctrl+p` the complete surface and `?` the rebinding one.

Whichever way it goes, state the resulting division of labour in
`aidocs/framework/tui_conventions.md` so the next TUI does not have to re-derive it,
and keep it generic across TUIs rather than board-only — `ShortcutsMixin` is shared.

## Related

- t1418 added the `+N more (<key>)` footer affordance, which points users at the `?`
  editor when the footer runs out of room — that pointer is only as good as the
  editor's coverage, which is what this task fixes.
- t1421 fixes a rebind bug in `_relink_live_bindings` that affects punctuation keys
  (including `?` itself); worth landing before reworking the editor.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:39Z.1ec0b249d6c4ffdffdc1a53a from=t1794_9 from_verified=yes at=2026-09-22T06:09:39Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1424_reconcile_shortcuts_editor_and_command_palette.md) cites stale line anchors: aitask_board.py:5782; symbols you name -> current module: KanbanCommandProvider -> aitask_board.py.
