---
Task: t1377_4_column_merge_engine.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: aitasks/t1377/t1377_1_*.md, aitasks/t1377/t1377_2_*.md, aitasks/t1377/t1377_3_*.md, aitasks/t1377/t1377_5_*.md, aitasks/t1377/t1377_6_*.md
Archived Sibling Plans: aiplans/archived/p1377/p1377_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-06 10:38
---

# p1377_4 — column merge engine + rename migration

## Context

Deliverable 2 of t1377 adds a column-management dialog to `ait board`. Add / edit /
delete / reorder / collapse all exist already — **merge does not**. This child builds
the merge engine **headless-first**, so it is fully testable before any dialog exists
(t1377_5 is the UI). It also fixes a latent bug on the same code path: `update_column`'s
rename migrates `column_order` and every member's `boardcol` but orphans the column's
`settings.collapsed_columns` entry.

## Goal

`TaskManager.merge_columns(source_ids, dest_id)` — N→1, plus the `update_column`
collapsed-state fix. No UI in this task.

---

## Plan re-verification (2026-08-06)

Every anchor below was re-checked against current `main`. **All of the plan's original
claims still hold**; three things drifted and are folded into the steps.

**Confirmed unchanged:**

| Claim | Where | Status |
|---|---|---|
| `get_column_tasks(col_id) -> list[Task]` | `aitask_board.py:1320` | ✅ |
| `_resolve_parents` does `task_datas.get(name)` keyed by **filename** | `:1648-1665` | ✅ the `Task`-object trap is real and **silent** |
| `MoveResult` docstring: *"`refused` non-empty always means NOTHING was written"* | `:1011-1012` | ✅ must not be overloaded |
| `update_column` rename does **not** touch `collapsed_columns` | `:1800-1817` | ✅ bug confirmed |
| Rename path dead in UI — `_handle_column_edit_result` passes `col_id` twice | `:9634` | ✅ |
| `delete_column` flattens `board_idx = 0`, prunes collapsed | `:1841-1855` | ✅ |
| `respace_column` — "never from a movement path" + `respace_after_move` negative control | `:1780-1786`, `test_board_movement.py:580` | ✅ |
| `EXPECTED_CALL_SITES` frozen AST table | `test_board_persistence_seam.py:495-502` | ✅ |
| `collapsed_groups` / `boardgroup` | grep of `board/` + `lib/` | **absent** |
| `tests/test_board_column_manage.py` | — | does not exist (new file) |

**Drift 1 — t1369 has LANDED** (archived; commit `a3f0494a3`). `move_tasks_to_column`
now computes the whole append run from **one** scan via
`board_ordering.indices_for_append_run`, so the batch is O(N+K), not O(K×(N+K)).
Consequences: the plan's `## Coordination` perf caveat is **resolved** — merge is no
longer a large-K concern — and the mechanism is `indices_for_append_run` (inside
`move_tasks_to_column`), not a per-member `index_for_append`. The *effect* the plan
relies on is unchanged: members get fresh appended, distinct, ascending indices.

**Drift 2 — t1377_3 added `_reconcile_external_columns`, called from `save_metadata()`**
(`:1090-1156`; it is the immediately preceding sibling and the current HEAD commit).
`merge_columns` removes source columns and then calls `save_metadata()`, so the
reconciler runs on every merge. Its table row *"known=yes, in `self.columns`=no →
board DELETED it, leave gone"* (`:1113`, enforced by the `cid in self._known_col_ids`
skip at `:1135-1136`) is **exactly what makes merge's source removal stick** — a source
id was loaded by `load_metadata`, so it is in `_known_col_ids` and is never re-added
from disk. This interaction did not exist when the plan was written, it is load-bearing,
and it is untested for merge → **new test below**. Note `unordered` is synthetic and
therefore never in `_known_col_ids`, which is consistent with skipping its config removal.

