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

   **⚠ "No exception" does NOT mean "written" — verify every source's move against
   disk, not only the raising ones.** `reload_and_save_board_fields` returns early and
   **silently** when its reload fails, and `move_tasks_to_column` then calls
   `_mark_written` and reports that task in `MoveResult.moved` anyway. So a member can
   fail to land with no `OSError` at all, and a merge that trusted the nominal return
   would count it merged and **drain the source**.

   `Task.load()` returns `False` on *any* read exception, not just a missing file — a
   permission or decode error on a file that still exists takes the same path (and wipes
   `self.metadata`, so the in-memory copy cannot be asked about it either). That is the
   harmful variant: the file survives holding `boardcol: <src>` while the source column
   is removed, stranding it on a column that renders nowhere.

   Therefore classify **after every source's move**, raising or not, by re-reading each
   member from disk — independent ground truth, rather than asking the same in-memory
   objects the failed write already corrupted. Report a non-landed member as
   `file_missing` (unreadable/absent) or `not_written` (present but unchanged), and
   **drain a source only when every member is confirmed landed and nothing raised.**
   Recovery still converges: a vanished member's wiped metadata no longer claims the
   source, so the retry sees only real members and completes.

   **⚠ Deleted and unreadable are different states, and the difference decides the
   RETRY.** For a deleted file there is nothing left to orphan, so converging by draining
   is right. For a file that still exists but cannot be read, the failed `Task.load()`
   wiped its metadata — so `get_column_tasks(src)` no longer lists it, the source looks
   **empty**, and the retry drains it while the file on disk still names it. The retry is
   where the orphan actually lands, and a fresh manager is no safer: `load_tasks` drops an
   unreadable file as a phantom stub (`metadata == {}`), so it never appears at all.

   So unreadability must be **tracked as state**, not inferred per-attempt:
   - `Task.load()` records `load_ok` (`__init__` discards its return value, and afterwards
     a failed load is indistinguishable from an empty stub — both leave `metadata == {}`).
   - `load_tasks` populates `TaskManager.unreadable_files`, so a **fresh** manager
     re-derives the hazard instead of inheriting nothing.
   - `merge_columns` removes **no** column while that set is non-empty — an unreadable
     file may claim any column, so no source can be proven empty — and reports
     `("<unverifiable>", …)`. The block lifts by itself once the file parses again.

   **Attribute the failure precisely, and derive the boundary from SOURCE ORDER.** In
   `names` order, the first member that did not move is the one whose write raised; the
   remainder were never attempted. Report the first with the `OSError` text and the rest
   as `not_attempted`, so `MergeResult.failed` names the actual I/O casualty instead of
   blaming the whole tail.

   **⚠ The boundary must be computed over `names`, not over a list with the vanished
   members filtered out.** If the casualty's file also disappeared, filtering it out
   first drops it from the list and promotes the next — untouched — member to position 0,
   which then gets reported as the I/O casualty. With a three-member source failing on
   member 2, member 3 is blamed for an error it never saw. Walk `names` and take the
   first non-moved member as the casualty (reporting it `file_missing` when it vanished,
   otherwise `write_failed`); everything after it is `not_attempted`. **A two-member
   source cannot detect this** — the casualty is the last member, so no following member
   exists to be misattributed. The regression test needs a three-member source.

   `Task.load()` is the same reload the write path already uses (`:337`) and is **not**
   a `reload_and_save_board_fields` call, so this adds **no** new call site and
   `EXPECTED_CALL_SITES` stays unedited. Deriving `moved` by post-hoc reload is also
   strictly more reliable than a return value the raising call never produced.

3. **Do not remove a source whose move did not fully succeed.** Per source, catch
   `OSError`, reconcile as above, record it, and skip that source's config removal.
   Clean sources are still removed.

