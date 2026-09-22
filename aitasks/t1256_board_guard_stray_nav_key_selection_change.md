---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_board, tui, tmux, python]
gates: [risk_evaluated]
anchor: 1248
created_at: 2026-07-26 19:19
updated_at: 2026-07-26 19:19
boardidx: 40960
---

## Origin

Residual left open by t1248 (board column scroll jump). t1248 fixed the *scroll*
consequence of a stray cursor key: the column no longer teleports. It did not
address the *selection* consequence, and this task tracks that.

## Problem

Inside tmux, wheel-scrolling a board column can deliver spurious `up` / `down`
cursor keys to `ait board` (tmux's alternate-screen wheel → cursor-key
emulation). The board binds those with `priority=True`
(`.aitask-scripts/board/aitask_board.py:5411-5414`), so each one runs
`action_nav_up` / `action_nav_down` and **moves the focused card**.

After t1248 that focus move is visually harmless — the cursor re-anchors to a
card already on screen instead of dragging the view back. But the selection has
still changed without the user asking. A keystroke issued immediately afterwards
acts on the wrong task:

- `enter` opens a different task's detail;
- `shift+up` / `shift+down` reorders a different task;
- any column-move or archive shortcut targets a different task.

The newly focused card does carry the cyan focus border, so this is not silent —
but a user who was scrolling, not navigating, has no reason to re-check which
card is selected before pressing the next key.

## Direction (evaluate, do not adopt blindly)

t1248's plan sketched a **recency guard**: ignore `nav_up` / `nav_down` that
arrive within ~200 ms of a wheel event on the same column. Known constraint from
that investigation: `VerticalScroll._on_mouse_scroll_down` calls `event.stop()`
when it scrolls, so the App never sees the wheel event — the timestamp has to be
taken either in a small `_on_mouse_scroll_down` override on the four column
classes (`KanbanColumn`, `InFlightColumn`, `TopicColumn`, `TrailColumn`, each
calling `super()`), or in a `Screen._forward_event` hook.

Weigh that against the cost: a recency guard also suppresses *genuine* keyboard
navigation for that window, which is a real UX regression for someone who
scrolls and then immediately navigates. Alternatives worth considering before
committing to it — requiring a second keypress before a destructive action when
focus changed without an explicit nav intent, or confirming destructive
shortcuts when the focus moved within the last N ms.

## Acceptance criteria

1. Decide, with reasons recorded, whether the board should suppress nav keys
   during an active wheel scroll or defend at the destructive-action sites
   instead. A documented "no change, here is why" is an acceptable outcome.
2. If a guard is implemented, genuine keyboard navigation immediately after a
   wheel scroll must not be swallowed — pin that with a test.
3. Any guard must be pinned by a headless Pilot test in the style of
   `tests/test_board_scroll_focus_jump.py` (wheel events posted through
   `app.screen._forward_event`; note that priority-bound keys are consumed at
   App level and are invisible at `Screen._forward_event`).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:08:44Z.8796aead434252f122d721ee from=t1794_9 from_verified=yes at=2026-09-22T06:08:44Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1256_board_guard_stray_nav_key_selection_change.md) cites stale line anchors: aitask_board.py:5411-5414.