**Drift 3 — `snapshot()` covers `board_config*.json`, not just `*.md`**
(`tests/lib/board_fixture.py:595-602`). Two consequences: a refusal's byte-identical
snapshot assertion **already catches a spurious `save_metadata()`** (so refusal must
return before *any* write, config included), and `collapsed_columns` persists to
`board_config.local.json` (USER_KEYS) while `columns`/`column_order` go to
`board_config.json` (PROJECT_KEYS) — assert collapsed state via
`manager.collapsed_columns`, not the project file.

**t1243_10 / t1243_11 are both un-landed**, so every conditional branch in the original
plan collapses to the simple arm: do nothing extra, and record the sibling notes.

---

## Steps

### Pre-phase (risk mitigations)

Both run in `tests/test_board_column_manage.py`, before the merge engine is written —
they characterize the code the engine sits beside, so a later convergence refactor
cannot change it silently.

1. `[characterize_delete_column_drain]` Add a characterization test pinning
   `delete_column`'s **current** drain semantics against the fixture tree: after
   `delete_column("c0")`, every former member has `boardcol == "unordered"` **and**
   `board_idx == 0` (the flat tie t1243_11 §4 intends to replace), `"c0"` is gone from
   `columns` and `column_order`, and a collapsed `"c0"` entry is pruned from
   `manager.collapsed_columns`. Add a comment naming t1243_11 §4 as the task expected to
   change this expectation, so the failure is self-explaining when it fires.

2. `[pin_write_before_config_ordering]` Extend the `_ManagerBase` write-spy to record an
   ordered event log: append `("write", filename)` from the
   `reload_and_save_board_fields` wrapper and `("config", col_id)` from a spy on the
   source-removal point (or record `list(manager.column_order)` at each write). After a
   clean N→1 merge, assert that for **every** source, all of its member writes appear
   strictly before that source's config removal. This is the "ordering is the safety
   property" rule of §3.1 stated executably.

### 1. `merge_columns(source_ids, dest_id) -> MergeResult`

Validate **all** inputs before the first write — unknown id, `dest in sources`,
duplicate sources, empty sources → refuse and write nothing, **including no
`save_metadata()`** (Drift 3: the snapshot assertion sees config files).

#### Pass filenames, not `Task` objects — the trap

`get_column_tasks(col_id)` returns `list[Task]`. `move_tasks_to_column` routes through
`_resolve_parents`, which does `self.task_datas.get(name)` against a `dict[str, Task]`
**keyed by filename**. Handing it `Task` objects makes every lookup return `None` → the
whole batch is refused `not_a_parent_task` → **nothing is written**. A silent no-op
merge, not a crash.

```python
names = [t.filename for t in self.get_column_tasks(src)]
result = self.move_tasks_to_column(names, dest_id)
```

The asymmetry that hides this: `update_column`'s rename path iterates
`get_column_tasks()` and assigns `task.board_col` **directly**, never touching
`_resolve_parents` — so the `Task`-object shape is correct *there* and wrong *here*.

#### Source processing order — `unordered` has no position

Sources are processed in `column_order` order so the destination sequence is
deterministic. `unordered` is synthetic and **absent from `column_order`**, so a naive
`column_order.index(src)` raises `ValueError` on a mixed merge. **Rule: configured
columns first in `column_order` order, then `unordered` last** — it is the catch-all
lane, and sorting it last keeps the configured columns' relative order as the primary
sequence:

```python
order = self.column_order
srcs = sorted(source_ids,
              key=lambda c: order.index(c) if c in order else len(order))
```

Then drop each source from `columns` + `column_order`, prune its
`settings.collapsed_columns` entry, `save_metadata()`.

Members get **fresh appended** indices — never their old ones. That is the `boardidx`
collision answer, and it is why merge must not copy `delete_column`'s flat
`board_idx = 0`. The arithmetic is `move_tasks_to_column`'s own single-scan
`indices_for_append_run` (t1369); merge composes it and adds no index arithmetic.

