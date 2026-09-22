---
priority: medium
effort: high
depends: []
issue_type: bug
status: Ready
labels: [tui, textual, modal_dismiss]
gates: [risk_evaluated]
anchor: 1816
followup_kind: risk_mitigation
created_at: 2026-09-17 12:57
updated_at: 2026-09-17 12:57
---

## Origin

Risk-mitigation ("after") follow-up for t1816, created at Step 8d after implementation landed.

## Risk addressed

code-health: the other TUIs' ~314 dismiss sites stay unguarded.

- The ~314 sites in other TUIs remain unguarded after this task, so the convention is enforced only in brainstorm · severity: low · → mitigation: guard_dismiss_remaining_tuis

## Goal

Convert board/monitor/settings/syncer/chatlink/other TUI screens to `lib/guarded_dismiss.GuardedModalScreen` and extend the AST enforcement test to their directories.

t1816 introduced `.aitask-scripts/lib/guarded_dismiss.py` (`GuardedDismissMixin`, `GuardedModalScreen`). Textual 8.2.7's `Screen.dismiss` calls `app.pop_screen()`, which pops whatever screen is on top. A stale key still dispatched to a closed modal therefore pops the screen beneath it, and with only one screen left it raises `ScreenStackError`, which kills the TUI. t1816 converted every brainstorm screen, `lib/section_viewer.SectionViewerScreen`, and the whole `diffviewer/` package, replacing `DiffViewerScreen.action_back`'s direct `app.pop_screen()` with `self.dismiss()`. The rule is documented in `aidocs/framework/tui_conventions.md` ("Modal dismissal: subclass `GuardedModalScreen`, never bare `ModalScreen`").

Scope:
- Switch every `ModalScreen` / `Screen` subclass in `board/aitask_board.py` (~89 dismiss sites), `monitor/monitor_shared.py` (~40), `settings/settings_app.py` (~37), `chatlink/wizard.py` (~16), `syncer/upgrade_screens.py` (~15), `syncer/settings_screens.py` (~11), and every other TUI to `GuardedModalScreen`, or to `GuardedDismissMixin, Screen` for a non-modal base.
- Convert the shared `lib/` screens as well, including those reached through app-level mixins from any TUI: `TuiSwitcherOverlay`, `ShortcutEditorModal`, `StaleEntryModal`, `_RepointInputScreen`, `AgentCommandScreen`, `AgentModelPickerScreen`, `LaunchModePickerScreen`, `KeyCaptureScreen`, `EditStringScreen`, `ProfileEditScreen`, `SyncConflictScreen`. `KeyCaptureScreen` / `ShortcutEditorModal` use `ModalScreen[T]` generics, so check that `GuardedModalScreen` subscripting still works (or add a generic alias).
- Replace every direct `app.pop_screen()` / `self.app.pop_screen()` that closes the calling screen with `self.dismiss()`.
- Extend `_screen_source_files()` in `tests/test_brainstorm_guarded_dismiss.py` (or move the enforcement into a repo-wide test) so it covers every TUI directory and `lib/`. It checks for unguarded screen bases and for direct `pop_screen` calls.
- Audit each converted screen for a dismiss issued while a child screen is legitimately on top (worker/timer/`call_later` paths). Under the guard that dismiss becomes a logged no-op. Result callbacks are safe because Textual runs them via `call_next` after the child pops.
- Coordinate with t1450 (board modal Escape result loss), which owns the dismiss-result rule in the same doc.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:10:23Z.5a8fc88ff9655b0ac3f38c5c from=t1794_9 from_verified=yes at=2026-09-22T06:10:23Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Specific to t1830: the "~89 dismiss sites in board/aitask_board.py" figure no longer describes one file. A plain `grep -c 'dismiss('` count at this SHA (a rough count, not your exact metric): aitask_board.py 41, board_detail_screen.py 44, board_column_dialogs.py 20, board_trail_view.py 8. The board's ModalScreen/Screen subclasses to convert are spread across those four modules; the trail modals in board_trail_view.py are also pushed by `ait trails`, so converting them affects both TUIs.
