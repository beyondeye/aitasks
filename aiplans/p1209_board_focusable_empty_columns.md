---
Task: t1209_board_focusable_empty_columns.md
Base branch: main
plan_verified: []
---

# t1209 — Make empty board columns focusable so column reordering works

## Context

In `ait board`, a column that shows no task cards cannot receive focus. Every
column-scoped action resolves its target column from the *focused card*, so an
empty column can neither be reached with arrow navigation nor reordered with
`ctrl+left` / `ctrl+right`.

Three variants of the same defect, all confirmed in
`.aitask-scripts/board/aitask_board.py`:

1. **Genuinely empty column** (no task has that `boardcol`). `refresh_board`
   (~4879-4886) mounts every configured column regardless of task count, so the
   column *is* on screen — but `KanbanColumn.compose` (~1663-1677) yields only a
   `ColumnHeader` (a plain `Static`, `can_focus` defaults to `False`) plus one
   `TaskCard` per task. Nothing focusable exists. `_nav_lateral` (~5401-5429)
   then *deliberately* skips it (`new_idx += direction`).
2. **Filter-emptied column.** `apply_filter` (~4970-4997) sets
   `card.styles.display = "none"` but leaves cards in the DOM, so
   `_get_column_cards` still reports them. Arrow navigation into such a column
   lands focus on an **invisible** card.
3. **Collapsed column.** It *does* have a focusable `CollapsedColumnPlaceholder`
   (~1074-1087), so it can be reached — but `_shift_column` (~6217-6234) starts
   with `focused = self._focused_card()` and returns early, so a collapsed
   column cannot be reordered either. The generalized helper it should be using,
   `_get_focused_col_id()` (~5391-5399), already exists and already understands
   placeholders.

Intended outcome: any column visible on the board — empty, filter-emptied,
collapsed, or populated — can be focused and reordered, and focus survives the
refresh that follows a move.

Per the exploration decision, all three cases are in scope. The collapsed
placeholder keeps its current `···` glyph (the task count is already rendered in
the column header, so it is not duplicated there).

## Design

Single principle: **every board column always owns exactly one focusable
anchor.** Populated columns anchor on a card; every other state anchors on a
placeholder. All column-scoped actions then resolve through column *identity*,
never through a card.

### 1. `EmptyColumnPlaceholder` widget

Add immediately after `CollapsedColumnPlaceholder` (~line 1088), mirroring it:

```python
class EmptyColumnPlaceholder(Static):
    """A focusable placeholder for columns that show no cards.

    Covers both a column with no tasks at all and one whose cards are all
    hidden by the active filter/search — in either case there is no TaskCard
    to anchor focus on, so column-scoped actions (reorder, collapse) would be
    unreachable.
    """

    can_focus = True

    def __init__(self, col_id: str):
        super().__init__("(empty)", classes="empty-placeholder")
        self.column_id = col_id
```

No inline `on_focus` / `on_blur` styling (unlike `CollapsedColumnPlaceholder`,
which hardcodes `#444444` and thereby overrides its own CSS rule) — focus
styling comes from CSS using the accent shade. Add next to the existing
`.collapsed-placeholder` rules (~4467-4468):

```css
.empty-placeholder { height: 1; width: 100%; text-align: center; color: $text-muted; }
.empty-placeholder:focus { background: $primary 30%; }
```

### 2. Always compose the placeholder; `apply_filter` owns its visibility

In `KanbanColumn.compose`, non-collapsed branch — yield the placeholder right
after the header, seeded with the correct initial display so there is no
one-frame flash before `apply_filter` runs:

```python
else:
    tasks = self.manager.get_column_tasks(self.col_id)
    placeholder = EmptyColumnPlaceholder(self.col_id)
    if tasks:
        placeholder.styles.display = "none"
    yield placeholder
    for task in tasks:
        ...
```

In `apply_filter`, collect columns that kept a visible card during the existing
card loop, then drive the placeholders and repair focus — O(n), no extra
queries:

