---
priority: high
effort: medium
depends: [t1377_3]
issue_type: feature
status: Implementing
labels: [aitask_board, board_columns]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1243
created_at: 2026-08-04 09:55
updated_at: 2026-08-06 08:54
---

## Context

Deliverable 2 of t1377 adds a column-management dialog to `ait board`. Add / edit /
delete / reorder / collapse all exist already — **merge does not**. This child
builds the merge engine headless-first, so it is fully testable before any dialog
exists (t1377_5 is the UI).

It also fixes a latent bug on the same code path.

## Key Files to Modify

- **`.aitask-scripts/board/aitask_board.py`** — add `MergeResult` and
  `TaskManager.merge_columns`; fix `update_column`'s rename path.
- **`tests/test_board_column_manage.py`** — NEW.

## Reference Files for Patterns

- `aitask_board.py` `TaskManager.move_tasks_to_column` — the batch move to compose
  (K distinct ascending indices via `board_ordering.index_for_append`, input order
  preserved, destination-only writes).
- `aitask_board.py` `MoveResult` — the report shape and its documented invariant.
- `aitask_board.py` `TaskManager.delete_column` — already prunes
  `settings.collapsed_columns`; note it flattens `board_idx` to `0` for every
  reassigned task, which merge must **not** do.
- `tests/test_board_manager_moves.py` — manager-level tests without a Pilot
  (patch `B.TASKS_DIR` / `B.METADATA_FILE`); every refusal case asserts a
  byte-identical tree snapshot.
- `tests/test_board_movement.py` — the `_apply_mutation` injection style used for
  the fault-injection test below, and the `respace_after_move` negative control.

## Implementation Plan

### 1. `merge_columns(source_ids, dest_id)`

All-or-nothing on **inputs**: resolve and validate every id first (unknown id,
`dest in sources`, duplicate sources, empty sources) and write nothing on refusal.

**Pass filenames, not `Task` objects — this is the trap.** `get_column_tasks(col_id)`
returns `list[Task]`, but `move_tasks_to_column` routes through `_resolve_parents`,
which does `self.task_datas.get(name)` against a `dict[str, Task]` keyed by
**filename**. Handing it `Task` objects makes every lookup return `None`, so the
whole batch is refused as `not_a_parent_task` and **nothing is written** — a silent
no-op merge, not a crash. So:

```python
names = [t.filename for t in self.get_column_tasks(src)]
result = self.move_tasks_to_column(names, dest_id)
```

Note the asymmetry that makes this easy to get wrong: `update_column`'s rename path
iterates `get_column_tasks()` and assigns `task.board_col` **directly**, never
touching `_resolve_parents` — so the `Task`-object shape is correct *there* and
wrong *here*.

Process sources in `column_order` order so the destination sequence is
deterministic. Then drop each source from `columns` and `column_order`, prune its
`settings.collapsed_columns` entry, and `save_metadata()`.

Members of A get **fresh appended** indices in B, never their old ones — that is the
`boardidx` collision answer. **Never call `respace_column` from this path**:
appending past the destination maximum is unbounded and cannot exhaust an interval,
and `tests/test_board_movement.py` ships a `respace_after_move` negative control
that fails if a movement path respaces.

### 2. `unordered` semantics — define them explicitly

`unordered` is a **synthetic** column: absent from both `columns` and
`column_order`, existing only as a rendered lane for tasks with no `boardcol`, and
hand-injected wherever a picker needs it.

- **As destination: allowed** — `move_tasks_to_column(names, "unordered")` is
  exactly what `delete_column` already does.
- **As source: allowed, with the config-removal step skipped.** "Empty the inbox
  into Backlog" is meaningful, and there is no config entry to remove. The removal
  must be **conditional** — a blind `column_order.remove("unordered")` raises
  `ValueError`.

### 3. Partial-merge contract — the merge is NOT transactional

`MoveResult`'s all-or-nothing guarantee covers **input resolution** only. It says
nothing about I/O. `merge_columns` writes one task file per member and calls
`save_metadata()` at the end, so an `OSError`, a full disk or a `SIGINT` between
writes leaves a **partially merged** state. Per-file writes are atomic (`Task.save`
-> `atomic_write_text`), so no file is ever corrupt — but the multi-file operation
is not. Match the framework's existing non-transactional model rather than inventing
a journal, and make the partial state safe, self-describing and recoverable:

1. **Ordering is the safety property.** Task writes first, config removal **last**.
   A failure then leaves the source column still present holding its unmoved
   members — never tasks pointing at a column that no longer exists. Removing the
   config first would orphan them into a lane that renders nowhere.
2. **Do not remove a source whose move did not fully succeed.** Per source, catch
   `OSError` from the write loop, record it, and skip that source's config removal.
   Sources that completed cleanly are still removed.
3. **Report it in a distinct field — do not overload `refused`.** `MoveResult`'s
   docstring guarantees *"`refused` non-empty always means NOTHING was written"*;
   stuffing write failures there makes that invariant a lie for every existing
   consumer. Return a separate `MergeResult`:

   ```python
   @dataclass(frozen=True)
   class MergeResult:
       merged: tuple[str, ...] = ()
       failed: tuple[tuple[str, str], ...] = ()      # (filename, reason)
       sources_removed: tuple[str, ...] = ()
       refused: tuple[tuple[str, str], ...] = ()     # input validation only
       @property
       def complete(self) -> bool: return not (self.failed or self.refused)
   ```
