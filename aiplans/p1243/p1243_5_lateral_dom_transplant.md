---
Task: t1243_5_lateral_dom_transplant.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_6_multiselect_marking.md, aitasks/t1243/t1243_7_move_to_column_command.md, aitasks/t1243/t1243_8_boardgroup_field_and_model.md, aitasks/t1243/t1243_9_group_focus_and_rendering.md, aitasks/t1243/t1243_10_group_collapse_and_filtering.md, aitasks/t1243/t1243_11_group_formation_and_block_moves.md, aitasks/t1243/t1243_12_group_membership_commands.md, aitasks/t1243/t1243_13_documentation.md, aitasks/t1243/t1243_14_retrospective_benchmark.md, aitasks/t1243/t1243_15_manual_verification_board_groups_and_reordering.md
Archived Sibling Plans: aiplans/archived/p1243/p1243_1_movement_baseline_and_harness.md, aiplans/archived/p1243/p1243_2_board_field_persistence_seam.md, aiplans/archived/p1243/p1243_3_gap_indexing.md, aiplans/archived/p1243/p1243_4_render_filter_scoping.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-03 16:37
---

# t1243_5 — Lateral DOM transplant

## Context

A lateral card move on `ait board` costs a **median 2173.2 ms** per keypress on a
200-card board. t1243_1 measured by ablation that **93.6 % of that is the column
recompose**: `_move_task_lateral` ends in `refresh_columns({src, dst})`, which
runs `_recompose_column` on *both* columns — `remove_children()` + `compose()` +
`mount_all()`, destroying and rebuilding every card widget of two columns to
express a one-card move. `_move_task_to_extreme` does the same for one column.

t1243_4 removed the other two levers (`apply_filter` scoping, the per-keypress
`git status`) and measured them at **0.4 %**; at the user-confirmed checkpoint
the **entire ≥ 30 % Workstream-B latency target moved onto this child**. This is
the certain and dominant win of Workstream B.

Outcome: lateral and to-edge moves update only the DOM block that actually
moved, and lateral median keypress latency drops from 2173.2 ms to the
low-hundreds of ms.

---

## Step 0 — Anchor re-verification: DONE (HEAD `b9987e189`, 9567 lines)

Re-checked at current HEAD so implementation need not repeat it. Anchors are
symbol names; the line numbers below are informative.

| plan / task premise | current state |
|---|---|
| `_move_task_lateral` ends in `refresh_columns({src,dst})` | **holds** — `:8568-8599`, ends `refresh_columns({current_col_id, new_col}, refocus_filename=…, refocus_col_id=new_col)` |
| `_move_task_to_extreme` ends in `refresh_column(col)` | **holds** — `:8695-8717` |
| `_swap_adjacent_cards` defines a reusable "block" | **holds** — `:8607-8633`; the block logic is a **nested closure `_block`** at `:8615`, called only on `card_below` |
| `_card_block` already exists | **no** — zero hits repo-wide |
| movement actions are `async` | **no** — every one is a plain `def` |
| `_focus_side_candidate` exists (named in the task file) | **no such symbol.** The real helpers are `_viewport_anchor` (`:7127`) and `_column_focus_target` (`:7186`). Task-file wording is stale; ignore it |
| `column_id` read in "12 places" | **17 runtime read sites** (35 total occurrences). Writes: exactly **3** `self.column_id = …` (`:1785` collapsed placeholder, `:1801` empty placeholder, `:1953` `TaskCard`) plus 13 construction kwargs |
| `apply_filter(cols={src,dst})` exists in the shape Step 4 needs | **holds** — `:6655`; `_filter_units` `:6628` filters ONE app-wide `query(TaskCard)` by `column_id` |
| `refresh_git_status()` still in the movers | **gone** (t1243_4); the dirty marker comes from `TaskManager._mark_written` at the write site |
| board Textual version | **8.2.7 in both** `~/.aitask/venv` (CPython 3.14) and `~/.aitask/pypy_venv`; `diff -rq` of the two `textual/` trees shows zero `.py` differences |

### Two premises the task file and parent plan do NOT record — both load-bearing

1. **`ColumnHeader` bakes its task count in at construction** (`:1807`, rendered
   `:1815-1825`). The recompose refreshes it for free today; a transplant that
   skips the recompose leaves **both** headers showing stale counts. This is a
   correctness item the plan must handle explicitly.
2. **`TaskCard.compose` bakes the dirty `*`** at `:1970-1972` from
   `manager.is_modified()`. A lateral move calls `_mark_written`, flipping that
   file to modified — so today the recompose is what makes the `*` appear.
   Constructing **fresh** cards preserves this; a widget-preserving move would
   silently lose it. (The same latent staleness already exists on the vertical
   `move_child` path — see "Upstream defects", out of scope here.)

