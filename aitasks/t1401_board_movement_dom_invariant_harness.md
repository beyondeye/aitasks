---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
anchor: 1243
followup_kind: risk_mitigation
created_at: 2026-08-03 22:43
updated_at: 2026-08-13 23:07
boardidx: 6144
---

## Origin

Risk-mitigation ("after") follow-up for t1243_5, created at Step 8d after
implementation landed.

## Risk addressed

> Two invariants the recompose used to maintain for free — `ColumnHeader.task_count`
> and the dirty `*` — become explicit obligations of the movement path, and a
> future third one could be missed the same way · severity: medium

`addresses`: code-health — recompose-maintained invariants become explicit
caller obligations.

## Goal

Promote t1243_5's post-move consistency checks into a shared assertion helper in
`tests/lib/board_fixture.py` and apply it to the lateral, vertical **and**
to-edge paths, so a future in-place movement path inherits the net instead of
re-deriving it.

The invariants to fold into one helper (all currently asserted only in
`tests/test_board_dom_transplant.py`, and only for the paths t1243_5 touched):

1. **DOM order matches the model** — the column's parent-card filenames in DOM
   order equal `manager.get_column_tasks(col_id)`, recomputed independently
   rather than read back from the board.
2. **`column_id` is correct across the whole block** — the moved parent card
   *and* every child card inside its `.child-wrapper` rows. Assert it
   behaviourally (a search applied after the move) as well as structurally; the
   behavioural form is what catches a stale id, and t1243_5's negative control
   showed a source-column rebuild fails exactly there.
3. **The header count** — asserted at render level, not on `task_count`.
4. **The dirty `*`** — asserted at render level on the moved card.
5. **Exactly one card exists for the moved filename** — not zero (the
   lost-card failure mode) and not two.

## Notes

- **The vertical path will fail invariant 4 today.** That is a real, pre-existing
  defect, tracked as **t1399** (`_swap_adjacent_cards` reorders with `move_child`
  and never repaints). Sequence this task after t1399, or land the helper with
  the vertical case marked expected-fail and flip it when t1399 lands — do not
  weaken the invariant to make the suite green.
- **t1243_11 (group block moves) is the intended beneficiary.** Shape the helper
  so a block move of N cards can be checked with one call.
- Reuse `bf.PristineTreeMixin` (promoted by t1243_5) — `FixtureBoardTestBase`
  builds one tree per class, so an unrestored tree makes a later move
  early-return and its assertions vacuous.
- Keep each assertion paired with a discriminating control; t1243_5's file has
  the idioms (seeded sentinel, mis-attributed `column_id`, untouched-column
  comparison).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:09:25Z.0ab4dbe87ee4f0851bafcbb2 from=t1794_9 from_verified=yes at=2026-09-22T06:09:25Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
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
> | Your body (aitasks/t1401_board_movement_dom_invariant_harness.md) cites symbols you name -> current module: ColumnHeader -> board_widgets.py.
