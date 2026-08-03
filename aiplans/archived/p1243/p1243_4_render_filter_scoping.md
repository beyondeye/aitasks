---
Task: t1243_4_render_filter_scoping.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_10_group_collapse_and_filtering.md, aitasks/t1243/t1243_11_group_formation_and_block_moves.md, aitasks/t1243/t1243_12_group_membership_commands.md, aitasks/t1243/t1243_13_documentation.md, aitasks/t1243/t1243_14_retrospective_benchmark.md, aitasks/t1243/t1243_15_manual_verification_board_groups_and_reordering.md, aitasks/t1243/t1243_5_lateral_dom_transplant.md, aitasks/t1243/t1243_6_multiselect_marking.md, aitasks/t1243/t1243_7_move_to_column_command.md, aitasks/t1243/t1243_8_boardgroup_field_and_model.md, aitasks/t1243/t1243_9_group_focus_and_rendering.md
Archived Sibling Plans: aiplans/archived/p1243/p1243_1_movement_baseline_and_harness.md, aiplans/archived/p1243/p1243_2_board_field_persistence_seam.md, aiplans/archived/p1243/p1243_3_gap_indexing.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-03 12:03
---

# t1243_4 — Render filter scoping

## Context

`ait board`'s render pass is whole-board on every keypress. `KanbanApp.apply_filter`
(`aitask_board.py:6516`) iterates `self.query(TaskCard)` over **every** card, assigns
`card.styles.display` unconditionally, rebuilds `f"{filename} {metadata}".lower()` per
card when a search is active, and runs a second app-wide query over
`EmptyColumnPlaceholder`. On top of that each of the three movement actions calls
`TaskManager.refresh_git_status()` — a blocking `git status --porcelain` subprocess on
the UI thread — before repainting.

**This child no longer carries a latency target.** t1243_1's ablation (recorded in the
parent plan's "Decision checkpoint", user-confirmed) measured these two levers at
**0.4 % removable** against a 30 % target, because the column recompose is 93.6 % of a
2173.2 ms lateral keypress and belongs to **t1243_5**. The scope was retained for two
non-latency reasons:

1. **t1243_10 structurally depends on it.** A collapsed group mounts a `GroupHeader` and
   *none* of its member cards, so the match decision must be computable from `Task`
   **data** with no widget mounted, and the visible-content accumulator must accept a
   widget kind that is not a `TaskCard`.
2. **Removing the per-keypress `git status` subprocess** — git churn / hygiene.

Structural assertions are the pass condition; latency is a **no-regression guard** only.

### Anchor re-verification — done (HEAD `c63aa808e`, 9429 lines)

| plan premise | current state |
|---|---|
| `apply_filter` at `:~5900`, `~12` call sites | **`:6516`, 14 call sites** (7 deferred via `call_after_refresh`, 7 sync) |
| `normalize_indices` still in move paths | **gone** (t1243_3); movers call `move_task_to_column` / `reposition_task` / `move_task_to_edge` |
| `refresh_git_status()` per move | **still true** — `:8459`, `:8524`, `:8578`; t1243_3 left them verbatim and handed them here |
| `refresh_git_status` misses `OSError` (p1243_1 upstream note) | **already fixed** (`:1156` catches it) — no action |
| `TaskCard.task_data` reassigned after construction | **never** — only `__init__` (`:1840`) |
| column resolution needs a new scan | **no** — `_column_widget(col_id)` (`:6953`) and `_column_widgets()` (`:6942`) already exist; reuse them |
| `FLIP_TABLE` / `EXPECTED_CALL_SITES` need editing | **no** — this change alters no write counts and adds/removes no `reload_and_save_board_fields` call site. Both frozen tables stay untouched **by design**; if either goes red, that is a real finding, not a table to update. |

Verified safe: movement is hidden in the derived views (`check_action`, `:6035-6042`
returns `False` for `inflight`/`bytopic`/`bytrail`), so a scoped pass can only originate
from the Kanban view. `_column_widget` covers every column class anyway.

