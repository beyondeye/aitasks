---
Task: t1243_3_gap_indexing.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Archived Sibling Plans: aiplans/archived/p1243/p1243_1_movement_baseline_and_harness.md, aiplans/archived/p1243/p1243_2_board_field_persistence_seam.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-02 06:29
---

# t1243_3 — Gap indexing

> Child 3 of 14 in the t1243 decomposition. Parent design:
> `aiplans/p1243_board_task_groups_and_fast_reordering.md` (Workstream A).
> t1243_1 (archived) owns the movement characterization harness this child
> flips; t1243_2 (archived) owns the `reload_and_save_board_fields(fields)`
> seam every write below goes through.

## Context

`TaskManager.normalize_indices(col)` renumbers **every** task in a column to
`(i+1)*10`, one `reload_and_save_board_fields(("boardidx",))` per changed task,
and it runs on every lateral move (**both** columns), every vertical move and
every to-edge move. Moving one card from column A to C via B rewrites
frontmatter in A and B that the user never intended to touch — real cost as git
churn and merge-conflict surface on the shared `aitask-data` branch, where
`boardcol`/`boardidx` are resolved **silently local-wins**
(`aitask_merge.py:134-138`).

This child replaces canonical renumbering with **gap indexing**, so a single
move writes exactly one file.

## Step 0 — anchor re-verification (done at `HEAD` = `84a305109`)

`aitask_board.py` is now **9176 lines** (9043 when t1243 was planned, 9128 when
t1243_2 ran). Line numbers moved; **every symbol is intact and every behavioural
premise still holds**. Verified:

| Symbol | Location | Status |
|---|---|---|
| `TaskManager.get_column_tasks` | `aitask_board.py:1050-1060` | sorts by `(normalize_board_idx(idx), filename)`; **nothing requires dense, contiguous, positive or canonical indices** |
| `TaskManager.move_task_col` | `:1338-1346` | `max((t.board_idx …), default=0) + 10` over the **raw** value |
| `TaskManager.swap_tasks` | `:1348-1354` | 2 writes; no-op when the two indices are equal |
| `TaskManager.normalize_indices` | `:1356-1363` | `(i+1)*10`, one write per changed task |
| `TaskManager.update_column` | `:1371-1388` | membership only — **not touched by this child** |
| `TaskManager.delete_column` | `:1412-1426` | sets every evicted task to `board_idx = 0` — **not touched** (t1243_11 tidies it) |
| `_move_task_lateral` | `:8186-8216` | `move_task_col` + `normalize_indices` × **2** + `refresh_git_status` + `refresh_columns` |
| `_move_task_vertical` | `:8250-8293` | `swap_tasks` + `normalize_indices` + DOM `_swap_adjacent_cards` |
| `_move_task_to_extreme` | `:8301-8326` | raw `tasks[0].board_idx - 10` / `tasks[-1].board_idx + 10`, 1 write, then `normalize_indices` |
| `Task.reload_and_save_board_fields(fields)` | `:264-312` | required, validated `fields`; layout-only names stay timestamp-neutral |
| `Task.board_idx` | `:322-328` | `metadata.get("boardidx", 0)` — an absent index reads as `0` |
| `normalize_board_idx` | `lib/task_yaml.py:67-88` | `int → raw` unchanged (**negatives pass through**); non-numeric → `0` |
| `lib/topic_semantics.py` | 75 lines, `import re` only | the pure-module precedent; board imports it at `aitask_board.py:346-353` |

**Four `normalize_indices` call sites** confirmed: `:8212`, `:8213` (lateral,
both columns), `:8268` (vertical), `:8324` (to-edge). **One** `move_task_col`
call site (`:8211`) and **one** `swap_tasks` call site (`:8267`). No CLI, shell
script, merge path or other TUI calls any of the three.

### Premise changes found by this verify pass — three, all material

1. **`t1354_1` landed (`a53e3ac3c`) and moved the harness helpers.**
   `build_tree`, `snapshot`, `diff_snapshots`, `fixture_name`, `_fixture_text`
   now live in the **new** `tests/lib/board_fixture.py`;
   `tests/test_board_movement.py` imports them at `:70-83` and shrank
   1078 → 964 lines. New code must import from `board_fixture`, **not** from
   `test_board_movement`. (`load_board_module()` — an in-process board boot
   under a synthetic module name — also arrived; this child does **not** use it,
   because the movement harness's subprocess isolation is what its own negative
   control pins.)

2. **`tests/test_board_persistence_seam.py` must be edited by this child, and
   neither the task file nor the previous revision of this plan said so.**
   t1243_2 froze `EXPECTED_CALL_SITES` (`:487-495`) as an **ordered, source-order**
   AST table naming `move_task_col`, `swap_tasks` (×2) and `normalize_indices`;
   five runtime-spy tests (`:602-653`) call those three methods directly; and
   `test_ast_guard_rejects_an_extra_field` (`:558-571`) uses a **source-text
   anchor inside `swap_tasks`**. Renaming/removing those methods breaks all
   three mechanisms. t1243_2's own note — "`EXPECTED_CALL_SITES` is frozen like
   `FLIP_TABLE`; any task adding a call site must consciously edit it" — is
   hereby honoured in the *removal* direction too. This is added to Key files.

3. **The `skip_normalize` mutation goes inert.** `tests/test_board_movement.py:308-315`
   injects `B.TaskManager.normalize_indices = lambda self_, col_id: None` to
   prove the flip table discriminates. After the rename that assignment merely
   *creates* an unused attribute, so `HarnessDiscriminationTests` would fail
   **for the wrong reason** (the negative control must fail *because the
   behaviour is pinned*, not because the mutation missed). It is re-pointed
   below.

