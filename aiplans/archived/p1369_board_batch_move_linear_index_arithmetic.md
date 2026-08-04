---
Task: t1369_board_batch_move_linear_index_arithmetic.md
Worktree: . (current-branch mode — no worktree created)
Branch: main (current branch)
Base branch: main
Output branch: main
---

# t1369 — Linear index arithmetic for the board's batch column move

## Context

`TaskManager.move_tasks_to_column` (`.aitask-scripts/board/aitask_board.py:1591-1600`)
re-scans the whole destination column once per moved task:

```python
indices = self._column_indices(new_col)          # N entries
for task in tasks:                               # K tasks
    task.board_idx = board_ordering.index_for_append(indices)
    indices.append(task.board_idx)
```

`index_for_append` does `list(indices)` then `max(values)`, so each iteration is
O(N + i) and the loop is **O(K × (N + K))**.

The re-scan is redundant by construction: the value appended each round is
always the new maximum, so after the first index `M = max(existing) + STEP`
every subsequent one is exactly `M + i * STEP`. Verified equivalent for every
input shape the method accepts — empty destination (`index_for_append([]) ==
STEP`, run = `STEP, 2*STEP, …`), non-empty destination, and a mover already
sitting in the destination column (no `exclude` is passed, so its own index
participates in `max()` identically under both formulations).

Today the only caller is `move_task_to_column` (K = 1), so nothing is slow yet.
The consumers that pass a large K are **t1243_7** (`m` — move marked tasks) and
**t1210_5** (`M` — move a whole By-Trail wave), both still pending. Fixing it
now keeps the cost linear from their first use.

This was raised at t1243_3's Step-8 review and deferred there by explicit user
disposition — correct behaviour, superlinear arithmetic only.

**Out of scope (explicit):** no file under `aitasks/t1243/` is touched. The
pending children (t1243_7, t1243_11) are named here only as the future consumers
that motivate the helper's placement; their task files stay exactly as they are,
and the forward pointer lives in the helper's docstring instead.

## Approach