---

## Step 1 — Data-level match predicate + memoized haystack (`aitask_board.py`)

**`Task` gains a memoized haystack.** Deviation from the task file, recorded
deliberately: the task says "cache per `TaskCard` at construction". Caching on the
**`Task`** instead satisfies the same goal *and* is what t1243_10 actually needs, since a
collapsed group's members have no card to hang a cache on. It also closes a hole the
card-level cache would open: `_move_task_vertical` mutates `board_idx` and then reorders
the DOM **without** a recompose, so a card-lifetime cache would serve a stale haystack
(the haystack stringifies the whole metadata dict, board keys included).

```python
class Task:
    def __init__(self, filepath: Path):
        ...
        self._search_haystack = None      # memo; see `search_haystack`
        self.load()

    def _invalidate_search_haystack(self):
        self._search_haystack = None

    @property
    def search_haystack(self) -> str:
        """Lowercased ``"<filename> <metadata>"`` — the search corpus, memoized.

        Rebuilt per card per filter pass before t1243_4. The memo is invalidated at
        the FULL set of sites that can change its inputs, enumerated rather than
        assumed:
          * `load()`          — metadata replaced wholesale (also the `reload_task`
                                path: it calls `load()` on the SAME object).
          * `save()`          — the tail of every persisted metadata mutation
                                (`save_with_timestamp`, the detail-screen edits at
                                :4736 / :5007, the dep-cleanup helpers at :2903 /
                                :2976).
          * `board_col` / `board_idx` setters — in-memory board-key mutation with no
                                save in between (the gap-indexing movers).
        A metadata mutation that is neither saved nor a board-key write would go
        stale; there is none today (grep `.metadata[...] =` — every site saves).
        """
        if self._search_haystack is None:
            self._search_haystack = f"{self.filename} {self.metadata}".lower()
        return self._search_haystack
```

Invalidate in `load()` (`:228`), `save()` (`:250`), and both board-field setters
(`:318`, `:326`). **`Task.from_text` (`:213`) uses `cls.__new__` and sets every attribute
by hand — it must set `task._search_haystack = None` or the property raises
`AttributeError` on archived tasks.**

**The predicate — module level, takes a `Task`, never a widget:**

```python
def task_matches_filter(task, visible: set | None, search: str) -> bool:
    """Filter decision over task DATA. No widget required.

    t1243_10 evaluates collapsed-group members that mount no card at all, so this
    must never take a widget and must stay callable per member (so a *count* of
    matching members is computable, not just a boolean per card).
    `visible=None` is the existing "all cards eligible" sentinel; `search` is
    already lowercased by the caller (`on_search`, :6513).
    """
    if visible is not None and task.filename not in visible:
        return False
    if search and search not in task.search_haystack:
        return False
    return True
```

**The display writer — module level, widget-kind-agnostic, no-op-guarded:**

```python
def set_unit_display(unit, is_visible: bool) -> None:
    """Show/hide one filter unit, skipping no-op assignments.

    Assigning `styles.display` triggers a Textual refresh even when the value is
    unchanged, and most cards on any given pass do not change. `is_child` is read
    with `getattr` so a future non-card unit (t1243_10's `GroupHeader`) needs no
    branch here.
    """
    display = "block" if is_visible else "none"
    if unit.styles.display != display:
        unit.styles.display = display
    # An expanded child card lives inside a `.child-wrapper` Horizontal that also
    # holds the "↳" connector Static; hiding only the card leaves a bare connector.
    wrapper = unit.parent
    if (getattr(unit, "is_child", False) and isinstance(wrapper, Horizontal)
            and wrapper.has_class("child-wrapper")
            and wrapper.styles.display != display):
        wrapper.styles.display = display
```

## Step 2 — Scope `apply_filter`