4. **Recovery is re-running the merge, and that is convergent.** A member already
   moved is no longer in the source column, so a second run moves only the remainder
   and then removes the now-empty source. Document this idempotence in the method
   docstring as the retry contract — it is what makes "leave it partial" acceptable.
5. **The UI must never imply success on a partial merge** (enforced in t1377_5):
   complete -> `notify("Merged N tasks into <dest>")`; partial -> `severity="warning"`
   naming counts and the retry.

### 4. Fix `update_column`'s rename path

It migrates `column_order` and every member's `boardcol`, but **not**
`settings.collapsed_columns` — a rename orphans the collapsed entry. The path is
currently dead in the UI (`_handle_column_edit_result` passes `col_id` twice); the
dialog in t1377_5 makes it live, so fix it here.

### Composite group collapse keys — check, don't assume

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

### Column-drain semantics — shared with `t1243_11`, order undecided

`merge_columns` drains a column and removes it — the **same operation shape** as
`delete_column`, and `t1243_11_group_formation_and_block_moves` has two sections
that overlap it directly. Both chains are live; neither is a prerequisite.

**§4 `delete_column` tidy-up.** t1243_11 wants to replace `delete_column`'s flat
`board_idx = 0` (which mass-ties every task on arrival in `unordered`) with
contiguous indices preserving relative order and group runs. This task already
produces that property for merge, via `index_for_append` per member. So:

- **If `t1243_11` landed first**, read how it re-indexed `delete_column` and
  **reuse that helper** rather than adding a second drain strategy. Two mass-move
  implementations with different index arithmetic in the same class is the outcome
  to avoid.
- **If it has not**, implement merge as planned and record in this task's
  `## Notes for sibling tasks` that `merge_columns` is the reference drain path, so
  t1243_11 §4 can consume it instead of writing its own.

**§3 coalesce-on-move.** Group identity is `(column, slug)`, so merging column A
into B where both hold group `perf_work` coalesces **automatically by derivation**
— and t1243_11 requires a **notify** ("merged into existing group 'perf work'"),
not a refusal. A column merge is a mass move that triggers exactly this. If
`boardgroup` exists when this task runs, emit that notify (aggregated once per
coalesced group, not per task) and hand collapse-key combination to t1243_10's
rule. If it does not exist, ignore — there are no groups to coalesce.

## Verification Steps

```bash
bash tests/run_all_python_tests.sh     # read ONLY the last line for the verdict
```

Tests in `tests/test_board_column_manage.py` (patch `B.TASKS_DIR` /
`B.METADATA_FILE`, no Pilot):

- **The real merge call path, asserted on on-disk effect.** Drive `merge_columns`
  end-to-end and assert the destination's member set and the **re-read** `boardcol`
  values actually changed — not just the returned object. `MoveResult.ok` is
  `not refused`, so it does surface the `Task`-object bug **if** the inner result is
  propagated; the failure mode to guard is a `merge_columns` that **swallows** the
  per-source `MoveResult` and returns its own success. Test both halves: feed one
  bad source and assert the refusal reaches the caller, and on the happy path assert
  `len(get_column_tasks(dest))` grew by the expected count with the sources emptied.
- N->1 merge: every member's `boardcol` is the destination, indices distinct and
  ascending, relative order within each source preserved, sources gone from **both**
  `columns` and `column_order`.
- `unordered` as source (config-removal skipped, no `ValueError`, tasks move) and as
  destination (tasks land, nothing removed from config).
- Collapsed state: a collapsed source's entry is removed; a collapsed **destination**
  stays collapsed.
- Refusal cases (unknown id, `dest in sources`, empty sources) each assert a
  byte-identical tree snapshot.
- **Partial-merge recovery** via an injected `OSError` on the Nth
  `reload_and_save_board_fields`: assert (a) members 1..N-1 moved on disk and the
  rest not, (b) the failing source **still present** in both `columns` and
  `column_order`, (c) `result.complete` is `False` and `result.failed` names the
  file, (d) a **second run with the injection removed completes the merge** and only
  then removes the source — the convergence claim, tested rather than asserted.
- Rename migrates the collapsed entry, **with a negative control** that reverts only
  the migration line and shows the test failing.
- `FLIP_TABLE` in `tests/test_board_movement.py` stays green **unedited**.
- `EXPECTED_CALL_SITES` in `tests/test_board_persistence_seam.py`: `merge_columns`
  composes `move_tasks_to_column` and adds **no** new
  `reload_and_save_board_fields` call site. If the implementation drifts to a direct
  call, that AST-parsed frozen table must be edited in the same commit.

## Coordination

`t1369_board_batch_move_linear_index_arithmetic` (Ready) notes that
`move_tasks_to_column` is O(K x (N+K)). This merge is its first large-K consumer.
K is bounded by one column's task count, so this is a perf note, not a correctness
gate — but re-check against t1369's result if it lands first.

`aitask_board.py` is edited by other in-flight tasks (t1243_4 was mid-flight during
planning). Re-read the file before editing, grep for symbols rather than trusting
line numbers, stage explicit paths, and never `git stash` / `git add -A` here.
