---
Task: t1377_4_column_merge_engine.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: aitasks/t1377/t1377_1_*.md, aitasks/t1377/t1377_2_*.md, aitasks/t1377/t1377_3_*.md, aitasks/t1377/t1377_5_*.md, aitasks/t1377/t1377_6_*.md
Archived Sibling Plans: aiplans/archived/p1377/p1377_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# p1377_4 — column merge engine + rename migration

## Goal

`TaskManager.merge_columns(source_ids, dest_id)` — N→1, headless-first so it is
fully testable before t1377_5's dialog exists. Plus a latent-bug fix on the same
path.

## Steps

### 1. `merge_columns(source_ids, dest_id) -> MergeResult`

Validate **all** inputs before the first write: unknown id, `dest in sources`,
duplicate sources, empty sources → refuse and write nothing.

#### Pass filenames, not `Task` objects — the trap

`get_column_tasks(col_id)` returns `list[Task]`. `move_tasks_to_column` routes
through `_resolve_parents`, which does `self.task_datas.get(name)` against a
`dict[str, Task]` **keyed by filename**. Handing it `Task` objects makes every
lookup return `None` → the whole batch is refused `not_a_parent_task` → **nothing
is written**. A silent no-op merge, not a crash.

```python
names = [t.filename for t in self.get_column_tasks(src)]
result = self.move_tasks_to_column(names, dest_id)
```

The asymmetry that hides this: `update_column`'s rename path iterates
`get_column_tasks()` and assigns `task.board_col` **directly**, never touching
`_resolve_parents` — so the `Task`-object shape is correct *there* and wrong *here*.

Process sources in `column_order` order → deterministic destination sequence. Then
drop each source from `columns` + `column_order`, prune its
`settings.collapsed_columns` entry, `save_metadata()`.

Members get **fresh appended** indices via `index_for_append` — never their old
ones. That is the `boardidx` collision answer, and it is why merge must not copy
`delete_column`'s flat `board_idx = 0`.

**Never call `respace_column` from this path.** Appending past the destination
maximum is unbounded and cannot exhaust an interval;
`tests/test_board_movement.py` ships a `respace_after_move` negative control that
fails if a movement path respaces.

### 2. `unordered` semantics — explicit

`unordered` is **synthetic**: absent from both `columns` and `column_order`,
rendered only as a lane for tasks with no `boardcol`, hand-injected wherever a
picker needs it.

- **Destination: allowed** — `move_tasks_to_column(names, "unordered")` is exactly
  what `delete_column` already does.
- **Source: allowed, config-removal skipped.** "Empty the inbox into Backlog" is a
  real operation, and there is no config entry to remove. The removal must be
  **conditional** — a blind `column_order.remove("unordered")` raises `ValueError`.

### 3. Partial-merge contract — NOT transactional

`MoveResult`'s all-or-nothing guarantee covers **input resolution** only; it says
nothing about I/O. `merge_columns` writes one file per member and calls
`save_metadata()` last, so an `OSError` / full disk / `SIGINT` mid-loop leaves a
**partial merge**. Per-file writes are atomic (`Task.save` → `atomic_write_text`), so
no file is corrupt — but the multi-file operation is not. Match the framework's
non-transactional model; make the partial state safe, self-describing, recoverable:

1. **Ordering is the safety property.** Task writes first, config removal **last**.
   A failure leaves the source column present holding its unmoved members — never
   tasks pointing at a column that no longer exists. Config-first would orphan them
   into a lane that renders nowhere.
2. **Do not remove a source whose move did not fully succeed.** Catch `OSError` per
   source, record it, skip that source's config removal. Clean sources still go.
3. **Distinct field — do not overload `refused`.** `MoveResult`'s docstring
   guarantees *"`refused` non-empty always means NOTHING was written"*; putting write
   failures there makes that invariant a lie for every existing consumer.

   ```python
   @dataclass(frozen=True)
   class MergeResult:
       merged: tuple[str, ...] = ()
       failed: tuple[tuple[str, str], ...] = ()     # (filename, reason)
       sources_removed: tuple[str, ...] = ()
       refused: tuple[tuple[str, str], ...] = ()    # input validation only
       @property
       def complete(self) -> bool: return not (self.failed or self.refused)
   ```