```python
def apply_filter(self, cols: set | None = None):
    """Apply base filter ∩ add-ons ∩ search.

    `cols=None` is today's whole-board pass, byte-for-byte — view and filter
    toggles depend on it. A `cols` set restricts the pass to those columns' units,
    their placeholders and their focus rescue: a scoped pass must never flip a
    placeholder in an untouched column.
    """
```

Two small scoped iterators.

> **AS-SHIPPED — this section was rewritten during implementation.** The version
> planned here resolved each column with `self._column_widget(col_id)` and iterated
> `col.query(TaskCard)`, per the task file's stated method. **Measured, it was a 10x
> pessimization** (see Final Implementation Notes, deviation 2): `query()` walks the
> whole tree wherever it is rooted, so the resolution cost dominates. What shipped
> filters ONE app-wide query by `column_id`. The scoping contract — only units in
> `cols` are decided, displayed or accumulated — is identical; only the mechanism
> differs.

```python
def _filter_units(self, cols):
    """The widgets whose visibility this pass decides.

    Yields `TaskCard`s today. t1243_10 adds `GroupHeader` HERE, as a second query
    filtered the same way — the accumulator below reads only `.column_id`, so a
    second widget kind needs no rewrite of the loop or of the scoping.
    """
    for card in self.query(TaskCard):
        if cols is None or card.column_id in cols:
            yield card

def _filter_placeholders(self, cols):
    for placeholder in self.query(EmptyColumnPlaceholder):
        if cols is None or placeholder.column_id in cols:
            yield placeholder
```

Body becomes:

```python
    cols_with_visible = set()
    for unit in self._filter_units(cols):
        v = task_matches_filter(unit.task_data, visible, self.search_filter)
        set_unit_display(unit, v)
        if v:
            cols_with_visible.add(unit.column_id)

    for placeholder in self._filter_placeholders(cols):
        set_unit_display(placeholder, placeholder.column_id not in cols_with_visible)

    focused = self.screen.focused if self.screen else None
    if (isinstance(focused, (TaskCard, EmptyColumnPlaceholder))
            and (cols is None or focused.column_id in cols)
            and focused.styles.display == "none"):
        self._refocus_column(focused.column_id)
```

The `visible`-set computation (`:6518-6533`) is unchanged — it runs once per pass, not
per card. The focus-rescue `cols` gate is safe because only this pass's own columns can
have been hidden by it; a widget hidden by an earlier pass was already rescued then.

**Call sites that pass `cols` (3 of 14); every other site keeps the whole-board pass:**

| site | change |
|---|---|
| `refresh_column` `:6483` | `self.call_after_refresh(self.apply_filter, {col_id})` |
| `refresh_columns` `:6508` | `self.call_after_refresh(self.apply_filter, set(col_ids))` |
| `_swap_adjacent_cards` `:8493` | `self.apply_filter({col_widget.col_id})` |

Unchanged (`None`): `_rerender_trail` `:6290`; the four `refresh_board` branches `:6377`
`:6387` `:6393` `:6419`; `on_search` `:6514`; the type-filter dialog `:6741` `:6749`;
`_toggle_git_filter` `:6822`; `_toggle_type_filter` `:6835`; the detail-cancel branch
`:7299`. Filter-state changes are global and must stay whole-board.

This is also the exact shape t1243_5 wires into: "`_move_task_lateral` /
`_move_task_to_extreme` … both then call the scoped `apply_filter(cols={src, dst})` from
t1243_4."

## Step 3 — Drop the per-keypress `git status`

`modified_files` (`:929`) holds git-porcelain relative paths and is read only by
`is_modified` (`:1398`, `str(task.filepath) in modified_files`). The gap-indexing block
already knows exactly which files it wrote, so mark at the **write site** in
`TaskManager` rather than at the caller — a caller that forgets loses the dirty marker
silently.