---

## Step 1 — The spike: DONE. Verdict recorded

**Textual 8.2.7 has no lifecycle-safe cross-parent move of a mounted widget.**
Read from the installed source, not from docs:

- `Widget.move_child` (`widget.py:1610`) hard-validates membership via
  `self._nodes.index(child)` and raises
  `WidgetError("… is not a child of …")` (`widget.py:1654`). Same-parent only.
- **`dst.mount(live_widget)` is a silent no-op, not an error.** `App._register`
  (`app.py:3665`) and `_register_child` (`app.py:3597`) both short-circuit on
  `widget in self._registry`, so no `_attach`, no NodeList insert, no stylesheet
  pass — and the returned `AwaitMount` resolves instantly because
  `_mounted_event` is already set. Code written assuming "mount moves it" looks
  like it works and moves nothing. **This is the trap this spike exists to find.**
- `remove()` is **irreversible**: `Prune` → `_close_messages` →
  `_message_loop_exit` (`widget.py:4514`) clears `_nodes`, detaches, discards
  from `_registry` and leaves `_closed = True` on a `cached_property` queue. A
  removed widget object cannot be re-mounted.
- Nothing named `reparent` / `transplant` exists anywhere in the package.

**Chosen shape — the second candidate in the task file:** `await
src.remove_children(block)` then `await dst.mount_compose(dst.task_block(task),
before=…)` with **freshly constructed** cards. This is precisely what Textual's
own `Widget.recompose` does (`widget.py:1704-1716`), scoped to the moved block
instead of two whole columns. Fresh cards get `column_id` right by construction
across all 17 read sites, and repaint the dirty `*`.

**Rejected:** the private three-call NodeList reparent
(`old._nodes._remove` → `new._nodes._insert` → `widget._attach(new)`). It
preserves the widget instance, but it is unsupported private API with no
upstream contract, and it needs hand-rolled fixups for the stylesheet
(`app.stylesheet.update`), both parents' `_arrangement_cache`, `_query_one_cache`
invalidation on chains `updated()` did not walk, and sibling `nth-child` styling.
The cost it would save is one card's construction — not worth it. Recorded here
so t1243_11's block moves do not re-litigate it.

**The documented fallback is therefore NOT taken.** The spike passed; the
escalation branch in the task file does not fire.

---

## Step 2 — Two extractions, no forked logic

### 2a. `KanbanApp._card_block(col_widget, card) -> list` (new method)

Hoist the nested `_block` closure out of `_swap_adjacent_cards` (`:8615-8624`)
verbatim; `_swap_adjacent_cards` then calls `self._card_block(col_widget,
card_below)`. Behaviour must be identical — `tests/test_board_movement.py`'s
vertical scenarios are the regression net.

```python
def _card_block(self, col_widget, card) -> list:
    """A parent card plus the `.child-wrapper` rows that belong to it.

    An expanded parent's child rows are SIBLINGS that follow its card, so every
    DOM operation on a card has to carry them along. `EmptyColumnPlaceholder`
    only ever appears before the first card, so "stop at the first non-wrapper"
    is a complete rule.
    """
```

### 2b. `KanbanColumn.task_block(task) -> ComposeResult` (new method)

Extract the per-task body of `KanbanColumn.compose` (`:2817-2827`) so **one**
generator builds a task's block for both the full compose and the transplant.
`compose` becomes `for task in tasks: yield from self.task_block(task)`; the
`with Horizontal(classes="child-wrapper")` idiom is kept **verbatim**.

The transplant consumes it through `Widget.mount_compose(compose_result,
before=…)` (`widget.py:1546`), which is `mount_all(compose(self,
compose_result), …)` — `textual.compose.compose(node, compose_result)` accepts a
pre-made generator in 8.2.7 and drives the `with`-block stack exactly as
`compose()` does. So there is **no second construction path** to drift.

`KanbanColumn.expanded_tasks` is the app's own set passed by reference at
`:6513`/`:6523`, so `task_block` sees live expansion state.

---

## Step 3 — `KanbanApp._transplant_block` (new, async)