Two smaller confirmations: `t1210_5` already carries
`depends: [t1210_4, t1243_3, t1243_7]`, so the parent's guard-swap completed and
only the `## Notes for sibling tasks` hand-off remains; and `boardidx` is
**deliberately excluded** from trail digests (`lib/trail_schema.py:501-504`), so
no re-indexing scheme can cause trail drift.

## Key files

| File | Change |
|---|---|
| `.aitask-scripts/lib/board_ordering.py` | **new** — pure module |
| `.aitask-scripts/board/aitask_board.py` | manager API + the three movement actions |
| `tests/test_board_ordering.py` | **new** — pure-module unit tests |
| `tests/test_board_manager_moves.py` | **new** — manager-level API contract (batch all-or-nothing, refusal reasons) |
| `tests/test_board_movement.py` | flip table (deliberate), seven new scenarios, re-pointed mutation, multi-step runner |
| `tests/test_board_persistence_seam.py` | frozen call-site table, five driver tests, AST-discrimination anchor |
| `website/content/docs/tuis/board/how-to.md`, `.../reference.md` | the "normalized to 10, 20, 30" sentences become false |
| `aidocs/implementation_trail_design.md` | three passages naming `move_task_col` + `normalize_indices` |
| `aitasks/t1243/t1243_3_gap_indexing.md` | record the widened scope (premise changes 2 and 3) |

## 1. `.aitask-scripts/lib/board_ordering.py` — pure module

Headless: stdlib only, **no Textual, no board, no `task_yaml` import**. Mirrors
`lib/topic_semantics.py`'s shape — filename-prefixed one-line docstring, a "Why
this exists" paragraph naming `t1243_3`, an explicit ownership statement (the
board is the semantic owner; `tests/test_board_ordering.py` and
`tests/test_board_movement.py` must stay green in the same commit), and a
contract note that **all inputs are already `normalize_board_idx`-coerced ints**
— the module never sees a raw frontmatter value.

```python
STEP = 1024          # power of two -> ~10 midpoint halvings before a gap exhausts

def index_for_append(indices)  -> int          # max(indices) + STEP, or STEP when empty
def index_for_prepend(indices) -> int          # min(indices) - STEP, or STEP when empty
def index_between(lo, hi)      -> int | None   # (lo + hi) // 2; None when hi - lo < 2
def indices_between(lo, hi, k) -> list[int] | None   # k distinct interior ints; None when hi - lo < k + 1
def respace_indices(n, stride=STEP) -> list[int]     # [(i + 1) * stride for i in range(n)]
def stride_for(k)              -> int          # max(STEP, next power of two >= k + 1)
```

- `indices_between`: `step = (hi - lo) // (k + 1)`, returning
  `[lo + step * (j + 1) for j in range(k)]`. With `hi - lo >= k + 1` we get
  `step >= 1` and `lo + step * k <= hi - step < hi`, so the results are distinct
  and strictly interior.
- `stride_for(k) = max(STEP, _next_pow2(k + 1))` with
  `_next_pow2(n) = 1 if n <= 1 else 1 << (n - 1).bit_length()`. This is what makes
  the compaction retry unconditional: after `respace_indices(n, stride)` every
  adjacent gap is exactly `stride`, and `stride >= k + 1` by construction. A
  fixed `STEP = 1024` would only guarantee the retry for `k <= 1023` — an
  unstated cap `stride_for` removes.
- **`int` stays the on-disk type and negative values are legal.** Readers only
  sort, and `normalize_board_idx` returns an `int` unchanged, which is exactly
  what makes "move to top" one write instead of a renumber.

**`indices_between` has no production caller in this child — deliberately.**
Every operation here places either **one** task into a bounded interval
(`index_between`) or a run **past a column extremum** (`index_for_append` /
`index_for_prepend`). The K-wide insert-between that consumes `indices_between`
is **t1243_11**'s block move. It lands with this module because the module is
the arithmetic home and splitting the pair across two children would leave
`stride_for`'s guarantee unexpressible; it is covered by pure-module unit tests
including the `stride_for` round-trip property, and §7e's seam guard stops it
being re-inlined elsewhere. This is recorded so its absence from the call graph
is not later mistaken for dead code. `stride_for` **does** have a live caller —
`reposition_task`'s compaction remedy calls `stride_for(1)`.

## 2. Manager API (`TaskManager`, replacing the three methods on the hot path)