```python
def _mark_written(self, task) -> None:
    """Record a file this session just wrote as modified, without a `git status`.

    Add-only, by construction: a file that becomes clean again (a commit from
    another terminal, or an exact round-trip back to its committed index) stays
    marked until the next full scan. The full scan still runs on `refresh_board`
    (manual `r`, view switches, the auto-refresh tick), on the detail-screen return
    (`:7326`), and after the board's own commit (`_do_git_commit_tasks`) — all
    verified present.
    """
    self.modified_files.add(str(task.filepath))
```

Call it immediately after each of the four existing `reload_and_save_board_fields`
calls in the gap-indexing block — `move_tasks_to_column` `:1479`, `move_task_to_edge`
`:1498`, `reposition_task`, and `respace_column` `:1557`. **`respace_column` is why the
marking lives here and not in the actions:** `reposition_task` can compact, writing N
files that `MoveResult.moved` does not name, so a caller-side update keyed on `moved`
would under-mark exactly in the compaction case.

Then delete `self.manager.refresh_git_status()` from `_move_task_lateral` `:8459`,
`_move_task_vertical` `:8524` and `_move_task_to_extreme` `:8578` — nothing else changes
in those actions (the DOM work is t1243_5's).

Keeping the four direct `reload_and_save_board_fields` calls (rather than folding them
into one helper) is deliberate: `EXPECTED_CALL_SITES` in
`tests/test_board_persistence_seam.py` maps each caller to the field tuple it names, and
collapsing them would weaken that guard.

**Behavior change to record:** the dirty `*` marker no longer self-heals on every
movement keypress. It heals on `r`, a view switch, a detail return, or a commit. The
marker is read at `TaskCard.compose` time (`:1857`) only, so nothing repainted mid-move
before this change either.

## Step 4 — Tests (`tests/test_board_render_scoping.py`, new)

`bf.FixtureBoardTestBase` + `unittest.TestCase`, `sys.path` bootstrapped from `__file__`,
patch targets bound to `self.ab` (never the string `"aitask_board"`), a
`test_fixture_facts` precondition test, `if __name__ == "__main__": unittest.main()`.

`FIXTURE_TASKS` is class-scoped, so this splits into two classes: the movement cases
(§6, §7) use `bf.wide_topology(15)` — 3 parents per column, so every move is performable
— and the filter/scoping cases (§1-§5, §8) use `bf.DEFAULT_TOPOLOGY`. Focus a specific
card with the `_focus(B, app, filename)` helper idiom from `test_board_movement.py`.

1. **Predicate with no widget mounted** — the t1243_10 prerequisite. Build a `Task` from
   the fixture tree, call `ab.task_matches_filter(task, None, "<slug>")` /
   `(task, set(), …)` / a non-matching search. No `KanbanApp`, no Pilot.
2. **Memo lifecycle — every stated guarantee exercised, one case each.** Read
   `search_haystack`, then assert it changes after each of the four invalidation sites
   **separately**: `board_idx` setter, **`board_col` setter**, `load()`, `save()`. Plus a
   **`Task.from_text` construction case** — it bypasses `__init__` via `cls.__new__`, so
   assert an archived-task instance can *read* `search_haystack` at all (without the
   added `task._search_haystack = None` this raises `AttributeError`, which is precisely
   the regression). Negative control: drop each invalidation in turn and the
   corresponding case must fail — one control per site, not one for the group.
3. **`set_unit_display` skips no-ops** — a `_RecordingStyles` fake counting assignments:
   0 writes when already at the target, 1 when changing. Negative control: without the
   guard the count is 1 in both cases.
4. **Scoped iteration** — `_filter_units({c0, c1})` yields exactly `_get_column_cards(c0)
   + _get_column_cards(c1)`; `_filter_units(None)` yields every card (the discriminating
   control).
5. **A scoped pass leaves untouched columns alone — seeded sentinel.** Pre-set a card in
   an untouched column to `display="none"`, press `shift+right`, assert it is **still**
   `"none"`. A whole-board pass would flip it back to `"block"`; the unscoped
   `apply_filter()` call is the negative control that proves the test discriminates.
   Also assert the `cols` actually passed on the keypress via a spy on `apply_filter`.
6. **No move spawns a subprocess — all three action families, parameterized.** One case
   per binding, not one for lateral: `shift+right` / `shift+left` (`_move_task_lateral`),
   `shift+up` / `shift+down` (`_move_task_vertical`), `ctrl+up` / `ctrl+down`
   (`_move_task_to_extreme`). A retained `refresh_git_status()` in *any* of the three
   would otherwise pass a lateral-only suite. Use `bf.wide_topology(15)` so every column
   holds 3 parents and each move is actually performable.

   Each case asserts, in this order:
   1. **The move happened** — a `reload_and_save_board_fields` write spy recorded ≥ 1
      write. Without this precondition an early-returned action (focused card already at
      the extreme, or a child card) spawns nothing and the "no subprocess" assertion
      passes **vacuously** — the same trap as the benchmark harness's zero-write validity
      invariant.
   2. **No subprocess** — `patch("subprocess.run", side_effect=spy)` around the keypress
      (the `FixtureCwdDependencyTests` idiom in `test_board_bytrail_view.py`) records an
      empty spawn set.
   3. **The dirty marker landed** — `manager.modified_files` gained exactly
      `str(task.filepath)` for the file the spy saw written.

   Negative control (proves the spy sees spawns at all): the same spy around `r`
   (`refresh_board`) **must** record `git status`.
7. **Targeted marking equals the real scan — genuinely independent ground truth.**
   `refresh_git_status()` **clears and repopulates `manager.modified_files` itself**, so
   calling it on the manager under test would overwrite the observed value and compare
   the scan with itself — concealing a wrong `_mark_written`. Instead, for each of the
   four manager operations (including a forced compaction):
   1. snapshot `observed = set(manager.modified_files)` **before** any scan;
   2. derive `expected` from a **separate, freshly constructed `TaskManager`** whose
      `refresh_git_status()` scans the same tree (patch-mode, no app — `__init__` runs
      `load_tasks` but never touches git status, so its set is a clean independent scan);
   3. cross-check both against `bf.diff_snapshots` (filesystem sha deltas over the
      allowlist).

   Three sources — our bookkeeping, a real `git status` from an untouched manager, and
   the filesystem — none of which is derived from the others.
8. **Placeholder interaction under a scoped pass** — a column filtered empty shows its
   `EmptyColumnPlaceholder`; a scoped pass does not flip an untouched column's
   placeholder.

## Verification

- `bash tests/run_all_python_tests.sh` — read **only** the last line
  (`PYTHON SUITE: PASSED|FAILED`); use `set -o pipefail` if piping.
- `tests/test_board_view_filter.py` passes **unchanged** — the `cols=None` path is
  behaviour-preserving.
- `tests/test_board_movement.py`, `test_board_manager_moves.py`,
  `test_board_persistence_seam.py`, `test_board_ordering.py` pass with `FLIP_TABLE` and
  `EXPECTED_CALL_SITES` **unedited**.
- Prove the new guards can fail: each "must not happen" assertion is run once against a
  deliberately broken source, and the suite must exit 1.
- **Latency no-regression guard** (not a target): `AITASK_BOARD_BENCH=1 python3 -m pytest
  tests/test_board_movement.py -v -k bench`, before and after. Median keypress latency
  must not regress on either axis versus lateral **2173.2 ms** / vertical **184.1 ms**.
  Record the delta and the dominant remaining span in the parent plan for t1243_14.
  Note the `git_status` span will read 0.0 after this change — verified harmless: none of
  the four per-sample validity invariants requires it to be non-zero, and the
  `no_af_git` ablation config degrades to a no-op rather than failing.
- Manual smoke in a real `ait board`: move a card laterally / vertically / to an extreme
  with and without an active search, confirm the `*` marker appears and focus lands
  correctly.

## Risk

### Code-health risk: medium
- A scoped call site that under-names the columns it changed leaves a card at a stale `display` — `apply_filter` is the terminus of every repaint path (14 call sites) · severity: medium · → mitigation: none (covered in-task by the seeded-sentinel test §4.5 and its unscoped negative control)
- The memoized haystack introduces an invalidation contract; a *future* in-memory metadata mutation that never calls `save()` would serve a stale search corpus silently · severity: medium · → mitigation: none (covered in-task by §4.2, whose negative control proves each invalidation site is load-bearing)
- The dirty `*` marker becomes add-only between full scans, so a file that becomes clean elsewhere keeps its marker until `r` / a view switch / a commit · severity: low · → mitigation: none (bounded; the four full-scan sites are verified present)

No mitigation tasks confirmed (user decision).

### Goal-achievement risk: low
- The Task-level memo deviates from the task file's "cache per `TaskCard`" wording; recorded explicitly, and it strictly supersets the stated requirement (it is also what t1243_10's widget-less members need) · severity: low · → mitigation: none needed