4. **Recovery = re-run, and it converges.** An already-moved member is no longer in
   the source, so a second run moves only the remainder and then removes the
   now-empty source. Document this idempotence in the docstring as the retry
   contract — it is what makes "leave it partial" an acceptable answer.
5. **t1377_5 must branch on `complete`** — partial gets a warning-severity toast
   naming counts and the retry, never a bare "Merged".

### 4. Fix `update_column`'s rename path

It migrates `column_order` and every member's `boardcol` but **not**
`settings.collapsed_columns` — a rename orphans the collapsed entry. Dead in the UI
today (`_handle_column_edit_result` passes `col_id` twice); t1377_5 makes it live.

## Composite group collapse keys — check, don't assume

`t1243_10_group_collapse_and_filtering` introduces `settings.collapsed_groups`
holding composite `"<col>/<slug>"` keys, whose **column half** must be re-pointed
on a merge and rewritten on a column rename. **The order between that task and this
one is undecided** — both are live.

Before implementing, grep for `collapsed_groups` in
`.aitask-scripts/board/aitask_board.py` and `lib/`:

- **Present** (t1243_10 landed first) -> this task owns the integration. Re-point
  the column half of every affected key in both `merge_columns` and the fixed
  `update_column`, applying t1243_10's coalesce rule ("destination key wins if it
  already exists; otherwise the arriving key's state is adopted under the
  destination name"). Merging two columns can collide two same-slug groups into one
  `(column, slug)` identity — that is the coalesce case. Read
  `aiplans/archived/p1243/p1243_10_*.md` for the exact rule, and add tests.
- **Absent** -> do nothing extra; t1243_10 carries a sibling note instructing it to
  extend `merge_columns` / `update_column` when it lands after this task.

## Tests — `tests/test_board_column_manage.py`

Patch `B.TASKS_DIR` / `B.METADATA_FILE`, no Pilot (per
`tests/test_board_manager_moves.py`).

| Case | Assertion |
|---|---|
| **real call path** | drive `merge_columns` end-to-end; assert the **re-read** `boardcol` values and destination member set changed — not just the returned object |
| **propagation** | feed one bad source; assert the inner refusal **reaches the caller**. `MoveResult.ok` is `not refused`, so it surfaces the `Task`-object bug *if* propagated — the failure mode to guard is a `merge_columns` that **swallows** the per-source result and reports its own success |
| N→1 | every member's `boardcol` is the destination; indices distinct + ascending; relative order within each source preserved; sources gone from **both** lists |
| `unordered` source | config-removal skipped, no `ValueError`, tasks move |
| `unordered` destination | tasks land, nothing removed from config |
| collapsed state | collapsed **source** entry removed; collapsed **destination** stays collapsed |
| refusals | unknown id / `dest in sources` / empty sources each assert a byte-identical tree snapshot |
| **partial recovery** | inject `OSError` on the Nth `reload_and_save_board_fields` (the `_apply_mutation` style in `test_board_movement.py`): (a) members 1..N-1 moved, rest not; (b) failing source **still present** in both lists; (c) `complete is False` and `failed` names the file; (d) **a second run with the injection removed completes the merge** and only then removes the source |
| rename migration | collapsed entry migrated, **with a negative control** reverting only the migration line and showing the test fail |

Frozen tables: `FLIP_TABLE` (`test_board_movement.py`) stays green **unedited**.
`EXPECTED_CALL_SITES` (`test_board_persistence_seam.py`) — `merge_columns` composes
`move_tasks_to_column` and adds **no** new `reload_and_save_board_fields` call site;
assert that. If the implementation drifts to a direct call, edit the table in the
same commit.

## Verification

```bash
bash tests/run_all_python_tests.sh    # read ONLY the last line
```

## Coordination

`t1369_board_batch_move_linear_index_arithmetic` (Ready) notes
`move_tasks_to_column` is O(K × (N+K)); this merge is its first large-K consumer. K
is bounded by one column's task count → a perf note, not a correctness gate.
Re-check if t1369 lands first.

`aitask_board.py` is edited by other in-flight tasks. Re-read before editing, grep
for symbols rather than line numbers, stage explicit paths, never `git stash` /
`git add -A`.

## Notes for sibling tasks

*(fill in at Step 8 — record `MergeResult`'s final shape and the exact partial-merge
reporting contract t1377_5 must consume.)*
