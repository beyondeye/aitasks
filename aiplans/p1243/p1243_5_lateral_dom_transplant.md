---
Task: t1243_5_lateral_dom_transplant.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
---

# t1243_5 — Lateral DOM transplant

> Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` first — it holds
> the verified current-state table, the design decisions and the rejected
> alternatives. The task file `aitasks/t1243/t1243_5_lateral_dom_transplant.md` is the spec;
> this file is the execution order.

## Step 0 — anchor re-verification (every child starts here)

`aitask_board.py` grew 7378 → 9043 lines across six commits while t1243 was
planned, and it keeps moving. Before editing, re-locate every symbol this plan
names and confirm the behaviour still matches the parent plan's table. Anchor on
symbol names; never on line numbers. If a premise has changed, stop and record
it rather than working around it.

## Step 0b — read the checkpoint

As t1243_4: read t1243_1's recorded decision before implementing. In short, from
the measured baseline (ablation, 200 cards, production topology):

- lateral keypress median **2173.2 ms**; removing the recompose alone drops it to
  **138.6 ms** — **93.6 %** of the cost, and ~94 % of the whole Workstream-B
  opportunity;
- t1243_4's levers (`apply_filter`, `refresh_git_status`) measured **0.4 %**, so
  the user-confirmed checkpoint moved the **≥ 30 % latency target onto this
  child**;
- the fallback to `refresh_columns` therefore forfeits nearly the entire win and
  must be **escalated as a finding**, not taken quietly.

## Step 1 — the spike (gate everything else on it)

Textual 8.2.7 has no supported cross-parent widget move: `move_child` is
same-parent only and `remove()`/`mount()` are awaitables. Establish which of
these is viable and record it in this plan:

- a true cross-parent move, or
- `await old.remove()` + mount **freshly constructed** cards in the destination
  (a scoped rebuild of the moved block only, not of two columns).

If neither is safe, take the documented fallback below and stop — that is a
successful outcome, not a failure.

## Step 2 — `_card_block` extraction

Pull the block computation out of `_swap_adjacent_cards` (card + trailing
`.child-wrapper` Horizontals) into a shared helper. Do not fork it.

## Step 3 — `_transplant_block`

Async. **Identity is load-bearing**: `column_id` is read in 12 places including
`apply_filter`, `_visible_column_cards`, `_get_focused_col_id` and
`check_action`. Fresh cards get it right by construction; a true move must update
it on every card in the block. Movement actions become async (or dispatch via
`run_worker`) so awaitables are awaited.

## Step 4 — wire lateral and to-edge, then scoped filter

Replace `refresh_columns({src,dst})` / `refresh_column(col)` with the transplant,
then call `apply_filter(cols={src,dst})`.

## Documented fallback — reweighted

Keep `refresh_columns` and ship t1243_4's scoped filter alone. Do not force an
unsafe widget manipulation to match the plan's shape — but this is **no longer a
neutral outcome**: it forfeits ~94 % of the measured opportunity (t1243_4's
levers are worth 0.4 %). Record the spike result and the residual cost, and
**escalate it as a finding**: the premise holds and the cost is real, so a failed
spike means the remedy needs re-designing (e.g. an incremental recompose that
does not remount unchanged cards), not that the child is done.

## Verification

Real Pilot: destination focus, `.child-wrapper` travel, **post-move filter
correctness** (the assertion that catches stale `column_id`), scroll sanity,
`_get_focused_col_id` reports the destination, column reordering still resolves.

**Latency is a pass condition here:** ≥ 30 % reduction in median lateral
keypress latency versus the t1243_1 baseline (2173.2 ms), using t1243_1's
ping-pong method and per-sample validity rules. Record the delta whichever path
was taken. On a miss, run t1243_1's Performance-Gate Confirmation Checkpoint —
no automatic revision, no discarded code.
