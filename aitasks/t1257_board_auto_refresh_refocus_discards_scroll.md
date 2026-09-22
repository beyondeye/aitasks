---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Postponed
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 1248
created_at: 2026-07-26 19:20
updated_at: 2026-07-30 07:56
boardidx: 41984
---

## Origin

Deferred by t1248 (board column scroll jump). t1248 fixed the nav-key route to
the symptom; this is a second, independent route to the same user-visible
behaviour, and it survives that fix.

## Problem

When board auto-refresh is enabled (`auto_refresh_minutes > 0` in
`board_config.json`; the default and this repo's value is `0`, which is why it
did not surface during the t1248 investigation), the periodic tick rebuilds the
board and then restores focus:

`_start_auto_refresh_timer` (`.aitask-scripts/board/aitask_board.py:5685-5691`)
→ `_auto_refresh_tick` → `refresh_board` → `_queue_refocus` → `_refocus_card`
(`:5854`) → `card.focus()` → `TaskCard.on_focus` → `scroll_visible()`.

If the user has wheel-scrolled a column away from the focused card, that refocus
pulls the column straight back to the card and the scroll position is lost —
the same complaint t1248 fixed for the nav-key trigger, arriving on a timer
instead of a keystroke.

Note `refresh_board` unmounts and remounts every column, so the columns are new
widgets and their scroll offsets are gone regardless; the refocus then decides
where the rebuilt column lands. Any fix has to preserve the *user's* scroll
position across the rebuild, not merely change where the focus scroll goes.

## Relevant context from t1248

- `TaskCard.on_focus` now calls `scroll_visible(animate=False, immediate=True)`,
  so the pull is instantaneous rather than a deferred animation — the position
  is still discarded, just without the `scroll_target_y` corruption.
- `_reanchor_to_viewport` / `_viewport_anchor` / `_card_fully_visible` already
  exist and express "what is on screen"; they may be reusable here, but note
  they operate on a *live* layout and the refresh path rebuilds it.
- `_recompose_column` (`:5874`) keeps the column shell and replaces its
  children, so it preserves `scroll_y` where a full `refresh_board` does not —
  worth examining as the cheaper path for a periodic refresh.

## Acceptance criteria

1. With auto-refresh enabled and a column wheel-scrolled away from the focused
   card, an auto-refresh tick must not discard the user's scroll position.
2. Focus restoration itself must keep working — the refresh must not leave focus
   on nothing, and the existing behaviour covered by
   `tests/test_board_empty_column_focus.py` (Case 8, `refresh_column` /
   `_refocus_card` falling back to column identity) must not regress.
3. Pin the fix with a headless Pilot test: enable auto-refresh (or invoke the
   tick directly), wheel-scroll a column, run the refresh, assert the scroll
   position survived. Prove the test fails before the fix.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:08:46Z.299e1c82d9a7f22aba0695d7 from=t1794_9 from_verified=yes at=2026-09-22T06:08:46Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1257_board_auto_refresh_refocus_discards_scroll.md) cites stale line anchors: aitask_board.py:5685-5691; symbols you name -> current module: TaskCard -> board_widgets.py.