## Step 9 — Post-Implementation

Merge to `main` (current-branch profile, no worktree), then archive per the shared
workflow.

## Final Implementation Notes

- **Actual work done:** two files.
  - `.aitask-scripts/board/aitask_board.py` (+171/−33):
    - `Task.search_haystack` — memoized lowercased `"<filename> <metadata>"`, with
      `_invalidate_search_haystack()` called from `load()`, `save()`, and both the
      `board_col` / `board_idx` setters; the memo slot is seeded in `__init__` **and**
      in `from_text` (which bypasses `__init__` via `cls.__new__`).
    - `task_matches_filter(task, visible, search)` — module-level, takes a `Task`,
      never a widget. The t1243_10 prerequisite.
    - `set_unit_display(unit, is_visible)` — module-level, widget-kind-agnostic
      (`getattr(unit, "is_child", False)`), skips no-op `styles.display` writes and
      carries the `.child-wrapper` handling.
    - `apply_filter(cols=None)` plus `_filter_units` / `_filter_placeholders`; scoped
      placeholder update and scoped focus rescue.
    - `TaskManager._mark_written(task)` called at all four gap-indexing write sites
      (`move_tasks_to_column`, `move_task_to_edge`, `reposition_task`,
      `respace_column`); `refresh_git_status()` deleted from `_move_task_lateral`,
      `_move_task_vertical` and `_move_task_to_extreme`.
    - Scoped `apply_filter` wired at exactly 3 of the 14 call sites: `refresh_column`,
      `refresh_columns`, `_swap_adjacent_cards`.
  - `tests/test_board_render_scoping.py` — **new**, 644 lines, 33 tests in four
    classes.
  - `FLIP_TABLE` and `EXPECTED_CALL_SITES` deliberately **not** edited, as predicted at
    planning time; both stayed green.