```python
cols_with_visible = set()
for card in self.query(TaskCard):
    ...
    display = "block" if v else "none"
    card.styles.display = display
    # An expanded child card lives inside a `.child-wrapper` Horizontal that
    # also holds the "↳" connector Static. Hiding only the card leaves a bare
    # connector row behind — pre-existing, but newly conspicuous next to an
    # "(empty)" placeholder. Hide the wrapper with its card.
    wrapper = card.parent
    if card.is_child and isinstance(wrapper, Horizontal) and \
            wrapper.has_class("child-wrapper"):
        wrapper.styles.display = display
    if v:
        cols_with_visible.add(card.column_id)

for placeholder in self.query(EmptyColumnPlaceholder):
    placeholder.styles.display = (
        "none" if placeholder.column_id in cols_with_visible else "block"
    )

# Focus must never rest on a widget the filter just hid.
focused = self.screen.focused if self.screen else None
if isinstance(focused, (TaskCard, EmptyColumnPlaceholder)) and \
        focused.styles.display == "none":
    self._refocus_column(focused.column_id)
```

The focus-repair block keeps the two directions symmetric: filtering a column
down to nothing moves focus onto its placeholder, and clearing the filter moves
focus back onto a card.

**Why the `display != "none"` guards throughout this plan are load-bearing**
(verified against the installed Textual 8.2.7): `Screen.focus_chain` walks
`displayed_children`, which filters on `display`, so tab traversal and
`focus_next` already skip a hidden placeholder — no extra guard needed there.
But `Screen.set_focus` gates on `Widget.focusable`, which checks `visible` (the
`visibility` rule), **not** `display` — so a direct `.focus()` call on a hidden
widget succeeds. Every focus-target helper below must therefore filter on
`display` itself; Textual will not do it for us.

### 3. Focus helpers (the reusable seam)

Replace `_focused_collapsed_placeholder()` (~6310-6313) — its four call sites
(5344, 5359, 5396, 6324) all want "either placeholder" — with:

```python
def _focused_placeholder(self):
    """Return the focused column placeholder (collapsed or empty), or None."""
    focused = self.screen.focused if self.screen else None
    if isinstance(focused, (CollapsedColumnPlaceholder, EmptyColumnPlaceholder)):
        return focused
    return None

def _column_placeholder(self, col_id: str):
    """Return a column's placeholder widget (collapsed or empty), or None."""
    for cls in (CollapsedColumnPlaceholder, EmptyColumnPlaceholder):
        for widget in self.query(cls):
            if widget.column_id == col_id:
                return widget
    return None

def _visible_column_cards(self, col_id: str) -> list:
    """`_get_column_cards` filtered to cards the active filter left visible."""
    return [c for c in self._get_column_cards(col_id)
            if c.styles.display != "none"]

def _column_focus_target(self, col_id: str, preferred_pos: int = 0):
    """The widget to focus when entering `col_id`, or None."""
    placeholder = self._column_placeholder(col_id)
    if placeholder is not None and placeholder.styles.display != "none":
        return placeholder
    cards = self._visible_column_cards(col_id)
    if cards:
        return cards[min(preferred_pos, len(cards) - 1)]
    return None

def _refocus_column(self, col_id: str):
    """Restore focus to a column by identity (used after a board refresh)."""
    target = self._column_focus_target(col_id)
    if target is not None:
        target.focus()
```

`_get_focused_col_id()` keeps its shape but consults `_focused_placeholder()`.

### 4. Navigation

- `_nav_lateral`: replace the inline collapsed-placeholder/card probe with
  `_column_focus_target(col_ids[new_idx], old_pos)`; compute `old_pos` from
  `_visible_column_cards(cur_col)`. The skip-loop stays (it now only skips
  columns that truly have no anchor, which after this change means none).
- `action_nav_up` / `action_nav_down`: source their card list from
  `_visible_column_cards(...)` instead of `_get_column_cards(...)`; the
  existing placeholder no-op guard switches to `_focused_placeholder()`.
- `action_focus_board`: replace the "first card, else first collapsed
  placeholder" fallback with a leftmost-first sweep —
  `for col_id in self._get_visible_col_ids(): target = self._column_focus_target(col_id)`.

### 5. Column-scoped actions resolve by identity

