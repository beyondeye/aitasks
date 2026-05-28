---
Task: t850_board_improved_task_filtering.md
Base branch: main
plan_verified: []
---

# t850 — Board: Improved task filtering (locked/free + parallel git/type)

## Context

Today the board's view selector treats `a All`, `g Git`, `i Impl`, `t Type` as
**four mutually-exclusive** modes: you cannot, for example, restrict the Impl
view to only `bug`-type tasks, or list only git-linked tasks among the ones
currently being implemented. The task-selection workflow during multi-PC use is
also awkward — there is no quick way to see "tasks I could pick right now"
(neither locked by another user nor already in `Implementing`).

This task restructures the filter UI:

1. **Rename `i Impl` → `l Locked`** with broadened semantics: a task is
   *locked* if `status == Implementing` **OR** it appears in `lock_map`. This
   makes it the **exact inverse** of the new `f Free` filter and gives the
   board a clean three-way base radio: *show everything / show what's busy /
   show what's free to pick*.
2. **Add `f Free`** as the third base filter: tasks that are neither
   `Implementing` nor locked. For parents, "free" also requires that no
   child is locked or `Implementing`.
3. **Promote `g Git` and `t Type` to independent toggle add-ons** that apply
   on top of the active base. Search-by-name continues to apply on top of
   everything (unchanged).

The radio + add-on model keeps the selector compact while letting users
combine intent (`free` ∩ `bug` type ∩ git-linked) in one view.

## Clarifications captured (asked & answered)

1. **`l Locked` semantics**: `status == Implementing` **OR** present in
   `lock_map` (exact inverse of `free`; `all = locked ∪ free`,
   `locked ∩ free = ∅`). A task whose lock crashed but still says
   `Implementing` correctly appears in `locked`.
2. **Keyboard shortcut for locked**: `l`. Verified free at KanbanApp level
   (existing `l` is scoped inside the `TaskDetailScreen` modal — no
   collision while the modal is closed).
3. **Free + parents**: A parent is hidden in `free` when **any of its
   children** is `Implementing` or locked.
4. **Toggle keys**: `g` flips git add-on on/off. `t` flips the type add-on;
   **every** turn-on of `t` re-opens the type-picker dialog so the user can
   reconfirm/edit the selection; turn-off requires no dialog.
5. **Radio re-press**: Pressing the active base key (`a`/`l`/`f`) is a
   no-op. Exactly one base is always active.
6. **UI**: Single-line `[a All | l Locked | f Free]   g Git   t Type` —
   bracketed radio group on the left, two toggle slots to the right,
   separated by extra whitespace.

## Architectural change

Replace `self.view_mode: str` (single value `"all"|"git"|"implementing"|"type"`)
with three independent state vars on `KanbanApp`:

| Variable | Type | Values |
|---|---|---|
| `base_filter` | str | `"all"` \| `"locked"` \| `"free"` (default `"all"`) |
| `git_filter_active` | bool | `False` (default) |
| `type_filter_active` | bool | `False` (default) |

`manager.settings["filter_issue_types"]` keeps its current role (*which*
types are selected); `type_filter_active` becomes the on/off switch separate
from the selection.

`apply_filter` becomes an **AND of independent visible sets**:

```
visible = base_visible_set    # None when base == "all"
if git_filter_active:   visible &= _git_visible_set()
if type_filter_active:  visible &= _type_visible_set()
visible filtered by search_filter (existing behavior)
```

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — primary edits (single file).
- `tests/test_board_view_filter.py` — rename + extend existing tests.
- `website/content/docs/tuis/board/reference.md` — rewrite "View Modes"
  section (also corrects existing stale "three modes" count).

## Detailed implementation steps

### 1. State refactor (`KanbanApp.__init__`)

Replace:

```python
self.view_mode = "all"
```

with:

```python
self.base_filter = "all"          # "all" | "locked" | "free"
self.git_filter_active = False
self.type_filter_active = False
```

Keep `_view_auto_expanded` and `expanded_tasks` unchanged. The
auto-expansion logic (today fired on entering `implementing`) now fires on
entering `locked` — the same UX benefit applies (auto-expand parents whose
children are in flight).

### 2. `ViewSelector` widget rewrite (`aitask_board.py:594-638`)

Replace `MODES` and `render()` / `on_click()` with the new layout.

Render plan (Rich markup string):