**Never call `respace_column` from this path.** Appending past the destination maximum
is unbounded and cannot exhaust an interval; `tests/test_board_movement.py` ships a
`respace_after_move` negative control that fails if a movement path respaces.

### 2. `unordered` semantics — explicit

`unordered` is **synthetic**: absent from both `columns` and `column_order`, rendered
only as a lane for tasks with no `boardcol`, hand-injected wherever a picker needs it.

- **Destination: allowed** — `move_tasks_to_column(names, "unordered")` is exactly what
  `delete_column` already does.
- **Source: allowed, config-removal skipped.** "Empty the inbox into Backlog" is a real
  operation, and there is no config entry to remove. The removal must be **conditional**
  — a blind `column_order.remove("unordered")` raises `ValueError`.

### 3. Partial-merge contract — NOT transactional

`MoveResult`'s all-or-nothing guarantee covers **input resolution** only; it says
nothing about I/O. `merge_columns` writes one file per member and calls `save_metadata()`
last, so an `OSError` / full disk / `SIGINT` mid-loop leaves a **partial merge**.
Per-file writes are atomic (`Task.save` → `atomic_write_text`), so no file is corrupt —
but the multi-file operation is not. Match the framework's non-transactional model; make
the partial state safe, self-describing, recoverable:

1. **Ordering is the safety property.** Task writes first, config removal **last**. A
   failure leaves the source column present holding its unmoved members — never tasks
   pointing at a column that no longer exists. Config-first would orphan them into a
   lane that renders nowhere.

2. **⚠ The in-memory copy diverges from disk on a failed write — this is the trap that
   breaks naive recovery.** `reload_and_save_board_fields` (`aitask_board.py:336-344`)
   snapshots the **already-mutated** values, reloads from disk, re-applies them, and
   only then calls `self.save()`. So when the save raises `OSError`:

   - `task.board_col` is left at **`dest`** while the file on disk still says **`src`**;
   - the exception propagates out of `move_tasks_to_column`, so **no `MoveResult` is
     returned at all** — the per-source call yields nothing about which members landed;
   - `get_column_tasks` (`:1329`) filters on the **in-memory** `t.board_col`, so that
     task is now invisible in `src`.

   A same-manager retry would therefore skip it, find `src` "empty", and remove the
   source column — **orphaning a task onto a column that no longer exists**, precisely
   the outcome rule 1 exists to prevent.

   **Fix: on `OSError`, reconcile in-memory state back to disk before reporting.** Catch
   the exception around the per-source `move_tasks_to_column` call and re-read every
   member of that source from disk:

   ```python
   names = [t.filename for t in self.get_column_tasks(src)]   # BEFORE the call
   try:
       self.move_tasks_to_column(names, dest_id)
   except OSError as exc:
       moved, failed, gone = [], [], []
       for name in names:
           task = self.task_datas.get(name)
           if task is None:
               continue
           if not task.load():          # file vanished mid-merge: in-memory is
               gone.append(name)        # still at dest and CANNOT be trusted
               continue
           (moved if task.board_col == dest_id else failed).append(name)
       # first `failed` entry is the I/O casualty; the rest were never attempted
       # record; skip THIS source's config removal
   ```

   **`Task.load()` returning `False` is its own state, not a move.** The write path
   itself skips the save when the file is gone (`:337-338`), leaving the in-memory copy
   at `dest` — so a reload that also fails to load must **not** be read as "moved", or a
   deleted file would be counted a success. Record those separately
   (`("<name>", "file_missing")` in `failed`) rather than folding them into either bucket.

   **Attribute the failure precisely.** In source order, the first non-moved member is
   the one whose write raised; the remainder were never attempted. Report the first with
   the `OSError` text and the rest with a distinct `not_attempted` reason, so
   `MergeResult.failed` names the actual I/O casualty instead of blaming the whole tail.

   `Task.load()` is the same reload the write path already uses (`:337`) and is **not**
   a `reload_and_save_board_fields` call, so this adds **no** new call site and
   `EXPECTED_CALL_SITES` stays unedited. Deriving `moved` by post-hoc reload is also
   strictly more reliable than a return value the raising call never produced.

