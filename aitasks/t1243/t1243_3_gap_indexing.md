---
priority: high
effort: medium
depends: [t1243_2]
issue_type: enhancement
status: Implementing
labels: [aitask_board, tui, python, script-performance]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1243
created_at: 2026-07-28 01:13
updated_at: 2026-08-02 06:20
---

## Context

**Child 3 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md` — Workstream A).

`TaskManager.normalize_indices(col)` renumbers **every** task in a column to
`(i+1)*10`, one `reload_and_save_board_fields()` per changed task, and it runs on
every lateral move (**both** columns), every vertical move, and every to-edge
move. Moving one task from column A to C via B therefore rewrites frontmatter in
A and B that the user never intended to touch — real cost as git churn and
merge-conflict surface on the shared `aitask-data` branch.

This child replaces canonical renumbering with **gap indexing** so a single move
writes exactly one file.

**Coordination — `t1210_5`.** `t1210_5` (`trail_move_to_column_commands`) plans
its By-Trail `m`/`M` moves on `move_task_col` + `normalize_indices`, i.e. the API
this child deletes. It is dependency-guarded during t1243's decomposition and
will carry `depends: [t1210_4, 1243_3, 1243_7]`. When this child lands, its
`## Notes for sibling tasks` must name the replacement API so t1210_5 consumes it
instead of re-deriving a move path.

**Anchor re-verification (do this first)** — see t1243_1; anchor on symbol names.

## Key files to modify

- `.aitask-scripts/lib/board_ordering.py` — **new**, pure module.
- `.aitask-scripts/board/aitask_board.py` — `TaskManager.move_task_col`,
  `swap_tasks`, `normalize_indices`; the actions `_move_task_lateral`,
  `_move_task_vertical`, `_move_task_to_extreme`.
- `tests/test_board_ordering.py` — **new**, pure-module tests.
- `tests/test_board_movement.py` — the t1243_1 flip table (edit deliberately).

## Reference files for patterns

- `.aitask-scripts/lib/topic_semantics.py` — the precedent for extracting a pure,
  headless, import-testable core out of the board.
- `.aitask-scripts/lib/task_yaml.py` `normalize_board_idx` — the only sanctioned
  coercion of a raw `boardidx` to a sortable int; **every** read must go through
  it.
- `TaskManager.get_column_tasks` — the sole reader; it only *sorts*, by
  `(normalize_board_idx(board_idx), filename)`. Nothing anywhere requires indices
  to be dense, contiguous or canonical.

## Implementation plan

### 1. `lib/board_ordering.py` (pure, no Textual imports)

```python
STEP = 1024                      # power of two -> ~10 midpoint halvings per gap

def index_for_append(indices)  -> int          # max + STEP, or STEP
def index_for_prepend(indices) -> int          # min - STEP, or STEP
def index_between(lo, hi)      -> int | None   # (lo+hi)//2, None when hi-lo < 2
def indices_between(lo, hi, k) -> list[int] | None   # k distinct, None if gap < k+1
def respace_indices(n, stride=STEP) -> list[int]     # [(i+1)*stride for i in range(n)]
def stride_for(k)              -> int          # max(STEP, next power of two >= k+1)
```

`int` stays the on-disk type. **Negative values are legal** — readers only sort
and `normalize_board_idx` passes ints through unchanged — which is what makes
"move to top" a single write instead of a renumber.

### 2. Manager API

| Method | Writes (compaction-free) |
|---|---|
| `move_task_to_column(task, col)` | **1** — `boardcol` + `index_for_append`. Source column untouched. |
| `reposition_task(task, before, after)` | **1** — `index_between`. |
| `move_task_to_edge(task, col, top/bottom)` | **1** — prepend / append. |
| `move_tasks_to_column(tasks, col)` | **K** — K contiguous indices from `max+STEP`, input order preserved. |
| `respace_column(col, stride)` | **N** — `normalize_indices` renamed; **exhaustion remedy only**. |

`swap_tasks` is retired from the movement path in favour of `reposition_task`
(1 write instead of 2, and it fixes the existing no-op when both indices are
equal). `normalize_indices` is **not** deleted — it becomes `respace_column`.

### 3. The write guarantee, and its bounded exception

- **Normal case:** each single-task move writes **exactly one** file and never a
  file outside the move. A multi-hop transit A→B→C writes the moved task once per
  hop and **nothing** in A or B.
- **Bounded exception — compaction:** when the destination interval cannot hold
  the required indices (`index_between` / `indices_between` returns `None`), do
  **one** `respace_column(col, stride=stride_for(K))` — N writes, that column
  only — then the placement write. The stride is derived from the pending insert
  size, so post-respace every gap holds at least K interior values and the retry
  is guaranteed **for any K**. A fixed `STEP=1024` would only guarantee it for
  K <= 1023; `stride_for` removes that unstated cap. There is never a second
  compaction.
- **Bound:** at `STEP=1024`, exhaustion needs ~10 consecutive inserts into the
  same gap. Legacy `10`-spaced columns exhaust after ~4 and self-heal once.

### 4. Migration

Existing boards keep their `10/20/30` values and self-heal lazily on first
exhaustion. **No upfront rewrite, no migration commit** — a load-time respace
would be exactly the churn this task removes.

### 5. Correctness fixes bundled in

- `move_task_col` computes `max((t.board_idx for t in existing), default=0)` over
  the **raw** value — a hand-quoted `boardidx: "20"` mixed with ints raises
  `TypeError`. Route it through `normalize_board_idx`.
- `_move_task_to_extreme` does raw `tasks[0].board_idx - 10` /
  `tasks[-1].board_idx + 10` arithmetic with the same flaw. Same fix.

### 6. Rejected alternative (record in the plan, do not implement)

A never-compacting representation (fractional / LexoRank-style string ranks)
would make the guarantee absolute, but `boardidx` is an **int** on disk with
three consumers (`normalize_board_idx`, `lib/work_report_gather.py`,
`board/aitask_merge.py`) and `aitask_update.sh --boardidx IDX` documents
"integer". Changing the on-disk type is a far larger blast radius than a rare,
bounded, single-column respace.

## Verification

Pure-module unit tests for append / prepend / between / `indices_between` /
exhaustion / `stride_for` / `respace_indices`.

Through the t1243_1 harness, with **exact changed-path sets**, not just counts:

- healthy column → **exactly 1** write per single-task move, changed set ==
  `{moved task}`;
- at-bound (interval driven to exactly fit) → still **no** compaction;
- over-bound → **exactly one** `respace_column`, then success; all writes
  confined to that column; no second compaction;
- **multi-hop transit A→B→C dirties nothing outside the moved task**;
- a legacy `10`-spaced column self-heals once and is `STEP`-spaced thereafter;
- a column containing a hand-quoted `boardidx: "20"` alongside ints no longer
  raises `TypeError`.

The t1243_1 flip table is updated **deliberately** in this commit; a silent pass
means the table was not discriminating.