```python
async def _transplant_block(self, task, src_col, dst_col, *, before=None,
                            refocus_col_id="") -> bool:
    """Move one task's DOM block between (or within) columns, no recompose.

    Textual 8.2.7 offers no cross-parent widget move — `move_child` refuses a
    foreign child and `mount()` on a live widget is a SILENT no-op — so the old
    widgets are pruned and the block is rebuilt from `KanbanColumn.task_block`.
    Rebuilding is not a workaround: it is what keeps `column_id` (17 read sites)
    and the dirty `*` marker correct by construction.

    **The caller has ALREADY committed the model write before calling this.** So
    this helper owns its own recovery: on any failure it recomposes the affected
    columns from the committed model and returns False. It never leaves the DOM
    disagreeing with the model, and it never propagates — an exception escaping
    an async action reaches Textual's pump and takes the app down.

    Returns True only on a clean transplant. False means "recovered by
    recompose" — the caller must NOT then run the scoped follow-ups, because
    `refresh_columns` has already done the filter pass and the refocus.
    """
```

Body:

```python
    affected = {src_col.col_id, dst_col.col_id}

    def _recover():
        self.refresh_columns(affected, refocus_filename=task.filename,
                             refocus_col_id=refocus_col_id or dst_col.col_id)

    card = self._find_parent_card(src_col, task.filename)
    if card is None:
        _recover()
        return False
    try:
        block = self._card_block(src_col, card)
        await src_col.remove_children(block)
        await dst_col.mount_compose(dst_col.task_block(task), before=before)
    except Exception as exc:
        # Everything past the write is inside this guard, because the write is
        # already on disk: `_card_block` can raise on a card that is not a
        # direct child, and `mount_compose` can raise MountError / DuplicateIds
        # or anything out of `task_block`. After `remove_children` the old
        # widgets are gone, so the failure mode without this guard is a task the
        # model says exists and the board renders NOWHERE.
        self.log.error("board: block transplant failed; recomposing", exc)
        self.notify(f"Board repaint failed ({type(exc).__name__}: {exc}) — "
                    "affected columns were rebuilt.", severity="error")
        _recover()
        return False
    return True
```