3. **Do not remove a source whose move did not fully succeed.** Per source, catch
   `OSError`, reconcile as above, record it, and skip that source's config removal.
   Clean sources are still removed.

4. **Metadata writes fail too — roll back the in-memory config.** `save_metadata`
   (`:1158-1169`) performs **two** separate writes (`save_project_config`, then
   `save_local_config` for the user-keys half that holds `collapsed_columns`) *after*
   the in-memory removal. An `OSError` from either leaves `self.columns`,
   `self.column_order` and `settings["collapsed_columns"]` already stripped of sources
   that are still on disk, and propagates out of `merge_columns` with no result. A
   same-manager retry then refuses every source as an unknown id.

   Snapshot the three structures immediately before the removal step and restore them if
   `save_metadata()` raises, then report the failure rather than raising:

   ```python
   before = (list(self.columns), list(self.column_order),
             list(self.collapsed_columns))
   try:
       ... remove sources ...; self.save_metadata()
   except OSError as exc:
       self.columns, self.column_order, self.collapsed_columns = (
           before[0], before[1], before[2])
       failed.append(("<metadata>", f"metadata_write_failed: {exc}"))
       sources_removed = ()
   ```

   `"<metadata>"` is a reserved sentinel in the `failed` tuple — never a real filename —
   so a caller can distinguish a task-write failure from a config-write failure. With
   the rollback, both a same-manager retry and a fresh manager see the sources present
   but empty, and converge by removing them.

5. **Distinct field — do not overload `refused`.** `MoveResult`'s docstring guarantees
   *"`refused` non-empty always means NOTHING was written"*; putting write failures
   there makes that invariant a lie for every existing consumer.

   ```python
   @dataclass(frozen=True)
   class MergeResult:
       merged: tuple[str, ...] = ()
       failed: tuple[tuple[str, str], ...] = ()     # (filename|"<metadata>", reason)
       sources_removed: tuple[str, ...] = ()
       refused: tuple[tuple[str, str], ...] = ()    # input validation only
       @property
       def complete(self) -> bool: return not (self.failed or self.refused)
   ```

6. **Recovery = re-run, and it converges — on the same manager or a fresh one.** Rules 2
   and 4 are what make that true: after either failure class, in-memory state matches
   disk, so an already-moved member is genuinely absent from the source and an unmoved
   one is genuinely present. A second run moves only the remainder and then removes the
   now-empty source. Document this idempotence in the docstring as the retry contract,
   **naming both retry paths** — it is what makes "leave it partial" acceptable.

7. **t1377_5 must branch on `complete`** — partial gets a warning-severity toast naming
   counts and the retry, never a bare "Merged". A `"<metadata>"` failure means the tasks
   moved but the columns remain; word it as "tasks merged; column list not saved — retry".

### 4. Fix `update_column`'s rename path

It migrates `column_order` and every member's `boardcol` but **not**
`settings.collapsed_columns` — a rename orphans the collapsed entry. Dead in the UI
today (`_handle_column_edit_result` passes `col_id` twice); t1377_5 makes it live. The
fix touches `settings` only, so it adds **no** `reload_and_save_board_fields` call site.

### 5. Sibling notes (Step 8, `## Notes for sibling tasks`)

Both coordinating tasks are un-landed, so this plan records rather than integrates:

- **t1243_11 §4** — `merge_columns` is the **reference drain path** (fresh appended
  indices preserving relative order, via `move_tasks_to_column`); §4 should consume it
  rather than write a second re-index strategy for `delete_column`. Any shared helper
  must preserve this task's **non-transactional** contract (per-file atomic writes,
  config removal last, `MergeResult.failed`, convergent re-run) — a refactor must not
  introduce an all-or-nothing assumption a partial merge would violate.