```
\[<base>a All</base> [dim]|[/] <base>l Locked</base> [dim]|[/] <base>f Free</base>\]    <toggle>g Git</toggle>   <toggle>t Type</toggle>
```

Where:
- `<base>X</base>` is `[bold cyan]X[/]` if `X == active_base`, else `[dim]X[/]`.
- `<toggle>X</toggle>` is `[bold cyan]X[/]` when active, `[dim]X[/]` when off.
- The framing `[` / `]` characters are escaped (`\[` `\]`) and rendered dim.

Update constructor signature:

```python
def __init__(self, base: str, git_on: bool, type_on: bool, **kwargs):
```

`on_click`: rebuild click-target metadata as a list of
`(start_col, end_col, target)` segments computed inside `render()` (cache
on `self._click_targets`). Map base segments to
`app._set_base_filter(name)`, the git segment to `app._toggle_git_filter()`,
the type segment to `app._toggle_type_filter()`. Same hand-rolled column-
arithmetic approach as today, just over the new 3+2 segment layout.

`KanbanApp.compose()` updates the constructor call:

```python
yield ViewSelector(
    self.base_filter, self.git_filter_active, self.type_filter_active,
    id="view_selector",
)
```

### 3. Bindings (`KanbanApp.BINDINGS`)

Replace the existing four view-mode bindings (~line 3317) with:

```python
Binding("a", "view_all", "All", show=False),
Binding("l", "view_locked", "Locked", show=False),
Binding("f", "view_free", "Free", show=False),
Binding("g", "view_git", "Git", show=False),
Binding("t", "view_type", "Type", show=False),
```

`i` is no longer bound at KanbanApp level. (t848_2 will eventually sweep
these through the shortcut registry — author them in their natural
`Binding(...)` form for now.)

### 4. New / renamed `action_*` methods

Replace the existing `action_view_all/git/implementing/type` plus
`_set_view_mode(mode)` with:

```python
def action_view_all(self):     self._set_base_filter("all")
def action_view_locked(self):  self._set_base_filter("locked")
def action_view_free(self):    self._set_base_filter("free")
def action_view_git(self):     self._toggle_git_filter()
def action_view_type(self):    self._toggle_type_filter()
```

`_set_base_filter(name)`:
- If `name == self.base_filter`: return (no-op — radio semantics).
- Manage `locked` auto-expansion (replaces the `implementing`-keyed code):
  on leaving `locked`, restore `expanded_tasks` from
  `_view_auto_expanded`; on entering `locked`, call
  `_auto_expand_locked()`.
- Update `self.base_filter`, refresh the `ViewSelector`, recompute search
  placeholder, refresh board.