4. **Metadata writes fail too — and the two boundaries need OPPOSITE handling.**
   `save_metadata` (`:1158-1169`) performs **two independent** `_save_json` writes:
   `save_project_config` for `PROJECT_KEYS = {"columns", "column_order"}` →
   `board_config.json`, then `save_local_config` for `USER_KEYS = {"settings"}` (which
   holds `collapsed_columns`) → `board_config.local.json`. There is no cross-file
   transaction, and **project is written first**. A blanket in-memory rollback is
   therefore wrong at one of the two boundaries:

   **Boundary A — `save_project_config` raises.** Nothing durable was written. Roll back
   `self.columns` / `self.column_order` / `collapsed_columns` to the pre-removal
   snapshot; disk still holds the sources, so in-memory and disk agree again.
   - Report `failed += [("<metadata>", f"config_write_failed: {exc}")]`,
     `sources_removed = ()`.
   - **Retry = re-run `merge_columns`**, and it converges on the same manager *and* a
     fresh one: the sources are present on disk but empty (all members already moved),
     so the re-run moves nothing and removes them.

   **Boundary B — `save_local_config` raises after the project write SUCCEEDED.** The
   column removal is **durable**; only the user-local half is pending.
   - **Do NOT roll back `self.columns` / `self.column_order`.** Restoring them would
     contradict disk, and because `save_metadata` writes `self.columns` **wholesale**
     (`:1160-1166`), any later `save_metadata()` on that same manager — a collapse
     toggle, an `add_column`, a reorder — would **resurrect the merged-away source
     columns on disk**. The blanket rollback is not merely insufficient here; it is
     actively harmful.
   - Keep `collapsed_columns` pruned in memory: that *is* the desired end state, it
     simply is not persisted yet.
   - The merge structurally **succeeded** — tasks moved, columns removed durably. Report
     it asymmetrically: `sources_removed` is **populated** (they really were removed),
     plus `failed += [("<metadata:local>", f"local_cleanup_pending: {exc}")]`.
   - **Retry is NOT `merge_columns`** — a fresh manager loads `columns` from disk with
     the sources already gone, so `merge_columns(src, dest)` correctly refuses them as
     unknown ids. The retry is a **metadata-only re-save**: `manager.save_metadata()`.

   ```python
   before = (list(self.columns), list(self.column_order),
             list(self.collapsed_columns))
   ... remove sources from columns / column_order / collapsed_columns ...
   try:
       self.save_metadata()
   except OSError as exc:
       if self._project_columns_on_disk_still_have(srcs):   # boundary A
           self.columns, self.column_order, self.collapsed_columns = before
           failed.append(("<metadata>", f"config_write_failed: {exc}"))
           sources_removed = ()
       else:                                                # boundary B
           failed.append(("<metadata:local>", f"local_cleanup_pending: {exc}"))
           # sources_removed stays populated; in-memory stays as-is
   ```

   Discriminate the boundary by **re-reading the project file** (`project_columns_at`,
   already imported and used by `_reconcile_external_columns` at `:1123`) rather than by
   guessing from the exception — the same fail-closed principle the reconciler uses.

   `"<metadata>"` and `"<metadata:local>"` are reserved sentinels in `failed` — never
   real filenames — so a caller can tell a task-write failure from a config-write
   failure, and a *retryable merge* from a *pending local cleanup*.

4b. **Durable recovery record: the orphan IS the record — no journal needed.** After
   boundary B, disk carries a `collapsed_columns` entry naming a column absent from both
   `columns` and `column_order`. That orphan signature is self-describing, so any later
   session can converge without a merge retry. Add a **load-time prune** in
   `load_metadata`: drop `collapsed_columns` entries naming neither an existing column
   nor the synthetic unordered lane; the next natural `save_metadata()` persists it (do
   not force a write on every board open). This also heals configs already corrupted by
   the pre-existing §4 rename bug — the identical orphan class.

   **⚠ The prune MUST whitelist `UNORDERED_ID`.** `unordered` is collapsible
   (`is_column_collapsed("unordered")` at `:6894`, `:8271`, `:9714`, `:9739`) yet is
   deliberately absent from `columns` — an unguarded "prune ids not in `columns`" would
   silently drop a legitimately collapsed unordered lane. That is the trap in this
   self-heal, and it gets its own test.