- **t1243_10** — when `settings.collapsed_groups` lands with composite `"<col>/<slug>"`
  keys, its column half must be re-pointed by **both** `merge_columns` and the fixed
  `update_column`, applying t1243_10's coalesce rule. t1243_10 already carries the
  reciprocal note.
- **t1377_5** — record `MergeResult`'s final shape and the exact partial-merge reporting
  contract the dialog must consume.

---

## Tests — `tests/test_board_column_manage.py` (new)

Patch `B.TASKS_DIR` / `B.METADATA_FILE`, no Pilot — clone the `_ManagerBase` harness in
`tests/test_board_manager_moves.py:87-145` (`build_fixture_tree` + `mock.patch.object`,
write-spy on `B.Task.reload_and_save_board_fields`, `snapshot` / `diff_snapshots`).
`build_fixture_tree(..., settings={"collapsed_columns": [...]})` seeds collapsed state.
The write-spy patch point **is** the `OSError` injection seam.

| Case | Assertion |
|---|---|
| **real call path** | drive `merge_columns` end-to-end; assert the **re-read** `boardcol` values and destination member set changed — not just the returned object |
| **propagation** | feed one bad source; assert the inner refusal **reaches the caller**. `MoveResult.ok` is `not refused`, so it surfaces the `Task`-object bug *if* propagated — the failure mode to guard is a `merge_columns` that **swallows** the per-source result and reports its own success |
| N→1 | every member's `boardcol` is the destination; indices distinct + ascending; relative order within each source preserved; sources gone from **both** `columns` and `column_order` |
| `unordered` source | config-removal skipped, no `ValueError`, tasks move |
| `unordered` destination | tasks land, nothing removed from config |
| **mixed-source ordering** | merge `{c1, unordered, c0}` → `c2` in one call: no `ValueError`, and the destination sequence is `c0`'s members, then `c1`'s, then `unordered`'s — configured columns in `column_order` order, `unordered` last. Assert the full appended filename sequence, not just membership |
| collapsed state | collapsed **source** entry removed; collapsed **destination** stays collapsed (assert via `manager.collapsed_columns`) |
| refusals | unknown id / `dest in sources` / empty sources each assert a byte-identical tree snapshot — which also proves no `save_metadata()` fired (Drift 3) |
| **reconcile survival** (Drift 2) | after a merge, construct a **fresh** `TaskManager` over the same tmp tree and assert the merged-away source is absent from `columns` / `column_order` — i.e. `save_metadata()`'s `_reconcile_external_columns` did not resurrect it from disk |
| **partial recovery — same manager** | inject `OSError` on the Nth `reload_and_save_board_fields`: (a) members 1..N-1 moved on disk, rest not; (b) failing source **still present** in both lists; (c) `complete is False` and `failed` names the failing file; (d) **the in-memory `board_col` of the failed task reads `src`, not `dest`** — the divergence rule of §3.2, and the single assertion that catches a missing `task.load()` reconcile; (e) `get_column_tasks(src)` still lists it; (f) **retry on the SAME manager** with the injection removed completes the merge and only then removes the source |
| **partial recovery — fresh manager** | same injection, then build a **new** `TaskManager` over the same tree and retry: also converges. Run *both* — a fresh instance reloads from disk and would mask the stale-mutation bug entirely, so the fresh-manager case alone is not evidence |
| **failure attribution** | with the injection on member N of a 4-member source, `failed` names member N with the `OSError` text and members N+1.. with `not_attempted` — not one undifferentiated blob, and not the whole source |
| **vanished file during merge** | delete a member's file after `names` is captured but before its write, so `Task.load()` returns `False`: it is reported `file_missing` in `failed` and is **not** counted in `merged`, and the source is not removed |
| **metadata-write failure** | inject `OSError` at each of the two `save_metadata` write boundaries in turn (`save_project_config`, then `save_local_config`): (a) all task moves persisted; (b) `self.columns` / `self.column_order` / `collapsed_columns` **rolled back** to include the sources; (c) `complete is False` and `failed` carries the `"<metadata>"` sentinel; (d) `sources_removed` is empty; (e) retry on the same manager **and** on a fresh one both converge — sources empty, then removed |
| rename migration | collapsed entry migrated, **with a negative control** reverting only the migration line and showing the test fail |

