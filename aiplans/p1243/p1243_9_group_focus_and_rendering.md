---
Task: t1243_9_group_focus_and_rendering.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Archived Sibling Plans: aiplans/archived/p1243/p1243_*_*.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-09 12:37
---

# t1243_9 — Group focus and rendering

> Design source of truth: `aiplans/p1243_board_task_groups_and_fast_reordering.md`
> — Workstream C, §"Rendering" and §"Focus and navigation must become unit-level
> too". The task file `aitasks/t1243/t1243_9_group_focus_and_rendering.md` is the
> spec; this file is the execution order.

## Context

Child 9 of 14. t1243_8 landed the **data model** — `lib/board_groups.py` derives
render units from the `boardgroup` frontmatter field (INV-R), and
`aitask_update.sh --boardgroup` writes it — but **the board does not read
`boardgroup` anywhere** (verified: zero matches in `aitask_board.py`). This child
makes groups visible and navigable.

The larger half is not the widget: **every focus/navigation seam in the board is
`TaskCard`-or-placeholder centric**, so declaring a header focusable is not
enough. In particular `_column_focus_target` returns `None` for a column showing
no cards and no placeholder, and `_refocus_column` then silently does nothing —
focus is lost. That is the case this child exists to close.

## Step 0 — Anchor re-verification (RESULT)

`aitask_board.py` moved **9043 → 11316 lines** since t1243 was planned (t1377_1/3/4/5
column management, t1418 multi-row footer). Every symbol the plan names still
exists. **Five premises drifted**; record them, do not work around them.

| # | Plan premise | Current source | Consequence for this plan |
|---|---|---|---|
| 1 | `_focused_card()` is `query("TaskCard:focus")` | **`:8258`** — an `isinstance(self.screen.focused, TaskCard)` attribute read since t1243_7 (docstring: *27 whole-board walks per footer sweep, 59 ms, now zero*) | The plan's `_focused_unit()` = `query("TaskCard:focus, GroupHeader:focus").first()` would **reintroduce that cost on the same hot path** (`check_action` runs it per binding per `refresh_bindings()`). `_focused_unit()` **must** be an isinstance read. |
| 2 | "all four `_move_task_*`" | Three helpers: `_move_task_lateral` `:10063`, `_move_task_vertical` `:10253`, `_move_task_to_extreme` `:10313` (six public actions) | Same drift class p1243_8 recorded for "seven call sites → six". Wire three, not four. |
| 3 | `apply_filter` needs generalising | `:7873` — the unit loop reads **`unit.task_data`** | A `GroupHeader` cannot be yielded from `_filter_units`. p1243_4's own note prescribes the right shape: *"add `GroupHeader` as a second query filtered the same way"*. |
| 4 | header prior art = `ColumnHeader` | `:2307` — carries **`col_id`**, and is **not focusable** | `GroupHeader` must carry **`column_id`** (like `TaskCard` / the placeholders) or the filter accumulator, `_column_focus_target` and `_get_focused_col_id` will not see it. |
| 5 | — (not in the plan) | `_move_task_to_extreme` `:10350` resolves its move-to-top anchor as `first non-child TaskCard` | With a header composed first, that mounts the moved card **between a header and its members**, splitting the block. |

**Confirmed intact and reusable** — t1243_4 pre-laid three seams that name this
work explicitly, and they hold:

- `task_matches_filter(task, visible, search)` `:382` — data-level, per-task,
  callable so a caller can *count*. **Do not reimplement** (`board_groups.py`
  deliberately does not re-export it).
- `set_unit_display(unit, is_visible)` `:399` — reads `is_child` via `getattr`
  *"so a future unit that is not a `TaskCard` (t1243_10's collapsed-group header)
  needs no branch added here"*.
- `_filter_units` `:7816` / `_filter_placeholders` `:7837` — one whole-DOM query
  plus a `column_id` filter. Its docstring records the measurement that forbids
  the obvious alternative: **per-column widget resolution inside a filter pass
  cost 128 ms against 13 ms for the whole-board pass.** Never resolve column
  widgets in the filter path.
- `_card_block` `:10138` already stops at the first non-`.child-wrapper` sibling,
  so a `GroupHeader` terminates a block correctly with **no change**.

## Scope decisions (confirmed with the user)

Three boundaries the decomposition left open. All three were put to the user and
the recommended option was chosen.

1. **Minimal filter awareness lands here, not in t1243_10.** A collapsed group
   mounts a header and no member cards, so `cols_with_visible` omits the column,
   the `EmptyColumnPlaceholder` flips visible, and `_column_focus_target` returns
   the *placeholder* instead of the header — **two focus anchors, violating the
   very invariant this child restates**. This child therefore makes `GroupHeader`
   a filter unit (Step 6). t1243_10 keeps persistence, the five lifecycle owners,
   the prune sweep, the match-count badge, collapsed-via-child-text matching, and
   the full matrix.
2. **Header movement is a dispatch seam, and the AC is amended.** t1243_11 owns
   the model write, so *"movement from a header moves the block"* is not testable
   here. This child lands the router + `_apply_group_move` seam and tests the
   **dispatch** with a spy; the task file's Verification bullet is edited to say
   so. Member-move and child-refusal are tested for real.

   **This is a material scope decision, and it was put to the user as one.** The
   alternatives offered were *"Pull the block-move implementation forward"*
   (t1243_9 also lands the N-write lateral/vertical/to-edge group moves) and
   *"Refuse header movement in t1243_9"* (shift/ctrl+arrows no-op with a notify;
   t1243_11 wires dispatch and implementation together). The user chose the
   dispatch-seam option. Pre-phase step `amend_the_ac_first` executes the AC edit
   **before** any code, so the acceptance contract is never retro-fitted to what
   was built.
3. **Grouped columns fall back to recompose.** `_swap_adjacent_cards` /
   `_transplant_block` assume a card-only column. When a move touches grouping,
   fall back to `refresh_column(s)`, which re-derives the DOM from
   `build_column_units`. Zero cost today (no group exists) and bounded to grouped
   columns after; t1243_11 restores the fast path for group blocks. This matches
   `_transplant_block`'s already-documented recompose-recovery contract.

## Key files

- `.aitask-scripts/board/aitask_board.py` — all production changes.
- `tests/test_board_group_focus.py` — **new**.
- `aitasks/t1243/t1243_9_group_focus_and_rendering.md` — amend the one
  Verification bullet per decision 2 (no silent AC deviation).

---

### Pre-phase (risk mitigations)

Runs **before** Step 1. Nothing in the implementation body starts until both
steps below are done.

1. `[amend_the_ac_first]` Edit
   `aitasks/t1243/t1243_9_group_focus_and_rendering.md`: change the Verification
   bullet *"movement from a header moves the block, from a member moves only that
   member, from a child is refused"* to *"movement from a header **dispatches**
   the block move (`_apply_group_move`) with the right members and refocuses the
   header — t1243_11 implements the write; from a member moves only that member;
   from a child is refused"*, and add scope decisions 1 and 3 to its
   Implementation plan. The AC changes **first**, never retro-fitted to match
   what was built.
