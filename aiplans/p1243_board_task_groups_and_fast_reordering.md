---
Task: t1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1243 — Board task groups and fast reordering

**This is a design + decomposition plan.** Its deliverable is a finalized design
plus fourteen child tasks with their own plans. No production code is edited
under this parent.

## Context

Reordering tasks on `ait board` is slow and noisy, and the board has no way to
group related tasks inside a column. Four workstreams were scoped in the task:
(A) eliminate index renumbering, (B) cut the per-keypress render cost, (C) add
in-column task groups, (D) add bulk move / group-membership commands.

### Corrections to the task's premises (re-verified at `HEAD` = `ceb07381d`)

1. **The task's line numbers are stale.** They came from a working tree holding
   ~1050 uncommitted lines of t1210_4, which has since landed (`03eade720`)
   along with t1212, t1245, t1247, t1248 and t1268. `aitask_board.py` is now
   **9043 lines and clean**. **Every anchor here is a symbol name**; child plans
   re-verify line numbers at implementation time.
2. **The free-key list is wrong.** `v`, `e`, `S`, `u` are taken. Verified free:
   `space`, `m`, `M`, `G`, `d`, `h`, `k`. This plan uses `space`, `m`, `G` and
   extends the existing `x`.
3. **`BOARD_KEYS` is not the single lever the framing implies.** The board's save
   path ignores it; its merge rule is the wrong one for grouping; that rule
   cannot express deletion; and its `updated_at` tie-break is task-wide, so an
   unrelated edit can decide a field it never touched. All four need explicit
   work (Workstream C).

### Verified current state

| Symbol (`.aitask-scripts/board/aitask_board.py` unless noted) | Behaviour |
|---|---|
| `TaskManager.normalize_indices(col)` | Renumbers a whole column to `(i+1)*10`, one `reload_and_save_board_fields()` per changed task. |
| `TaskManager.move_task_col()` | Appends at `max(t.board_idx) + 10`. `max()` reads the **raw** value — a hand-quoted `boardidx: "20"` mixed with ints raises `TypeError`. Resolves `self.task_datas` **only** (parents). |
| `TaskManager.swap_tasks()` | Swaps two indices → 2 writes; a no-op when the indices are equal. |
| `TaskManager.get_column_tasks()` | Sorts by `(normalize_board_idx(board_idx), filename)`. **Readers only sort.** |
| `TaskManager.delete_column()` | Sets **every** task in the column to `board_idx = 0` (mass ties) and prunes `collapsed_columns` — but nothing else. |
| `Task.save()` / `save_with_timestamp()` | `save()` is timestamp-neutral; `save_with_timestamp()` calls `_update_timestamp()` first and is documented "Use for semantic metadata changes." |
| `Task.reload_and_save_board_fields()` | Snapshots `boardcol`/`boardidx` **by name, hardcoded**, reloads, re-applies, then calls the **timestamp-neutral** `save()`. `Task._BOARD_KEYS = BOARD_KEYS` exists but is **never read anywhere** — a dead assignment. |
| `_move_task_lateral` | `move_task_col` + `normalize_indices` on **both** columns + `refresh_git_status()` + `refresh_columns({src,dst})`. |
| `_move_task_vertical` | `swap_tasks` + `normalize_indices` + `refresh_git_status()` + in-place `move_child` + synchronous `apply_filter()`. |
| `_move_task_to_extreme` | Raw `±10` arithmetic + 1 write + `normalize_indices` + `refresh_column`. |
| All four movement actions | Early-return on `focused.is_child`; `check_action` hides them for child cards. |
| `apply_filter()` | `self.query(TaskCard)` over the **whole screen**; assigns `card.styles.display` on every card unconditionally; rebuilds the search haystack per card; second full query over `EmptyColumnPlaceholder`. No column scoping. |
| `TaskManager.refresh_git_status()` | Spawns `git status --porcelain -- aitasks/` **once per movement keypress**. |
| `lib/task_yaml.py` `BOARD_KEYS` | `("boardcol", "boardidx")`. Drives frontmatter key ordering, the "empty metadata" probe in `work_report_gather` / `trail_gather`, and `_KEEP_LOCAL_FIELDS`. **Does not** drive the board's save path. |
| `board/aitask_merge.py` `merge_frontmatter` | One-sided presence is resolved **first and unconditionally** (`in_local and not in_remote → local`, `in_remote and not in_local → remote`), *before* any field rule. Divergent values then hit `_KEEP_LOCAL_FIELDS` (local wins, silent) or `anchor` (newer-wins). **Precedent for overriding this:** `_ACTIVE_TUPLE_FIELDS` is resolved in a pre-loop block precisely because "the generic one-side-only rule below would resurrect the older side's obsolete snapshot." Signature is **two-way** (`local_meta, remote_meta`) and `main()` reads only the file's text. `updated_at` is minute-resolution (`%Y-%m-%d %H:%M`). |
| `_swap_adjacent_cards` | Defines a **block** = `TaskCard` + trailing `.child-wrapper` Horizontals, moved via same-parent `move_child`. |
| `TaskCard` | No `id`, no `DEFAULT_CSS`; identity is `task_data.filename` + `column_id`. `column_id` is read in **12 places** — `apply_filter`, `_column_widget`, `_visible_column_cards`, `_get_focused_col_id`, `_refocus_column`, `check_action`. `on_focus`/`on_blur` set the border **imperatively**. |
| Textual | **8.2.7**. `move_child` is **same-parent only**; `remove()`/`mount()` return awaitables. **No supported cross-parent widget move**, and no existing cross-column DOM helper in the board. |
| `config_utils.task_dir()` | Honors `TASK_DIR`, documented for tests. `TASKS_DIR` is a **module-load constant** — a real-file fixture must set `TASK_DIR` *before* importing `aitask_board`. |
| Conflict style / sync path | `merge.conflictStyle` is configured **nowhere** (git config, `.aitask-scripts/`, `seed/`), so conflicts carry 2-way markers and no `|||||||` base. `aitask_sync.sh:270` runs plain `task_git pull --rebase`; `:221` invokes `aitask_merge.py <file> --batch --rebase`. The diff3 `base_lines` the parser collects is discarded — and would be `None` in production anyway. |
| `tests/test_aitask_merge.sh` | Hand-written marker fixtures only; exactly **one** includes a `||||||| merged common ancestor` section. No test drives a real git conflict. |
| Board movement tests | **None exist.** |

---

## Sequencing and coordination

**The original concurrency premise is void.** `t1210_4` and `t1248` are both
`Done` and archived; `aitask_board.py` has no uncommitted changes; no currently
`Implementing` task touches it. No child carries `depends: [1210_4]`. Instead:

- Every child plan opens with an **anchor re-verification step**.
- The in-flight scan is **re-run immediately before creation**; if a board task
  is live by then, the dependency is added to the affected children.

### t1210_5 — close the claim window *before* creating children