Frozen tables: `FLIP_TABLE` (`test_board_movement.py`) stays green **unedited**.
`EXPECTED_CALL_SITES` (`test_board_persistence_seam.py`) — `merge_columns` composes
`move_tasks_to_column` and the `update_column` fix touches only `settings`, so **no** new
`reload_and_save_board_fields` call site is added; assert the table is unchanged. If the
implementation drifts to a direct call, edit the table in the same commit.

## Verification

```bash
bash tests/run_all_python_tests.sh    # read ONLY the last line for the verdict
```

## Coordination

`aitask_board.py` is edited by other in-flight tasks. Re-read before editing, grep for
symbols rather than line numbers, stage explicit paths, never `git stash` / `git add -A`.
(The working tree already carries unrelated modified files from a concurrent session.)

t1369's perf caveat is **resolved** — see Drift 1.

Step 9 (Post-Implementation) handles cleanup, archival, and merge.

## Risk

### Code-health risk: medium
- `merge_columns` becomes a **second column-drain path** alongside `delete_column`, with different index arithmetic (fresh appended vs flat `board_idx = 0`). The convergence is owned by t1243_11 §4, which has not landed — so this is deliberate transitional duplication in one class · severity: medium · → mitigation: inline pre-phase characterize_delete_column_drain
- The **non-transactional** partial-merge contract is subtle and encoded mostly in prose + one test; a later refactor that folds merge and delete onto a shared helper could silently introduce an all-or-nothing assumption a partial merge violates · severity: medium · → mitigation: inline pre-phase pin_write_before_config_ordering
- **In-memory/disk divergence on a failed write** is the sharpest edge in this task: `reload_and_save_board_fields` leaves `task.board_col` at the destination when the save raises, and `get_column_tasks` filters on that in-memory value — so a recovery path that does not reconcile back to disk silently orphans a task onto a removed column. Handled explicitly (§3.2, §3.4) and pinned by the same-manager recovery and metadata-failure tests, but it is failure-path code with no live caller until t1377_5, so it is exercised only by those tests · severity: medium · → mitigation: covered by the core test table (same-manager + fresh-manager recovery, both metadata write boundaries)

### Goal-achievement risk: low
- The deliverable is headless-only and its real consumer (t1377_5's dialog) does not exist yet, so "does it work" is judged by tests rather than by using the board. Bounded — headless-first is the task's explicit scope, and every API anchor was re-verified against source · severity: low · → mitigation: none needed

### Planned mitigations
- timing: pre-phase | name: characterize_delete_column_drain | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (second column-drain path) | desc: Characterization test pinning delete_column's current flat board_idx=0 drain semantics so t1243_11 §4's convergence changes it visibly, not silently.
- timing: pre-phase | name: pin_write_before_config_ordering | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 2 (non-transactional contract encoded in prose) | desc: Ordered event-log assertion that every source's member writes precede that source's config removal, stating §3.1's safety rule executably.

**Reassessment after inlining and the failure-semantics review:** both mitigations are
additive tests in a file this plan already creates; they make the code-health risks
*detectable* but do not remove the structural duplication. The plan review additionally
closed a real correctness hole in the recovery path (in-memory/disk divergence and the
unrolled-back metadata write), which raised the explicit failure-path surface while
removing the silent-orphan outcome. Net: code-health stays **medium**, goal-achievement
stays **low** — the added rules are contained and each is pinned by a named test.