5. **Distinct field — do not overload `refused`.** `MoveResult`'s docstring guarantees
   *"`refused` non-empty always means NOTHING was written"*; putting write failures
   there makes that invariant a lie for every existing consumer.

   ```python
   @dataclass(frozen=True)
   class MergeResult:
       merged: tuple[str, ...] = ()
       failed: tuple[tuple[str, str], ...] = ()     # (filename|"<metadata>"|"<metadata:local>", reason)
       sources_removed: tuple[str, ...] = ()
       refused: tuple[tuple[str, str], ...] = ()    # input validation only
       @property
       def complete(self) -> bool: return not (self.failed or self.refused)
   ```

6. **Recovery converges — but the retry path depends on the failure class.** The unifying
   rule is that in-memory state is left matching disk (rules 2, 4A, 4B), so a member is
   absent from its source exactly when it really moved. Document all three in the
   docstring as the retry contract:

   | failure | in-memory after | retry |
   |---|---|---|
   | task write (`OSError`) | reconciled to disk via `Task.load()` | re-run `merge_columns` — same or fresh manager |
   | metadata, boundary A | rolled back to pre-removal | re-run `merge_columns` — same or fresh manager |
   | metadata, boundary B | left as-is (sources removed) | `save_metadata()`, **not** `merge_columns`; a fresh session also self-heals via the 4b load-time prune |

7. **t1377_5 must branch on `complete` — and on which sentinel.** Partial gets a
   warning-severity toast naming counts and the retry, never a bare "Merged":
   - `"<metadata>"` → "tasks merged; column list not saved — retry the merge".
   - `"<metadata:local>"` → the merge **did** land; word it as "columns merged; collapsed
     state not saved" and retry the save, **never** re-offer the merge (it would refuse).

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
| **failure attribution** | with the injection on member N of a **three**-member source, `failed` names member N with the `OSError` text and members N+1.. with `not_attempted` — not one undifferentiated blob, and not the whole source. Three members is the minimum: with two, the casualty is the last member and nothing follows it to be misattributed |
| **vanished casualty does not shift blame** | three-member source, member 2 both fails **and** is deleted: member 2 is `file_missing` and member 3 is `not_attempted` — member 3 must NOT inherit the `write_failed` reason. Negative control: deriving the boundary from the vanished-filtered list reproduces exactly that misattribution |
| **vanished file during merge** | delete a member's file after `names` is captured but before its write, so `Task.load()` returns `False`: it is reported `file_missing` in `failed` and is **not** counted in `merged`, and the source is not removed |
| **silent skip — NO OSError** | delete a member's file just before its write and raise **nothing**: `complete` is `False`, the member is `file_missing` and absent from `merged`, and the source is **retained** in both `columns` and `column_order`. This is the path a nominal-return-trusting merge reports as a full success |
| **unreadable member is not orphaned** | make a member's file present but undecodable (so `Task.load()` fails without raising): the source is retained, because draining would leave that file's `boardcol: <src>` pointing at a removed column. Negative control: trusting the nominal return drains it |
| **retry after a silent skip converges** | re-run after the deletion: the vanished member no longer claims the source, so the retry completes and removes it |
| **unreadable: same-manager RETRY does not drain** | re-run after the corruption: `sources_removed` stays empty and `failed` carries `<unverifiable>`. This is the case the first-merge assertion cannot cover — the wiped metadata makes the source *look* empty only on the second pass |
| **unreadable: fresh-manager retry does not drain** | a new `TaskManager` lists the file in `unreadable_files` (re-derived by `load_tasks`, which otherwise drops it as a phantom stub) and refuses to remove the column |
| **block lifts once readable** | rewrite the member as valid frontmatter still naming the source; the next merge completes and removes the source — the guard is until-readable, not permanent |
| **metadata failure — boundary A** (`save_project_config` raises) | (a) all task moves persisted; (b) `self.columns` / `self.column_order` / `collapsed_columns` **rolled back** to include the sources; (c) `complete is False`, `failed` carries the `"<metadata>"` sentinel, `sources_removed` empty; (d) re-running `merge_columns` on the same manager **and** on a fresh one both converge — sources empty, then removed |
| **metadata failure — boundary B** (`save_local_config` raises, project write already succeeded) | (a) the source columns are **gone from `board_config.json` on disk**; (b) `self.columns` / `self.column_order` are **NOT** rolled back — they match disk; (c) `failed` carries `"<metadata:local>"` and `sources_removed` **is populated**; (d) `save_metadata()` on the same manager persists the pruned `collapsed_columns`; (e) **a fresh manager's `merge_columns(src, dest)` REFUSES with an unknown-column reason** — this replaces the impossible merge-retry assertion and pins that the retry path here is the save, not the merge |
| **no resurrection after boundary B** | after the boundary-B failure, trigger any later `save_metadata()` on the same manager (e.g. `toggle_column_collapsed` on a surviving column) and assert the merged-away sources are **still absent** from `board_config.json` — the regression a blanket rollback would cause, since `save_metadata` writes `self.columns` wholesale |
| **load-time orphan prune** (§4b) | seed `collapsed_columns` with an id present in neither `columns` nor `column_order`, construct a `TaskManager`, and assert it is dropped from `manager.collapsed_columns` and persisted on the next save — the durable self-heal for boundary B and for the §4 rename-orphan class |
| **prune whitelists `unordered`** | seed `collapsed_columns = ["unordered"]` (absent from `columns` by design) and assert the prune **keeps** it and `is_column_collapsed("unordered")` stays `True` — negative control for the §4b trap |
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
- **The two metadata write boundaries need opposite handling** (§3.4), and the wrong choice is silently destructive: rolling back in-memory state after the *project* write already succeeded would make a later `save_metadata()` resurrect merged-away columns, because `save_metadata` writes `self.columns` wholesale. Pinned by the boundary-A/B and no-resurrection tests · severity: medium · → mitigation: covered by the core test table
- **§4b widens scope slightly** — a load-time `collapsed_columns` prune in `load_metadata`, a method this task otherwise does not touch. Justified as the durable recovery record for boundary B and as the heal for the §4 rename-orphan class, but it runs on every board open and must whitelist the synthetic `unordered` lane or it silently drops a legitimate collapse · severity: medium · → mitigation: the prune-whitelist negative control
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