`_find_parent_card(col_widget, filename)` is a new one-line helper scanning
`col_widget.children` for the non-child `TaskCard` with that filename —
**direct children, never `query()`**, which walks the whole tree wherever it is
rooted (see the measured pessimization in `_filter_units`' docstring at `:6635`).

**Why `except Exception` is the right width here, and why it is not a swallow.**
This is a convergence-of-last-resort on a UI path, not a gate: the remedy —
rebuild from the committed model — is correct for *every* failure, and
enumerating the raisable types would only let an unforeseen one leave the board
inconsistent. `BaseException` (notably `CancelledError`) deliberately propagates
— that is app teardown, where a repaint is meaningless.

**It is not silent, and the surfacing was checked against the installed
Textual.** There is **no `Logger.exception`** in 8.2.7 — `Logger` exposes
`.error` as a *property* returning a logger (`textual/__init__.py:60-175`) — and
`Logger.__call__` returns early unless devtools is connected or `TEXTUAL_LOG` is
set, so a log line alone would be invisible in normal use. The user-visible
surface is therefore `self.notify(..., severity="error")`, which is already this
file's established error idiom (`:7399`, `:7571`, `:7672`, `:8078`); the
`self.log.error(...)` line is the devtools-only diagnostic channel. `traceback`
is not imported in this module and is not worth adding for one call site — the
exception type and message in the toast, plus a reproducing test, are the
diagnosis path.

**Recovery is idempotent regardless of how far the mount got.** If it raised
inside `compose()`, nothing was registered; if it raised after `_register`
inserted the widgets, `_recover`'s `_recompose_column` calls `remove_children()`
on the whole column first, so a half-mounted block cannot survive as a duplicate.
`refresh_columns` with a single-element set is exactly `refresh_column` for a
non-`unordered` column, so the to-edge path shares this recovery unchanged.

**Awaiting is required, not stylistic.** `mount` inserts synchronously but
`remove` does not: `App._prune` posts `Prune` messages and the NodeList removal
happens in each widget's own task. Without the await, `apply_filter` and
`query(TaskCard)` would still see the departed card. The awaits are safe from
pump deadlock because the pruned/mounted widgets run on their **own** asyncio
tasks, not the app's.

### `_sync_header_count(col_widget)` (new)

```python
def _sync_header_count(self, col_widget) -> None:
    """Repaint a column header's count after an in-place DOM change.

    `ColumnHeader` bakes `task_count` in at construction, so a transplant that
    skips the recompose would leave both headers stale. Reads the manager
    (unfiltered), matching what `KanbanColumn.compose` puts there.
    """
```

Resolve the header from `col_widget.children` (not `query_one`), compare
`header.task_count`, and on a change assign it and call
`header.refresh(recompose=True)` — 3 widgets, not a column.

---

## Step 4 — Wire the two movement actions

Both actions and their `action_*` wrappers become `async def`. Textual awaits
coroutine action results, and message processing is serialized, so no
re-entrancy is introduced. `_move_task_vertical` is **deliberately untouched**:
it already has the in-place fast path (184.1 ms), and changing it is pure risk
with no latency to win.

### `_move_task_lateral(direction)`

Replace the terminal `refresh_columns({current_col_id, new_col}, …)` with:

1. **Structural guard — keep the old path when `"unordered"` is involved.**
   `refresh_columns` (`:6603-6609`) escalates to a full `refresh_board` when the
   `unordered` column's widget-presence and task-presence disagree — which is
   exactly what happens when the last unordered task leaves. A transplant cannot
   express "the column disappears", so if `"unordered" in {current_col_id,
   new_col}` the action keeps calling `refresh_columns` unchanged.
2. Resolve **both** column widgets from a **single** `self.query(KanbanColumn)`
   pass (never two `_column_widget()` calls — `_column_widgets()` is four
   full-tree class queries, measured at ~25 ms). If either is missing, call
   `refresh_columns(...)` and return — mirroring `_move_task_vertical`'s existing
   unresolvable-widget fallback (`:8685-8687`).
3. Run the transplant and gate the scoped follow-ups on its result. The False
   branch is already fully recovered by the helper, so it must **not** re-run
   them:

   ```python
   if await self._transplant_block(task, src, dst, refocus_col_id=new_col):
       self._sync_header_count(src)
       self._sync_header_count(dst)
       # Synchronous: the awaits above settled the DOM, so the deferral
       # `refresh_columns` needs (to avoid racing compose) is unnecessary.
       # Same shape `_swap_adjacent_cards` already uses (:8633).
       self.apply_filter({current_col_id, new_col})
       # Identical to what `_queue_refocus` does today, so the benchmark's
       # "keypress fully applied" signal is unchanged.
       self.call_after_refresh(self._refocus_card, filename, new_col)
   ```

Destination position is **append** (`before=None`): `move_task_to_column` →
`index_for_append`, so the moved task sorts last in the destination.

### `_move_task_to_extreme(direction)`

Same helper with `src_col is dst_col`, resolving the `before` anchor **before**
the removal:

- to top: `before` = the first parent `TaskCard` in the column (the action
  already early-returns when the card is already first, so that anchor is always
  a different widget, and it sits after the header/placeholder);
- to bottom: `before=None`.

Gated on the same `if await self._transplant_block(...)` result, then
`apply_filter({col_id})` and the same refocus (no header sync — a same-column
move does not change the count). **Deviation from the task
file, deliberate:** it says "`move_child` to first/last". `move_child` is
supported and cheaper, but it preserves the widget and would therefore leave the
dirty `*` unpainted — a visible regression against today's `refresh_column`.
Header counts do not change on this path, so a rebuild of one block is the
cheapest correct option and keeps a single code path to test.

---

## Step 5 — Tests

### 5a. Shared fixture: promote the pristine-tree mixin

`FixtureBoardTestBase` builds **one tree per class**, so a movement test leaves
the tree mutated and the next test's move can early-return and pass vacuously.
`tests/test_board_render_scoping.py` already solved this with `_PristineTreeMixin`.
Move it into `tests/lib/board_fixture.py` as `PristineTreeMixin` and leave
`_PristineTreeMixin = bf.PristineTreeMixin` in the render-scoping module, so that
file's classes are unchanged and the helper is not duplicated.

### 5b. `tests/test_board_dom_transplant.py` (new)

House style: 4-line `sys.path` preamble, `import board_fixture as bf`, one class
per property with a `test_fixture_facts` precondition case, `unittest.main()`
guard. Classes use `bf.wide_topology(15)` (3 parents per column, so every move is
performable) and, for the child-row cases, `with_children=True`.

Properties pinned (each paired with a discriminating negative control, **one
mutation per control**):

1. **No recompose.** A lateral keypress records **zero** `_recompose_column`
   calls. *Control:* a direct `refresh_columns({c0,c1})` records calls — proves
   the spy sees them.
2. **DOM matches data.** After `shift+right` the moved filename is in
   `_get_column_cards("c1")` and absent from `c0`, and DOM order equals
   `manager.get_column_tasks` order (recomputed independently, not read back
   from the board).
3. **`column_id` is rewritten — via behaviour, not the attribute.** Apply a
   search matching only the moved task *after* the move; it stays visible in the
   destination and the source column's `EmptyColumnPlaceholder` decision is
   right. This is the assertion the task file names as the stale-`column_id`
   catcher. *Control:* force the moved card's `column_id` back to the source and
   the case must fail.
4. **Focus lands on the moved card in the destination** —
   `app.screen.focused is moved_card` and `_get_focused_col_id() == "c1"`.
5. **Scroll sanity** — the moved card's region lies inside the destination
   column's `scrollable_content_region` (reuse `test_board_scroll_focus_jump.py`'s
   `_visible_cards` idiom), and the column did not jump to `scroll_y == 0` when
   the card is at the bottom.