A small frozen dataclass carries the result — a bare boolean cannot tell
t1243_7 *which* ids were refused (the repo's rich-return convention):

```python
@dataclasses.dataclass(frozen=True)
class MoveResult:
    moved:     tuple[str, ...] = ()          # filenames actually written, in input order
    refused:   tuple[tuple[str, str], ...] = ()   # (name, reason) — reason in {"not_a_parent_task"}
    compacted: bool = False                  # a respace_column ran first
    @property
    def ok(self) -> bool: return not self.refused
```

| Method | Writes (compaction-free) |
|---|---|
| `move_task_to_column(task_name, new_col)` | **1** — `boardcol` + `index_for_append` over the destination. Source column untouched. |
| `move_tasks_to_column(task_names, new_col)` | **K** — K contiguous indices from `max + STEP`, input order preserved, **all-or-nothing** |
| `reposition_task(task_name, before, after)` | **1** — `index_between` |
| `move_task_to_edge(task_name, col_id, to_top)` | **1** — prepend / append |
| `respace_column(col_id, stride=STEP)` | **N** — `normalize_indices` renamed; **exhaustion remedy only** |

- **`reposition_task(task_name, before, after)`** places the task *between* the
  two neighbours in rendered order: `before` is the `Task` that will sit
  immediately **above** it (`None` = it becomes first) and `after` the one
  immediately **below** (`None` = it becomes last). `before is None` → prepend,
  `after is None` → append, otherwise `index_between`. It replaces `swap_tasks`
  on the movement path: 1 write instead of 2, and it fixes the existing
  **equal-index no-op** (two cards sharing an index are ordered by filename, so
  swapping them today moves nothing).
- **`move_tasks_to_column` fails closed.** If *any* name does not resolve in
  `self.task_datas` (a child id, an unknown file) it writes **nothing** and
  returns a `MoveResult` naming every offending id. t1243_7 requires exactly
  this. `move_task_to_column` returns the same type for one item.
- **Every index read goes through `normalize_board_idx`.** This is what fixes
  the two live raw-value bugs: `max((t.board_idx …))` in `move_task_col`
  (`:1343`) and the `±10` arithmetic in `_move_task_to_extreme` (`:8320-8322`)
  both raise `TypeError` today on a column mixing a hand-quoted `boardidx: "20"`
  with ints.
- **`respace_column` is the rename of `normalize_indices`**, not a deletion —
  it keeps the "write only where the value actually differs" guard. It must
  never be called from a move path except as the compaction remedy.
- `move_task_col` and `swap_tasks` are **removed**, not aliased: they have one
  production caller each, both rewired below, and a dead alias is the "unread
  duplicate" the repo's conventions forbid.

## 3. The write guarantee, and its bounded exception

- **Normal case.** Each single-task move writes **exactly one** file and never a
  file outside the move. A multi-hop transit A→B→C writes the moved task once
  per hop and **nothing** in A or B.
- **Bounded exception — compaction, reachable from `reposition_task` alone.**
  It is the only operation in this child that places a task into a **bounded**
  interval between two neighbours, so `index_between` returning `None` is its
  sole trigger: do **one** `respace_column(col_id, stride=stride_for(1))` — N
  writes, that column only — re-read the neighbour indices, then place. There is
  never a second compaction.
  **The append family can never compact.** `move_task_to_column`,
  `move_tasks_to_column` and `move_task_to_edge` all place past a column
  extremum, an unbounded region (Python ints do not overflow), so no interval
  can be exhausted and `indices_between` is never consulted. That is asserted,
  not assumed — see the batch table in §7c. The `indices_between` half of this
  exception activates in **t1243_11**, which inserts a K-wide block *between*
  two units.
- **The retry is asserted in code, not only in tests.** After the respace the
  recomputed index is checked; `None` raises `AssertionError` with the column,
  the stride and the neighbour indices. It is unreachable by construction
  (`stride_for`), and a silent wrong placement would be strictly worse than a
  loud, diagnosable failure in a Textual action handler.
- **Bound.** At `STEP = 1024`, exhaustion needs ~10 consecutive inserts into the
  *same* gap. A legacy `10`-spaced column exhausts after ~4 and self-heals once.

## 4. Migration

Existing boards keep their `10/20/30` values and self-heal lazily on first
exhaustion. **No upfront rewrite, no migration commit** — a load-time respace
would be exactly the churn this task removes.

## 5. Rewiring the three actions

**Every index computation excludes the moving task.** `index_for_append` /
`index_for_prepend` receive the indices of the **other** tasks in the target
column, so a card already holding the column minimum still lands strictly above
it. (`move_task_to_column` already had this property — the destination column
does not yet contain the mover; the existing `# Calculate new index before
changing column to avoid counting self` comment is preserved.)

- **`_move_task_lateral` (`:8211-8213`)** → `self.manager.move_task_to_column(filename, new_col)`;
  **both** `normalize_indices` calls deleted. `refresh_git_status()` and
  `refresh_columns({current_col_id, new_col}, …)` stay verbatim — the DOM and
  git-churn work is t1243_4/t1243_5's, and the source column still needs a
  *repaint* even though it no longer needs a *write*.
- **`_move_task_vertical` (`:8267-8268`)** → resolve the destination slot from
  the already-computed `tasks` list and call
  `reposition_task(filename, before, after)`; `swap_tasks` and
  `normalize_indices` deleted. **Bounds are explicit — never Python's negative
  indexing**, because `tasks[current - 2]` at `current == 1` silently returns the
  *last* card in the column rather than "absent", which is precisely the
  move-to-first case:

  ```python
  if direction == 1:                       # moving down past tasks[current+1]
      before = tasks[current + 1]
      after  = tasks[current + 2] if current + 2 < len(tasks) else None
  else:                                    # moving up past tasks[current-1]
      before = tasks[current - 2] if current >= 2 else None
      after  = tasks[current - 1]
  ```

  `before is None` → prepend (becomes first); `after is None` → append (becomes
  last). The existing `_swap_adjacent_cards` DOM path is unchanged — it is still
  an adjacent-pair exchange visually. `tie_two_way_up` in §7b is the scenario
  that fails if the bound is dropped.
- **`_move_task_to_extreme` (`:8319-8324`)** → `move_task_to_edge(filename, col_id, to_top=(direction == -1))`;
  the raw `±10` arithmetic, the inline `reload_and_save_board_fields` and the
  `normalize_indices` call all go, which is what turns 4 writes into 1.

## 6. Rejected alternative (recorded, not implemented)

A never-compacting representation (fractional / LexoRank-style string ranks)
would make the guarantee absolute, but `boardidx` is an **int** on disk with
three consumers (`normalize_board_idx`, `lib/work_report_gather.py:204,214`,
`board/aitask_merge.py:225`), `aitask_update.sh:225` documents "integer", and
`tests/test_work_report_gather.sh` pins int semantics. Changing the on-disk type
is a far larger blast radius than a rare, bounded, single-column respace.

## 7. Tests

### 7a. `tests/test_board_ordering.py` (new) — the pure module

Fast, in-process, no board import. Append/prepend on empty and populated
inputs; `index_between` above, at and below the bound (`hi - lo` = 3, 2, 1, 0
and negative); `indices_between` for `k = 1 … 5` asserting **distinct, strictly
interior, ascending**; `respace_indices` shape; `stride_for` at
`k = 0, 1, 1022, 1023, 1024, 1025` (the boundary trio the parent plan requires
for t1243_11's block moves); and the **round-trip invariant** that for every
tested `k`, `indices_between` over any adjacent gap of
`respace_indices(n, stride_for(k))` returns a list rather than `None` — this is
the retry guarantee expressed as a property rather than as prose.

Negative values are exercised throughout (prepend from a minimum of `10`
yields `-1014`).

### 7b. `tests/test_board_movement.py` — the flip table, edited deliberately

Three harness changes first:

1. **Multi-step scenarios.** `SCENARIOS` entries gain an optional
   `"steps": [{"focus": i, "key": "…"}, …]`; `"focus"`/`"key"` stay as the
   single-step shorthand so the six existing entries are untouched. The child's
   scenario branch (`_run_in_app`, `:370-381`) loops the steps, re-focusing
   before each press. Needed because multi-hop transit and gap exhaustion are
   *sequences*, and the current runner presses exactly one key.
2. **`respace_calls` reported.** The probe wraps `TaskManager.respace_column`
   and the result carries the count, so "**exactly one** compaction" is asserted
   directly instead of inferred from a write total.
3. **The mutation is re-pointed.** `skip_normalize` →
   `respace_after_move`, which wraps `move_task_to_column` to also
   `respace_column(src, stride=10)` and `respace_column(dst, stride=10)` — i.e.
   it reinstates precisely the amplification this task removes, and must break
   the new frozen record for `lateral_gapped`. The assertion message is updated
   to name it. (An inert mutation would make `HarnessDiscriminationTests` fail
   for the wrong reason; the control has to fail *because* the table pins
   behaviour.)

**Fixtures.** `_assert_frozen` compares the **full** on-disk `state` dict, the
exact `changed` path set and the exact write count, so every scenario below
declares all three plus its complete card layout. Three fixtures are new:

```python
CANONICAL = [(1,"c0",10), (2,"c0",20), (3,"c0",30), (4,"c1",10), (5,"c1",20), (6,"c2",10)]   # existing
GAPPED    = [(1,"c0", 5), (2,"c0",17), (3,"c0",42), (4,"c1",10), (5,"c1",20), (6,"c2",10)]   # existing
QUOTED    = [(1,"c0",10), (2,"c0",20), (3,"c0",30), (4,"c1","20"), (5,"c1",30), (6,"c2",10)] # new: 9004 is the STRING "20"
TIED2     = [(1,"c0",10), (2,"c0",10), (3,"c0",30), (4,"c1",10), (5,"c1",20), (6,"c2",10)]   # new: 9001/9002 tied
TIED3     = [(1,"c0",10), (2,"c0",10), (3,"c0",10), (4,"c1",10), (5,"c1",20), (6,"c2",10)]   # new: three-way tie
```

`build_tree` passes `idx` straight into `serialize_frontmatter`, so the string
`"20"` is emitted as `boardidx: '20'` and read back as a `str` — which is what
makes `QUOTED` a real reproduction of today's `TypeError` in `max()`.

**The flip table, flipped.** Derived from the new code; a mismatch on the first
run is a real finding to diagnose, not a value to paste over. `state` is
`(col, idx)` per card 1–6.

| scenario | fixture · steps | writes | respace | changed | final state |
|---|---|---|---|---|---|
| `lateral_canonical` | CANONICAL · focus 3, `shift+right` | 1 | 0 | `{9003}` | 1:(c0,10) 2:(c0,20) **3:(c1,1044)** 4:(c1,10) 5:(c1,20) 6:(c2,10) |
| `lateral_gapped` | GAPPED · focus 3, `shift+right` | **1** (was 3) | 0 | **`{9003}`** (was 3 files) | **1:(c0,5) 2:(c0,17)** **3:(c1,1044)** 4:(c1,10) 5:(c1,20) 6:(c2,10) |
| `vertical_swap` | CANONICAL · focus 2, `shift+down` | **1** (was 2) | 0 | `{9002}` | 1:(c0,10) **2:(c0,1054)** 3:(c0,30) 4:(c1,10) 5:(c1,20) 6:(c2,10) |
| `extreme_top` | CANONICAL · focus 3, `ctrl+up` | **1** (was 4) | 0 | **`{9003}`** | 1:(c0,10) 2:(c0,20) **3:(c0,-1014)** 4:(c1,10) 5:(c1,20) 6:(c2,10) |
| `extreme_bottom` | CANONICAL · focus 1, `ctrl+down` | **1** (was 4) | 0 | **`{9001}`** | **1:(c0,1054)** 2:(c0,20) 3:(c0,30) 4:(c1,10) 5:(c1,20) 6:(c2,10) |
| `shift_column` | CANONICAL · focus 1, `ctrl+right` | 0 | 0 | `{board_config.json}` | unchanged canonical |

`lateral_gapped` is the headline: `c0` **keeps `5 / 17 / 42`** instead of being
renumbered to `10 / 20 / 30`. Every untouched card keeping its original
`(col, idx)` in all six rows *is* the "never a file outside the move" claim,
asserted through `_assert_frozen`'s existing exact `state` comparison rather
than added as prose.

**Seven new scenarios.**

`transit_multi_hop` — CANONICAL, focus 3, `shift+right` ×2 (c0→c1→c2). Hop 1
appends past `max(10,20)` → `1044`; hop 2 past `max(10)` → `1034`.
**writes 2** (same file twice) · respace 0 · **changed `{9003}` only** ·
state `1:(c0,10) 2:(c0,20) 3:(c2,1034) 4:(c1,10) 5:(c1,20) 6:(c2,10)`.
*The transit guarantee: c0 and c1 are byte-identical after a two-hop move.*

`vertical_at_bound` — CANONICAL, three steps, each derivation shown because the
whole scenario is an arithmetic claim:

| step | focus | key | pos | `before` / `after` | result |
|---|---|---|---|---|---|
| 1 | 9003 | `shift+up` | 2 | 9001(10) / 9002(20) | `index_between(10,20)` = **15** → 9001(10), 9003(15), 9002(20) |
| 2 | 9002 | `shift+up` | 2 | 9001(10) / 9003(15) | `index_between(10,15)` = **12** → 9001(10), 9002(12), 9003(15) |
| 3 | 9003 | `shift+up` | 2 | 9001(10) / 9002(12) | `index_between(10,12)` = **11** → 9001(10), 9003(11), 9002(12) |

**writes 3** · **respace 0** · changed `{9002, 9003}` (9001 never written) ·
state `1:(c0,10) 2:(c0,12) 3:(c0,11) 4:(c1,10) 5:(c1,20) 6:(c2,10)`.
Step 3's gap is exactly 2 — the **at-bound** case, which must still not compact.

`vertical_exhaustion` — CANONICAL, the same three steps **plus** step 4: focus
9002, `shift+up`, at pos 2 with `before` 9001(10) / `after` 9003(11).
`index_between(10,11)` → `None` (gap 1) → **one**
`respace_column("c0", stride=stride_for(1)=1024)` → 9001=1024, 9003=2048,
9002=3072 → re-read → `index_between(1024,2048)` = **1536**.
**writes 7** (3 + respace 3 + placement 1) · **respace exactly 1** ·
changed `{9001, 9002, 9003}`, all confined to c0 ·
state `1:(c0,1024) 2:(c0,1536) 3:(c0,2048) 4:(c1,10) 5:(c1,20) 6:(c2,10)`.
*Legacy 10-spaced column self-heals once; the retry succeeds; there is no second
compaction.* Sharing a step prefix with `vertical_at_bound` is deliberate: the
pair is what distinguishes "did not compact when it must not" from "compacted
exactly once when it must", which neither proves alone.

`quoted_boardidx` — QUOTED, focus 3, `shift+right`. Destination c1 holds the
**string** `'20'` next to the int `30`; `max()` over raw values raises
`TypeError` today. Normalized: `max(20,30)` → `1054`.
**writes 1** · respace 0 · changed `{9003}` ·
state `1:(c0,10) 2:(c0,20) 3:(c1,1054) 4:(c1,'20') 5:(c1,30) 6:(c2,10)`.
The expected value for card 4 is the **string** `'20'` — proving the quoted file
was neither rewritten nor coerced.

`tie_two_way_up` — TIED2 (9001 and 9002 both at `10`; filename breaks the tie so
9001 renders first), focus 2, `shift+up`. `current == 1` → `before = None`
(**the case the negative-index defect fixed in §5 got wrong**) → prepend past
`min(others) = 10` → **-1014**.
**writes 1** · respace 0 · changed `{9002}` ·
state `1:(c0,10) 2:(c0,-1014) 3:(c0,30) 4:(c1,10) 5:(c1,20) 6:(c2,10)`.
*Today `swap_tasks` exchanges 10↔10, both writes are byte-identical and the card
does not move at all — this is the equal-index no-op, pinned as fixed.*

`tie_two_way_down` — TIED2, focus 1, `shift+down`. `current == 0` →
`before = 9002(10)`, `after = 9003(30)` → `index_between(10,30)` = **20**.
**writes 1** · respace 0 · changed `{9001}` ·
state `1:(c0,20) 2:(c0,10) 3:(c0,30) 4:(c1,10) 5:(c1,20) 6:(c2,10)` ·
order 9002(10), 9001(20), 9003(30) — the card really moved past its tied
neighbour.

`tie_three_way_up_compacts` — TIED3 (all of c0 at `10`), focus 3, `shift+up`.
`before` 9001(10) / `after` 9002(10) → `index_between(10,10)` → `None` → one
respace → 1024/2048/3072 → `index_between(1024,2048)` = **1536**.
**writes 4** (respace 3 + placement 1) · **respace exactly 1** ·
changed `{9001, 9002, 9003}` ·
state `1:(c0,1024) 2:(c0,2048) 3:(c0,1536) 4:(c1,10) 5:(c1,20) 6:(c2,10)`.
*A tie is the densest possible interval, so it is the shortest path to the
compaction branch — one keypress where `vertical_exhaustion` needs four, so the
two fail independently.* Ties are reachable in production: `delete_column`
assigns `board_idx = 0` to every evicted task.

A second discrimination test runs `vertical_exhaustion` under a mutation pinning
`respace_indices` to a stride of `1`, making the post-respace gap too narrow and
the in-code retry assertion fire — proving the assertion is reachable and the
guarantee not vacuous. (Pinning `stride_for` to `STEP` would **not** serve as a
control: at `k = 1` that is already the correct value.)

### 7c. `tests/test_board_manager_moves.py` (new) — the batch API, tested directly

Neither the pure-module tests nor the TUI scenarios reach
`move_tasks_to_column`, so **an implementation that writes each resolved task as
it goes and only then discovers an invalid one would pass every other test in
this plan** while leaving the batch half-applied — silently breaking the
hand-off t1243_7 is built on.

In-process, no Textual, using the patch-mode seam
(`mock.patch.object(B, "TASKS_DIR" / "METADATA_FILE", …)` — the helper shape at
`tests/test_board_persistence_seam.py:580-587`) over a `build_fixture_tree`
topology that includes **real child tasks** (`FixtureTask(task_id="9000_1")`),
so a child id is a genuine on-disk file the manager legitimately refuses rather
than a fabricated string.

Every refusal case asserts **three** things, not one: `MoveResult.refused`, a
write-spy count of **0**, and a `snapshot` / `diff_snapshots` byte comparison
showing the tree is **unchanged**. The byte check is what a partial-write
implementation fails.

| case | input | expected |
|---|---|---|
| happy path, K = 3 | three parents → `c2` | `moved` == input order; **3** writes; indices contiguous from `max + STEP`; `refused` empty; `ok` true |
| single unknown name | `["t9999_nope.md"]` | `refused == (("t9999_nope.md", "not_a_parent_task"),)`; **0** writes; tree byte-identical |
| single child id | the real `t9000_1_*.md` | same shape, reason `not_a_parent_task`; **0** writes; tree byte-identical |
| **mixed valid + child** | 2 valid parents + 1 child | **0** writes, tree byte-identical — the valid ones must **not** land; `refused` names only the child |
| **mixed valid + unknown + child** | 1 valid, 1 unknown, 1 child | `refused` names **both** offenders in input order; `moved` empty; **0** writes |
| duplicate names | the same parent twice | resolved once; **1** write, not 2; no duplicate in `moved` — a repeat must not consume two indices |
| empty list | `[]` | `ok` true, `moved` empty, **0** writes — distinguishable from a refusal, which t1243_7 needs |
| ordering | 3 parents in reverse render order | destination order matches **input** order, not source order |
| **append-only never compacts** | K = 5 into a dense legacy column (`c1` = 10/20) | `respace_calls == **0**`; indices exactly `max+STEP … max+5·STEP`; **5** writes — the batch path has no bounded interval, so compaction is unreachable *by construction*, and this asserts it rather than leaving it unstated |

`move_task_to_column` gets the single-item equivalents (valid, unknown, child)
so the shared refusal path is covered on both entry points.

### 7d. `tests/test_board_persistence_seam.py` — the second frozen table

- `EXPECTED_CALL_SITES` (`:487-495`) is re-derived in **source order** for the
  new call sites and edited deliberately, with the existing comment extended to
  say t1243_3 rewrote it:

  ```python
  EXPECTED_CALL_SITES = [
      ("move_task_to_column",  ("boardcol", "boardidx")),
      ("move_tasks_to_column", ("boardcol", "boardidx")),
      ("reposition_task",      ("boardidx",)),
      ("move_task_to_edge",    ("boardidx",)),
      ("respace_column",       ("boardidx",)),
      ("update_column",        ("boardcol",)),
      ("delete_column",        ("boardcol", "boardidx")),
  ]
  ```

  (Final order and membership follow the definition order actually written in
  §2; the AST guard fails closed, so a mismatch is loud.) Note
  `_move_task_to_extreme` **leaves** the table: the action no longer writes
  directly, which is itself part of the deliverable.
- The five runtime-spy tests (`:602-653`) are retargeted:
  `test_move_task_col_names_both_layout_keys` → `move_task_to_column`;
  `test_swap_tasks_names_the_index_only_twice` → **replaced** by
  `test_reposition_task_names_the_index_only_once` (one record, not two — the
  halved write count expressed at the seam layer);
  `test_normalize_indices_*` → `test_respace_column_*`. Both end-to-end
  hazard-C assertions (`:640-653`) are kept, with `normalize_indices` →
  `respace_column`.
- `test_ast_guard_rejects_an_extra_field` (`:558-571`) anchors on a source-text
  snippet inside `swap_tasks`; it is re-anchored on `reposition_task`'s
  `("boardidx",)` call and its `assertIn` updated. Verify the guard still
  discriminates by running it — a *passing* negative control here would mean the
  guard stopped testing anything.

### 7e. Seam guard

Mirroring `tests/test_trail_gather.py:960-967` (the `topic_semantics`
precedent), assert the board **imports** `board_ordering` and that
`def index_between(` / `def stride_for(` did not stay behind in
`aitask_board.py` — so a future edit cannot quietly re-inline the arithmetic.

## 8. Documentation

Two website sentences become **false** the moment this lands, and both are
one-line current-state corrections about behaviour this task changes (the
`boardgroup` doc sweep remains t1243_13's):

- `website/content/docs/tuis/board/how-to.md:25` — "After any move, indices are
  automatically normalized to 10, 20, 30, etc. to prevent drift."
- `website/content/docs/tuis/board/reference.md:331` — "After any movement
  operation, indices are normalized to 10, 20, 30, etc."

Both are rewritten to the gap-indexing contract: a move rewrites only the moved
task; indices are spaced, not consecutive, and may be negative; the whole column
is re-spaced only when a gap is exhausted.

`aidocs/implementation_trail_design.md:353-355`, `:481-483` and `:562-564` name
`move_task_col` + `normalize_indices` as the mutators T5 reuses. All three are
updated to `move_task_to_column` / `move_tasks_to_column`, with the note that
`move_tasks_to_column` preserves input order in one pass (so "wave moves
preserve `position` order" is now a property of the API rather than of a
follow-up normalize).

## Verification

```bash
/home/ddt/.aitask/venv/bin/python -m unittest tests.test_board_ordering -v
/home/ddt/.aitask/venv/bin/python -m unittest tests.test_board_manager_moves -v
/home/ddt/.aitask/venv/bin/python -m unittest tests.test_board_movement -v
/home/ddt/.aitask/venv/bin/python -m unittest tests.test_board_persistence_seam -v
bash tests/run_all_python_tests.sh          # read ONLY the last line for the verdict
```

- All pure-module tests pass, including the `stride_for` boundary trio and the
  retry round-trip property.
- All **thirteen** movement scenarios match the edited flip table **exactly**
  (`assertEqual`, never `assertGreater`), and both discrimination controls fail
  the frozen record as intended.
- `respace_calls == 0` for every scenario except `vertical_exhaustion` and
  `tie_three_way_up_compacts`, where it is exactly `1`.
- Every `move_tasks_to_column` refusal case leaves **zero writes and a
  byte-identical tree**; the append-only batch never compacts.
- The seam file's AST guard matches the new table for every call site, its two
  discrimination tests still reject their mutations, and the retargeted runtime
  spies record the exact `(filename, fields)` sequences.
- `grep -rn "normalize_indices\|swap_tasks\|move_task_col" .aitask-scripts/ tests/ aidocs/ website/`
  returns nothing outside deliberate historical prose in archived plans.
- `git status --porcelain` after a full test run shows no change under the real
  `aitasks/` tree — the subprocess isolation and its negative control still hold.

## Notes for sibling tasks

- **t1210_5** (`trail_move_to_column_commands`, `depends: [t1210_4, t1243_3, t1243_7]`)
  planned its By-Trail `m`/`M` moves on `move_task_col` + `normalize_indices`.
  Both are **gone**. Use `move_task_to_column(name, col)` for one task and
  **`move_tasks_to_column(names, col)`** for a wave — K writes, input order
  preserved, no follow-up normalize. Both return a `MoveResult`; check
  `.refused` rather than assuming success, and never call `respace_column` from
  a move path.
- **t1243_7** — `move_tasks_to_column` **fails closed as a batch**: one child id
  refuses the whole call and writes nothing, with every offending id named in
  `MoveResult.refused`. Distinguish that from the empty-selection case yourself;
  the manager treats `[]` as a successful no-op.
- **t1369 is the linear-arithmetic follow-up, and t1243_7 / t1210_5 are exactly
  why it exists.** `move_tasks_to_column` recomputes the append index *inside*
  its loop, so it is O(K x (N + K)). That is invisible at today's only call site
  (`move_task_to_column`, K = 1) but becomes real work the moment a marked set
  or a whole By-Trail wave is moved. Land **t1369** before shipping either
  command, or at minimum do not assume the batch path is linear. Raised and
  confirmed at this task's Step-8 review; deferred by user disposition (see
  Change Request 1).
- **t1243_11** — `index_for_append`, `respace_column` and `stride_for` are the
  block-move primitives. Formation/removal write `boardgroup` only and must
  never touch an index, so they can never compact. For a K-wide insert use
  `indices_between(lo, hi, K)` and, on `None`, one
  `respace_column(col, stride=stride_for(K))` then retry — the retry is
  guaranteed for **any** K and is asserted in code.
- **Both frozen tables must be edited consciously.** `FLIP_TABLE`
  (`tests/test_board_movement.py`) and `EXPECTED_CALL_SITES`
  (`tests/test_board_persistence_seam.py`) are now equally load-bearing; a
  silent pass after a movement rewrite is a bug in the table.
- **Negative `boardidx` values are normal**, produced by every "move to top".
  Anything that reads an index must go through `normalize_board_idx` and must
  not assume positivity, contiguity or a spacing of 10.

## Risk

### Code-health risk: medium

- **The change removes three `TaskManager` methods that two frozen test tables
  and five runtime-spy tests name directly** — `EXPECTED_CALL_SITES`,
  `FLIP_TABLE`, and the AST-discrimination anchor inside `swap_tasks` ·
  severity: medium · → mitigation: all three mechanisms are enumerated in §7 and
  edited deliberately in this commit, and the verify pass added
  `tests/test_board_persistence_seam.py` to Key files precisely because the
  original plan and task file omitted it; the AST guard fails **closed**, so a
  missed site cannot pass silently.
- **The negative control can go inert.** `skip_normalize` targets a method this
  child renames; left alone it would still "pass" the mutation step and fail the
  assertion for the wrong reason · severity: medium · → mitigation: the mutation
  is re-pointed to `respace_after_move` (a faithful reinstatement of today's
  amplification), and a second control drives the in-code retry assertion so the
  compaction guarantee is shown to be non-vacuous.
- **The on-disk ordering contract changes for three consumers**
  (`normalize_board_idx`, `work_report_gather`, `aitask_merge`) and negative
  indices become normal · severity: medium · → mitigation: all three were
  re-read at `HEAD` and **only sort** — none assumes positivity, contiguity or
  spacing; `normalize_board_idx` returns ints unchanged; `boardidx` is excluded
  from trail digests by construction; and the real-file characterization suite
  landed **before** this change.
- **The arithmetic is new code on the board's only layout-write path** ·
  severity: medium · → mitigation: it is isolated in a pure, dependency-free
  module with its own unit tests plus a seam guard proving it was not re-inlined;
  the manager methods contain no arithmetic of their own.
- **`reposition_task` changes the vertical move from a symmetric swap to an
  asymmetric insert**, so an off-by-one in neighbour selection would move the
  card to the wrong slot while still writing exactly one file · severity: medium
  · → mitigation: `_assert_frozen` compares the full on-disk `state` **and**
  recomputes the expected column order independently of the board
  (`expected_order`, `test_board_movement.py:108-121`), so "right file, wrong
  value" fails; `vertical_at_bound` walks three consecutive inserts.
- **`AssertionError` can now escape a Textual action handler** · severity: low ·
  → mitigation: it is unreachable by construction (`stride_for` guarantees the
  post-respace gap), it is preferable to a silently wrong placement, and a
  dedicated control proves it fires when the guarantee is deliberately broken.
- **`move_tasks_to_column`'s all-or-nothing contract is invisible to the
  scenario tests.** An implementation that writes each resolved task as it goes
  and refuses on the first bad id would satisfy every pure-module and TUI-driven
  assertion while leaving the batch half-applied — silently violating the
  hand-off t1243_7 is built on · severity: medium · → mitigation: §7c asserts
  **zero writes and a byte-identical tree** on every refusal path, including two
  mixed valid/invalid inputs, rather than only inspecting the returned report.
- **Six documentation passages state the superseded contract** · severity: low ·
  → mitigation: all six are enumerated in §8 and corrected in this commit, with
  a Verification grep proving nothing outside archived plans still names the
  removed API.

### Goal-achievement risk: low

- The deliverable is specified down to the function signatures, the per-call-site
  rewiring and the exact expected flip-table values, and every anchor was
  re-verified at current `HEAD` · severity: low · → mitigation: none needed.
- **Scope is wider than the task file states** — it now also edits
  `tests/test_board_persistence_seam.py` and the harness's mutation hook ·
  severity: low · → mitigation: the widening is forced by t1243_2's frozen
  guards rather than chosen; it is recorded in the task file (§Step 0 premise
  changes) rather than deviated to silently.
- **The harness needs a multi-step runner it does not have**, so three of the
  four new scenarios depend on a test-infrastructure change · severity: low ·
  → mitigation: the change is additive and backwards-compatible (`"steps"` is
  optional; the six existing entries keep `"focus"`/`"key"`), and the six
  original scenarios re-run through the same path as a regression check on the
  runner itself.
- The exhaustion path is reachable only after ~4 (legacy) or ~10 (`STEP`)
  inserts into one gap, so it could go untested in practice · severity: low ·
  → mitigation: `vertical_exhaustion` drives it deterministically in four
  keypresses, paired with `vertical_at_bound` so the boundary is pinned from
  both sides, and `tie_three_way_up_compacts` reaches the same branch in one
  keypress by a different route so the two fail independently.
- **The equal-index no-op fix was claimed but unexercised** — no fixture held
  tied indices, yet ties are reachable in production (`delete_column` assigns
  `board_idx = 0` to every evicted task) · severity: low · → mitigation: three
  tie scenarios (`tie_two_way_up`, `tie_two_way_down`,
  `tie_three_way_up_compacts`) pin both directions and the tie-driven compaction
  path with exact state.
- **`indices_between` ships with no caller in this child**, so its correctness
  rests on unit tests alone until t1243_11 consumes it · severity: low ·
  → mitigation: the exclusion is recorded explicitly in §1 rather than left
  implicit, and its contract is pinned by the `stride_for` round-trip property
  (for every tested K, an adjacent gap of `respace_indices(n, stride_for(K))`
  always admits K interior values) — the exact invariant t1243_11 relies on.

> **Mitigation follow-ups: none confirmed** (user decision at planning). No
> "before" mitigation is warranted — the characterization harness this child
> flips is itself the de-risking prework and already landed in t1243_1 — and the
> retrospective re-measurement is already scheduled as **t1243_14**. Two "after"
> candidates were proposed and declined: a randomised move-sequence property
> suite (the ten exact-set scenarios in §7b cover the same ground at fixed
> points), and a `delete_column` index tidy-up (already owned by **t1243_11**).

---

## Post-Review Changes

### Change Request 1 (2026-08-02 12:58) — superlinear index arithmetic in the batch move

- **Requested by user:** `move_tasks_to_column`
  (`.aitask-scripts/board/aitask_board.py:1426-1434`) calls
  `board_ordering.index_for_append(indices)` **inside** the loop, re-scanning a
  destination list that grows from N to N+K. `index_for_append` does
  `list(indices)` then `max(values)`, so the loop is **O(K x (N + K))** even
  though, after the first index `M = max(existing) + STEP`, every subsequent
  value is deterministically `M + i * STEP`. Disposition: **follow-up**.
- **Verified: CONFIRMED.** Read at the call site and in the helper. The
  quadratic term is real, and the values genuinely are a fixed-stride run —
  each appended index is by construction the new maximum, so nothing needs
  re-scanning.
- **Changes made:** none to the code, per the stated disposition. Filed
  **t1369** (`board_batch_move_linear_index_arithmetic`, performance, low/low,
  `--followup-of 1243_3`) carrying the confirmed diagnosis, the exact linear
  rewrite, and a verification rule that
  `tests/test_board_manager_moves.py` and `FLIP_TABLE` must pass **unedited**
  (they already pin the exact resulting indices, ordering and write counts, so
  an unedited pass is the proof the optimization is behaviour-preserving) plus
  a call-count guard so the regression cannot return silently.
- **Why deferring is safe today:** the only current caller is
  `move_task_to_column`, i.e. **K = 1**, where the loop runs once and the cost
  is identical to the linear form. The large-K consumers — **t1243_7** (`m`,
  marked tasks) and **t1210_5** (`M`, a By-Trail wave) — have not landed, so
  t1369 can land ahead of them and no user-visible path is ever slow.
- **Files affected:** `aitasks/t1369_board_batch_move_linear_index_arithmetic.md`
  (new), this plan.

## Step 9 (Post-Implementation)

Merge to `main`, run the declared `risk_evaluated` gate via the Step-9
orchestrator, then archive with `./.aitask-scripts/aitask_archive.sh 1243_3`.
