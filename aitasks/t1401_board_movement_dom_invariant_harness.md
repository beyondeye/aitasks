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