`t1210_5` (`trail_move_to_column_commands`) is `Ready`, unlocked, and — now that
`t1210_4` has landed — **unblocked**. Its plan calls `move_task_col` +
`normalize_indices` and builds its own column picker. Any picker could claim it
during decomposition and implement the API this task deletes. Child ids do not
exist yet, so the protective dependency cannot be written last. Three ordered
steps at the top of Step 7, before any child is created:

1. **Guard now** — `aitask_update.sh --batch 1210_5 --deps 1210_4,1243`. `1243`
   exists today; the task immediately reads as Blocked in `ait ls` and stops
   being offered. Commit and push.
2. **Create the children.**
3. **Swap atomically** — replace the guard with
   `--deps 1210_4,1243_3,1243_7` (gap indexing; move-to-column command) and add
   a `## Notes for sibling tasks` entry naming the replacement API
   (`move_tasks_to_column`) and the shared picker. Reverse pointers go into
   `t1243_3` and `t1243_7`, per the bidirectional-coordination-link convention.
   Commit and push.

If step 3 cannot complete, the step-1 guard is the fail-safe: t1210_5 stays
blocked rather than free. `t1210_5` is being edited by another session as this
plan is written, so the guard is applied with `aitask_update.sh --batch --deps`
(frontmatter read-modify-write) after re-reading the file, staging only that
path.

### t1268 — landed; anchors re-verified against it

`t1268` (`bytrail_refresh_semantics_and_key_footer_contract`) edited
`KanbanApp.BINDINGS`, the `check_action` `bytrail` branches, `refresh_board()` /
`_set_base_filter` reload behaviour and `TrailTaskCard.compose` — the same
surfaces t1243's binding- and render-touching children edit. **It is now `Done`
and archived (`ceb07381d`), so no child carries a dependency on it.**

Every load-bearing claim in the table above was re-verified against the
post-t1268 file and still holds: `normalize_indices` / `move_task_col` /
`swap_tasks` intact; `reload_and_save_board_fields` still hardcodes two names and
still calls the timestamp-neutral `save()`; `Task._BOARD_KEYS = BOARD_KEYS` still
dead; `apply_filter` still a whole-screen `query(TaskCard)` with no `cols`
parameter; `_focused_card` / `_get_column_cards` / `_column_focus_target` /
`_get_focused_col_id` still card-and-placeholder centric; and `space`, `m`, `M`,
`G` still unbound. Only the line count moved (8591 → 9043) — which is exactly why
child plans anchor on symbol names and re-verify at implementation time.

Nothing currently `Implementing` edits `aitask_board.py`, and the file is clean.
The scan is re-run one final time immediately before creation.

`m` therefore means the same thing in every view — "move the selected task(s) to
a column" — with per-view semantics gated in `check_action`.

---

## Workstream A — gap indexing

### New pure module: `.aitask-scripts/lib/board_ordering.py`

Headless, no Textual imports (mirrors how `lib/topic_semantics.py` was extracted):

```python
STEP = 1024                      # power of two → ~10 midpoint halvings per gap

def index_for_append(indices)  -> int          # max + STEP, or STEP
def index_for_prepend(indices) -> int          # min - STEP, or STEP
def index_between(lo, hi)      -> int | None   # (lo+hi)//2, None when hi-lo < 2
def indices_between(lo, hi, k) -> list[int] | None   # k distinct, None if gap < k+1
def respace_indices(n, stride=STEP) -> list[int]     # [(i+1)*stride for i in range(n)]
def stride_for(k)              -> int          # max(STEP, next power of two ≥ k+1)
```

All inputs are `normalize_board_idx`-coerced ints. `int` stays the on-disk type;
negative values are legal (readers only sort) — that is what makes "move to top"
a single write.

### Manager API (replaces `normalize_indices` on the hot path)

| Method | Writes (normal case) |
|---|---|
| `move_task_to_column(task, col)` | **1** — `boardcol` + `index_for_append`. Source column untouched. |
| `reposition_task(task, before, after)` | **1** — `index_between`. |
| `move_task_to_edge(task, col, top\|bottom)` | **1** — prepend / append. |
| `move_tasks_to_column(tasks, col)` | **K** — K contiguous indices from `max+STEP`, input order preserved. |
| `respace_column(col)` | **N** — `normalize_indices` renamed, retained **only** as the exhaustion remedy. |

`swap_tasks` is retired from the movement path in favour of `reposition_task`
(1 write instead of 2; also fixes the equal-index no-op).

### The write guarantee — stated with its exception

> **Normal case.** Each single-task move writes **exactly one** task file, and
> never a file outside the move. A multi-hop transit A→B→C writes the moved task
> once per hop and **nothing** in A or B.
>
> **Bounded exception — compaction.** When the destination interval cannot hold
> the required indices (`index_between` / `indices_between` returns `None`), the
> operation performs **one** `respace_column(col, stride=stride_for(K))` — N
> writes, that column only — and then the placement writes. The stride is chosen
> from the pending insert size, so post-respace every gap holds at least `K`
> interior values and the retry is guaranteed for **any** K; there is never a
> second compaction. (A fixed `STEP=1024` would only guarantee the retry for
> K ≤ 1023 — `stride_for` removes that unstated cap. Boundary cases K = 1023,
> 1024 and 1025 are tested.)
>
> **This exception applies only to operations that assign ranks** — single
> moves, bulk moves, and group block moves. Group **formation** and **removal**
> write the `boardgroup` field alone (see INV-R below), touch no index, and can
> therefore never trigger compaction. Every "N writes" figure below is the
> **compaction-free** count; the compacted count is always `N + column size`,
> confined to that one column.
>
> **Bound.** At `STEP=1024`, exhaustion needs ~10 consecutive inserts into the
> *same* gap. Legacy `10`-spaced columns exhaust after ~4 and self-heal once.

Every regime is pinned (per the repo's bounded-recovery convention — quantify the
bound, pin at-bound and over-bound): healthy → exact write count with an exact
changed-path set; at-bound (interval driven to exactly fit) → still no
compaction; over-bound → exactly one `respace_column` then success, all writes
confined to that column.

**Rejected alternative — a never-compacting representation** (fractional /
LexoRank-style string ranks). It would make the guarantee absolute, but
`boardidx` is an **int** on disk with three consumers (`normalize_board_idx`,
`lib/work_report_gather.py`, `board/aitask_merge.py`) and `aitask_update.sh
--boardidx IDX` documents "integer". Changing the on-disk type is a far larger
blast radius than a rare, bounded, single-column respace.

**Migration.** Existing boards keep `10/20/30` and self-heal lazily on first
exhaustion. No upfront rewrite, no migration commit.

**Correctness fixes bundled in:** `max(t.board_idx)` in `move_task_col` and the
raw `±10` arithmetic in `_move_task_to_extreme` both bypass `normalize_board_idx`
today; the new API routes every read through it.

---

## Workstream B — render cost

### Measurement precedes redesign — with a pre-registered decision checkpoint

"The render pass is the wall" is an inference by elimination from a YAML timing
(~9 ms) and a git timing (~4 ms); neither measures render or end-to-end keypress
latency, and the board has changed five times since. So **t1243_1 fixes its
method and success rule before observing any result**:

