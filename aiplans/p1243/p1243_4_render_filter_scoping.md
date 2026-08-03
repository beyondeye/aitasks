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

Two small scoped iterators, both reusing the existing `_column_widget`:

```python
def _filter_units(self, cols):
    """The widgets whose visibility this pass decides.

    Yields `TaskCard`s today. t1243_10 adds `GroupHeader` HERE — the accumulator
    below reads only `.column_id`, so a second widget kind needs no rewrite of the
    loop or of the scoping.
    """
    if cols is None:
        yield from self.query(TaskCard)
        return
    for col_id in cols:
        col = self._column_widget(col_id)
        if col is not None:            # column not mounted -> it has no units
            yield from col.query(TaskCard)

def _filter_placeholders(self, cols):
    if cols is None:
        yield from self.query(EmptyColumnPlaceholder)
        return
    for col_id in cols:
        col = self._column_widget(col_id)
        if col is not None:
            yield from col.query(EmptyColumnPlaceholder)
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