6. **`.child-wrapper` rows travel and stay adjacent** — expand a parent with
   children, move it laterally, assert its wrapper rows are direct children of
   the destination column, immediately after its card, and that the child cards
   inside them carry the destination `column_id`.
7. **Header counts** — source shows n−1, destination n+1, asserted at
   **render level** (`header.query_one(…).render().plain`), not on the
   `task_count` attribute. *Control:* skip `_sync_header_count` and it fails.
8. **Dirty `*` renders on the moved card** — render-level, mirroring
   `test_board_render_scoping.py::test_moved_card_renders_the_dirty_marker`.
9. **Round trip** — `shift+right` then `shift+left` restores the exact
   pre-state (`board_order` for both columns), the stationarity property the
   benchmark depends on.
10. **To-edge** — `ctrl+up` / `ctrl+down` each: zero recomposes, correct DOM
    position, focus on the moved card, `*` painted, wrappers travel.
11. **`unordered` keeps the recompose path** — with a fixture task in
    `unordered`, moving it out must leave a consistent board (the column
    disappears). Asserted behaviourally on the resulting board, not by spying on
    which internal path ran.
12. **Fault injection — a mid-transplant failure converges, it does not lose the
    card.** The model write lands before the DOM work, so this is the case that
    decides whether a partial transplant is recoverable. Patch
    `KanbanColumn.mount_compose` on the class to raise `RuntimeError` once, then
    press `shift+right` and assert the board **converged on the committed
    model**:
    - exactly **one** card exists for the moved filename anywhere in the DOM
      (not zero — the failure mode — and not two);
    - it is in the **destination** column, and `_get_column_cards(dst)` matches
      `manager.get_column_tasks(dst)` recomputed independently;
    - both header counts are right and focus is on a real widget;
    - the app is still running (the exception did not reach Textual's pump);
    - the failure was **surfaced**, not swallowed — spy `KanbanApp.notify` and
      assert one `severity="error"` call naming the exception type.

    `mount_compose` is the correct injection point precisely because the
    recovery path does **not** use it — `_recompose_column` goes through
    `mount_all` — so the injection breaks only the fast path and leaves the
    recovery functional. Run the same case a second time injecting at
    `remove_children` (nothing removed, write already committed) to cover the
    pre-removal half of the window.

    *Control:* delete the `try/except` in `_transplant_block` (one mutation) and
    this case must fail with **zero** cards for the moved filename — the exact
    "model says moved, board renders it nowhere" state.

Per the repo convention, each "must not happen" assertion is additionally run
once against a deliberately broken source and the suite must exit 1.

### 5c. `tests/test_board_movement.py` — mechanics only, expectations frozen

`_install_probe` stamps `sync_end` in a `finally` around `_move_task_lateral` /
`_move_task_vertical` / `_move_task_to_extreme`. Two of those become coroutine
functions, so the wrapper must gain an async variant that awaits the body before
stamping — otherwise `sync_end` records coroutine *creation* and `defer` becomes
meaningless.

**The timed region must also close on the post-move SCROLL, not just the refocus
(added during review — the original plan missed this and the first measurement
was invalid because of it).** `_refocus_card` returns as soon as it *schedules*
`_scroll_into_view_after_layout` for a card with no layout yet, and that helper
re-queues itself until the card is laid out. Closing on the refocus alone
therefore

- **excludes** the work that actually puts the moved card on screen — work this
  change newly deferred, and which the baseline *did* include, because
  `on_focus`'s scroll used to run synchronously inside `_refocus_card`; and
- lets that work **bleed into the next sample's** timed region, smearing the
  measurement rather than merely under-counting it.

So the refocus wrapper hands the close to the scroll chain whenever one is
outstanding (`probe.scroll_pending`), and the scroll wrapper closes on its
terminal invocation — scrolled, budget exhausted, or card gone. It resolves the
default hop budget from `self_._SCROLL_LAYOUT_HOPS` rather than copying the
value, so harness and production cannot drift. A card that is already laid out
schedules no helper, so every pre-t1243_5 path and the whole vertical axis close
exactly as before. Verified load-bearing rather than assumed: the helper fires 24
times during the ungated smoke bench.

**`FLIP_TABLE` and `EXPECTED_CALL_SITES` must NOT be edited.** This change alters
no manager call, so write counts, changed-path sets and final board state are all
unchanged. If either goes red, that is a real finding, not a table to update —
the same contract t1243_4 honoured.

Note for the record: the `no_rc` ablation config becomes a no-op on the lateral
axis after this change (there is no recompose left to ablate). That is expected;
t1243_14 owns re-measuring.

---

## Verification

- `python3 -m pytest tests/test_board_dom_transplant.py -v` — all pass.
- `bash tests/run_all_python_tests.sh` — read **only** the last line
  (`PYTHON SUITE: PASSED|FAILED`); use `set -o pipefail` if piping.
- `tests/test_board_movement.py`, `test_board_render_scoping.py`,
  `test_board_empty_column_focus.py`, `test_board_scroll_focus_jump.py`,
  `test_board_manager_moves.py`, `test_board_persistence_seam.py` pass with
  `FLIP_TABLE` and `EXPECTED_CALL_SITES` **unedited**.
- Each new guard is proven able to fail (one mutation per control), including the
  fault-injection control: with `_transplant_block`'s `try/except` deleted, the
  §5b-12 cases must report **zero** cards for the moved filename.
- **Latency is a pass condition.** Before touching the box, check for concurrent
  agents (`ait_tmux list-panes`) and run nothing else alongside the bench:
  ```bash
  AITASK_BOARD_BENCH=1 ~/.aitask/venv/bin/python -m unittest \
    tests.test_board_movement.BoardMovementBenchmarkTests.test_bench_baseline -v
  ```
  The timed region must close on the post-move **scroll**, not the refocus (see
  §5c) — otherwise the number omits user-visible work this change introduced and
  cannot prove the pass condition at all.

  **Target: ≥ 30 % reduction in median lateral keypress latency versus the
  t1243_1 baseline of 2173.2 ms — i.e. ≤ 1521.2 ms.** Report the harness floor
  and the vertical axis alongside (vertical must not regress against 184.1 ms).
  Record the delta and method parameters in the parent plan for t1243_14.
  Cross-run absolutes on this box drift ~4-10 % under agent load; the expected
  win here is an order of magnitude, so drift is immaterial — but say so with the
  floor number rather than assuming it.
- **On a miss, run t1243_1's Performance-Gate Confirmation Checkpoint**
  (parent plan, "Decision checkpoint"): present the data, revise nothing, revert
  nothing, and let the user choose. NON-SKIPPABLE — the `fast` profile and
  `post_plan_action` do not bypass it.
- Manual smoke in a real `ait board`: move a card laterally with and without an
  active search, with a parent expanded, into and out of the last position of a
  column; confirm the `*` marker, both header counts, focus and scroll.

## Risk

### Code-health risk: medium

- Widget-lifecycle manipulation on a hot UI path, in a file with no prior async action; a mis-sequenced await or a dropped awaitable leaves the DOM and the data model disagreeing · severity: medium · → mitigation: none (covered in-task by §5b properties 2/3/4 under a real Pilot, plus `_transplant_block`'s own recompose recovery)
- **The model write is committed before the DOM work, so a failure between `remove_children` and `mount_compose` would leave a task the model says exists and the board renders nowhere — and an exception escaping an async action reaches Textual's pump and kills the app** · severity: **high** · → mitigation: none (structural: the recovery lives inside `_transplant_block`, not as a rule each caller must remember, and it is proven by the §5b-12 fault-injection cases at both injection points, whose negative control reproduces the zero-cards state)
- Two invariants the recompose used to maintain for free — `ColumnHeader.task_count` and the dirty `*` — become explicit obligations of the movement path, and a future third one could be missed the same way · severity: medium · → mitigation: board_column_header_live_count, board_movement_dom_invariant_harness (in-task cover: the render-level header and `*` assertions, §5b 7/8, each with its own negative control)
- Making `action_move_task_*` async is a first for this file and changes the dispatch contract the benchmark harness wraps · severity: low · → mitigation: none (the harness wrapper is updated in the same commit and `FLIP_TABLE` staying green is the regression net)
- `KanbanColumn.task_block` adds a second entry point into card construction; if it ever forks from `compose`, transplanted cards diverge from composed ones · severity: low · → mitigation: none (`compose` is rewritten to `yield from task_block`, so there is exactly one generator and no copy to drift)

### Goal-achievement risk: medium

- The mechanism is unproven **in this app**: awaiting `remove`/`mount` inside an action body is new here, and an unforeseen pump interaction could stall or reorder the repaint · severity: medium · → mitigation: none (the real-Pilot suite is the proof; if awaiting inline misbehaves, the bounded alternative is to dispatch the body via `run_worker(..., exclusive=True)` and keep the same helper — recorded here so it is a planned branch, not an improvisation)
- The ≥ 30 % target is a hard pass condition measured on a box that carries 4-5 ambient load from concurrent agents · severity: low · → mitigation: none (the predicted win is ~15×, far outside drift; the harness-floor control is reported alongside, and a miss routes to the user checkpoint rather than to an automatic decision)
- The `unordered` structural case is handled by *declining* the fast path rather than by transplanting, so that column keeps the old latency · severity: low · → mitigation: none (`unordered` only exists when tasks lack a `boardcol`, it is empty on a normally-maintained board, and correctness beats latency there)

### Planned mitigations

No **before** mitigation. The one uncertainty that warranted pre-work — "does a
lifecycle-safe cross-parent move exist" — was the spike, and it is resolved above
before any code is written. t1243_14 (`retrospective_benchmark`) already exists as
a sibling and re-measures this axis.

- timing: after | name: board_column_header_live_count | type: refactor | priority: medium | effort: low | addresses: code-health — recompose-maintained invariants become explicit caller obligations | desc: Make ColumnHeader derive its task count from the manager at render time instead of baking it in at construction, so no movement path has to remember _sync_header_count
- timing: after | name: board_movement_dom_invariant_harness | type: test | priority: medium | effort: medium | addresses: code-health — recompose-maintained invariants become explicit caller obligations | desc: Promote the post-move consistency checks (DOM order matches get_column_tasks, column_id correct across the whole block, header count, dirty marker) into a shared assertion helper in tests/lib/board_fixture.py and apply it to the lateral, vertical and to-edge paths so t1243_11's block moves inherit the net

## Step 9 — Post-Implementation

Merge to `main` (current-branch profile, no worktree), then archive per the
shared workflow.

## Final Implementation Notes

- **Actual work done:** two production files' worth of change in one, plus four
  test files.
  - `.aitask-scripts/board/aitask_board.py` (+233/−37, 9 hunks):
    - `KanbanColumn.task_block(task)` — the per-task compose body extracted so
      **one** generator builds a task's block for both `compose` and the
      transplant; `compose` is now `yield from self.task_block(task)`.
    - `KanbanApp._card_block(col_widget, card)` — the `_block` closure hoisted
      out of `_swap_adjacent_cards`, now shared with the transplant.
    - `KanbanApp._find_parent_card`, `_sync_header_count`, and
      `async _transplant_block(...)` with its own recompose recovery.
    - `_move_task_lateral` / `_move_task_to_extreme` and their four `action_*`
      wrappers became `async`; both end in a scoped `apply_filter` + refocus
      gated on the transplant's result.
    - `_refocus_card` gained a guarded call to the new
      `_scroll_into_view_after_layout`.
  - `tests/test_board_dom_transplant.py` — **new**, 733 lines, 20 tests.
  - `tests/lib/board_fixture.py` — `PristineTreeMixin` promoted for reuse.
  - `tests/test_board_render_scoping.py` — mixin replaced by a one-line alias.
  - `tests/test_board_movement.py` — probe mechanics only; **`FLIP_TABLE` and
    `EXPECTED_CALL_SITES` deliberately untouched and green**, as predicted.

- **Deviations from plan:**
  1. **`_move_task_to_extreme` rebuilds its block instead of `move_child`** —
     planned as a deviation up front and confirmed correct. `move_child` is
     supported and cheaper, but it preserves the widget, so the dirty `*` that
     the move's own write turns on would go unpainted — a visible regression
     against the `refresh_column` it replaces. Rebuilding one block is cheap and
     keeps a single code path.
  2. **`_scroll_into_view_after_layout` — NOT in the plan, and needed.** The
     moved card ended up focused but **off-screen**. `TaskCard.on_focus` scrolls
     synchronously (t1248), but `scroll_visible` is a silent no-op for a widget
     with no size, and a card mounted in this cycle has none. The recompose path
     never hit this because it *drops* its mount awaitables, so its deferred
     refocus naturally lands after the pump has laid out; awaiting the mount
     inside the action blocks that pump instead. Measured: the size lands on the
     3rd refresh callback, so the fix is a bounded re-queue (5-hop cap, reads
     `card.region.area`), not a guessed hop count.
  3. **The benchmark's timed region had to close on that scroll** — see "Issues".

- **Issues encountered:**
  1. **The first post-implementation measurement was invalid** (found in review,
     not by me). The probe closed the timed region when `_refocus_card`
     returned, but after deviation 2 that only *schedules* the scroll. So the
     number excluded work this change newly deferred — work the baseline
     included, since `on_focus`'s scroll used to run synchronously inside
     `_refocus_card` — and let it bleed into the next sample. `_install_probe`
     now hands the close to the scroll chain whenever one is outstanding.
     Verified load-bearing rather than assumed: the helper fires 24× in the
     ungated smoke bench.
  2. **A single benchmark run cannot adjudicate anything on this box.** One
     corrected run read 1631.6 ms (a miss) while its own within-run controls —
     `-recompose` 1038.9, `-filter-git` 1065.0, `-filter-recompose` 1103.3,
     legacy 1146.7 — clustered ~500 ms lower, though they differ from `full`
     only by levers measuring 0–6 %. Repeating the lateral `full` config 5×
     gave 1094.7 / 1105.5 / 1162.4 / 1343.9 / 1344.0 ms: the 1631.6 sits outside
     the whole distribution. **Target met 5/5** (−46.5 % at the median of run
     medians, −38.2 % worst run, against −30 %).
  3. **A flaky-looking negative-control rerun** turned out to be my own fault
     injection being able to fire outside the keypress. Arming it explicitly
     before the press made the controls deterministic; the spurious extra
     failures disappeared.
  4. A concurrent session landed **t1379** into this same checkout mid-task,
     including two hunks inside `aitask_board.py`, and advanced `main` three
     commits. The code commit was built from a **hunk-filtered patch** so only
     this task's 9 hunks were staged, and the suite was re-run on the moved base.

- **Key decisions:**
  - **Rebuild, don't reparent.** Textual 8.2.7 has no cross-parent move:
    `move_child` raises for a foreign child, and — the trap — `mount()` on a live
    widget is a **silent no-op** (`App._register` short-circuits on the
    registry), so code assuming "mount moves it" looks like it works. The private
    3-call NodeList reparent was rejected: unsupported, and it needs hand-rolled
    stylesheet / arrangement-cache / query-cache fixups to save one card's
    construction.
  - **Recovery lives inside `_transplant_block`, not in its callers.** The model
    write is committed before the DOM work, so a raise between the prune and the
    mount would leave a task the model says exists and the board renders nowhere
    — and an exception escaping an async action kills the app. Structural rather
    than a rule each caller must remember; `except Exception` is broad by intent
    (rebuilding from the committed model is right for every failure) and is
    surfaced via `notify(severity="error")`, not swallowed.
  - **`Logger.exception` does not exist in Textual 8.2.7**, and `Logger.__call__`
    returns early unless devtools is attached — so the user-visible surface is
    `notify`, with `log.error` as the devtools-only channel.
  - **One generator for card construction.** `task_block` is consumed by both
    `compose` and `mount_compose`, so a transplanted card cannot drift from a
    composed one.

- **Upstream defects identified:**
  - `.aitask-scripts/board/aitask_board.py:8654-8663 — _swap_adjacent_cards reorders cards with move_child and never repaints them, so the dirty * marker that _move_task_vertical's write turns on (TaskManager._mark_written) does not appear on the moved card until the next full refresh. Pre-existing on the vertical axis; this task fixed the lateral and to-edge paths only, because touching the 184 ms vertical fast path buys no latency and adds risk.`
  - `.aitask-scripts/board/aitask_board.py:7079-7098 — _column_widgets() issues four separate full-DOM class queries per call (~25 ms on a 200-card board, measured in t1243_4) and is still reached from the post-move refocus path via _card_fully_visible / _viewport_anchor. Reported by t1243_4 and still unaddressed; now named as a suspect in t1395.`

- **Notes for sibling tasks:**
  - **t1243_11 (block moves):** `_card_block` and `_transplant_block` are the
    seams you want, and `KanbanColumn.task_block` is the single construction
    path. Do **not** re-litigate the private NodeList reparent — the spike
    result is recorded in the parent plan. Budget for the fact that a transplant
    must explicitly maintain what the recompose maintained for free:
    `column_id` on the **whole** block (child cards inside `.child-wrapper` rows
    too), the header count, and the dirty `*`.
  - **Anyone making a board action `async`:** awaiting inside the action blocks
    the pump that lays out, so anything you queue afterwards runs *before* the
    layout. `scroll_visible` silently does nothing on an unlaid-out widget.
  - **t1243_14:** re-measure with repeats, never a single run (issue 2). The
    three pre-implementation opportunity gates the bench still prints
    (`R_pair`, `R_rm4`, `R_rm5`) ablate a recompose that no longer exists on the
    lateral path — retire or re-scope them. Post-t1243_5 reference: lateral
    ~1162 ms (range 1095–1344), vertical 192.6 ms, floor ~82 ms.
  - **t1395** owns the ~1.16 s residual; read it before optimising anything here.