`_shift_column` — the actual reported bug:

```python
def _shift_column(self, direction):
    col_id = self._get_focused_col_id()
    if not col_id or col_id == "unordered":
        return
    order = self.manager.column_order
    if col_id not in order:
        return
    idx = order.index(col_id)
    new_idx = idx + direction
    if not (0 <= new_idx < len(order)):
        return
    focused = self._focused_card()
    filename = focused.task_data.filename if focused else ""
    order[idx], order[new_idx] = order[new_idx], order[idx]
    self.manager.save_metadata()
    self.refresh_board(refocus_filename=filename,
                       refocus_col_id="" if filename else col_id)
```

`action_toggle_column_collapsed` collapses to `col_id = self._get_focused_col_id()`
(warning text becomes "No column selected"), and `toggle_column_collapse`
re-anchors by column when focus was inside the toggled column — today it drops
focus entirely in that case:

```python
def toggle_column_collapse(self, col_id: str):
    focused = self._focused_card()
    focused_col = self._get_focused_col_id()
    self.manager.toggle_column_collapsed(col_id)
    refocus, refocus_col = "", ""
    if focused and focused.column_id != col_id:
        refocus = focused.task_data.filename
    elif focused_col == col_id:
        refocus_col = col_id
    self.refresh_board(refocus_filename=refocus, refocus_col_id=refocus_col)
```

### 6. Column-identity refocus on **every** refresh path

`refresh_board` is not the only path that destroys the focused widget:
`refresh_column` (~4914) and `refresh_columns` (~4943) recompose column
contents via `_recompose_column` and are reached from six call sites (task
detail-screen results at 5581/5583, `_toggle_expand` at 6056, `_move_task_lateral`
at 6098, `_move_task_vertical` at 6174, `_move_task_to_extreme` at 6207). All
three helpers currently accept only `refocus_filename`, and `_refocus_card`
silently no-ops when no card matches — so focus is simply lost whenever the task
was archived, deleted, or filtered out by the refresh. Rather than justify why
placeholders can't reach those paths, give all three the same contract.

Introduce one shared tail and a fallback-aware `_refocus_card`:

```python
def _refocus_card(self, filename: str, fallback_col_id: str = ""):
    for card in self.query(TaskCard):
        if card.task_data.filename == filename and card.styles.display != "none":
            card.focus()
            return
    if fallback_col_id:
        self._refocus_column(fallback_col_id)

def _queue_refocus(self, refocus_filename: str = "", refocus_col_id: str = ""):
    """Queue a post-refresh focus restore: by task filename, else by column."""
    if refocus_filename:
        self.call_after_refresh(self._refocus_card, refocus_filename, refocus_col_id)
    elif refocus_col_id:
        self.call_after_refresh(self._refocus_column, refocus_col_id)
```

Then add `refocus_col_id: str = ""` to `refresh_board`, `refresh_column`, and
`refresh_columns`, and replace each of their `if refocus_filename:
call_after_refresh(...)` tails with `self._queue_refocus(refocus_filename,
refocus_col_id)`. Update the six call sites to pass the column they already
have in hand (`old_col` / `new_col` / `col_id`), and the DOM-swap refocus at
6172 likewise. Net effect: a partial refresh that loses its card falls back to
the column, and a placeholder-focused column survives any refresh path.

Ordering is load-bearing: `call_after_refresh(self.apply_filter)` is already
queued first in all three helpers, so placeholder visibility is settled before
`_refocus_column` picks a target.

**No `check_action` change.** `move_col_right` / `move_col_left` /
`toggle_column_collapsed` (~4758) were never focus-gated — they are hidden only
in the `inflight` / `bytopic` views — so the footer already behaves correctly
once the actions work.

## Files to modify

- `.aitask-scripts/board/aitask_board.py` — the only source file.
- `tests/test_board_empty_column_focus.py` — new.

## Tests

New `tests/test_board_empty_column_focus.py`, following the Textual-Pilot
harness in `tests/test_board_footer_visibility.py` and
`tests/test_board_topic_view.py` (chdir to `REPO_ROOT`, `KanbanApp()`,
`async with app.run_test(size=(160, 48))`). Auto-discovered by
`tests/run_all_python_tests.sh`.

