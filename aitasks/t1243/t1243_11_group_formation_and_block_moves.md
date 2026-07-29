---
priority: high
effort: medium
depends: [t1243_10]
issue_type: feature
status: Ready
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-07-28 01:17
updated_at: 2026-07-28 01:17
---

## Context

**Child 11 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md` — Workstream C).

Makes groups **mutable and movable**: joining, leaving, and moving as a block.
The data model is t1243_8's, the widgets and dispatch are t1243_9's; this child
owns the manager-level operations and their write contracts.

**Anchor re-verification (do this first)** — see t1243_1; anchor on symbol names.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — `TaskManager` group operations,
  `_card_block` generalisation, the four `_move_task_*` block paths,
  `TaskManager.delete_column`.
- `tests/test_board_group_moves.py` — **new**.

## Reference files for patterns

- `.aitask-scripts/lib/board_ordering.py` (t1243_3) — `indices_between`,
  `index_for_append`, `respace_column`, `stride_for`.
- `.aitask-scripts/lib/board_groups.py` (t1243_8) — the INV-R derivation. Consume
  it; never re-derive grouping.
- `_swap_adjacent_cards` / `_card_block` (t1243_5) — the block concept to
  generalise from "card + its child-wrappers" to "group of such blocks".

## Implementation plan

### 1. Formation and removal write **only** `boardgroup`

Because INV-R derives rendering from persisted state rather than requiring
contiguous indices (see t1243_8), grouping needs **no index writes at all**:

- **Formation** (adding K tasks to a group): K writes, each setting `boardgroup`
  via t1243_2's `reload_and_save_board_fields(fields=("boardgroup",))` — naming a
  non-layout key *is* what makes it a semantic write; there is no `semantic=True`
  bool. **No `boardidx` is touched** — and because the seam persists only the
  named fields, naming `boardgroup` alone is also what stops a stale in-memory
  index from being written back over a concurrent move. **Non-members are never
  rewritten.**
- **Removal**: 1 write per removed task, setting the `""` tombstone. Position is
  untouched — membership no longer depends on it, so a mid-run removal cannot
  strand anything.

Neither operation has a gap case or a compaction case, because neither assigns a
rank. Do **not** write gap/compaction tests for them.

### 2. Block moves

Generalise `_card_block()` to a group block (the header plus each member's own
card-and-child-wrappers block), then:

- **Lateral / to-edge**: N writes (N = members), relative order preserved.
- **Vertical past an adjacent unit**: assign the group N distinct indices below
  (or above) that unit's sort key — **N writes; the neighbouring unit is never
  touched.**
- **Opportunistic contiguity**: because the move rewrites those N files anyway,
  assign them *contiguous* indices. A group the user actually moves becomes tidy
  through use; a group that only ever arrived by sync renders correctly with zero
  writes. **Tidiness is a by-product, never a repair pass.**
- **Bounded compaction**: when the destination interval cannot hold N distinct
  indices, one `respace_column(col, stride=stride_for(N))` then retry — that
  column only, guaranteed to succeed for any N, never a second compaction.

**Rejected optimization — "rewrite the smaller side".** Moving a 5-card group
past 1 card would cost 1 write instead of 5, but it dirties a file the user never
selected — exactly the unrelated-file churn this whole task exists to remove.
Predictability wins.

### 3. Coalesce on move

Group identity is `(column, slug)`, so moving group `G` into a column that
already holds `G` **coalesces automatically** — that is just the derivation.
Arriving members get indices above the residents' maximum, so they render after
them: deterministic and reload-stable. **Notify** ("merged into existing group
'perf work'"); do not refuse a legitimate move. Hand the collapse-key combination
to t1243_10's rule. (Rename onto an existing slug is different — it is a naming
act and **confirms** first; that is t1243_12.)

### 4. `delete_column` tidy-up

`delete_column` currently sets `board_idx = 0` for **every** task in the column,
mass-tying them on arrival in `unordered`. Under INV-R this is no longer
correctness-critical (ties break by filename and groups still render as blocks),
but it is a worthwhile fix: assign contiguous indices that preserve the existing
relative order and group runs. Same-slug groups arriving from different columns
coalesce per section 3.

## Verification

Exact **changed-path sets**, not just counts, through the t1243_1 harness:

- formation touches only the K grouped files, and **no `boardidx` anywhere**;
- removal touches only the ungrouped file, and no index;
- lateral block move: exactly N writes, relative order preserved;
- vertical block move: exactly N writes, and **the neighbouring unit is provably
  untouched**;
- each move case additionally at-gap, exhausted-gap (exactly one
  `respace_column`, confined to that column), and retry-succeeds — plus the
  **K = 1023 / 1024 / 1025 stride boundary**, proving `stride_for` removes the
  fixed-STEP cap;
- **reload round-trip after every operation**: a freshly reloaded manager
  reproduces the same rendered order (INV-R);
- coalesce-on-move: arriving members render after residents, deterministically;
- `delete_column` on a column with two groups and loose tasks preserves relative
  order and both group runs.