2. `[pin_current_focus_behaviour]` Run `tests/test_board_empty_column_focus.py`,
   `tests/test_board_dom_transplant.py`, `tests/test_board_scroll_focus_jump.py`,
   `tests/test_board_toggle_children_gate.py`, `tests/test_board_move_command.py`
   (it pins `MoveGatingTests`) and `tests/test_board_work_report.py` (the other
   column-scoped `_get_focused_col_id` consumer) **green before editing any
   seam**, and re-run all six after each of Steps 3, 4 and 7. They are the
   existing characterization of the seams being generalised — a break there is a
   regression in this change, not a stale fixture. *(Module list widened beyond
   the four originally proposed, to cover the §3a widened-seam audit — the
   mitigation's scope, not a new mitigation.)*

## Step 1 — `GroupHeader`

New widget near `ColumnHeader` (`:2307`) / the placeholders (`:2281`–`:2306`).

```python
class GroupHeader(Static):
    """A focusable in-column task-group header: `▾ perf work (3)`.

    Carries `column_id` — NOT `col_id` like `ColumnHeader` — because it is a
    first-class focus/filter unit: `_filter_units`' accumulator, the focus
    rescue, `_column_focus_target` and `_get_focused_col_id` all key off
    `column_id`, exactly as `TaskCard` and the two placeholders do.

    `members` is a list of `Task` DATA, not widgets. A collapsed group mounts no
    member cards at all, so the filter pass has nothing to evaluate unless the
    header carries the members itself (t1243_10 needs the same list to count
    matches for its badge).
    """

    can_focus = True

    def __init__(self, col_id: str, slug: str, members: list, collapsed: bool):
        super().__init__(classes="group-header")
        self.column_id = col_id
        self.slug = slug
        self.members = members
        self.collapsed = collapsed
        self.update(self._label())

    def _label(self) -> str:
        glyph = "▸" if self.collapsed else "▾"
        return f"{glyph} {group_display_title(self.slug)} ({len(self.members)})"

    def set_collapsed(self, collapsed: bool) -> None:
        """Flip the glyph in place — no recompose (the same in-place repaint
        idiom `_repaint_card_mark` uses for the ☑/☐)."""
        if self.collapsed != collapsed:
            self.collapsed = collapsed
            self.update(self._label())
```

Imports at the board's `lib` import block (alongside `task_yaml`):

```python
from board_groups import build_column_units, group_display_title, task_group_slug
```

CSS, added beside the placeholder rules at `:6775`–`:6778`, using the board's own
`$primary 30%` focus idiom and keeping `:focus:hover` **in the focus family**
(the rule `TaskCard.markable-card:focus:hover` at `:6734` documents why):

```css
.group-header { height: 1; width: 100%; padding: 0 1; color: $accent; text-style: bold; }
.group-header:focus { background: $primary 30%; }
.group-header:hover { background: $surface-lighten-1; }
.group-header:focus:hover { background: $primary 30%; }
```

## Step 2 — Collapse state, and composing units in `KanbanColumn`

### 2a. Collapse-state owner and data flow

Nothing owns group-collapse state today, and t1243_10 — which owns *persistence*
— depends on this child. So this child defines the **in-memory owner** and the
path by which it reaches `compose`, and t1243_10 later migrates only the
load/save ends. Three pieces, mirroring `expanded_tasks` exactly, which is the
board's existing precedent for session-only view state consumed at compose time:

**(i) The app owns it.** In `KanbanApp.__init__`, immediately after
`self.expanded_tasks: set = set()` (`:7038`):

```python
        # Keys are "<col_id>/<slug>". SESSION-ONLY here, exactly like
        # `expanded_tasks` (which is likewise never persisted). t1243_10 adds
        # load/save against `settings.collapsed_groups` in the USER layer of
        # board_config, alongside `collapsed_columns` — it replaces the two ends,
        # not this attribute or anything downstream of it.
        self.collapsed_groups: set = set()
```

**(ii) Each column holds the same set by reference.** `KanbanColumn.__init__`
(`:3391`) takes `collapsed_groups` as a **trailing** parameter — appended after
`collapsed`, never inserted mid-list, so no existing positional argument shifts
(p1243_8's own lesson from `write_task_file`):

```python
    def __init__(self, col_id: str, title: str, color: str, manager: TaskManager,
                 expanded_tasks: set = None, collapsed: bool = False,
                 collapsed_groups: set = None):
        ...
        # By REFERENCE, like `expanded_tasks` above: the app mutates its own set
        # and every column sees it, so a toggle needs no per-column propagation.
        self.collapsed_groups = collapsed_groups if collapsed_groups is not None else set()

    def is_group_collapsed(self, slug: str) -> bool:
        return f"{self.col_id}/{slug}" in self.collapsed_groups
```

**(iii) Both construction sites pass it.** `refresh_board` builds the
`"unordered"` column (`:7666`) and each configured column (`:7677`); both already
pass `self.expanded_tasks` positionally and `collapsed=` by keyword. Add
`collapsed_groups=self.collapsed_groups` by keyword to each.

**Why this is enough for `compose` to omit member widgets.** `action_toggle_group`
(Step 5) mutates the **app's** set and then calls `refresh_column(col_id)`, whose
`_recompose_column` (`:7742`) re-runs `_compose_widgets` on the *same*
`KanbanColumn` instance — which still holds the reference to that set. So the
recomposed column reads the just-mutated state with no propagation step and no
re-construction. This is the same mechanism by which `x` on a card already makes
`task_block` see a changed `expanded_tasks`.

### 2b. The unit loop

`compose()` (`:3425`–`:3426`) replaces the flat task loop with a unit loop.
Everything else in `compose` is untouched — the `ColumnHeader`, the
pre-hidden `EmptyColumnPlaceholder` and the collapsed-column branch all stay:

```python
            for slug, members in build_column_units(tasks):
                # A single-member group renders as a plain card (design §Rendering;
                # board_groups keeps its slug so the group is not silently
                # dissolved, but the caller decides not to draw a header).
                if slug and len(members) > 1:
                    collapsed = self.is_group_collapsed(slug)
                    yield GroupHeader(self.col_id, slug, members, collapsed)
                    if collapsed:
                        continue
                for task in members:
                    yield from self.task_block(task)
```

Headers and member cards are **flat siblings**, the same shape as
`.child-wrapper` rows — which is what lets `_card_block` generalise later
instead of forking.

`task_block` is **unchanged**: it stays the single construction path shared with
`_transplant_block` (p1243_5's note: *"do not fork it"*).

Both `KanbanColumn(...)` construction sites (`:7668`, `:7678`) pass
`self.collapsed_groups`.

## Step 3 — The focus-unit abstraction

Focus/nav seams. `_focused_card()` **survives unchanged** as the narrow "focused
*task*" accessor that ~10 `check_action` gates genuinely need.

```python
    #: One DOM-ordered union query. A comma selector yields nodes in DOM order,
    #: which is what makes header→member→child a single walk; pinned by
    #: `test_unit_query_is_in_dom_order` because it is an assumption about
    #: Textual, not about this file.
    _UNIT_SELECTOR = "TaskCard, GroupHeader"

    def _focused_unit(self):
        """The focused navigation unit — a `TaskCard` or a `GroupHeader`.

        An attribute read, NOT a query, for the reason `_focused_card` documents:
        `check_action` runs the gates once per binding on every
        `refresh_bindings()`, i.e. on every focus change during a move.
        """
        focused = self.screen.focused if self.screen else None
        return focused if isinstance(focused, (TaskCard, GroupHeader)) else None

    def _get_column_units(self, col_id: str) -> list:
        """`TaskCard`s and `GroupHeader`s of a column, in DOM order."""
        return [w for w in self.query(self._UNIT_SELECTOR) if w.column_id == col_id]

    def _visible_column_units(self, col_id: str) -> list:
        return [w for w in self._get_column_units(col_id)
                if w.styles.display != "none"]
```

`_column_focus_target` (`:8397`) — restate the invariant over units:

```python
    def _column_focus_target(self, col_id: str, preferred_pos: int = 0):
        """Return the widget to focus when entering `col_id`, or None.

        Every board column owns exactly one focus anchor: a placeholder when it
        shows no UNITS, otherwise its first visible unit. Before t1243_9 this
        read "cards", and a column of only collapsed groups — which mounts
        headers and no cards — returned None, so `_refocus_column` silently did
        nothing and focus was lost.
        """
        placeholder = self._column_placeholder(col_id)
        if placeholder is not None and placeholder.styles.display != "none":
            return placeholder
        units = self._visible_column_units(col_id)
        if units:
            return units[min(preferred_pos, len(units) - 1)]
        return None
```

`_get_focused_col_id` (`:8693`) — `self._focused_unit()` in place of
`self._focused_card()`; the placeholder fallback is unchanged.

`_refocus_column` (`:8412`) needs **no edit** — it delegates to
`_column_focus_target`.

### 3a. Widened-seam audit — every `_get_focused_col_id()` caller

`_get_focused_col_id` returns `None` today whenever a `GroupHeader` is focused
(neither `_focused_card` nor `_focused_placeholder` matches), and after this
change it returns a column id. **Every caller inherits that.** Enumerated rather
than assumed — all twelve call sites:

| caller | behaviour with a focused header | verdict |
|---|---|---|
| `check_action("work_report")` `:7212` and `action_work_report` `:9095` | the column-scoped report resolves its column | **desired** — a header identifies a column exactly as a placeholder does |
| refocus fallbacks `:7535`, `:7609`, `:7757`, `:7789` | the column resolves for a refresh | **desired** |
| `_nav_lateral` `:8704` | lateral nav no longer bails to `action_focus_board()` | **desired** — the point of the change |
| `_shift_column` `:10374` | `ctrl+←` / `ctrl+→` reorder the column | **desired** — an explicit AC |
| `toggle_column_collapse` `:10561`, `action_toggle_column_collapsed` `:10576` | `X` collapses the focused column and re-anchors by column identity | **desired** |
| **`action_move_to_column` `:8597`** | **the `else` branch reviews EVERY task in the column** | **DEFECT** — see Step 7c |

`:7265` is a comment, not a call. The single defect is fixed in Step 7c; the ten
desirable sites are what makes a header a first-class column anchor, and cases
9 and 20 in the Verification pin two of them.

## Step 4 — Navigation over units

Two notions of "unit" stay distinct, and this is the subtle part:

- **Navigation stops** = every focusable content widget in DOM order:
  `GroupHeader`, member/ungrouped parent `TaskCard`, **and expanded child
  `TaskCard`** (already included today, because `_get_column_cards` filters by
  the `column_id` *attribute*, which child cards carry too). This preserves
  today's behaviour exactly.
- **Movement units** = what a movement key acts on: header → the whole group;
  parent card → its `_card_block()`; child card → **refused**, as today.

`action_nav_up` (`:8635`) / `action_nav_down` (`:8653`): swap `_focused_card()` →
`_focused_unit()` and `_visible_column_cards` → `_visible_column_units`. Nothing
else changes — `_reanchor_to_viewport` reads only `.column_id` and `.region`,
both of which a `GroupHeader` has.

`_nav_lateral` (`:8703`): same two swaps for `focused` and `old_cards`. The
positional index is then measured over **navigation stops**, so `←`/`→`
preserve position across columns unchanged.

Resulting sequence for the combined case, which gets its own integration test:

```
▾ perf work (2)                  ← GroupHeader
    t9000  parent                ← member parent
      ↳ t9000_1 …                ← its expanded child
      ↳ t9000_2 …
    t9003  gamma                 ← next member
t9004  delta                     ← next unit (ungrouped)
```

## Step 5 — `x`, collapse, and the footer label

`x` becomes "expand/collapse the thing under focus". The footer must stay
truthful, and `check_action` **cannot relabel a binding** — so use the board's
own **duplicate-key fall-through** pattern (the `r` / `s` By-Trail pairs at
`:7163`–`:7186`): two bindings on `x`, mutually exclusive in `check_action`.

`BINDINGS`, beside `:6993`:

```python
        Binding("x", "toggle_children", "Toggle Children"),
        Binding("x", "toggle_group", "Toggle Group"),
```

`check_action`, at the `toggle_children` branch (`:7187`):

```python
        elif action == "toggle_children":
            if self.base_filter in ("inflight", "bytopic", "bytrail"):
                return False
            # The GroupHeader half of the duplicate-key pair owns `x` while a
            # header is focused, so the footer reads "Toggle Group" there.
            if isinstance(self._focused_unit(), GroupHeader):
                return False
            focused = self._focused_card()
            ...                                    # unchanged below
        elif action == "toggle_group":
            if self.base_filter in ("inflight", "bytopic", "bytrail"):
                return False
            return isinstance(self._focused_unit(), GroupHeader)
```

The action:

```python
    def action_toggle_group(self):
        """`x` on a `GroupHeader`: collapse / expand the group."""
        if self.check_action("toggle_group", None) is not True:
            return
        header = self._focused_unit()
        key = f"{header.column_id}/{header.slug}"
        if key in self.collapsed_groups:
            self.collapsed_groups.discard(key)
        else:
            self.collapsed_groups.add(key)
        # Recompose so members and their `.child-wrapper` rows appear/disappear
        # together, then land focus back on the header — focus must never be
        # left on an unmounted widget.
        self.refresh_column(header.column_id, refocus_col_id=header.column_id)
        self.call_after_refresh(self._refocus_group_header,
                                header.column_id, header.slug)

    def _refocus_group_header(self, col_id: str, slug: str) -> None:
        header = next((h for h in self.query(GroupHeader)
                       if h.column_id == col_id and h.slug == slug), None)
        if header is not None and header.styles.display != "none":
            header.focus()
```

`refresh_column`'s `refocus_filename` path targets a card, so the header refocus
is queued separately through `call_after_refresh` — the same deferral
`_refocus_card` already uses.

`action_toggle_children` / `_toggle_expand` are **unchanged**: the gate now hides
them while a header is focused, so `_toggle_expand`'s `_focused_card()` can never
see one.

## Step 6 — Minimal filter awareness (decision 1)

A second query, filtered exactly like `_filter_units` — the shape p1243_4's notes
prescribe:

```python
    def _filter_group_headers(self, cols):
        """`GroupHeader`s a filter pass may flip, scoped like `_filter_units`.

        A separate generator rather than a `_filter_units` extension because
        `apply_filter`'s unit loop reads `unit.task_data`, which a header does
        not have — it carries `members` instead.
        """
        for header in self.query(GroupHeader):
            if cols is None or header.column_id in cols:
                yield header
```

The visibility rule must be **child-aware from the start**, not member-only.
`Task.search_haystack` is `f"{filename} {metadata}".lower()` (`:231`) — a
parent's corpus does **not** include its children's text. So a search matching
only a child's text hides the parent card and leaves the child card visible
(pre-existing, `_filter_units` includes expanded child cards because they carry
`column_id`). A member-only header rule would then hide the header **above a
still-visible `↳` child row** — a new orphan the group hierarchy makes worse. The
design already states the correct rule: *"visible iff ≥ 1 member — or ≥ 1
member's child — matches"*.

```python
    def _group_header_matches(self, header, visible, search: str,
                              child_index) -> bool:
        """A header is visible iff >= 1 member — or >= 1 member's CHILD — matches.

        One formula for both states, which is what keeps a collapsed group
        findable by exactly the text that would find it expanded: an expanded
        group's members mount cards (evaluated in the unit loop) and a collapsed
        group's mount none, but the member DATA answers either way.

        Child-aware because a parent's `search_haystack` does not contain its
        children's text — a member-only rule would hide the header while
        `_filter_units` left a matching child card visible underneath it.

        `child_index` is built ONCE per filter pass by the caller. Members are
        tested first and short-circuit, so the child lookups only run for a
        group whose own members all failed.
        """
        members = header.members
        if any(task_matches_filter(m, visible, search) for m in members):
            return True
        for m in members:
            num, _ = TaskCard._parse_filename(m.filename)
            if num and any(task_matches_filter(c, visible, search)
                           for c in child_index.get(num, ())):
                return True
        return False
```

**The child lookup must be indexed, not repeated.**
`TaskManager.get_child_tasks_for_parent` (`:1439`) is **not** a cheap accessor: it
scans all of `child_task_datas`, runs a per-child `re.match` against an
f-string-built pattern, and `sorted()`s the result — and that sort is pure waste
for a boolean "does any child match". Calling it once per non-matching grouped
member would make one `apply_filter` pass `O(members × children)` with a regex per
pair, on a path that runs **on every search keystroke** (`on_search` → whole-board
`apply_filter`, `:7811`). That is exactly the hot-path cost t1243_4 measured and
rejected (whole pass 13 ms; its per-column alternative 128 ms).

Build the reverse index once per pass instead. `get_parent_num_for_child`
(`:1455`) is `child_task.filepath.parent.name` — O(1), no regex, no sort — so the
whole index is one linear walk:

```python
    def _children_by_parent(self) -> dict:
        """`{parent_num: [child Task, …]}` for the whole board, built in one pass.

        Deliberately NOT `get_child_tasks_for_parent` per parent: that helper
        re-scans `child_task_datas`, regex-matches every child and sorts it, and
        the sort is meaningless for a membership test. Keyed by
        `get_parent_num_for_child`, which yields the same form as
        `TaskCard._parse_filename(parent.filename)[0]` — the pairing
        `KanbanColumn.task_block` already relies on (`:3446`).
        """
        index = {}
        for child in self.manager.child_task_datas.values():
            index.setdefault(
                self.manager.get_parent_num_for_child(child), []).append(child)
        return index
```

In `apply_filter`, **between** the unit loop (`:7873`) and the placeholder loop
(`:7880`) — the ordering is load-bearing, the placeholder decision reads
`cols_with_visible`:

```python
        # Materialized so the index is built AT MOST ONCE, and only when a header
        # is actually in scope. No board renders a group header until a task
        # carries `boardgroup`, so `headers` is empty on today's boards and this
        # whole block is free — t1243_4's measured baseline is untouched.
        headers = list(self._filter_group_headers(cols))
        child_index = self._children_by_parent() if headers else {}
        for header in headers:
            v = self._group_header_matches(header, visible, self.search_filter,
                                           child_index)
            set_unit_display(header, v)
            if v:
                cols_with_visible.add(header.column_id)
```

Net cost once groups exist: one `O(children)` dict build per pass plus a dict hit
per member, replacing `O(members × children)` regex-and-sort calls. Cost with no
group present: unchanged from today.

t1243_10 builds the collapsed **match-count badge** (`▸ perf work (3) · 2 match`)
on this same helper — which is why `task_matches_filter` is per-task and
countable rather than a bulk boolean.

And the focus rescue (`:7890`) gains the header:

```python
        if (isinstance(focused, (TaskCard, GroupHeader, EmptyColumnPlaceholder))
```

**Out of scope, recorded not fixed:** the underlying orphaned-`↳`-row behaviour
(a visible child card under a parent the filter hid) predates groups and is
independent of them. It belongs in the canonical *Upstream defects identified*
bullet, not in this child — fixing it would change `apply_filter` semantics for
every ungrouped board.

## Step 7 — Movement dispatch and the grouped-column fallback

### 7a. The router (decision 2)

Each of the three `_move_task_*` helpers replaces its opening
`focused = self._focused_card()` with a unit-aware head. `_move_task_lateral`
(`:10063`) shown; `_move_task_vertical` (`:10253`) and `_move_task_to_extreme`
(`:10313`) take the same three lines with their own axis:

```python
        unit = self._focused_unit()
        if unit is None:
            return
        if isinstance(unit, GroupHeader):
            await self._move_focused_group(unit, "lateral", direction)
            return
        focused = unit
        if focused.is_child: return              # unchanged from here down
```

The router — real, testable behaviour (member resolution + the focus contract)
around a seam t1243_11 fills:

```python
    async def _move_focused_group(self, header, axis: str, direction: int):
        """Move a whole group as a block.

        t1243_9 owns the DISPATCH and the focus contract; the model write is
        t1243_11's (`Block moves`: N writes, relative order preserved, the
        neighbouring unit never touched). `_apply_group_move` is that seam.
        """
        members = group_members(
            self.manager.get_column_tasks(header.column_id), header.slug)
        if not members:
            return
        moved_to = await self._apply_group_move(header, members, axis, direction)
        if moved_to is None:
            return
        # Focus lands on the header in the DESTINATION column.
        self.call_after_refresh(self._refocus_group_header, moved_to, header.slug)

    async def _apply_group_move(self, header, members, axis: str, direction: int):
        """Commit a group block move; return the destination `col_id`, or None.

        SEAM — t1243_11 implements the model write and the DOM placement. Until
        then the move is reported rather than silently dropped, so the key is
        never a dead no-op.
        """
        self.notify(f"Moving the group '{group_display_title(header.slug)}' as a "
                    f"block lands in t1243_11.", severity="information")
        return None
```

`group_members` joins the `board_groups` import.

### 7b. The grouped-column fallback (decision 3)

```python
    def _column_has_group(self, col_id: str) -> bool:
        """True when the column renders at least one `GroupHeader`."""
        return any(slug and len(members) > 1 for slug, members
                   in build_column_units(self.manager.get_column_tasks(col_id)))

    def _move_needs_recompose(self, task, *col_ids) -> bool:
        """True when a single-task move touches grouping.

        The in-place DOM paths (`_swap_adjacent_cards`, `_transplant_block`)
        assume a card-only column: they append or swap card blocks, while a
        grouped column's DOM must follow INV-R's unit order — and a member moved
        laterally CARRIES its `boardgroup`, so it has to land inside a same-slug
        group in the destination, not at the end. Recomposing re-derives the
        column from `build_column_units`, which is correct by construction.
        t1243_11 restores the fast path for group blocks.
        """
        if task_group_slug(task):
            return True
        return any(self._column_has_group(c) for c in col_ids)
```

Wired at the three fast-path decision points:

- `_move_task_lateral` `:10106` — extend the existing escape hatch:
  `if "unordered" in (current_col_id, new_col) or self._move_needs_recompose(task, current_col_id, new_col):` → `_full_refresh()`.
- `_move_task_to_extreme` — before the `_transplant_block` call (`:10350`ff): if
  `self._move_needs_recompose(task, col_id)`, use
  `self.refresh_column(col_id, refocus_filename=filename, refocus_col_id=col_id)`
  instead.
- `_move_task_vertical` — before `_swap_adjacent_cards` (`:10298`): same test on
  `col_id`, same `refresh_column` substitute.

Plus the **anchor fix** from drift #5, kept as defence in depth even though a
grouped column now recomposes (`:10350`):

```python
                before = next((w for w in col_widget.children
                               if isinstance(w, (GroupHeader, TaskCard))
                               and not getattr(w, "is_child", False)), None)
```

`_card_block` needs **no change** — a `GroupHeader` is not a `.child-wrapper`
`Horizontal`, so it already terminates a block.

`space` (`toggle_mark`) stays inert on a header: its gate reads `_focused_card()`,
which is `None` there. Pinned by a test so t1243_12 changes it deliberately.

### 7c. The `action_move_to_column` gateway (the one defect from §3a)

`action_move_to_column`'s final `else` branch (`:8592`–`:8605`) exists for a
focused **column placeholder**: it reads `_get_focused_col_id()` and reviews
**every task in that column**. Today a focused header cannot reach it, because
`_get_focused_col_id()` returns `None`; after Step 3 it can.

`check_action` already hides `m` correctly (its chain falls through to
`_focused_placeholder() is not None`, which is `None` for a header) — but that is
**only the binding gate**. The action itself is reachable from the command
palette entry `("Move Tasks to Column", "action_move_to_column", …)` (`_COMMANDS`
`:6611`), and the function's own comment at `:8553` says so: *"the command
palette invokes `action_*` directly and never consults it."* So the guard must be
**inside the action**, not in `check_action`.

Make the branch's precondition explicit — it was always "a placeholder is
focused", stated as "no card is focused", and a header now falsifies that
identity:

```python
        else:
            # A column PLACEHOLDER is focused (collapsed, or every card hidden by
            # the filter) — scope the review to that column. A GroupHeader also
            # names a column now (t1243_9), but pointing at a group is not
            # pointing at the column: acting on every task in it would be a
            # destructive surprise. Refuse with the reason; a bulk group move is
            # t1243_11's block move and t1243_12's `G`.
            if isinstance(self._focused_unit(), GroupHeader):
                self.notify("Select tasks, or a column, to move — moving a whole "
                            "group lands in t1243_11.", severity="warning")
                return
            col_id = self._get_focused_col_id()
            ...                                    # unchanged from here down
```

The marked-set path above is unaffected and must stay so: `m` with marks acts on
the marks *regardless of focus* (`check_action` returns `True` early at `:7263`,
and `MoveGatingTests` pins it), so a header holding focus while tasks are marked
must still move the marked set. Verification case 21 asserts both halves.

## Step 8 — Refocus after every state change

| After | Lands on | Mechanism |
|---|---|---|
| a filter pass hides the focused header | the column's focus target | `apply_filter` rescue (Step 6) → unit-aware `_column_focus_target` |
| collapsing a group | the header | `_refocus_group_header` via `call_after_refresh` (Step 5) |
| a block move | the header in the destination | `_move_focused_group` (Step 7a) |
| a member move | that card | existing `_refocus_card`, unchanged |

### Post-phase (risk mitigations)

Runs **after** Step 8, before the change is offered for review.

1. `[assert_fast_path_both_ways]` Verification case 19 must assert **both**
   directions of `_move_needs_recompose` with a `_recompose_column` spy — grouped
   column → recompose, ungrouped column → transplant. A one-sided assertion would
   pass a predicate that always returns `True`, silently forfeiting t1243_5's
   measured 93.6 % lateral win. While here, pin the other cost-shaped assumptions
   that share this risk bullet: the **child index is built once per pass and zero
   times with no header in scope** (case 14c, with both its controls),
   `_UNIT_SELECTOR` yields DOM order (case 4), and a membership change always
   recomposes its column so `GroupHeader.members` cannot go stale.
2. `[record_sibling_boundary_shift]` Record the amended split in **two** places —
   this plan's *Notes for sibling tasks*, and the parent design plan
   `aiplans/p1243_board_task_groups_and_fast_reordering.md` §Workstream C, which
   t1243_10 and t1243_11 read at their own Step 0. State:
   - the header is already a filter unit and counts as column content, and its
     visibility rule is **already child-aware** (`_group_header_matches`) — so
     t1243_10 inherits persistence, the five lifecycle owners, the prune sweep
     and the match-count badge, and builds the badge on that same helper rather
     than writing a new predicate;
   - `self.collapsed_groups` on `KanbanApp` is the session-only owner, held by
     reference in every `KanbanColumn`; t1243_10 replaces only the load/save
     ends against `settings.collapsed_groups` in the **user** layer — it should
     not restructure the data flow;
   - `_apply_group_move` is the seam t1243_11 fills, and `_move_needs_recompose`
     is the fast path it restores;
   - `merge_columns` (t1377_4, landed after t1243 was designed) is a **sixth**
     `collapsed_groups` lifecycle owner absent from the design's five-row
     staleness table;
   - `action_move_to_column`'s Step 7c guard is the pattern for any future
     column-scoped action: the palette bypasses `check_action`, so the guard
     belongs in the action body.

   Log under the canonical *Upstream defects identified* bullet: the drift-table
   items, and the pre-existing **orphaned `↳` row** — `apply_filter` can leave a
   child card visible under a parent it hid, because a parent's `search_haystack`
   does not contain its children's text (`aitask_board.py:231` /
   `apply_filter:7873`). That predates groups and is out of scope here.

---

## Verification

`tests/test_board_group_focus.py` — new, real Pilot, modelled on
`tests/test_board_dom_transplant.py` (t1243_5) and
`tests/test_board_empty_column_focus.py` (t1209). It uses the **shared harness**
`tests/lib/board_fixture.py`, not `test_board_movement.py`'s subprocess rig.

```python
class _GroupFocusBase(bf.FixtureBoardTestBase, bf.PristineTreeMixin):
    FIXTURE_TASKS = GROUP_TOPOLOGY          # module-local, additive
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.TaskCard = cls.ab.TaskCard
        cls.GroupHeader = cls.ab.GroupHeader
        cls.EmptyColumnPlaceholder = cls.ab.EmptyColumnPlaceholder
        cls._snapshot_pristine()
```

Fixtures are built with `bf.FixtureTask(..., extra={"boardgroup": "perf_work"})`
— `extra` already merges into the frontmatter through the canonical
`serialize_frontmatter`. **`DEFAULT_TOPOLOGY` / `RICH_TOPOLOGY` are not widened**
(both are pinned by green files that byte-differ or count them); the module
declares its own additive topology, per the harness's stated rule.

Carry over the harness gotchas verbatim: `_settle()` must drain
`pilot.pause()` ×4 **plus** `wait_for_scheduled_animations()` (a recompose queues
`call_after_refresh`, a header repaint queues `call_next`, and focus scrolls);
capture results into a dict inside the coroutine and assert **outside** it.

Each class opens with a `test_fixture_facts` precondition case, and every
positive assertion is paired with a **discriminating negative control** — the
house style in every t1243 test module.

**Rendering**
1. A ≥2-member group renders a `GroupHeader` reading `▾ perf work (2)`
   (`header.render().plain`); collapsed reads `▸ perf work (2)`.
2. A **single-member** group renders a plain card and **no** header (negative
   control: the 2-member group in the same fixture does emit one).
3. Header and member cards are **flat siblings** of the column — asserted off
   `column.children`, and cross-checked against `manager.get_column_tasks`
   ordering as **independent ground truth** (the t1243_5 rule: comparing the DOM
   with itself passes a wrong-place mount).
4. `_UNIT_SELECTOR` yields units in **DOM order** — pins the Textual comma-selector
   assumption Step 3 relies on.

**Focus and navigation**
5. **A column of only collapsed groups** — `_column_focus_target` returns the
   header, `_refocus_column` lands on it, and `_get_focused_col_id` reports the
   column. Negative control: the same fixture on unmodified `_column_focus_target`
   returns `None` (asserted by calling `_visible_column_cards` and showing it is
   empty while `_visible_column_units` is not).
6. Exactly **one** focus anchor in that column — the `EmptyColumnPlaceholder`
   stays hidden (this is what decision 1 buys).
7. `↓` / `↑` enter and leave an expanded group correctly, and `↑` is the exact
   reverse of `↓`.
8. `←` / `→` preserve the positional index across columns with a header in the
   index.
9. `ctrl+left` / `ctrl+right` still resolve the focused column from a header
   (`_shift_column` reorders and focus survives) — the t1209 regression this
   generalises.

**Collapse**
10. `x` on a header collapses: members **and their `.child-wrapper` rows**
    unmount, and focus lands on the header (never on an unmounted widget).
11. `x` on a member card still toggles children; the footer advertises
    "Toggle Group" on a header and "Toggle Children" on a card
    (`app.screen.active_bindings` — the duplicate-key pair must never show both).

**Filtering**
12. A search matching one member keeps the header visible; a search matching no
    member **and no member's child** hides it, and the column's
    `EmptyColumnPlaceholder` then reappears.
13. Focus resting on a header the pass just hid is rescued.
14. The scoped variant `apply_filter({col})` reaches headers in that column and
    leaves an untouched column's header alone.
14b. **Child-only match keeps the header visible.** With a grouped, expanded
    parent, search for text that appears only in a **child's** filename: the
    child card stays visible, and the header **must** too — no header hidden
    above a visible `↳` row. Negative control that proves the case
    discriminates: assert the parent card *is* hidden by that same search (i.e.
    the parent's `search_haystack` genuinely does not contain the child's text),
    so a member-only rule would have failed here.
14c. **The child index is built once per pass, not per member.** Spy
    `_children_by_parent` (`mock.patch.object` + `addCleanup` — the
    `_spy_recompose` idiom in `tests/test_board_dom_transplant.py`). Over a
    fixture with a **multi-member group whose members all fail the search** —
    the worst case, where every member reaches the child lookup — one
    `apply_filter()` must call it **exactly once**. Two controls so the count is
    evidence and not an artefact: (a) a board with **no** group header in scope
    calls it **zero** times, proving the `if headers` guard holds and today's
    baseline is untouched; (b) a second `apply_filter()` call raises the count to
    exactly two, proving the spy is live and a "1" was not a dead spy. Case 14b
    must stay green under the indexed implementation — the optimisation may not
    change the answer, only the cost.

**Movement**
15. From a header: `_apply_group_move` is called with the right
    `(column_id, slug, member filenames, axis, direction)` — spy-patched to
    return a destination — and focus lands on the header there. Negative control:
    the spy is cleared and a *card* is moved, proving the empty record is
    evidence of absence.
16. From a member card: only that card moves (exact changed-path set via
    `bf.snapshot` / `bf.diff_snapshots`).
17. From a child card: refused, as today.
18. `space` on a header is inert (no mark recorded) — pins the t1243_12 boundary.
19. A move in a **grouped** column takes the recompose path and a move in an
    ungrouped column still takes the transplant fast path — spied on
    `_recompose_column`, both directions asserted.

**Action gateways (the widened `_get_focused_col_id`)**
20. With a header focused, `_shift_column` still resolves the column
    (`ctrl+left` reorders and focus survives) and `action_toggle_column_collapsed`
    still collapses it — the desirable half of §3a's audit.
21. **`action_move_to_column` is guarded.** Called **directly** (the palette
    path, bypassing `check_action`) with a header focused and **no marks**: no
    `ColumnSelectScreen` and no review screen is pushed, and a warning is
    notified. Two controls that make this discriminate: (a) with a *placeholder*
    focused the column-scoped review **is** pushed, proving the guard is not
    simply disabling the branch; (b) with a header focused **and tasks marked**,
    the marked set is still reviewed and moved, proving the guard did not break
    `m`'s marks-win-over-focus contract (`MoveGatingTests`).
22. `check_action("move_to_column")` returns `False` with a header focused and no
    marks — the footer must not advertise `m`.

**Integration — a grouped parent with visible children** (its own case, not
inferred from the separate ones): pins the
header → member → its children → next member → next unit sequence, lateral
positional preservation across it, collapse refocus, and child adjacency after a
block move.

**Run:**

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line only
python3 -m pytest tests/test_board_group_focus.py -v
```

The new module does **not** join `SERIAL_CARVE_OUT` — that is only for modules
touching the real repo/git index or a real tmux pane. Re-run the neighbours the
change can reach: `test_board_empty_column_focus.py`,
`test_board_dom_transplant.py`, `test_board_render_scoping.py`,
`test_board_toggle_children_gate.py`, `test_board_marking.py`,
`test_board_movement.py` (its `FLIP_TABLE` must pass **unedited** — this child
changes no index arithmetic).

---

## Risk

### Code-health risk: medium
- Six load-bearing focus/nav seams (`_column_focus_target`, `_get_focused_col_id`,
  `action_nav_up`/`_down`, `_nav_lateral`, plus all three `_move_task_*`) change
  in one commit, and every board interaction routes through them · severity: medium · → mitigation: inline pre-phase `pin_current_focus_behaviour`
- The recompose fallback (decision 3) intentionally forfeits t1243_5's measured
  93.6 % lateral win **on grouped columns**, and the `_move_needs_recompose`
  predicate is the only thing keeping ungrouped columns on the fast path — if it
  ever over-matches, the win is lost silently · severity: medium · → mitigation: inline post-phase `assert_fast_path_both_ways`
- **`apply_filter` is a per-keystroke hot path and this change adds work to it.**
  The child-aware header rule is indexed (`_children_by_parent`, once per pass,
  only when a header is in scope) precisely so it does not become
  `O(members × children)` regex-and-sort calls — but the guard that keeps it
  once-per-pass is a single `if headers` and an easy thing to lose · severity: medium · → mitigation: inline post-phase `assert_fast_path_both_ways`
- **Widening `_get_focused_col_id` changes behaviour at all twelve of its call
  sites at once.** Ten are desirable and one (`action_move_to_column`) is a
  defect fixed in Step 7c — but `check_action` is only the binding gate, and the
  command palette calls `action_*` directly, so any future column-scoped action
  inherits the same trap · severity: medium · → mitigation: inline pre-phase `pin_current_focus_behaviour`
- `GroupHeader.members` caches `Task` objects at compose time; a membership change
  that does not recompose the column would leave the filter pass reading a stale
  member list · severity: low · → mitigation: inline post-phase `assert_fast_path_both_ways`
- `_UNIT_SELECTOR`'s DOM-order guarantee is an assumption about Textual 8.2.7, not
  about this file · severity: low · → mitigation: inline post-phase `assert_fast_path_both_ways`

### Goal-achievement risk: medium
- Two of the three scope boundaries were open in the decomposition and are
  resolved here by decision, not by the design document — t1243_10 and t1243_11
  inherit the amended split and could double-implement or leave a gap · severity: medium · → mitigation: inline post-phase `record_sibling_boundary_shift`
- The headline AC ("movement from a header moves the block") is **not** literally
  deliverable in this child; it is amended to a dispatch contract · severity: medium · → mitigation: inline pre-phase `amend_the_ac_first`
- t1377_4 landed `merge_columns`, a **sixth** column-lifecycle transition absent
  from the design's five-row `collapsed_groups` staleness table · severity: low · → mitigation: inline post-phase `record_sibling_boundary_shift`

### Planned mitigations

All four confirmed **inline** — each is a bounded, independently-verifiable
addition (a doc edit, a test-ordering discipline, a test assertion, a notes
entry), so both decision metrics are `low` and none warrants a task lifecycle.

- timing: pre-phase | name: amend_the_ac_first | type: chore | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the headline AC is not literally deliverable in this child | desc: amend the task file's Verification bullet to a dispatch contract and record scope decisions 1 and 3, before any code
- timing: pre-phase | name: pin_current_focus_behaviour | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — six load-bearing focus/nav seams change in one commit, and widening `_get_focused_col_id` changes behaviour at twelve call sites | desc: run the six existing focus/DOM/gateway characterization modules green before touching a seam and after each of Steps 3, 4 and 7
- timing: post-phase | name: assert_fast_path_both_ways | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the recompose fallback could silently forfeit t1243_5's lateral win; the per-keystroke filter pass could regress to O(members x children); plus the DOM-order and stale-members assumptions | desc: spy `_recompose_column` in both directions of `_move_needs_recompose`, spy `_children_by_parent` for once-per-pass and zero-without-headers, and pin the `_UNIT_SELECTOR` DOM-order and members-freshness assumptions
- timing: post-phase | name: record_sibling_boundary_shift | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — t1243_10/11 inherit an amended split resolved by decision, not by the design document | desc: record the amended split in both the Final Implementation Notes and the parent design plan's Workstream C, including `merge_columns` as a sixth collapse-key lifecycle owner

**Reassessment after inlining** (`risk-evaluation.md` Steps 1–2, re-run once
against the augmented plan): both levels stay **medium**. The mitigations tighten
verification and provenance but do not shrink the blast radius — six focus/nav
seams still change together, and the AC amendment is still a deviation from the
recorded decomposition, only now an explicit and reviewed one.

---

## Post-Review Changes

### Change Request 1 (2026-08-10)

- **Requested by user:** `_move_needs_recompose` regressed the card-only movement
  hot path the plan explicitly promised to preserve. Its `_column_has_group(col_id)`
  ran `build_column_units(get_column_tasks(col_id))` — filtering every task on the
  board and sorting **twice** (`get_column_tasks` sorts, then the derivation sorts
  again) — for up to two columns on every lateral move, *even when no task carries
  `boardgroup`*. Determine group presence without deriving or sorting, and add a
  performance-shaped assertion for the ungrouped path. Confirmed and blocking.

- **Changes made:**
  - `_column_has_group(col_id)` → **`_column_widget_has_group(col_widget)`**: a
    scan of the column widget's direct children for a `GroupHeader`. No model
    lookup, no derivation, no sort. Headers are flat siblings of the cards, so
    the scan is exact rather than an approximation. Deliberately not
    `query(GroupHeader)` either — Textual 8.2.7 walks the whole tree wherever a
    query is rooted, and every movement path already holds the widget (the
    reasoning `_find_parent_card` documents).
  - `_move_needs_recompose(task, *col_widgets)` now takes column **widgets**;
    every caller already holds them, so taking ids would force the lookup this
    must not pay for.
  - In `_move_task_lateral` the check **moved** to after `src_col` / `dst_col`
    are resolved (it previously sat beside the `unordered` early return, before
    any widget existed).
  - New case `test_ungrouped_move_derives_no_units`: an ungrouped vertical move
    and an ungrouped lateral move each derive **zero** units, with a grouped move
    as the live-spy control. Asserted as a call count, not a duration — a
    wall-clock threshold on a shared box is a flake, while "zero derivations" is
    exact and is the property that actually bounds the cost. A precondition
    assertion pins that the lateral move really happened, so the zero cannot be
    vacuous.
  - Fixture note: the ungrouped lateral must go **left** (c3 → c2, whose
    single-member group draws no header). c3's right neighbour c4 holds a group,
    so that move correctly falls back and would derive — the first draft of the
    case failed for exactly that reason.
  - New negative control "presence check goes back to deriving units" —
    **CAUGHT**, so the new assertion discriminates.

- **Files affected:** `.aitask-scripts/board/aitask_board.py`,
  `tests/test_board_group_focus.py`.

## Final Implementation Notes

- **Actual work done:** `.aitask-scripts/board/aitask_board.py` (+474/−32) and a
  new `tests/test_board_group_focus.py` (30 cases, real Pilot on
  `tests/lib/board_fixture.py`). `GroupHeader` (focusable `Static`, carries
  `column_id` and its members as **data**) + `.group-header` CSS;
  `KanbanApp.collapsed_groups` held by reference in every `KanbanColumn`;
  `KanbanColumn.compose` emits units via `build_column_units` (single-member
  group → plain card, collapsed group → header alone); the focus-unit
  abstraction (`_UNIT_SELECTOR`, `_focused_unit`, `_get_column_units` /
  `_visible_column_units`, unit-aware `_column_focus_target` and
  `_get_focused_col_id`); `↑↓←→` over units; the `x` duplicate-key pair
  (`toggle_children` / `toggle_group`) with `action_toggle_group` and
  `_refocus_group_header`; child-aware indexed header filtering
  (`_filter_group_headers`, `_children_by_parent`, `_group_header_matches`) plus
  `GroupHeader` in the focus-rescue tuple; and the movement dispatch
  (`_dispatch_group_move` → `_move_focused_group` → the `_apply_group_move`
  seam), the `_move_needs_recompose` fallback, the move-to-top anchor fix and the
  `action_move_to_column` gateway guard.

- **Deviations from plan:**
  1. **Movement dispatch moved from the three `_move_task_*` helpers into the six
     actions.** With a header focused `_focused_card()` is already `None`, so the
     helpers early-return harmlessly and need no group branch at all. This also
     keeps `_move_task_vertical` **synchronous**, which `test_board_movement`'s
     probe depends on (it reads `iscoroutinefunction` off each helper to decide
     where to stamp `sync_end`). Strictly smaller blast radius than the plan's
     shape. `action_move_task_up` / `_down` became `async`; the other four
     already were.
  2. **`_column_has_group(col_id)` → `_column_widget_has_group(col_widget)`**
     after review (see Post-Review Changes). The planned model-derived predicate
     regressed the very hot path the fallback exists to protect.
  3. **A planned `check_action` guard turned out to be dead code.** The
     `toggle_children` branch does not need an explicit `GroupHeader` check —
     `_focused_card()` is a `TaskCard` isinstance read, so a header already
     yields `None` at the existing `if not focused`. A negative control proved
     the check never changed the answer; it was removed and the reason recorded
     inline so it is not re-added.
  4. `action_toggle_group` gained an `isinstance` re-resolve **in addition to**
     its `check_action` re-assert. Verified mutually redundant (removing either
     alone leaves the tests green) and kept deliberately: the failure it prevents
     is an `AttributeError` into Textual's message pump, which kills the app.

- **Issues encountered:**
  - The plan's `_focused_unit()` as `query("TaskCard:focus, GroupHeader:focus")`
    would have undone t1243_7's measured fix (27 whole-board walks per footer
    sweep, 59 ms). Implemented as a `screen.focused` isinstance read instead.
  - Two test cases were written asserting things that cannot hold yet, and were
    corrected rather than the code: (a) "focus lands on the destination header"
    is unreachable while `_apply_group_move` is a stub that moves nothing — it is
    now a spy on the refocus *request*, which keeps passing once t1243_11 fills
    the seam; (b) `ctrl+left` on `c0` is a no-op because `c0` is leftmost, so the
    case moved to `c1`.
  - Two fixtures were not discriminating until reshaped: the collapse-refocus
    case needed a column whose group is **not** first (otherwise
    `_column_focus_target` lands on the header for free), and the ungrouped
    lateral had to go **left** (c3's right neighbour holds a group).
  - `MarkedSelection` has `toggle()`, not `add()`.

- **Key decisions:**
  - **Header filtering could not be deferred to t1243_10.** A collapsed group
    mounts no cards, so the column contributed nothing to `cols_with_visible`,
    the `EmptyColumnPlaceholder` turned visible, and `_column_focus_target`
    returned the placeholder instead of the header — two focus anchors, breaking
    the invariant this child restates.
  - **The header rule is child-aware from the start.** A parent's
    `search_haystack` is `"<filename> <metadata>"` and does not contain its
    children's text, so a member-only rule hid the header above a still-visible
    `↳` row.
  - **The child index is built once per pass and only when a header is in
    scope**, so ungrouped boards pay nothing.
  - **Grouped columns fall back to recompose**; t1243_11 restores the fast path.
  - Ten of eleven negative controls discriminate; the eleventh is the documented
    mutual redundancy above.

- **Mitigation `assert_fast_path_both_ways` — what it actually covers.** Stated
  precisely rather than by summary: both directions of `_move_needs_recompose`
  (case 19), the child index built once per pass and **zero** times with no
  header in scope (case 14c), zero unit derivations on an ungrouped move (the
  post-review case), and `_UNIT_SELECTOR`'s DOM order (case 4). The fifth item
  the mitigation named — "`GroupHeader.members` cannot go stale" — has **no
  dedicated test**, deliberately: membership can only change through a
  `boardgroup` write, the board has no such write path until t1243_11/t1243_12,
  and an external `aitask_update.sh --boardgroup` edit is only observed via
  `refresh_board`, which reconstructs every column and header. There is no
  reachable staleness path to assert against today. **t1243_11 must add one**
  the moment it lands a membership write.

- **Upstream defects identified:**
  - `.aitask-scripts/board/aitask_board.py:231,7873 — apply_filter can leave an expanded child card visible under a parent it hid, because Task.search_haystack is "<filename> <metadata>" and a parent's corpus never contains its children's text; the result is an orphaned "↳" row with no parent above it. Predates groups and is independent of them — fixing it would change apply_filter semantics for every ungrouped board.`

- **Notes for sibling tasks:**
  - **t1243_10 inherits a working filter half.** `GroupHeader` is already a
    filter unit, already counts toward `cols_with_visible`, and is already in the
    focus-rescue tuple; `_group_header_matches` is already child-aware. Build the
    `· N match` badge **on that helper** rather than writing a second predicate —
    `task_matches_filter` is per-task and countable for exactly this reason. Keep
    `_children_by_parent` built once per pass and behind the `if headers` guard.
    What remains yours: collapse **persistence** (`settings.collapsed_groups`, the
    user layer), the lifecycle owners, the prune-on-load sweep and the full
    matrix.
  - **Collapse state already has an owner.** `KanbanApp.collapsed_groups`
    (`"<col_id>/<slug>"`) is held **by reference** in every `KanbanColumn`, which
    is what lets `_recompose_column` observe a toggle with no propagation step.
    Replace only the load/save ends; do not restructure the data flow.
  - **`merge_columns` (t1377_4) is a SIXTH `collapsed_groups` lifecycle owner**,
    landed after t1243 was designed and absent from the parent plan's five-row
    staleness table. Merging column A into B must re-point the col half of every
    `"A/<slug>"` key, combining per the coalesce rule.
  - **t1243_11 fills `_apply_group_move(header, members, axis, direction)`** —
    return the destination `col_id` to trigger the header refocus there, `None`
    to decline. Dispatch lives in the six actions, not the three helpers; keep
    `_move_task_vertical` synchronous. Removing the `_move_needs_recompose`
    fallback requires **both** directions tested — grouped → recompose, ungrouped
    → transplant *and* zero unit derivations — or t1243_5's lateral win is
    silently lost. Keep any presence check off the model: deriving units there
    was the review-blocking regression.
  - **Anyone adding a column-scoped action:** `_get_focused_col_id` now resolves
    from a `GroupHeader` too. The command palette calls `action_*` directly and
    never consults `check_action`, so a "no card is focused ⇒ a placeholder is
    focused" assumption must be guarded **in the action body** —
    `action_move_to_column` is the worked example.

## Step 9 (Post-Implementation)

Merge, archival and cleanup follow `task-workflow` Step 9. Output branch is
`main` (current-branch mode).
