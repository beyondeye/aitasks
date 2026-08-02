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
| `tests/test_board_movement.py` | flip table (deliberate), new scenarios, re-pointed mutation, multi-step runner |
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
- **Bounded exception — compaction.** When the destination interval cannot hold
  the required indices (`index_between` / `indices_between` returns `None`), do
  **one** `respace_column(col_id, stride=stride_for(K))` — N writes, that column
  only — re-read the neighbour indices, then place. There is never a second
  compaction.
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

- **`_move_task_lateral` (`:8211-8213`)** → `self.manager.move_task_to_column(filename, new_col)`;
  **both** `normalize_indices` calls deleted. `refresh_git_status()` and
  `refresh_columns({current_col_id, new_col}, …)` stay verbatim — the DOM and
  git-churn work is t1243_4/t1243_5's, and the source column still needs a
  *repaint* even though it no longer needs a *write*.
- **`_move_task_vertical` (`:8267-8268`)** → resolve the destination slot from
  the already-computed `tasks` list and call
  `reposition_task(filename, before, after)`; `swap_tasks` and
  `normalize_indices` deleted. For `direction = +1` the new neighbours are
  `tasks[current+1]` and `tasks[current+2] if present else None`; for
  `direction = -1` they are `tasks[current-2] if present else None` and
  `tasks[current-1]`. The existing `_swap_adjacent_cards` DOM path is unchanged
  — it is still an adjacent-pair exchange visually.
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

**The flip table, flipped.** Derived from the new code; a mismatch on the first
run is a real finding to diagnose, not a value to paste over.

| scenario | writes | changed | final `(col, idx)` of the moved card | note |
|---|---|---|---|---|
| `lateral_canonical` | 1 (was 1) | `{t9003}` (unchanged) | `("c1", 1044)` | `max(10,20) + 1024` |
| `lateral_gapped` | **1** (was 3) | **`{t9003}`** (was 3 files) | `("c1", 1044)` | **the headline flip** — `c0` keeps `5/17/42` |
| `vertical_swap` | **1** (was 2) | `{t9002}` (was 2 files) | `("c0", 1054)` | appended past `30`; order `9001, 9003, 9002` |
| `extreme_top` | **1** (was 4) | **`{t9003}`** (was 3 files) | `("c0", -1014)` | `10 - 1024`; negative index is the point |
| `extreme_bottom` | **1** (was 4) | **`{t9001}`** (was 3 files) | `("c0", 1054)` | `30 + 1024` |
| `shift_column` | 0 | `{board_config.json}` | — | unchanged; still 0 task writes |

Every untouched card keeps its original `(col, idx)` in all six rows — that is
the "never a file outside the move" claim, asserted through
`_assert_frozen`'s existing exact `state` comparison rather than added as prose.

**Four new scenarios**, all with exact write counts and exact changed-path sets:

| scenario | steps | expected |
|---|---|---|
| `transit_multi_hop` | focus 3, `shift+right` ×2 (c0→c1→c2) | writes **2** (same file twice), changed **`{t9003}`** only, final `("c2", 1034)`; `c0` and `c1` byte-identical — *the transit guarantee* |
| `vertical_at_bound` | focus 3 `shift+up`, focus 2 `shift+up`, focus 3 `shift+up` | writes **3**, `respace_calls == 0`, final `c0` = `10 / 11 / 12` — the interval driven to **exactly** fit still does not compact |
| `vertical_exhaustion` | the same three, then focus 2 `shift+up` into the now-1-wide gap | writes **7** (3 + respace 3 + placement 1), `respace_calls == **1**`, all writes confined to `c0`, final `c0` = `1024 / 1536 / 2048` — legacy self-heal, one compaction, retry succeeds |
| `quoted_boardidx` | `c1` seeded with `boardidx: "20"` (a str card spec) alongside ints; focus 3, `shift+right` | no `TypeError`; lands at `20 + 1024 = 1044` — the raw-`max()` bug, pinned |

`vertical_at_bound` and `vertical_exhaustion` share a step prefix deliberately:
the pair is what distinguishes "did not compact when it must not" from
"compacted exactly once when it must", which neither scenario proves alone.

A second discrimination test runs `vertical_exhaustion` with a mutation that
pins `stride_for` to `STEP`; at `k = 1` that is still correct, so the control
instead pins `respace_indices` to a stride of `1`, making the post-respace gap
too narrow and the in-code retry assertion fire — proving the assertion is
reachable and that the guarantee is not vacuous.

### 7c. `tests/test_board_persistence_seam.py` — the second frozen table

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

### 7d. Seam guard

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
/home/ddt/.aitask/venv/bin/python -m unittest tests.test_board_movement -v
/home/ddt/.aitask/venv/bin/python -m unittest tests.test_board_persistence_seam -v
bash tests/run_all_python_tests.sh          # read ONLY the last line for the verdict
shellcheck .aitask-scripts/aitask_*.sh      # unchanged, but the repo lint gate
```

- All pure-module tests pass, including the `stride_for` boundary trio and the
  retry round-trip property.
- All ten movement scenarios match the edited flip table **exactly**
  (`assertEqual`, never `assertGreater`), and both discrimination controls fail
  the frozen record as intended.
- `respace_calls == 0` for every scenario except `vertical_exhaustion`, where it
  is exactly `1`.
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
  both sides.

### Planned mitigations

None. No "before" mitigation is warranted — the characterization harness this
child flips is itself the mitigation, and it already landed in t1243_1. The
retrospective re-measurement is already scheduled as **t1243_14**.

## Step 9 (Post-Implementation)

Merge to `main`, run the declared `risk_evaluated` gate via the Step-9
orchestrator, then archive with `./.aitask-scripts/aitask_archive.sh 1243_3`.
