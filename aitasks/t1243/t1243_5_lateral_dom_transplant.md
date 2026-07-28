---
priority: medium
effort: medium
depends: [t1243_4]
issue_type: performance
status: Ready
labels: [aitask_board, tui, python, script-performance]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-07-28 01:14
updated_at: 2026-07-28 01:14
---

## Context

**Child 5 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md` — Workstream B, Tier 2).

A lateral move currently ends in `refresh_columns({src, dst})`, which runs
`_recompose_column` on **both** columns — `remove_children()` + `compose()` +
`mount_all()`, destroying and rebuilding every card widget of two columns. A
to-edge move does the same for one column. Only `_move_task_vertical` avoids it,
via the in-place `move_child` fast path in `_swap_adjacent_cards`.

**This child is a spike first, because the operation may not exist.** Installed
Textual is **8.2.7**: `move_child` is **same-parent only**, `remove()` and
`mount()` return awaitables, and there is **no supported cross-parent widget
move**. The board has no existing cross-column DOM helper — the column-change
path in the detail-screen callback also goes through `refresh_columns`.

> **t1243_1's DECISION CHECKPOINT HAS RUN — this child PASSED and its scope
> GREW.** Do **not** read t1243_4's note as precedent: t1243_4 is the child that
> *missed* and lost its latency target, and that target moved **here**.
> Measured: recompose is **93.6 %** of a 2173.2 ms lateral keypress. Read the
> recorded baseline and decision in the parent plan before implementing, and see
> "Documented fallback — REWEIGHTED" below.

**Anchor re-verification (do this first)** — see t1243_1; anchor on symbol names.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — `_swap_adjacent_cards` (extract
  `_card_block`), `_move_task_lateral`, `_move_task_to_extreme`.
- `tests/test_board_dom_transplant.py` — **new**.

## Reference files for patterns

- `_swap_adjacent_cards` — already defines a **block** = `TaskCard` + trailing
  `.child-wrapper` `Horizontal`s, moved together via same-parent `move_child`.
  Extract that block computation; do not fork it.
- `tests/test_board_empty_column_focus.py` — Pilot fixture with `with_children`,
  which composes real `.child-wrapper` rows.

## Implementation plan

### Step 1 — the spike (do this before writing the feature)

Determine whether Textual 8.2.7 permits a lifecycle-safe cross-parent block move.
Record the finding in the plan file either way. Two candidate shapes:

- a true move (if any supported path exists), or
- `await old.remove()` then mount **freshly constructed** `TaskCard`s in the
  destination — a scoped rebuild of the moved block only, not of two columns.

### Step 2 — the helper

```python
def _card_block(self, card) -> list[Widget]:      # extracted from _swap_adjacent_cards
async def _transplant_block(self, block, src_col, dst_col, before=None): ...
```

**Identity is load-bearing.** `TaskCard.column_id` is set at construction and read
in **12 places** — `apply_filter`, `_column_widget`, `_visible_column_cards`,
`_get_focused_col_id`, `_refocus_column`, `check_action`. If the block is moved
rather than rebuilt, `column_id` **must** be updated on every card in it;
otherwise the data model is correct while navigation and filtering still point at
the old column. Constructing fresh cards gets this right by construction.

Movement actions become `async` (or dispatch via `run_worker`) so the awaitables
are awaited rather than dropped.

### Step 3 — wire it in

- `_move_task_lateral` → transplant instead of `refresh_columns({src, dst})`.
- `_move_task_to_extreme` → `move_child` to first/last instead of
  `refresh_column`.
- Both then call the scoped `apply_filter(cols={src, dst})` from t1243_4.

### Documented fallback — REWEIGHTED by t1243_1's measured baseline

**This child now carries the entire Workstream-B latency target.** t1243_1
measured, by ablation on a 200-card board: lateral keypress median **2173.2 ms**,
of which removing the recompose alone accounts for **93.6 %** (dropping to
138.6 ms). t1243_4's levers were worth 0.4 %, so its ≥ 30 % target was moved
here at the user-confirmed checkpoint.

Consequently the fallback is **no longer a neutral outcome**: keeping
`refresh_columns` and shipping the scoped `apply_filter` alone forfeits ~94 % of
the available win (Tier 1 is worth ~0.4 %, not the "whole-board filter pass"
saving the original wording assumed).

If the spike shows no lifecycle-safe transplant exists in 8.2.7: still do **not**
force an unsafe widget manipulation. Record the spike result and the residual
cost — and **escalate it as a finding** (the workstream's premise holds and the
cost is real, so a failed spike means the remedy must be re-designed, e.g. an
incremental/diffing recompose that avoids remounting unchanged cards), rather
than closing the child as done.

## Verification

Real Pilot, not structural-only:

- focus lands on the moved card **in the destination column** after a lateral
  move;
- an expanded parent's `.child-wrapper` rows travel with it and stay adjacent;
- a search filter applied **after** the move hides/shows the right cards (this is
  the assertion that catches stale `column_id`);
- `_get_focused_col_id()` reports the **destination**;
- scroll position is sane (the moved card is visible, no jump to top);
- `ctrl+left` / `ctrl+right` column reordering still resolves the focused column
  afterwards.

**Latency is a pass condition for this child:** ≥ 30 % reduction in median
keypress latency on the **lateral** axis versus the t1243_1 baseline
(2173.2 ms), measured with t1243_1's ping-pong method and per-sample validity
rules. Record the delta versus the baseline **whichever path was taken**
(transplant or fallback), for t1243_14. If the target is missed, do **not**
revise or discard anything automatically — run t1243_1's Performance-Gate
Confirmation Checkpoint (parent plan) and let the user choose.