- **Method (pre-registered).** Synthetic board of 200 parent cards over 5
  columns (matching the live tree's ~226 tasks), warm headless Pilot. Samples
  must be **stationary and valid**: a naive run of 50 consecutive `shift+right`
  reaches the last column after a few moves and every later press early-returns,
  so median/p90 would measure *rejected actions* and any change could
  "beat" the target for free. Instead the harness **ping-pongs around a stable
  position** — `shift+right` / `shift+left` between two adjacent non-collapsed
  columns, `shift+down` / `shift+up` between two adjacent positions mid-column —
  so the state returns to the start after each pair. Warm-up samples are
  discarded explicitly, and **every recorded sample must be accompanied by the
  expected write** (write-spy count > 0): a zero-write sample means the action
  was rejected and **fails the run** rather than being averaged in. Report
  **median and p90** end-to-end keypress latency over valid samples only, plus
  per-span totals from a monotonic-clock wrapper around `apply_filter`,
  `refresh_column(s)`/`_recompose_column`, `refresh_git_status`, and
  `reload_and_save_board_fields`.
- **Premise rule (pre-registered).** Workstream B's premise holds **iff
  `apply_filter` + column recompose together account for ≥ 40 % of median
  keypress latency.**
- **Target rule (pre-registered).** t1243_4 and t1243_5 must deliver **≥ 30 %
  reduction in median keypress latency** versus the baseline.

**Decision checkpoint.** t1243_1's final step compares the measurement to the
premise rule. If the premise is **refuted**, t1243_1 does not proceed as if it
held: it **revises, replaces, or postpones t1243_4 and t1243_5** — rewriting
those task files and plans to target whichever span actually dominates — and
records the decision and data in this parent plan before either child is picked.
The dependency chain must not carry a predetermined implementation past a
falsified premise.

Assuming the premise holds, two tiers ordered by certainty:

**Tier 1 — certain win, no widget-lifecycle risk (t1243_4).**
1. `apply_filter(cols: set[str] | None = None)` — when `cols` is given, iterate
   only those columns' cards and update `EmptyColumnPlaceholder` / focus-rescue
   for those columns only. `None` keeps today's whole-board pass for view/filter
   changes.
2. Cache the lowercased search haystack per card.
3. Only assign `card.styles.display` when the value changes.
4. **Stop spawning `git status` per keypress** — a move writes exactly the files
   we just wrote, so add those filenames to `manager.modified_files` directly.
   The full scan stays on explicit refresh / commit.

**Tier 2 — spike-first, explicitly de-risked (t1243_5).** Textual 8.2.7 offers
**no supported cross-parent widget move**. So the lateral fast path is a genuine
unknown and its child **begins with a spike**:

- Specify `_card_block(card) -> list[Widget]` (extracted from
  `_swap_adjacent_cards`) and a lifecycle-safe
  `async _transplant_block(block, src_col, dst_col, before=None)`.
- The helper must either construct **fresh** `TaskCard`s in the destination (so
  `column_id` is right by construction) or update `card.column_id` on every card
  in the block — with **12 read sites** including `apply_filter`,
  `_visible_column_cards`, `_get_focused_col_id` and `check_action`, stale
  identity would leave nav and filtering pointed at the old column while the data
  model is correct.
- Movement actions become `async` (or dispatch via `run_worker`) so the
  awaitables are awaited rather than dropped.
- **Documented fallback:** if no lifecycle-safe transplant exists in 8.2.7, keep
  `refresh_columns({src,dst})` and ship Tier 1 only. The child records the spike
  result and residual cost.
- Verification is real-Pilot: focus lands on the moved card in the destination;
  expanded `.child-wrapper` rows travel with the parent; a search filter applied
  after the move hides/shows the right cards; scroll is sane;
  `_get_focused_col_id` reports the destination.

---

## Workstream C — task groups (decided data model)

**A task group is a frontmatter-derived, in-column grouping keyed by a slug.**

```yaml
boardcol: now
boardidx: 3072
boardgroup: perf_work
```

- **Group identity is the slug**; display title is the slug rendered for humans
  (`perf_work` → "perf work"). No registry, no ids, no title/colour store in v1.
- **Membership** = tasks in the same column sharing the slug. A single-member
  group renders as a plain card (mirrors `_build_topic_lanes` singleton
  collapsing).
- Grouping functions live in a new pure `.aitask-scripts/lib/board_groups.py`,
  mirroring `lib/topic_semantics.py`.

### Key split — `BOARD_KEYS` is not one thing

```python
# lib/task_yaml.py
BOARD_LAYOUT_KEYS = ("boardcol", "boardidx")            # per-checkout layout
BOARD_KEYS        = BOARD_LAYOUT_KEYS + ("boardgroup",) # all board-owned keys
```

| Consumer | Set | Effect |
|---|---|---|
| `serialize_frontmatter` key ordering | `BOARD_KEYS` | `boardgroup` serialises last with the others |
| "empty metadata" probe (`work_report_gather`, `trail_gather`) | `BOARD_KEYS` | a task carrying only board keys still reads as empty |
| `_KEEP_LOCAL_FIELDS` (merge) | **`BOARD_LAYOUT_KEYS`** ← narrowed | layout stays local-wins; `boardgroup` does not |
| save-path snapshot loop | `BOARD_KEYS` | every board key survives the reload |

### Three seams `BOARD_KEYS` does **not** give us for free

**1. The save path ignores it — and is timestamp-neutral by design.**
`reload_and_save_board_fields()` snapshots two names, reloads, re-applies, and
calls `save()` (no timestamp). A group command that sets
`metadata["boardgroup"]` and calls it would have the change **silently reloaded
away**; and even once preserved, a newer-wins merge rule is meaningless if the
write never advances `updated_at`. Fix (t1243_2, ahead of all group work):

```python
def reload_and_save_board_fields(self, semantic: bool = False):
    snapshot = {k: self.metadata.get(k) for k in BOARD_KEYS}
    if not self.load():
        return                                   # file gone — do NOT recreate
    for k, v in snapshot.items():
        if v is not None:
            self.metadata[k] = v
    if semantic:
        self._update_timestamp()                 # membership is semantic
    self.save()
```

Layout-only moves keep calling it with `semantic=False` and stay
timestamp-neutral (correct — layout is per-checkout and merges local-wins).
**Every** `boardgroup` mutation — the bulk in-process path *and* the
`BoardGroupField` detail-screen path that shells out to `aitask_update.sh
--boardgroup` (which advances `updated_at` itself) — advances the timestamp.
The dead `Task._BOARD_KEYS` assignment is retired by making the loop the real
consumer. This is a latent bug today: *any* future board key is dropped.

**2. Keep-local is the wrong merge rule for grouping.** Which column a card sits
in is per-checkout layout, so local-wins is right for it. Group membership is
*shared task organization* — a user who groups on one machine expects the group
on another. So `boardgroup` must not be keep-local.

**3. Neither newer-wins nor presence alone can decide membership.** Two
independent defects:

- *No deletion semantics.* `merge_frontmatter` resolves one-sided presence
  **first and unconditionally**, so a side that clears the field by omitting the
  key loses to a side that still carries it — **membership resurrects on sync**.
- *No field-level causality.* `updated_at` is **task-wide** and only
  minute-resolution (`%Y-%m-%d %H:%M`). Machine A removes a task from its group
  at t1; unsynced machine B edits only `status` at t2 > t1 while still carrying
  the old `boardgroup`; newer-wins hands the field to B, which **never touched
  it**. A timestamp is a proxy for causality, not causality — and at minute
  granularity bulk group operations tie constantly.

**Decision: base-aware change detection, with the base read from git's index.**
The rule below needs a third side. The obvious source — the diff3 base already
parsed and discarded in `aitask_merge.py` — **is not available in production**:
`merge.conflictStyle` is configured nowhere (not in git config, not in
`.aitask-scripts/`, not in `seed/`), so git emits 2-way markers with no
`|||||||` section; `aitask_sync.sh:270` runs a plain `task_git pull --rebase`
and `:221` hands the conflicted file to `aitask_merge.py --batch --rebase`,
whose `main()` reads only the file's text. Plumbing `base_lines` through would
therefore be dead code: every real divergence would fail closed to PARTIAL while
marker-fixture tests passed. (`tests/test_aitask_merge.sh` is entirely
hand-written fixtures with exactly one diff3 case — it could not have caught
this.)

The base comes from **git's conflicted index instead**, which is authoritative
and conflict-style independent: for a conflicted path git holds stage 1 = merge
base, stage 2 = ours, stage 3 = theirs. Ownership is split so the Python stays a
pure text merger:

- `aitask_sync.sh` — which already owns the git context via `task_git` (the
  `.aitask-data` worktree) — extracts `task_git show ":1:$file_path"` to a temp
  file and passes `--base-file <tmp>`. Stage 1 is the merge base regardless of
  rebase side inversion, so the existing `--rebase` local/remote swap is
  unchanged and the base needs no swap.
- `aitask_merge.py` gains `--base-file` and uses it as the third side. The diff3
  marker parser is retained only as a fallback for invocations outside a
  conflicted index.
- An add/add conflict has no stage 1; `git show :1:` fails, there is genuinely no
  base, and PARTIAL is the correct answer.

| base vs sides | Result |
|---|---|
| only local differs from base | local (local made the change) |
| only remote differs from base | remote |
| both differ, same value | that value |
| both differ, different values | **unresolved / PARTIAL** — a genuine concurrent regrouping, surfaced to the syncer rather than guessed |
| no base (add/add, or driver invoked outside a conflicted index) and values diverge | **unresolved / PARTIAL** — fail closed rather than fall back to a timestamp guess |

This decides membership on *who actually edited the field*, needs no new
frontmatter key, and handles deletion naturally (base `perf_work`, local
`perf_work`, remote cleared → remote changed → cleared wins). The **`""`
tombstone is retained** on top of it: it makes "cleared" an explicit value rather
than an absence, and keeps presence symmetric for any task ever grouped.

*Rejected alternative — forcing `merge.conflictStyle=diff3`* on the sync
rebase paths. It only covers conflicts produced by that invocation, so any
conflict created outside the sync driver (a manual `git pull`, an IDE merge)
still arrives 2-way — a partial fix that also reaches into the user's git
behaviour. Reading the index covers every path.

*Rejected alternative — a field-level stamp* (`boardgroup_at`, with
`("boardgroup", "boardgroup_at")` merged as one tuple mirroring
`_ACTIVE_TUPLE_FIELDS`). It also gives field-level ordering without a base, but
it adds a frontmatter key that every extension-points layer must carry, and it
is still a timestamp proxy — two machines that regroup the same task in the same
second remain ambiguous, so the PARTIAL path is needed regardless.

**Tests must exercise the production path, not fixtures.** Unit cases over the
rule (local-only change, remote-only change, both-changed-same,
both-changed-different → PARTIAL, deletion from each side, no base → PARTIAL,
identical, absent-on-both) plus a **temporary-repository integration test**:
`git init`, commit a task with `boardgroup: perf_work`, have one side clear it
and the other change only `status`, produce a genuine conflict through the real
rebase path **under the repo's default conflict style**, run the actual merge
driver, and assert the cleared side wins — the `status`-only edit must not win a
field it never touched. Negative control: with the base withheld, the same
scenario yields PARTIAL, proving the base is what decided it. Plus a guard test
that every driver invocation site in `aitask_sync.sh` (currently one, `:221`)
passes `--base-file`.

*(Noted, not fixed here: `anchor` merges newer-wins and has the same
task-wide-timestamp weakness. Out of scope — recorded as an upstream observation
for the child's Final Implementation Notes rather than scope creep.)*

### Ordering invariant — render-derived, not persisted

An earlier draft required members to occupy a **contiguous run of `boardidx`**
on disk. That is unachievable under this design's own merge rules, and the
contradiction is decisive: `boardgroup` is shared (newer-wins) while `boardidx`
stays per-checkout (local-wins). So after a sync,

- a **remotely added** member arrives carrying `boardgroup` but keeping its
  *local* scattered index — instantly outside the run; and
- a **remotely removed** member arrives carrying the `""` tombstone but **not**
  the sender's repositioning write — instantly stranded inside the run.

Repairing that on load would mean writing task files every time the board opens
after a sync — the exact churn this task exists to remove — and two checkouts
could ping-pong repairs forever. Contiguity is therefore **dropped as a
persisted invariant** and replaced with a derivation invariant:

> **INV-R (render determinism).** A column's rendered order is a **pure, total
> function of the persisted state of that column's tasks**. Two checkouts holding
> identical task files render identical order, and reloading after any operation
> reproduces the order that was on screen.

Derivation (in `lib/board_groups.py`, pure and unit-testable — the same shape as
`_build_topic_lanes`, which already derives lanes from `anchor` without touching
any index):

1. Walk `get_column_tasks(col)` (already sorted by `(normalize_board_idx,
   filename)`). A task with a non-empty `boardgroup` joins that slug's **group
   unit**; every other task is a **singleton unit**.
2. A unit's sort key is the key of its **first** member in that walk.
3. Units are emitted in sort-key order; members render inside their unit in walk
   order. A group unit with one member renders as a plain card.

Consequences, stated honestly:

- Nothing on disk must be contiguous, so **formation and removal write only the
  `boardgroup` field** — no index rewrites at all (K writes to group K tasks, 1
  to ungroup one). The removal-strands-a-task bug cannot occur, because position
  no longer defines membership.
- A non-member whose index falls between two members renders **outside** the
  block, at its own key position. On-disk index order and rendered order can
  differ — that is the price of zero repair writes, and it is the same trade
  `_build_topic_lanes` already makes.
- **No post-sync reconciliation exists or is needed**: both checkouts render
  identically from the same files. The cross-PC checklist item therefore has a
  mechanism behind it — a property test that renders the same fixture under both
  a "remote add" and a "remote remove" merge result and asserts identical,
  stable output.
- `delete_column`'s `board_idx = 0` mass-tie is no longer correctness-critical
  (ties break by filename and groups still render as blocks). It stays a
  worthwhile tidy-up, downgraded to an opportunistic fix in t1243_11.

### Block moves — writes proportional to what the user selected

- **Lateral / to-edge**: N writes (N = members), relative order preserved.
- **Vertical past an adjacent unit**: the **moved group** is rewritten with N
  distinct indices placed below (or above) that unit's sort key — N writes; the
  neighbouring unit is never touched. Bounded-compaction exception applies when
  the interval cannot hold N distinct indices.
- **Opportunistic contiguity.** Because a move rewrites those N files anyway, it
  assigns them *contiguous* indices. A group the user actually moves becomes
  tidy through use; a group that only ever arrived by sync renders correctly with
  zero writes. Tidiness is a by-product, never a repair pass.
- **Rejected optimization — "rewrite the smaller side".** Moving a 5-card group
  past 1 card would cost 1 write instead of 5, but it dirties a file the user
  never selected — exactly the churn this task exists to remove.
- Never a whole-column renumber outside the compaction exception.

### Slug collisions

Group identity is `(column, slug)`, so two same-slug groups in one column *are*
one group by derivation. Three entry paths reach that state, handled differently
because only one of them is a naming act:

| Path | Behaviour |
|---|---|
| **Lateral / to-edge move** of group `G` into a column already holding `G` | **Coalesce**, with a notify ("merged into existing group 'perf work'"). Arriving members get indices above the residents' maximum, so they render after them — deterministic and reload-stable. N writes (arriving members only). |
| **`delete_column`** moving same-slug groups into `unordered` | Coalesce identically; no extra machinery, it is the same derivation. |
| **Rename** onto a slug already present in that column | **Confirm, never silently merge** — a rename that quietly fuses two distinct groups is a destructive surprise. `AskUserQuestion`-style modal: "Group 'X' already exists in this column — merge into it?" → merge / cancel. (Conflict over silent guess.) |

**Collapse-key combination** on any coalesce: the destination `"<col>/<slug>"`
key wins if it already exists; otherwise the arriving key's state is adopted
under the destination key. The vacated key is dropped by the same lifecycle
owner that performed the move. All three paths get a reload-round-trip test.

### Collapse state and its lifecycle

Per-user view state → `settings.collapsed_groups` (`"<col_id>/<slug>"` entries)
in `board_config.local.json`, the layer that already holds `collapsed_columns`
and `topic_sort_mode`. Explicitly *persisted*, unlike the in-memory-only
`expanded_tasks`. A composite key goes stale on five transitions, so **each
owning operation updates it**:

| Transition | Owner | Action on `collapsed_groups` |
|---|---|---|
| Group renamed | group-rename command | rewrite the slug half of matching keys (or combine, when the user confirmed a merge) |
| Group moved to another column | group lateral / to-edge move | rewrite the col half; on coalesce, combine per the rule above and drop the vacated key |
| Last member removed (group dissolved) | removal command | drop the key |
| Column id renamed | `TaskManager.update_column` (already reassigns `board_col`) | rewrite the col half |
| Column deleted | `TaskManager.delete_column` (already prunes `collapsed_columns`) | re-point the col half to `unordered` — the group survives the move |

Plus a **prune-on-load sweep**: drop any key whose `(col, slug)` has no members.
That is the accumulation backstop for states no transition caught (e.g. an
external `aitask_update.sh --boardgroup` edit). Each transition is tested by
restarting the board and asserting the group's collapse state.

### Rendering

`GroupHeader` (a focusable `Static`: `▾ perf work (3)`) plus member cards, all
**flat siblings** inside `KanbanColumn` — the same shape as `.child-wrapper`
rows, so `_card_block()` generalises instead of forking. A collapsed group
renders the header alone. `x` is extended: on a `GroupHeader` it toggles group
collapse, on a parent card it keeps toggling children — one key,
"expand/collapse the thing under focus".

### Focus and navigation must become unit-level too

Declaring `GroupHeader` focusable is not enough: every focus/nav seam in the
board is `TaskCard`-or-placeholder centric, verified in source —

| Seam | Current behaviour | Effect with a focused header |
|---|---|---|
| `_focused_card()` | `query("TaskCard:focus")` | returns `None` |
| `_get_column_cards` / `_visible_column_cards` | `query(TaskCard)` filtered by `column_id` | vertical nav skips headers entirely |
| `_get_focused_col_id()` | card, else placeholder | returns `None` → `_nav_lateral` bails to `action_focus_board()`, `_shift_column` no-ops |
| `_column_focus_target()` | visible placeholder, else visible cards | a column of only collapsed groups yields **`None`** → `_refocus_column` silently does nothing and focus is lost |
| all four `_move_task_*` | start from `_focused_card()` | no movement entry point from a header |

So the filter focus-rescue fix alone does not close the hole. The abstraction is
introduced with `GroupHeader`:

- **`GroupHeader` carries `column_id`**, exactly like `TaskCard`.
- **`_focused_unit()`** — `query("TaskCard:focus, GroupHeader:focus").first()`.
  `_focused_card()` survives as the narrow "focused *task*" accessor the
  task-level gates genuinely need.
- **`_get_column_units` / `_visible_column_units`** replace the card-only
  variants for vertical navigation and positional indexing.
- **`_column_focus_target`** returns a visible placeholder, else the first
  visible **unit**. The t1209 invariant is restated: *every board column owns
  exactly one focus anchor — a visible placeholder when it shows no units,
  otherwise its first visible unit.*
- **`_get_focused_col_id`** resolves unit → placeholder.

**Two different notions of "unit", kept distinct.** Expanded child tasks are
also `TaskCard`s (mounted inside `.child-wrapper`), they are *already* included
in today's `_get_column_cards` / `_column_focus_target` indexing, and group
membership **excludes** them. So:

- **Navigation stops** = every focusable content widget in DOM order:
  `GroupHeader`, member/ungrouped parent `TaskCard`, and expanded child
  `TaskCard`. This preserves today's behaviour, where `↑`/`↓` and lateral
  positional preservation already step through children.
- **Movement units** = what a movement key acts on: a `GroupHeader` → the whole
  group; a parent `TaskCard` → its `_card_block()` (card + its child-wrappers);
  a child `TaskCard` → **refused**, as today.

**Navigation sequence for the combined case** — a grouped parent with visible
children — is specified explicitly:

```
▾ perf work (2)          ← GroupHeader
    t1243_2  gap indexing        ← member parent
      ↳ t1243_2_1 ...            ← its expanded child
      ↳ t1243_2_2 ...
    t1243_3  render scoping      ← next member
t1229 guard zero-collection      ← next unit (ungrouped)
```

`↓` walks header → member → its children in order → next member → … → the next
unit; `↑` is the exact reverse. `←`/`→` preserve the positional index across
columns via `_column_focus_target(col, preferred_pos)`, indexed over **navigation
stops** — unchanged from today. Collapsing the group hides the members *and*
their child-wrappers and moves focus to the header. A group block move carries
each member's `_card_block()`, so children stay adjacent to their parent.

This combined shape gets its own **real-Pilot integration case** rather than
being inferred from the separate group and expanded-children tests.

**Movement dispatch — settled explicitly, no refusal case:**

| Focus | `shift+←/→`, `shift+↑/↓`, `ctrl+↑/↓` |
|---|---|
| `GroupHeader` (collapsed or expanded) | moves the **whole group as a block** (Workstream C's block moves) |
| Member card inside an expanded group | moves **only that member**. A lateral move carries its `boardgroup` value into the destination column — where it joins a same-slug group if one exists, else renders as a plain single-member group. That falls straight out of the `(column, slug)` derivation, so there is no special case; the move is notified so it is not a surprise. |

**Refocus after every state change** is specified: after a filter pass, off a
hidden header via the unit-aware `_refocus_column`; after collapsing, onto the
header (focus must never be left on an unmounted member); after a block move,
onto the header in the destination; after a member move, onto that card.

All of the above is pinned with real Pilot tests, including the
column-of-only-collapsed-groups case that motivated it.

### Filtering must become unit-level — a collapsed group mounts no cards

`apply_filter` evaluates **mounted `TaskCard`s**, derives `cols_with_visible`
from them, and rescues focus only off a `TaskCard` / `EmptyColumnPlaceholder`.
A collapsed group mounts a `GroupHeader` and **none of its members**, which
breaks four things at once: search and base/add-on filters have no member
widgets to evaluate, so the header's visibility is never computed; a column
holding only collapsed groups contributes nothing to `cols_with_visible` and
wrongly shows its `EmptyColumnPlaceholder`; and focus resting on a header the
pass just hid is never rescued.

The fix is to filter **units, from member data** rather than cards from widgets:

1. **Expanded group** — each member card is evaluated as today. The header is
   visible iff **≥ 1 member matches**; non-matching members hide individually.
2. **Collapsed group** — there are no member widgets, so the members' `Task`
   data is evaluated directly (the same predicate, factored out of the per-card
   branch so both paths share one implementation). The header is visible iff
   **≥ 1 member — or ≥ 1 member's child — matches**, so a collapsed group is
   still findable by a child's text, matching what the expanded view would show.
3. **Collapsed partial match** — the header stays visible and reports the match
   count (`▸ perf work (3) · 2 match`). A collapsed group deliberately does
   **not** auto-expand and does **not** hide non-matching members, because none
   are rendered; the count is what tells the user to expand.
4. **Column content** — a visible `GroupHeader` counts as content, so
   `cols_with_visible` includes its column and the empty placeholder stays
   hidden.
5. **Focus rescue** — `GroupHeader` joins the isinstance tuple that triggers
   `_refocus_column`.
6. **Scoped pass** — `apply_filter(cols=…)` queries `GroupHeader` within the
   scoped columns too, not just `TaskCard`.

**Ownership and ordering.** t1243_4 introduces `apply_filter(cols=…)` before any
group exists, so its only obligation is to **not bake in a card-only
assumption**: the match predicate is factored into a data-level helper and the
visible-content accumulator is widget-kind-agnostic. t1243_10 then generalises
the pass to units — building on the focus-unit abstraction t1243_9 lands — and
owns the full test matrix: expanded + search, collapsed + search, base filter,
add-on filter, partial match, no match, empty-placeholder interaction, focus
rescue off a hidden header, and the scoped-`cols` variant of each.

### Rejected data models

1. **`board_config.json` registry** (`groups[]` with membership + order + title +
   colour). Cheapest group move, but creating a group at runtime requires writing
   the **project** layer, which `aidocs/framework/tui_conventions.md` prohibits;
   membership desynchronises from task files on rename / archive / delete / fold;
   and it duplicates state that already has a home.
2. **Hybrid** (membership in frontmatter, title/colour in config). Same
   project-layer write problem, and splits one concept across two drifting files.
   *Kept as a later enhancement:* a read-only project-layer `board_groups` block
   for pretty titles/colours — additive, out of v1 scope.
3. **Overload `anchor`.** `anchor` is a semantic topic key with cross-tool
   consumers (`topic_semantics`, `trail_gather`, By-Topic view,
   `aitask_create.sh` parent inheritance, `normalize_anchor_id` validation).
   Board moves must not mutate semantic metadata, and a user may legitimately
   want a topic anchor and a board group at once.

---

## Workstream D — selection and bulk commands

### Child tasks are excluded from selection in v1 — explicitly

Every movement action early-returns on `focused.is_child`, `check_action` hides
the bindings for child cards, and `move_task_col` resolves parents only — a
marked child handed to the persistence API would be silently ignored. v1 keeps
that contract rather than half-changing it:

- `space` on a child card is a **no-op with a notify** ("child tasks move with
  their parent"), not a silent nothing.
- The task-select subdialog **omits** child rows.
- `move_tasks_to_column` / group-membership APIs **fail closed** on a child id,
  returning a which-items report rather than skipping silently.
- Both paths are tested: rejected (child marked → refused with the reason) and
  allowed (parent with expanded children → the whole block travels).

Independently movable children is a separate design question (it conflicts with
the filesystem parent-child model) and is recorded as out of scope.

### The commands

- **`space` marks the focused parent card** — `☑` bold-yellow / `☐` `#6272A4` in
  `.task-title-row`, always visible (t1004; a glyph, not a border, because
  `TaskCard.on_focus` overwrites the border imperatively). State is an app-level
  `MarkedSelection` keyed by filename, mirroring
  `brainstorm/utils.py::NodeSelection`; cleared on view change and refresh;
  guarded by the house `_modal_is_active()` idiom.
- **`m` — "Move to column…"**: acts on the marked set, else the focused card.
  With focus on a column it first opens a `SelectionList` **task-select
  subdialog** scoped to that column (the `WorkReportTaskSelectScreen` pattern,
  seeded with current marks), then chains to `ColumnSelectScreen` — the two-stage
  `push_screen`-with-callback flow `action_work_report` already uses. The
  synthetic `"unordered"` entry must be injected by hand.
- **`G` — "Group…"**: add marked tasks to a group (existing slug or a new one),
  remove marked tasks from their group, rename a group.
- **Command palette** entries for all of the above. **Before adding any**, the
  verbatim duplication between `KanbanCommandProvider.discover()` and `.search()`
  is collapsed into one `_COMMANDS` tuple ("Refactor duplicates before adding to
  them").
- A `BoardGroupField` is added to `TaskDetailScreen`, following the `AnchorField`
  pattern the board documents as mandatory for a new field.

---

## Decomposition — 14 children + a manual-verification sibling

Children auto-depend on siblings, so the numbering is the implementation order.
Each child owns its tests and opens with an anchor re-verification step.

| # | Child | Scope | Verification |
|---|---|---|---|
| 1 | `movement_baseline_and_harness` | `tests/test_board_movement.py`: **real task files** in a temp tree, driven from an **isolated subprocess**. `TASKS_DIR` is a module-load constant, and `bash tests/run_all_python_tests.sh` runs every `test_*.py` in **one** pytest process where 16 board tests already import `aitask_board` in `setUpClass` — so setting `TASK_DIR` in-process is a no-op against a cached module and the harness would silently exercise the **real** `aitasks/` tree. The parent test therefore spawns a child interpreter with `TASK_DIR` set, which imports the board fresh and writes results to a **JSON path passed as an argument** (not stdout, which carries Textual/pytest noise). Includes a `reload_and_save_board_fields` call-count spy and a **byte/path differ**. Plus the **pre-registered** profile method, premise rule and target rule above, run to produce the baseline. Characterizes today's four move ops in a self-enforcing flip table. Ends with the **decision checkpoint**: if the premise is refuted, revise/replace/postpone t1243_4 and t1243_5 and record it here. | Suite exits 1 when a guarded behaviour is reverted. **Run and assert identical results both standalone (`pytest tests/test_board_movement.py`) and via the full `run_all_python_tests.sh` suite**, plus a negative control proving the in-process variant would have read the real tree. Baseline table and checkpoint decision are deliverables. |
| 2 | `board_field_persistence_seam` | `reload_and_save_board_fields(semantic=False)` iterating `BOARD_KEYS`; `semantic=True` advances `updated_at`; retire the dead `Task._BOARD_KEYS`. Prerequisite for every group write and a latent-bug fix today. | External-concurrent-edit test: mutate a board field in memory, rewrite `status` on disk between mutation and save → both survive. `semantic=True` advances `updated_at`, `False` leaves it byte-identical. Missing file still not recreated. A synthetic third board key round-trips. |
| 3 | `gap_indexing` | `lib/board_ordering.py` + the manager API; rewire the four movement actions; retire `swap_tasks`; rename `normalize_indices` → `respace_column`; route every index read through `normalize_board_idx`. Flips the t1243_1 table. Carries the reverse pointer to t1210_5. | Pure-module unit tests; **exactly 1** write with an exact changed-path set on a healthy column; at-bound → still no compaction; over-bound → **exactly one** `respace_column` then success, all writes confined to that column; multi-hop transit dirties nothing outside the moved task; a legacy `10`-spaced column self-heals once. |
| 4 | `render_filter_scoping` | Scoped `apply_filter(cols=…)`, cached haystack, no-op display skip, targeted `modified_files` update replacing per-keypress `refresh_git_status()`. The match predicate is factored into a **data-level helper** and the visible-content accumulator is **widget-kind-agnostic**, so t1243_10 can generalise the pass to units without a rewrite. **Scope is subject to t1243_1's checkpoint.** | Spy proving a move queries only touched columns and spawns no subprocess; render-level assertions; the predicate helper is unit-tested against `Task` data with no widget mounted; **must meet the pre-registered ≥ 30 % median-latency target**, not merely pass structural checks. |
| 5 | `lateral_dom_transplant` | **Spike first**, then `_card_block()` + `_transplant_block()` with `column_id` identity handled and async dispatch. **Documented fallback** to `refresh_columns`. **Scope is subject to t1243_1's checkpoint.** | Real-Pilot: focus, `.child-wrapper` travel, post-move filter correctness, scroll sanity, `_get_focused_col_id` reports the destination. Latency delta recorded either way. |
| 6 | `multiselect_marking` | `MarkedSelection`, `space` binding, `☑`/`☐` glyph, footer + `check_action` gating, clear-on-view-change, `:focus:hover` accent-shade rules (the board has none), child-card refusal with notify. | Render assertions for both glyph states; marks survive a filter pass, cleared on view switch; `space` inert while a modal is open; child card refused with a reason. |
| 7 | `move_to_column_command` | `KanbanCommandProvider` de-duplication **first**, then `m` + task-select subdialog + `ColumnSelectScreen` chain + `move_tasks_to_column`. Injects the synthetic `unordered` entry; excludes child rows. Carries the reverse pointer to t1210_5. | Modal-chain construction spies; K marked → exactly K writes in input order with an exact changed-path set; `None` (Esc) vs `[]` distinguished; a child id fails closed with a which-items report. |
| 8 | `boardgroup_field_and_model` | The `BOARD_LAYOUT_KEYS` / `BOARD_KEYS` split; narrow `_KEEP_LOCAL_FIELDS`; **supply the merge base from git's conflicted index** — `aitask_sync.sh` extracts `task_git show :1:<path>` and passes `--base-file`, `merge_frontmatter` takes it as a third side (the diff3 marker path is production-dead: no `merge.conflictStyle` is configured anywhere) — and resolve `boardgroup` by **base-aware change detection, failing closed to unresolved/PARTIAL** when both sides changed or no base exists; the `""` tombstone contract; `--boardgroup` in `aitask_update.sh` (update-only, mirroring `--boardidx`); slug validation; `lib/board_groups.py` providing the **INV-R derivation** (unit bucketing + sort keys) and the shared match predicate; fold no-op note in `aitask_fold_mark.sh`; full extension-points sweep. **No contiguity requirement — grouping never writes an index.** | Pure unit tests for the INV-R derivation (scattered indices, ties, an interleaved non-member) and the **two post-sync fixtures** (remote add, remote remove) rendering identically and stably; merge unit tests for local-only, remote-only, both-same, both-different (PARTIAL), deletion from each side, no base (PARTIAL), identical, absent-both; a **temporary-repository integration test** producing a real unrelated-edit-vs-`boardgroup` conflict through the actual rebase path under the default conflict style and asserting the correct side wins, with a withheld-base negative control; a guard test that every `aitask_sync.sh` driver invocation passes `--base-file`; `aitask_update.sh` round-trip advances `updated_at`; a group field survives the t1243_2 save seam. |
| 9 | `group_focus_and_rendering` | `GroupHeader` (with `column_id`), flat composition, singleton renders as a plain card, `x` extended to headers. The **focus-unit abstraction**: `_focused_unit`, `_get_column_units` / `_visible_column_units`, unit-aware `_column_focus_target` and `_get_focused_col_id`, the restated one-anchor invariant, `↑`/`↓`/`←`/`→` over units, and movement dispatch (header → whole block, member → that member only, with the lateral-move-leaves-the-group notify). | Real Pilot: focus and nav through a column of **only collapsed groups**; enter/exit an expanded group with `↓`/`↑`; `←`/`→` preserve positional index across columns; movement from a header moves the block, from a member moves the member, from a child is refused; refocus lands correctly after collapse, after a block move and after a member move; and a dedicated **integration case for a grouped parent with visible children** pinning the header→member→children→next-member→next-unit sequence, lateral positional preservation across it, collapse refocus, and child adjacency after a block move. |
| 10 | `group_collapse_and_filtering` | `settings.collapsed_groups` in the **user** layer, the five lifecycle owners above, the coalesce key-combination rule, the prune-on-load sweep, and the **unit-level `apply_filter`** per the section above: header visibility from member *data*, collapsed match-count badge, headers counted as column content, focus rescue off headers, scoped-`cols` coverage. | The full filtering matrix — expanded + search, collapsed + search, **collapsed group matched only via a member's child**, base filter, add-on filter, partial match, no match, empty-placeholder interaction, focus rescue off a hidden header, and the scoped-`cols` variant of each; **restart-and-assert after each of the five transitions**; stale keys pruned; no project-layer write ever issued. |
| 11 | `group_formation_and_block_moves` | Formation and removal write **only** `boardgroup` (K writes / 1 write, no index rewrites); generalise `_card_block()` to group blocks; lateral / vertical / to-edge block moves with opportunistic contiguity; coalesce-on-move; the `delete_column` `board_idx = 0` tidy-up. | Exact changed-path sets: formation touches only the K grouped files and no index; removal touches only the ungrouped file — **neither has a gap or compaction case, because neither assigns a rank**; lateral (N) and vertical (N) with the neighbouring unit provably untouched, each with at-gap / exhausted-gap / retry plus the K = 1023/1024/1025 stride boundary; reload round-trip after every operation. |
| 12 | `group_membership_commands` | `G` command + palette entries (add / remove / rename), reusing the t1243_6 marked set and the t1243_7 subdialog; **rename-onto-existing-slug confirm modal**; `BoardGroupField` in `TaskDetailScreen`. | Modal-chain spies; rename rewrites exactly the member files and migrates the collapse key; rename onto an existing slug prompts and, on cancel, writes nothing; removing the last member dissolves the group and drops its key; child ids refused. |
| 13 | `documentation` | `website/content/docs/tuis/board*.md` and every frontmatter-field doc surface for `boardgroup` from the extension-points checklist (seed instructions + AGENTS.md mirror, `CLAUDE.md`, `docs/development/task-format.md`, `task-creation-batch.md`, board reference row). | Drift grep: every documented key exists in `BINDINGS`; the field appears in all enumerated surfaces. |
| 14 | `retrospective_benchmark` | Re-measure against the t1243_1 baseline using the same pre-registered method; record outcomes; file standalone follow-ups **only** if the data justifies them (`STEP` retuning, remaining hotspots, the Tier-2 fallback if the spike failed). | The recorded measurement table is the deliverable. |
| 15 | `manual_verification_*` | Aggregate manual-verification sibling seeded from the children's `## Verification` sections (marking, group collapse across transitions, block moves, bulk move, cross-PC sync of a group **and of a group removal**). | Pass/Fail/Skip checklist. |

---

## Risk

### Code-health risk: medium

- Twelve of the fifteen children edit `aitask_board.py`, which has grown from
  7378 to 9043 lines across six commits while this task was being planned ·
  severity: medium · → mitigation: every anchor is a symbol name, every child
  plan opens with an anchor re-verification step, the whole current-state table
  was re-verified after the most recent of those commits (t1268) and still
  holds, and the in-flight scan is re-run immediately before creation.
- Gap indexing changes an on-disk ordering contract with three consumers ·
  severity: medium · → mitigation: readers only *sort*; the real-file
  characterization suite lands **before** the change; arithmetic isolated in a
  pure module.
- Four independent silent-failure seams meet on one new field: the save path
  drops unnamed board keys, the merge rule prefers local on divergence,
  one-sided presence resurrects deleted values, and a task-wide `updated_at`
  lets an unrelated edit decide membership · severity: **high** ·
  → mitigation: t1243_2 fixes the save/timestamp seam ahead of all group work;
  t1243_8 replaces the timestamp proxy with **base-aware change detection**
  sourced from git's conflicted index (the diff3 marker base is unavailable in
  production), fails closed to PARTIAL, keeps the `""` tombstone for explicit
  deletion, and proves the rule through a real-conflict integration test rather
  than marker fixtures.
- A cross-parent DOM move is not a supported Textual 8.2.7 operation, and
  `column_id` is read in 12 places · severity: medium · → mitigation: t1243_5 is
  spike-first with a documented fallback that still banks the Tier-1 win.

### Goal-achievement risk: medium

- "The render pass is the wall" is an inference, not a measurement · severity:
  medium · → mitigation: pre-registered method, premise rule and target rule in
  t1243_1, plus a decision checkpoint empowered to revise, replace or postpone
  t1243_4 and t1243_5 before they are picked.
- Grouping is shared (newer-wins) while ordering stays per-checkout
  (local-wins), so no persisted contiguity invariant can survive a sync ·
  severity: **high as originally designed** · → mitigation: contiguity was
  **dropped**; INV-R makes render a pure function of persisted state, so a
  remote add or remote remove needs no reconciliation write. Pinned by the two
  post-sync render fixtures in t1243_8.
- INV-R must hold across formation, removal, both move axes, coalescing,
  `delete_column` and reload round-trips · severity: medium · → mitigation: the
  derivation is a single pure function with property tests per transition.
- The movement harness can silently read the real `aitasks/` tree in a
  full-suite run · severity: medium · → mitigation: subprocess isolation with a
  JSON result channel, verified standalone **and** in-suite, with a negative
  control proving the in-process variant fails.
- Collapse keys encode two mutable identifiers · severity: medium ·
  → mitigation: explicit lifecycle ownership per transition plus a prune-on-load
  backstop, each restart-tested.
- t1210_5 could be claimed mid-decomposition · severity: medium ·
  → mitigation: the `--deps 1210_4,1243` guard is applied **before** any child is
  created and swapped atomically afterwards; if the swap fails the guard holds.
- v1 groups have no title/colour and exclude child tasks · severity: low ·
  → mitigation: both recorded as explicit, reversible v1 boundaries with the
  additive next step named.

### Planned mitigations

No blocking pre-work mitigation tasks are needed — the coordination edges on
`t1210_5` are dependencies, not mitigation tasks.

The one follow-up mitigation is **t1243_14 `retrospective_benchmark`**, created
as a child at decomposition time (this parent ends at the child checkpoint, so
the Step 8d follow-up hook never runs).

---

## Verification (this parent)

1. `t1210_5` was guarded with `--deps 1210_4,1243` **before** any child was
   created, and afterwards carries `--deps 1210_4,1243_3,1243_7` plus a
   `## Notes for sibling tasks` entry naming the replacement API; `t1243_3` and
   `t1243_7` carry the reverse pointer.
2. Fifteen child task files exist under `aitasks/t1243/`, each with Context, Key
   files, Reference patterns, Implementation plan and Verification sections, and
   each independently executable from a fresh context.
3. Fifteen child plans exist under `aiplans/p1243/`, committed together.
4. A fresh in-flight scan was re-run immediately before creation and no live
   board editor was found (or a dependency was added if one was), and every
   child plan carries its anchor re-verification step.
5. The parent is reverted to `Ready` with its lock released, and shows as
   "Has children" in `ait ls`.
6. Every AC bullet in the task file is answered above: data model picked with
   rejected alternatives; ordering scheme with the qualified write guarantee and
   INV-R holding across every transition including post-sync; collapse-state
   persistence, lifecycle and collision handling decided; riskiest-first
   decomposition; children covering all seven named areas.

## Step 9 (Post-Implementation)

Not applicable in the usual form — a decomposing parent ends at the child
checkpoint in Step 6 rather than merging code. Archival of t1243 happens
automatically when its last child is archived.