- **Deviations from plan:**

  1. **The search-haystack memo lives on `Task`, not on `TaskCard`** — contrary to the
     task file's "cache per `TaskCard` (at construction / when its task data is
     replaced)". Planned as a deviation up front and confirmed correct in
     implementation, for two independent reasons: **(a)** t1243_10 filters collapsed
     group members that mount **no card at all**, so a card-level memo is unreachable
     exactly where that child needs it; **(b)** `_move_task_vertical` mutates
     `board_idx` and then reorders the DOM through `_swap_adjacent_cards` **without a
     recompose**, so the card survives its own task's mutation — and because the
     corpus stringifies the whole metadata dict (board keys included), a card-lifetime
     memo would serve a stale string on that path. Task-level invalidation covers both.
     The invalidation surface is enumerated in the property's docstring rather than
     assumed, and each of the four sites has its own test **and** its own negative
     control.

  2. **`_filter_units` / `_filter_placeholders` filter one app-wide query by
     `column_id` instead of querying each touched column widget** — contrary to both
     the task file ("via the column widget's own `query(TaskCard)`") and this plan's
     own Step 2, which has been corrected in place above. The literal method was
     implemented first and **measured as a 10x pessimization**. On a 200-card board:

     | | median |
     |---|---|
     | whole-board `apply_filter(None)` | 13.1 ms |
     | scoped `apply_filter({c0,c1})`, per-column resolution | **128.0 ms** |
     | `_column_widget('c0')` | 33.3 ms |
     | `_column_widgets()` | 24.8 ms |
     | `self.query(TaskCard)` | 6.8 ms |
     | `col.query(TaskCard)` | 1.4 ms |

     Textual 8.2.7's `query()` walks the entire tree wherever it is rooted, so
     `_column_widgets()` (four full-tree class queries) costs nearly twice the whole
     unscoped pass, and the planned code called it four times per pass. Even resolving
     once would have cost ~25 ms against the 13 ms it was meant to beat. Filtering a
     single `query(TaskCard)` costs ~6 ms, is cheaper than the whole-board pass, works
     for every column class without a class union, and preserves the t1243_10 seam
     (that child adds a second query filtered the same way). **The scoping contract is
     unchanged** — only units in `cols` are evaluated, display-written or accumulated,
     which is what the tests assert.

     Corollary worth carrying forward: `apply_filter`'s cost here is **DOM traversal,
     not per-unit work**, so column scoping can only ever buy a few percent. That
     independently corroborates t1243_1's measured 0.4% removable and is a second
     reason this child has no latency target.

  3. **One test added beyond the plan:** a render-level assertion
     (`test_moved_card_renders_the_dirty_marker`) that the moved card actually draws
     `t9005 *`. The plan's §4 had dropped the task file's "render-level assertions"
     requirement; `styles.display` is the right oracle for filtering, but the dirty
     marker is genuinely render-level and is the user-visible consequence of replacing
     the scan with targeted marking. Its negative control renders bare `t9005`.