## Final Implementation Notes

- **Actual work done:** `MergeResult` + `MetadataWriteError` + `TaskManager.merge_columns`
  in `.aitask-scripts/board/aitask_board.py`, the `update_column` collapsed-state
  migration (§4), the load-time `collapsed_columns` orphan prune (§4b), and
  `tests/test_board_column_manage.py` (new, 40 tests) covering both pre-phase
  mitigations, happy paths, refusals, t1377_3 reconcile survival, and the full failure
  matrix. One pinned entry added to `CANONICAL_IMPORT_ALLOWED` in
  `tests/test_board_fixture_harness.py`. `EXPECTED_CALL_SITES` and `FLIP_TABLE` stayed
  green **unedited**, as planned — `merge_columns` composes `move_tasks_to_column` and
  adds no `reload_and_save_board_fields` call site.

- **Deviations from plan:**
  1. **Boundary discrimination is by exception phase, not a config re-read.** The plan
     had `merge_columns` call `project_columns_at` to tell the two `save_metadata` write
     boundaries apart. That added a second call site and broke t1377_3's AST containment
     guard (`tests/test_board_columns_reconcile.py`), which pins disk I/O to the
     `save_metadata` path. Rather than weaken that performance invariant, `save_metadata`
     now raises `MetadataWriteError` tagged `phase="project"|"local"`. Exact instead of
     inferred, no extra I/O, frozen table untouched. An untagged `OSError` defaults to
     `"project"` (fail-safe: it rolls back).
  2. **Verification runs on the nominal path too, not only after an `OSError`** — see
     "Issues encountered" below.
  3. **Unreadability became tracked manager state** (`Task.load_ok`,
     `TaskManager.unreadable_files`, `_revalidate_unreadable`), which the plan did not
     anticipate at all.