**Fixture — deterministic layout, not live board state.** Asserting against
"the last populated column" or "some collapsed column" would make the tests
hostage to whatever the repo's board happens to look like on a given branch.
Instead, take the real `KanbanApp` (so the real compose/filter/focus code runs)
but replace the column layout wholesale *before* `run_test` triggers
`on_mount` → `refresh_board`:

```python
def _synthetic_board(app, n_cards=4, with_children=False):
    """Impose a deterministic Left(2) | Empty(0) | Right(2) layout.

    `with_children=True` guarantees the first Left card is a parent whose
    children are retained, so `.child-wrapper` rows actually compose.
    """
    mgr = app.manager
    mgr.save_metadata = lambda: None          # never write the real board config
    mgr.settings = dict(mgr.settings)
    mgr.settings["collapsed_columns"] = []
    mgr.columns = [
        {"id": "zz_left",  "title": "Left",  "color": "gray"},
        {"id": "zz_empty", "title": "Empty", "color": "gray"},
        {"id": "zz_right", "title": "Right", "color": "gray"},
    ]
    mgr.column_order = ["zz_left", "zz_empty", "zz_right"]

    parents = sorted(mgr.task_datas.values(), key=lambda t: t.filename)
    kept_children = {}
    if with_children:
        # Query children BEFORE child_task_datas is replaced below.
        def _children(task):
            num, _ = TaskCard._parse_filename(task.filename)
            return mgr.get_child_tasks_for_parent(num) if num else []
        parent = next((p for p in parents if _children(p)), None)
        if parent is None:
            raise unittest.SkipTest("needs a parent task with children in aitasks/")
        parents = [parent] + [p for p in parents if p is not parent]
        kept_children = {c.filename: c for c in _children(parent)}

    tasks = parents[:n_cards]
    if len(tasks) < n_cards:
        raise unittest.SkipTest(
            f"needs >= {n_cards} parent tasks in aitasks/; found {len(tasks)}"
        )
    mgr.task_datas = {t.filename: t for t in tasks}
    mgr.child_task_datas = kept_children      # {} unless with_children
    for i, task in enumerate(tasks):
        task.board_col = "zz_left" if i < 2 else "zz_right"
        task.board_idx = i * 10
    return tasks
```

Cases 1-6 and 8-10 use the default (`with_children=False`) so no `.child-wrapper`
noise perturbs the card/placeholder counts; only case 7 passes
`with_children=True`. Children render inline under their parent in
`KanbanColumn.compose` regardless of their own `boardcol`, and their `TaskCard`
carries the parent's `column_id`, so the `cols_with_visible` accounting is
unaffected.

Safe by construction: `Task.board_col` / `board_idx` are pure in-memory setters
(disk writes only go through `reload_and_save_board_fields`, which no test here
triggers), and `save_metadata` — the only persistence `_shift_column` and
`toggle_column_collapsed` perform — is stubbed. The environmental dependencies
are "≥4 parent tasks" and, for case 7 only, "≥1 parent with children" — both
surfaced as explicit `SkipTest` messages rather than silent conditional skips.

Cases:

1. `zz_empty` mounts a visible, `can_focus` `EmptyColumnPlaceholder`;
   `zz_left` / `zz_right` mount theirs at `display: none`.
2. `_nav_lateral` lands on the empty column — focus a `zz_left` card, press
   `right`, assert `app._get_focused_col_id() == "zz_empty"` and that the
   focused widget is the placeholder. Pressing `right` again reaches `zz_right`.
3. `action_move_col_left()` with the placeholder focused swaps `column_order` to
   `["zz_empty", "zz_left", "zz_right"]`, **and** focus is still on `zz_empty`
   after the refresh settles (the regression the `refocus_col_id` path exists for).
4. Boundaries: at index 0 `action_move_col_left()` leaves `column_order`
   unchanged; at the right edge `action_move_col_right()` likewise.
5. Collapsed-column reorder — collapse `zz_left`, focus its
   `CollapsedColumnPlaceholder`, `action_move_col_right()` reorders it
   (fails today: `_shift_column` bails on `_focused_card()`).