- **Issues encountered:**
  1. **The latency guard caught a regression I introduced** — this is the whole reason
     it exists. The first post-change benchmark showed the vertical axis at 255.7 ms
     against a 184.1 ms baseline, and `R_rm4` (the removable share of
     `apply_filter` + `git_status`) at **27.8%** versus 0.4% at baseline. Because
     ablation is a *within-run* comparison, that signal was sound even though the run
     was contended: ablating `apply_filter` dropped the axis to 184.6 ms, i.e. back to
     baseline. Root cause was deviation 2's pessimization. After the fix: `af` span
     0.6% lateral (identical to baseline), `R_rm4` **1.4%**, and ablating
     `apply_filter` on the vertical axis makes it *slower* than leaving it in — its
     cost is below the noise floor, as at baseline.
  2. **The first benchmark run was self-contaminated.** Tests and negative controls
     were run concurrently with it. Absolute cross-run numbers were discarded; only
     the within-run ablation was used. Re-measured afterwards on a quieter box.
  3. **Absolute latencies remain ~4–10% above the t1243_1 baseline** (lateral 2395.2
     vs 2173.2 ms; vertical 191.9 vs 184.1 ms) and this is **not attributable to this
     change**: ~8 coding agents were active at ~4.9 load, the harness floor actually
     *improved* (94.3 vs 104.5 ms) so the box is not uniformly slower, and every
     within-run attribution puts `apply_filter` and `git_status` at ~0%. Recorded for
     t1243_14 as ambient drift, not regression.
  4. The bench prints `MISS t1243_4 opportunity (max R_rm4 >= 0.30): 1.4% vs 30%`.
     This is the **already-adjudicated** gate from t1243_1's user-confirmed checkpoint,
     not a new miss — this child carries no latency target. No corrective action taken
     and none is required.