`_toggle_git_filter()`:
- Flip `self.git_filter_active`.
- Refresh selector and `apply_filter` (no board re-render — git filter
  doesn't change expansion).

`_toggle_type_filter()`:
- If currently OFF → call `_open_type_filter_dialog()` (every turn-on shows
  the dialog, per clarification #4). On dialog confirm with non-empty
  selection: set `type_filter_active = True`. On Cancel/Esc or empty
  confirm: leave OFF.
- If currently ON → set `type_filter_active = False`, refresh.

Update `_open_type_filter_dialog`'s `on_dismiss`:
- `result is None` (Cancel): leave `type_filter_active` unchanged.
- `result == []` (empty confirm): set `type_filter_active = False` **and**
  clear `manager.settings["filter_issue_types"]`.
- non-empty `result`: store types, set `type_filter_active = True`.

`_refresh_type_filter_summary` predicate flips from
`self.view_mode == "type"` to `self.type_filter_active`.

### 5. New `_locked_visible_set()` + `_free_visible_set()`, updated `apply_filter`

Rename `_implementing_visible_set` to `_locked_visible_set` and broaden:

```python
def _locked_visible_set(self) -> set:
    """Tasks visible in locked view: status==Implementing OR present in lock_map.

    Also includes parents of locked/impl children and all siblings of such
    children (preserves the existing context-grouping UX). Inverse of
    `_free_visible_set()` at the leaf (per-task) level.
    """
    locked_ids = set(self.manager.lock_map.keys())

    def _is_busy(filename, task):
        if task.metadata.get('status') == 'Implementing':
            return True
        task_num, _ = TaskCard._parse_filename(filename)
        return task_num.lstrip('t') in locked_ids

    visible = set()
    # Parents that are themselves busy.
    for filename, task in self.manager.task_datas.items():
        if _is_busy(filename, task):
            visible.add(filename)
    # Children + parent + sibling grouping when a child is busy.
    for filename, task in self.manager.child_task_datas.items():
        if _is_busy(filename, task):
            visible.add(filename)
            parent_num = self.manager.get_parent_num_for_child(task)
            parent = self.manager.find_task_by_id(parent_num)
            if parent:
                visible.add(parent.filename)
            for sib in self.manager.get_child_tasks_for_parent(parent_num):
                visible.add(sib.filename)
    return visible
```

Add `_free_visible_set` as the strict inverse at the leaf, with parent
cascade per clarification #3:

```python
def _free_visible_set(self) -> set:
    """Tasks visible in free view: NOT Implementing AND NOT locked.

    For parents: also hidden when any child is Implementing or locked.
    """
    locked_ids = set(self.manager.lock_map.keys())

    def _is_busy(filename, task):
        if task.metadata.get('status') == 'Implementing':
            return True
        task_num, _ = TaskCard._parse_filename(filename)
        return task_num.lstrip('t') in locked_ids

    visible = set()
    # Free children.
    for filename, task in self.manager.child_task_datas.items():
        if not _is_busy(filename, task):
            visible.add(filename)
    # Free parents only when self AND all children are free.
    for filename, task in self.manager.task_datas.items():
        if _is_busy(filename, task):
            continue
        task_num, _ = TaskCard._parse_filename(filename)
        children = self.manager.get_child_tasks_for_parent(task_num)
        if any(_is_busy(c.filename, c) for c in children):
            continue
        visible.add(filename)
    return visible
```

Extract `_is_busy` to a private method on `KanbanApp` so both helpers share
the definition.

Rewrite `apply_filter`:

```python
def apply_filter(self):
    if self.base_filter == "locked":
        visible = self._locked_visible_set()
    elif self.base_filter == "free":
        visible = self._free_visible_set()
    else:  # "all"
        visible = None  # sentinel — all cards eligible

    if self.git_filter_active:
        git_set = self._git_visible_set()
        visible = git_set if visible is None else visible & git_set

    if self.type_filter_active:
        type_set = self._type_visible_set()
        visible = type_set if visible is None else visible & type_set

    for card in self.query(TaskCard):
        v = True
        if visible is not None and card.task_data.filename not in visible:
            v = False
        if v and self.search_filter:
            search_content = f"{card.task_data.filename} {card.task_data.metadata}".lower()
            if self.search_filter not in search_content:
                v = False
        card.styles.display = "block" if v else "none"
```

Rename `_auto_expand_implementing` → `_auto_expand_locked` and broaden its
predicate from `c.metadata.get('status') == 'Implementing'` to use
`_is_busy(c.filename, c)`.

### 6. Search-box placeholder

The current map keys off `view_mode`. Rebuild as a dynamic computation in a
new `_compute_search_placeholder() -> str`, called from `_set_base_filter`,
`_toggle_git_filter`, and `_toggle_type_filter`:

- Base phrase: `"Search tasks..."` / `"Search locked tasks"` /
  `"Search free tasks"`.
- Append `" + git"` / `" + type"` when each add-on is active.
- Append `" (a/l/f to switch base)"` when base != all.

### 7. Type-filter summary line

`_refresh_type_filter_summary` keys off `type_filter_active`. Same text
(`"types: a, b, c"`) shown under the selector when the add-on is on and a
non-empty selection exists.

### 8. Tests (`tests/test_board_view_filter.py`)

Update existing tests; add new cases.

- Rename `test_implementing_filter_hides_non_matching` →
  `test_locked_filter_hides_non_matching`; key press `i` → `l`; assert
  against the renamed `_locked_visible_set()` (which now also covers
  lock_map-only tasks — extend the fixture to seed
  `app.manager.lock_map` with one entry).
- `test_git_filter_hides_non_matching` — base remains `all`, press `g`,
  same assertion (semantics unchanged for git-only).
- `test_back_to_all_restores_visibility` — re-test the new path
  (`l` then `a`, and `g` toggle).
- **New** `test_free_filter_excludes_locked_and_implementing` — set one
  task to `Implementing`, inject one entry into `lock_map`, press `f`,
  assert intersection.
- **New** `test_free_parent_hidden_when_child_busy` — synthesize a parent
  + child, mark child `Implementing`, assert parent hidden in `free`.
- **New** `test_locked_filter_includes_lockmap_only_tasks` — task with
  `status != Implementing` but present in `lock_map` is visible in
  `locked`.
- **New** `test_base_and_git_compose` — press `l` then `g`, assert
  intersection of `_locked_visible_set()` ∩ `_git_visible_set()`.
- **New** `test_base_and_type_compose` — set non-empty
  `filter_issue_types`, monkeypatch `_open_type_filter_dialog` to invoke
  its `on_dismiss` callback with that selection, press `f` then `t`,
  assert intersection.
- **New** `test_active_base_keypress_is_noop` — press `a` while
  base=all; assert state unchanged.

For headless Pilot, monkeypatch `KanbanApp._open_type_filter_dialog` to a
function that directly invokes `on_dismiss` with a synthetic selection,
avoiding the need to drive the modal.

### 9. Documentation (`website/content/docs/tuis/board/reference.md`)

Rewrite the "View Modes" section (~line 120):

- One-line intro distinguishing **base** (radio) and **add-on** (toggle).
- Table 1: **Base filters** — `a All`, `l Locked`, `f Free`. Define
  `Locked` = `status == Implementing` OR present in lock list; `Free` =
  inverse, with parents hidden when any child is busy.
- Table 2: **Add-on filters** — `g Git`, `t Type`. Note that turning `t`
  on always opens the dialog.
- Keep "Implementing view auto-expansion" paragraph but rename to
  "Locked view auto-expansion" and update text to reference
  `Locked` and the broader busy-child predicate.
- Add a one-line example: `l + g` shows only busy tasks linked to an
  issue/PR.
- Update Keybindings table (~line 27): replace the `i` row with an `l`
  row labelled "Switch to Locked view"; add `f` row "Switch to Free
  view".
- Fix the stale "three task filtering modes" claim — now three **base**
  filters + two **add-on** toggles.

## Reference functions / patterns reused

- `manager.lock_map` (populated by `refresh_lock_map`,
  `aitask_board.py:392`) — source of "locked" truth.
- `TaskCard._parse_filename` (`aitask_board.py:652`) — derives lock-id
  prefix from filename.
- `manager.get_child_tasks_for_parent`, `manager.get_parent_num_for_child`,
  `manager.find_task_by_id` — existing helpers used by
  `_implementing_visible_set`; reuse in both `_locked_visible_set` and
  `_free_visible_set`.
- `_open_type_filter_dialog` (`aitask_board.py:3666`) and
  `IssueTypeFilterScreen` modal — unchanged surface; only `on_dismiss`
  semantics change.

## Non-goals / explicitly out of scope

- **Routing the new `f`/`l` bindings through the t848 shortcut registry.**
  t848_2 will sweep `KanbanApp.BINDINGS` wholesale. Authoring the
  bindings in their natural form here is consistent with existing
  siblings; t848_2 picks them up automatically.
- **Persisting `base_filter` / add-on flags across sessions.** Today
  `view_mode` is not persisted — the board always starts in `all`.
  Preserve that behavior.
- **Adding `f`/`l` to the footer (`show=True`).** Existing view-mode
  bindings are `show=False`; they live in the selector widget.
- **A backwards-compat alias for `i`.** This is an internal-use framework
  still under active development; the rename lands clean.

## Verification

```bash
# Pilot tests
python3 -m pytest tests/test_board_view_filter.py -v

# Compile / syntax check
python3 -m py_compile .aitask-scripts/board/aitask_board.py

# Manual smoke (TTY)
./ait board
#   - confirm selector renders [a All | l Locked | f Free]   g Git   t Type
#   - press f → only non-busy tasks shown
#   - press g (with f still on) → intersect with git-linked
#   - press t → dialog opens; pick a type; confirm; intersection narrows
#   - press t again → dialog re-opens (per clarification #4)
#   - press l → switches base to Locked while keeping g/t add-ons on;
#     parents with busy children auto-expand
#   - press a while in All → no-op (radio)
#   - press Esc on type dialog → state unchanged
#   - confirm a task that is in lock_map but with status != Implementing
#     (manually seed via aitask_lock.sh) shows in Locked, hidden in Free
```

## Risks

- **`apply_filter` is on the hot path** (re-runs on every search keystroke).
  AND-of-sets stays O(N) per filter; for typical task counts (<500) the
  extra intersections are negligible.
- **Click hit-testing** in `ViewSelector.on_click` is hand-rolled column
  arithmetic. The new layout has more segments + brackets; compute
  segment offsets carefully and add a small Pilot test for the click
  paths if practical.
- **`_locked_visible_set` may include parents/siblings whose own status is
  Ready** (preserved from current Impl-view sibling grouping). This is
  intentional — `locked` is a *context* view, not a leaf filter. The doc
  note must make this explicit.

## Post-Review Changes

### Change Request 1 (2026-05-28 09:18)
- **Requested by user:** "The horizontal space reserved to show the filters
  is too narrow — the `g Git` and `t Type` add-ons are hidden behind the
  search box."
- **Changes made:** Widened the CSS `#view_col { width: 36 }` rule (sized
  for the old 31-char selector) to `width: 48` to accommodate the new
  selector text `[a All | l Locked | f Free]   g Git   t Type` (~44 chars
  + 2 cols horizontal padding).
- **Files affected:** `.aitask-scripts/board/aitask_board.py` (single
  CSS-rule line in the `KanbanApp.CSS` block; line ~3183). Pilot tests
  remain green (headless, CSS-agnostic).

### Change Request 2 (2026-05-28 09:18)
- **Requested by user:** "The `f Free` label has a spurious `\` at the end
  in the rendered output."
- **Root cause:** The closing-bracket segment was emitted as
  `r"[dim]\][/]"`. Rich markup only requires escaping `[` (the tag start)
  with `\[`; the `]` does not need escaping outside a tag context, so the
  literal backslash was being rendered to the screen.
- **Changes made:** Replaced `r"[dim]\][/]"` with `"[dim]][/]"` (no
  backslash). Verified via `rich.Console` round-trip that the visible
  output is `[a All | l Locked | f Free]   g Git   t Type` with no
  stray characters.
- **Files affected:** `.aitask-scripts/board/aitask_board.py`
  (`ViewSelector.render` closing-bracket line). Pilot tests still green.

## Final Implementation Notes

- **Actual work done:** Implemented the full plan as approved. Refactored
  `KanbanApp.view_mode` into three independent state vars
  (`base_filter`, `git_filter_active`, `type_filter_active`). Rewrote
  `ViewSelector` with the bracketed-radio + two-toggle layout and
  segment-range click hit-testing. Added `_set_base_filter`,
  `_toggle_git_filter`, `_toggle_type_filter` dispatchers. Renamed
  `_implementing_visible_set` → `_locked_visible_set` and broadened to
  `status==Implementing OR lock_map`. Added `_free_visible_set` with the
  parent-cascade rule. Rewrote `apply_filter` as AND-of-sets.
  Renamed/broadened `_auto_expand_locked`. Updated the docs reference page
  and replaced the test suite (4 updated, 5 new tests, all green).
- **Deviations from plan:** None at the architectural level. Two small
  layout/markup bugs surfaced during user review and are recorded above
  under Post-Review Changes (CSS width 36 → 48; Rich bracket escape).
- **Issues encountered:**
  - The new selector string is ~46 cols wide; the existing `#view_col
    { width: 36 }` CSS rule (sized for the old 31-col selector) clipped
    the add-on toggles behind the search box. Fixed in CR1.
  - Rich's markup syntax only requires escaping `[` (with `\[`). My
    initial render used `\]` symmetrically — which Rich rendered as a
    literal backslash. Fixed in CR2.
- **Key decisions:**
  - `_locked_visible_set` preserves the context-grouping behavior of the
    old `_implementing_visible_set` (busy child → include parent + all
    siblings). This makes `locked` a "see what's in flight + its
    surrounding work" view, not a strict leaf filter. `_free_visible_set`,
    by contrast, is a strict per-task check with parent cascade — the two
    are leaf-level inverses but `locked` is a superset at the
    context/sibling level. Documented this in the user-facing reference.
  - Did not route the new `l` / `f` bindings through the t848 shortcut
    registry; t848_2 will sweep all of `KanbanApp.BINDINGS` wholesale.
  - Did not persist `base_filter` / add-on flags across sessions — matches
    the prior behavior (board always starts in `all`).
- **Upstream defects identified:** None. The pre-existing docs note about
  "three task filtering modes" was incorrect before this change as well
  (four modes existed), but it's superseded by the rewrite — not a
  separate upstream defect.