- **Issues encountered:** four defects were found in review, each confirmed against
  source, fixed, and pinned by a test whose negative control reproduces it:
  1. **Attempt-boundary misattribution.** The casualty was derived from a list with
     vanished members filtered out, so a casualty that also disappeared promoted the next
     — never attempted — member into the `write_failed` slot. Fixed by deriving the
     boundary from source order. **A two-member source cannot detect this**; the
     regression test needs three.
  2. **Silent skip counted as success.** `reload_and_save_board_fields` returns early and
     raises nothing when its reload fails, yet `move_tasks_to_column` still reports the
     task in `moved`. A merge trusting that nominal return drained the source. For a
     file that exists but is unreadable (permission/decode error — `Task.load()` returns
     `False` for *any* read exception, not just a missing file) this stranded it holding
     `boardcol: <src>` on a removed column. Fixed by verifying every member against disk
     after every source's move.
  3. **Retry orphan.** A failed `Task.load()` wipes `metadata`, so the member vanished
     from `get_column_tasks(src)` and the *retry* found the source empty and drained it.
     A fresh manager was no safer — `load_tasks` drops an unreadable file as a phantom
     stub. Fixed by tracking `unreadable_files` at load time and refusing to remove any
     column while the set is non-empty.
  4. **Permanent block.** That guard was cleared only by `load_tasks`, so a same-manager
     retry after the file was repaired stayed blocked forever. Fixed by
     `_revalidate_unreadable()` at merge start, which also restores the repaired task to
     `task_datas` so the retry actually moves it.

  The recurring lesson: **three of the four were masked by a test that reconstructed the
  manager.** `fresh_manager()` re-runs `load_tasks` and rebuilds exactly the state the
  bug corrupts, so same-manager retry coverage is mandatory for every failure path here.

- **Key decisions:**
  - The `<unverifiable>` guard is deliberately **broad**: any unreadable task file blocks
    all column removals, not only ones traceable to that file. Narrowing it would require
    reading the file that just failed to read. Conservative-and-honest over
    precise-and-guessing; the message names the offending files.
  - `unreadable_files` tracks **parents only**, matching `load_tasks`. Column membership
    is a parent-level property (`get_column_tasks` reads `task_datas`), so an unreadable
    child cannot be stranded by removing a column.
  - Disk is used as independent ground truth for verification rather than the in-memory
    objects, because a failed write is precisely what corrupts those objects.

- **Upstream defects identified:**
  - `aitask_board.py:1707-1719 (move_tasks_to_column) — counts a task as moved when
    reload_and_save_board_fields silently skipped its save (failed reload), so
    MoveResult.moved can name a task that was never written. merge_columns now
    compensates by verifying against disk, but every other consumer of the movement API
    (move_task_to_column from the board/minimonitor move actions, delete_column,
    move_task_to_edge, reposition_task, update_column) still trusts it. delete_column has
    the same drain-and-strand shape as the merge bug fixed here. Out of scope for t1377_4,
    which does not own those paths.`

- **Notes for sibling tasks:**
  - **t1377_5 (dialog) — the reporting contract to consume.** Branch on
    `MergeResult.complete`, and on *which* sentinel appears in `failed`:
    `"<metadata>"` → the merge did not land, retry the merge; `"<metadata:local>"` → the
    merge **did** land, retry `save_metadata()` and never re-offer the merge (it would
    refuse with `unknown_column`); `"<unverifiable>"` → name the unreadable files and ask
    the user to fix them. Per-member reasons are `write_failed:` / `not_attempted` /
    `not_written` / `file_missing` / `unreadable`. Never show a bare "Merged" when
    `complete` is `False`.
  - **t1243_11 §4** — `merge_columns` is the **reference drain path** (fresh appended
    indices preserving relative order, via `move_tasks_to_column`); consume it rather
    than writing a second re-index strategy for `delete_column`. Any shared helper must
    preserve the non-transactional contract: per-file atomic writes, config removal last,
    `MergeResult.failed`, convergent re-run, and **verification against disk** — do not
    let a refactor reintroduce "no exception means written".
    `DeleteColumnDrainCharacterizationTests` pins `delete_column`'s current flat
    `board_idx = 0`; it is *expected* to fail when §4 lands, and names §4 in a comment.
  - **t1243_10** — when `settings.collapsed_groups` lands with composite `"<col>/<slug>"`
    keys, its column half must be re-pointed by **both** `merge_columns` and the fixed
    `update_column`, applying t1243_10's coalesce rule. Note `_prune_orphan_collapsed_columns`
    is the model for the equivalent group-key prune, **including its `unordered`
    whitelist** — the synthetic lane is collapsible but absent from `columns`.