Two changes. The arithmetic lands in `lib/board_ordering.py`, which the module's
own docstring declares the arithmetic home for this family (and which already
carries `indices_between` for t1243_11's block insert). t1243_11 names
`index_for_append` among its key files for block moves and will want the same
run, so a named helper avoids a second open-coded copy of the stride.

### 1. `.aitask-scripts/lib/board_ordering.py` — new `indices_for_append_run`

Add immediately after `index_for_append` (its sibling in the append family):

```python
def indices_for_append_run(indices, k):
    """``k`` ascending indices appending a run past every value in ``indices``.

    Equivalent to calling :func:`index_for_append` once per placement while
    feeding each result back in, but O(N + k) instead of O(k x (N + k)): the
    value appended each round is by construction the new maximum, so after the
    first index ``M`` every subsequent one is exactly ``M + i * STEP``.

    ``indices`` is consumed once and **no exclusion is applied** -- pass the
    destination column's indices exactly as the caller wants them counted (see
    `TaskManager._column_indices`'s ``exclude``). Returns exactly ``k`` values
    (``[]`` for ``k <= 0``), so a caller may zip it against its task list.

    Reuse
    -----
    This is the append-side counterpart of :func:`indices_between`, and the two
    cover the whole K-wide placement surface: ``indices_between`` for a block
    landing INSIDE a bounded interval, ``indices_for_append_run`` for a block
    landing PAST a column's maximum. Both exist so a K-wide placement is ONE
    arithmetic call rather than a per-item loop.

    `TaskManager.move_tasks_to_column` is the first caller. **t1243_11's block
    moves should call this** (lateral block move: exactly N writes, relative
    order preserved) instead of re-deriving the stride at the call site --
    that re-derivation is exactly the O(K x (N + K)) shape t1369 removed here.
    t1243_7's move-marked-tasks command reaches it through
    `move_tasks_to_column` and needs no direct call.
    """
    if k <= 0:
        return []
    start = index_for_append(indices)
    return [start + i * STEP for i in range(k)]
```

It consumes `indices` exactly once (through `index_for_append`'s `list()`), so
it keeps the any-iterable property `test_accepts_any_iterable` pins.

The `Reuse` block is the deliverable half of "consider whether the batch stride
belongs in `board_ordering`": the module docstring already explains why
`indices_between` sits here ahead of its t1243_11 consumer, and this note gives
the append-side twin the same forward pointer, so t1243_11 finds it by reading
the module rather than by rediscovering the arithmetic.

### 2. `.aitask-scripts/board/aitask_board.py` — `move_tasks_to_column`

Replace the re-scanning loop (lines 1591-1600) with:

```python
        run = board_ordering.indices_for_append_run(
            self._column_indices(new_col), len(tasks))
        moved = []
        for task, idx in zip(tasks, run):
            task.board_col = new_col
            task.board_idx = idx
            task.reload_and_save_board_fields(("boardcol", "boardidx"))
            self._mark_written(task)
            moved.append(task.filename)
        return MoveResult(moved=tuple(moved))
```

Everything above this block (the all-or-nothing `_resolve_parents` gate, the
empty early-return) is untouched, so `tasks` is non-empty and `run` has exactly
`len(tasks)` entries — `zip` cannot truncate. That totality is pinned by a unit
test (below) rather than left implicit, because a short return would silently
skip writes instead of failing.

Extend the method docstring with one line stating the run is computed once:
appends are O(N + K), not O(K × (N + K)).

## Tests

### `tests/test_board_ordering.py` — new `IndicesForAppendRunTests`

Placed after `AppendPrependTests` (the family it extends):

- `test_zero_and_negative_k_return_empty`
- `test_returns_exactly_k_values` — `len(...) == k` for k in 1..5 (the totality
  `zip` in the manager relies on)
- `test_run_starts_past_the_maximum` — `indices_for_append_run([10, 20, 30], 3)
  == [30 + STEP, 30 + 2*STEP, 30 + 3*STEP]`
- `test_empty_column_run_starts_at_step` — `== [STEP, 2*STEP, 3*STEP]`
- `test_matches_iterated_index_for_append` — the equivalence claim itself, run
  as an oracle: for several `(indices, k)` shapes, build the reference by
  iterating `index_for_append` + `append` and assert the helper matches it
  element-for-element. This is the independent ground truth for
  "behaviour-preserving"; the manager tests pin the resulting *state*, this pins
  the *arithmetic*.
- `test_accepts_any_iterable` — `indices_for_append_run(iter([10, 20]), 2)`

### `tests/test_board_manager_moves.py` — new `MoveTasksToColumnScalingTests(_ManagerBase)`

The scaling guard the task asks for. A call-count spy, not wall-clock timing
(stable in the shared parallel suite). `aitask_board` does
`import board_ordering` and calls through the module attribute, so
`mock.patch.object(BO, "index_for_append", …)` intercepts both the manager's
call and the one inside `indices_for_append_run`.

- `test_batch_scans_the_destination_once` — K = 5 (`[ALPHA, BETA, GAMMA, DELTA,
  EPSILON]` → `c2`); assert the spy recorded exactly **1** call. The old loop
  recorded 5, so the assertion discriminates.
- `test_single_move_scans_once_too` — K = 1; the count is 1 under both
  implementations, and stating it is what makes "once per call **regardless of
  K**" a constant rather than a coincidence.

The spy wrapper materializes `indices` into a list before delegating, so
spying cannot itself consume the iterable twice.

`_ManagerBase` already starts with an underscore, so the new subclass does not
trip `tests/test_collection_structure.py`'s inherited-test guard.

## Verification

Run from the repo root with the framework venv (`aitask_board` needs Textual):

1. **Existing manager contract, unedited** — the proof the optimization changed
   nothing observable:
   ```bash
   ~/.aitask/venv/bin/python -m unittest tests.test_board_manager_moves -v
   ```
   `test_k_tasks_land_in_input_order_with_k_writes` (exact indices `20+STEP,
   20+2*STEP, 20+3*STEP`), `test_append_only_batch_never_compacts` (`[10 + i *
   STEP for i in range(1, 6)]`), input ordering, write counts and
   `test_duplicate_names_resolve_once` must all pass **with no edits**. **If any
   of those assertions has to move, stop** — that is a real behavioural delta.

2. **Pure-module arithmetic:**
   ```bash
   ~/.aitask/venv/bin/python -m unittest tests.test_board_ordering -v
   ```

3. **Keyboard-level flip table, unedited:**
   ```bash
   ~/.aitask/venv/bin/python -m unittest tests.test_board_movement
   ```

4. **Prove the new guard can fail (negative control, manual, no `git checkout`):**
   temporarily restore the old `index_for_append`-per-task loop in
   `move_tasks_to_column`, re-run
   `~/.aitask/venv/bin/python -m unittest tests.test_board_manager_moves.MoveTasksToColumnScalingTests`
   and confirm it **exits 1** naming
   `test_batch_scans_the_destination_once` (expected 1 call, got 5). Then undo
   only that edit. A guard that has never been seen red proves nothing.

5. **Whole suite** — read only the last line for the verdict:
   ```bash
   bash tests/run_all_python_tests.sh
   ```

## Risk

### Code-health risk: low
- None identified. The change is two files, one method body and one added pure
  function in the module already declared the arithmetic home; the replaced
  arithmetic is provably identical for every accepted input shape, and the
  existing manager/flip-table tests pin the resulting state unedited. The one
  shape-level hazard — `zip` silently truncating if the helper ever returned
  fewer than `k` values — is closed by `test_returns_exactly_k_values` inside
  this plan rather than deferred.

### Goal-achievement risk: low
- None identified. The task states the target arithmetic, the exact expected
  indices, and the acceptance signal (existing tests pass unedited + a
  call-count guard); all three are covered above.

## Step 9 — Post-Implementation

Current-branch mode: no worktree or task branch to merge or clean up. Step 9
runs the gate orchestrator (`risk_evaluated` is this task's active gate), then
`./.aitask-scripts/aitask_archive.sh 1369` and `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Exactly the plan, no deviations in shape.
  - `.aitask-scripts/lib/board_ordering.py` — added `indices_for_append_run(indices, k)`
    between `index_for_append` and `index_for_prepend` (the append family). One
    `index_for_append` call, then `[start + i * STEP for i in range(k)]`;
    `[]` for `k <= 0`.
  - `.aitask-scripts/board/aitask_board.py` — `TaskManager.move_tasks_to_column`
    now computes the whole run from one destination scan and zips it against
    the resolved tasks. Docstring gained a paragraph stating the O(N + K) cost
    and why the closed form is valid (each appended value is the new maximum).
  - `tests/test_board_ordering.py` — `IndicesForAppendRunTests`, 7 tests.
  - `tests/test_board_manager_moves.py` — `MoveTasksToColumnScalingTests`, 3
    tests (65 insertions, **0 deletions** — no existing assertion moved).

- **Deviations from plan:** One addition beyond the planned test list:
  `test_refused_batch_never_scans` (a refused all-or-nothing batch performs no
  arithmetic at all), and `test_run_is_strictly_ascending_and_past_every_input`
  / `test_negative_column_appends` in the pure-module class. All additive; the
  planned tests were all written as specified.

- **Issues encountered:** None. The equivalence held on first run — the
  oracle test (`test_matches_iterated_index_for_append`, which rebuilds the run
  by iterating the superseded `index_for_append` + `append` formulation) passed
  across all six index shapes × k∈1..5, including the duplicate-value shape
  `[10, 10, 10]` and the negative-index shape.

- **Key decisions:**
  - *Named helper in `board_ordering`, not open-coded arithmetic in the
    manager.* The module docstring already declares itself the arithmetic home
    and precedents this exact situation with `indices_between` (which sits
    there for t1243_11 with no production caller). The helper's docstring
    carries a `Reuse` section naming t1243_11's block moves explicitly, per
    user direction — the forward pointer lives in the code, and **no file under
    `aitasks/t1243/` was touched**.
  - *Call-count spy, not wall-clock timing.* A timing assertion would be flaky
    in the shared parallel suite (`-n 4 --dist loadfile`). The spy patches
    `BO.index_for_append`; because `aitask_board` does `import board_ordering`
    and calls through the module attribute, one patch intercepts both the
    manager's call and the one inside the helper.
  - *`zip` over `enumerate`.* Safe only because the helper is total for
    `k >= 1` and `tasks` is non-empty past the early-return — so
    `test_returns_exactly_k_values` is load-bearing, not decorative: a short
    return would silently skip writes rather than raise.

- **Verification performed:**
  - `~/.aitask/venv/bin/python -m unittest tests.test_board_manager_moves` — 45 pass,
    file's pre-existing assertions **unedited** (`git diff --stat` shows
    insert-only).
  - `tests.test_board_ordering` — 45 pass. `tests.test_board_movement`
    (FLIP_TABLE) — 24 pass, 2 skipped, file untouched.
  - **Negative control (guard proven red).** The old
    `index_for_append`-per-task loop was temporarily restored in
    `move_tasks_to_column` (single mutation, restored with Edit — no
    `git checkout`); `MoveTasksToColumnScalingTests` then exited **1** with
    `AssertionError: 5 != 1` on `test_batch_scans_the_destination_once`, and
    the other two tests still passed. Restored and re-run green.
  - `bash tests/run_all_python_tests.sh` — `PYTHON SUITE: PASSED
    (runner=pytest, exit=0)`; 3299 passed / 2 skipped in the parallel lane plus
    2 passed in the serial carve-out.

- **Upstream defects identified:** None.

- **Concurrency note (not a code defect, but it cost a history repair):** an
  unrelated concurrent **t1409** session was editing
  `.aitask-scripts/aitask_gate.sh`, `lib/gate_ledger.py`,
  `lib/gate_orchestrator.py`, `aidocs/gates/*` and
  `tests/test_gate_orchestrator.sh` in the same worktree. The index was
  verified empty immediately before staging, but that session ran
  `git add` **and** `git commit` inside the window, so commit `f49d3ddd2
  "bug: … (t1409)"` swept up all four t1369 paths — leaving no `(t1369)`
  commit for `aitask_issue_update.sh` / archival to find, and tagging foreign
  code as t1409.

  Repaired **with user authorization** (the commit was unpushed and the t1409
  session confirmed idle): `git reset --mixed HEAD~1` (never `git revert` —
  that would have reverted the worktree), then two pathspec-limited commits —
  `cc04fbb69` re-creating t1409 from its preserved `%B` message, original
  author date restored via `--date`, and `a3f0494a3` for t1369.
  `git diff f49d3ddd2 HEAD` is **empty**, so the split is content-identical to
  the mixed commit; nothing was lost or altered.

  *Lesson for the next agent in a shared worktree:* checking `git diff --cached`
  is necessary but **not sufficient** — a concurrent session can stage and
  commit between the check and your own `git add`. Prefer
  `git commit -- <paths>` (pathspec-limited, ignores the rest of the index)
  over `git add` + `git commit`, and re-read `git log -1` afterwards to confirm
  your commit is the one that landed.

- **Timing note — the optimization is no longer pre-emptive.** t1243_7
  (`8b0e63a3e "feature: Add bulk move-to-column command to the board"`) landed
  during this session, one commit before t1369. `aitask_board.py:7762` now
  calls `move_tasks_to_column` with the full marked-task selection, so the K>1
  path this task de-superlinearized is reachable from the board's `m` command
  today rather than only after a future child. The full test suite and the
  t1369 tests were re-run against that new HEAD — 90 tests green.