6. Filter-emptied column — set `app.search_filter` to a no-match string, call
   `apply_filter()`, assert all three placeholders are visible and that a
   previously-focused `zz_left` card handed focus to `zz_left`'s placeholder;
   then clear the filter and assert focus returns to a card.
7. Child-wrapper leak (concern 3) — build with `with_children=True`, expand the
   parent (`app.expanded_tasks.add(parent.filename)`, `refresh_column("zz_left")`),
   assert `.child-wrapper` widgets actually exist (guard against a vacuous
   pass), then apply a no-match filter and assert every one is `display: none`
   — no bare `↳` connector survives beside the `(empty)` placeholder.
8. Partial-refresh refocus (concern 1) — with focus on `zz_empty`'s
   placeholder, call `refresh_column("zz_empty", refocus_col_id="zz_empty")`
   and assert focus is restored; and with a `zz_left` card focused, call
   `refresh_column("zz_left", refocus_filename="<gone>.md", refocus_col_id="zz_left")`
   and assert the fallback lands on the column rather than dropping focus.
9. Focus-chain check (concern 4) — assert no hidden `EmptyColumnPlaceholder`
   appears in `app.screen.focus_chain`, pinning the Textual `displayed_children`
   behaviour the design relies on so a future Textual bump surfaces here.
10. Negative control: `zz_left` (populated, unfiltered) focuses a **card** on
    lateral nav, and `_visible_column_cards("zz_left") == _get_column_cards("zz_left")`.

## Verification

```bash
bash tests/run_all_python_tests.sh -k board          # new + existing board tests
```

Prove the harness can fail before trusting it: run the new file against the
unmodified `aitask_board.py` first (`git stash` the source change) and confirm
cases 2, 3, 5, 6, 7, 8 exit non-zero — a placeholder-focus test that passes on
the old code is pinning nothing. (Cases 9 and 10 are invariants that must pass
both before and after; that asymmetry is the point.)

Then drive the real TUI manually:

```bash
./ait board
```

- Create/keep a column with no tasks; arrow onto it (dim `(empty)` row focuses),
  `ctrl+left` / `ctrl+right` move it, focus stays on it after each move.
- `X` collapses/expands it; the column stays focused across the toggle.
- Collapse a populated column and reorder it with `ctrl+arrow`.
- Type a no-match string in the search box: every column shows `(empty)` and
  focus moves off the hidden card; clear it and focus returns to a card.

Step 9 (Post-Implementation) applies as usual: merge approval, gate run,
archival.

## Risk

### Code-health risk: medium
- `apply_filter` is the board's shared visibility path (every base view, every
  search keystroke, and a synchronous call inside `_swap_adjacent_cards`); the
  new placeholder-toggle + focus-repair tail runs on all of them, so a mistake
  here degrades card movement and search, not just empty columns · severity: medium · → mitigation: TBD
- Replacing `_focused_collapsed_placeholder()` with `_focused_placeholder()`
  changes behaviour at all four existing call sites at once (vertical-nav
  no-op, `_get_focused_col_id`, collapse toggle), so a regression would surface
  as subtly wrong focus rather than an error · severity: medium · → mitigation: TBD
- Threading `refocus_col_id` through `refresh_board` / `refresh_column` /
  `refresh_columns` touches six existing call sites that today work correctly;
  the parameter is additive and defaults to `""`, so the failure mode is a
  missed *improvement* rather than a regression, but the diff is wider than the
  reported bug · severity: medium · → mitigation: TBD
- Focus repair inside `apply_filter` and `_refocus_column` both call `.focus()`;
  the paths are non-reentrant by inspection (`focus()` does not re-enter
  `apply_filter`) but that is an implicit contract, not an enforced one · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The root cause was read directly from the current source and the fix targets
  exactly the confirmed seam (`_shift_column` resolving through
  `_get_focused_col_id()`); the residual risk is that focus *rendering* in a
  real terminal does not read as clearly as the tests assert, which manual TUI
  verification covers · severity: low · → mitigation: TBD