- **Key decisions:**
  - **Mark at the write site, not in the movement action.** `reposition_task` can
    respace a whole column, writing N files its `MoveResult.moved` never names, so a
    caller-side update keyed on `moved` would under-report exactly in the compaction
    case. `_mark_written` sits next to each `reload_and_save_board_fields` call.
  - **The four `reload_and_save_board_fields` calls were deliberately NOT folded into
    a helper**, even though that would make the marking unforgettable:
    `EXPECTED_CALL_SITES` in `tests/test_board_persistence_seam.py` maps each caller to
    the field tuple it names, and collapsing them would weaken that guard. The
    behavioral marking test covers all four instead.
  - **Marking is add-only.** A file that becomes clean again keeps its marker until the
    next full scan. All four full-scan sites were verified present before removing the
    per-keypress one: `refresh_board` (manual `r`, view switches, auto-refresh tick),
    `_on_detail_result`, and `_do_git_commit_tasks`.
  - **The marking oracle uses three independent sources** — the observed set captured
    *before* any scan, a real `git status` from a separately constructed
    `TaskManager`, and a `bf.diff_snapshots` filesystem delta. `refresh_git_status()`
    clears and repopulates the manager it is called on, so scanning the manager under
    test would have compared the scan with itself.
  - **11 negative controls, one mutation each**, re-validated after the deviation-2
    rewrite. The two per-family ones are the load-bearing pair: restoring
    `refresh_git_status()` in *only* the vertical (or only the extreme) family fails
    exactly those cases while the lateral case still passes — which is what proves
    parameterizing over all three action families is not decorative.

- **Upstream defects identified:**
  - `aitask_board.py:7079-7096 — _column_widgets() issues four separate full-DOM class
    queries per call, so every _column_widget() lookup costs ~25 ms on a 200-card board
    (measured). It is called on the post-move refocus path via _card_fully_visible
    (:7118) and _focus_side_candidate (:7141), so a move pays it after the keypress.
    Out of scope here (this task stopped using it), but it is real cost sitting in
    t1243_5's territory — the residual 144.5 ms lateral keypress that remains once the
    recompose is ablated.`

- **Notes for sibling tasks:**
  - **t1243_5:** `apply_filter(cols={src, dst})` exists and is callable in exactly the
    shape your Step 3 specifies. Do **not** reintroduce per-column widget resolution
    inside the filter pass — measured at 10x worse (deviation 2). Your remaining
    lateral cost after ablating recompose is ~144.5 ms, and the `_column_widgets()`
    defect above is part of it. `refresh_git_status()` is already gone from
    `_move_task_lateral` / `_move_task_to_extreme`; the dirty marker now comes from
    `TaskManager._mark_written` at the write site, so a transplant that bypasses the
    manager's write helpers would silently lose the `*`.
  - **t1243_10:** both seams you depend on are in place and unit-tested with **no
    widget mounted**. `task_matches_filter(task, visible, search)` takes a `Task`, so
    collapsed members with no card can be evaluated, and it is deliberately per-task so
    you can *count* matching members rather than only ask a boolean. The accumulator
    reads only `.column_id`, and `_filter_units` / `_filter_placeholders` are
    single-query-plus-filter — add `GroupHeader` as a second query filtered the same
    way and both the scoped and unscoped paths work unchanged. `set_unit_display` reads
    `is_child` with `getattr`, so a header needs no branch. Note the search corpus is
    memoized **on the Task**, which is what makes evaluating an unmounted member cheap.
  - **t1243_14:** re-measure with `AITASK_BOARD_BENCH=1` and compare **within-run
    ablation**, not cross-run absolutes — this box carries 4–5 ambient load from
    concurrent agents and cross-run absolutes drift ~10%. Post-t1243_4 reference:
    lateral 2395.2 ms / vertical 191.9 ms, `af` span 0.6% lateral, `git` span 0.00% on
    both axes, `-recompose` lateral 144.5 ms.
  - Anyone benchmarking in this repo: **do not run other tests while a bench is in
    flight** (issue 2), and check for concurrent agents first — `ait_tmux list-panes`
    showed eight during this task.
