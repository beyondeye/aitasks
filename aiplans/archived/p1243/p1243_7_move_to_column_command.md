---
Task: t1243_7_move_to_column_command.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_10_group_collapse_and_filtering.md, aitasks/t1243/t1243_11_group_formation_and_block_moves.md, aitasks/t1243/t1243_12_group_membership_commands.md, aitasks/t1243/t1243_13_documentation.md, aitasks/t1243/t1243_14_retrospective_benchmark.md, aitasks/t1243/t1243_15_manual_verification_board_groups_and_reordering.md, aitasks/t1243/t1243_8_boardgroup_field_and_model.md, aitasks/t1243/t1243_9_group_focus_and_rendering.md
Archived Sibling Plans: aiplans/archived/p1243/p1243_1_movement_baseline_and_harness.md, aiplans/archived/p1243/p1243_2_board_field_persistence_seam.md, aiplans/archived/p1243/p1243_3_gap_indexing.md, aiplans/archived/p1243/p1243_4_render_filter_scoping.md, aiplans/archived/p1243/p1243_5_lateral_dom_transplant.md, aiplans/archived/p1243/p1243_6_multiselect_marking.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-04 12:52
---

# t1243_7 — Move-to-column command (`m`)

> Child 7 of 14 in the t1243 decomposition (Workstream D). The task file
> `aitasks/t1243/t1243_7_move_to_column_command.md` is the spec; this file is the
> execution order. Read `aiplans/p1243_board_task_groups_and_fast_reordering.md`
> §"Workstream D" for the design decisions and rejected alternatives.

## Context

Moving several tasks to another column today means repeating `shift+left` /
`shift+right` **per task per hop** — the board has no bulk move at all. t1243_3
landed the batch persistence API (`move_tasks_to_column`, K writes,
all-or-nothing) and t1243_6 landed the selection primitive (`space` marking,
`app.marked`). Both were built *for this child* and are currently unused by
production code. This task is the command that consumes them: `m` picks a
destination column and moves the marked set there in exactly K writes, input
order preserved.

It also carries a second, independent obligation the parent plan assigned here:
`KanbanCommandProvider` repeats its command list **verbatim** in `discover()` and
`search()`, so a command added to one and not the other silently disappears from
either discovery or search. That must be collapsed **before** this task adds two
commands to it — otherwise this task ships the first drift. `t1377_5` is written
to consume the de-dup rather than repeat it.

---

## Step 0 — anchor re-verification · **DONE 2026-08-04**

`aitask_board.py` is now **9986 lines** (9775 at t1243_6, 9043 at decomposition).
Every symbol the task file names was re-located. Two of its premises are stale
and are corrected below.

### Confirmed

| Claim | Anchor |
|---|---|
| `m` is free | zero `Binding("m"` hits in the file; free in `KanbanApp.BINDINGS` (`:6028-6103`) |
| `KanbanCommandProvider` duplicates verbatim | `discover()` `:5699-5735` and `search()` `:5737-5757` — the same 7 commands, twice |
| `WorkReportTaskSelectScreen` shape | `:4455` — `SelectionList` in `#dep_picker_dialog`, `space` toggles, `Enter` confirms via `on_key`, `_selected()` returns **displayed order**, Esc/Cancel dismiss `None` |
| `action_work_report` two-stage chain | `:7866` — nested `push_screen(screen, callback)`, with the `None` (Esc) vs `[]` (nothing selected) distinction spelled out |
| `ColumnSelectScreen` / `ColumnSelectItem` | `:5671` / `:5651` — takes `columns: list[dict]` of **col-conf dicts** (`id`/`title`/`color`), dismisses `col_id` or `None` |
| synthetic `unordered` is hand-injected | `action_collapse_column` `:9258-9261` — not in `manager.columns` |
| `move_tasks_to_column` | `:1574` — batch, all-or-nothing, input order, `MoveResult(moved, refused, compacted)`; `_resolve_parents` `:1551` refuses with `(name, "not_a_parent_task")` |
| `MarkedSelection` / `app.marked` | `:1967` / `:6117`; `effective()` `:2021` returns a **filename-sorted** list and documents that callers must re-sort by board geometry |
| `check_action` movement + `toggle_mark` gates | `:6298-6326` |
| `_get_focused_col_id` covers card **and** placeholder | `:7544` |
| `tests/test_board_move_command.py` is free | 30 `test_board_*.py` files, none named that |

### Corrected — two stale premises

1. **The task file's §2 subdialog rule contradicts t1243_6's landed notes, and
   t1243_6 wins** (user-confirmed 2026-08-04). §2 says a focused *card* acts on
   `effective()` directly and only a focused *column* opens the task-select
   subdialog. But t1243_6 shipped marks that deliberately **survive a filter
   pass**, and its "Notes for sibling tasks" assign the consequence here: *"a
   marked card that `apply_filter` has hidden is an invisible participant in a
   later bulk action — do not let the `m` command act on `effective()` without
   showing it."* The rule implemented is therefore:

   | marks | focus | chain |
   |---|---|---|
   | none | card | `ColumnSelectScreen` only — 1 target, focused, visible by construction |
   | any | card | **task-select → column-select** |
   | none | column placeholder | **task-select (scoped to the column) → column-select** |
   | any | column placeholder | **task-select (the marked set) → column-select** |

2. **`move_task_col` does not exist** (the task file's §3 names it).
   t1243_3 replaced it with `move_tasks_to_column` / `move_task_to_column`
   (`:1570-1600`). The task file's §3 conclusion still holds — the API resolves
   parents only and **fails closed** on a child id with a which-items report.

### The destination set — three filters, each matching an existing contract

"Every configured column" is the wrong destination list. `_move_task_lateral`
(`:8846-8859`) is the contract to match, and it applies **two** filters, not one:

1. **`unordered` only while it holds tasks** (`:8846`). Odd for a *destination*
   (an emptied Unsorted column becomes un-targetable), but the column exists
   only while some task has no `boardcol`, and `refresh_columns` (`:6822`)
   treats it appearing/disappearing as a *structural* change. Diverging would
   make `m` the one action that can resurrect it. Keep parity.
2. **Collapsed columns are skipped** (`:8852-8857` — `shift+right` steps *over*
   a collapsed column and never lands in one). The first draft of this plan
   claimed parity while offering every configured column, which would let `m`
   file tasks into a destination `shift+left/right` refuses to enter — and the
   cards would vanish on arrival, leaving `refresh_columns` a `refocus_filename`
   that is not rendered. `action_collapse_column` / `action_expand_column`
   (`:9256`, `:9282`) already establish that board pickers filter on collapse
   state. Filter them.
3. **A column that *every* target already sits in is excluded.** Picking it
   would still write all K files and append them to that column's bottom — a
   "send to bottom" reorder under a command that says "move to a column". A
   column only *some* targets sit in **stays**: moving a mixed set into one of
   them is a genuine consolidation, not a no-op.

Filter 3 makes the destination list depend on the **confirmed** target set, so
it is computed after the review, not before it.

---

## Step 1 — de-duplicate `KanbanCommandProvider` (NON-OPTIONAL, first)

Collapse `discover()` and `search()` onto one `_COMMANDS` tuple, storing the
**action attribute name** (resolved per-call against `self.app`) rather than a
bound method, so the tuple can be a class constant.

```python
class KanbanCommandProvider(Provider):
    """Provide board commands to the Textual command palette."""

    #: Single source for the palette: (display, action attribute, help).
    #: `discover()` and `search()` used to repeat this list verbatim, so a
    #: command added to one and not the other went missing from either
    #: discovery or search with nothing failing (t1243_7). t1377_5 adds its
    #: column-management entries HERE rather than re-splitting the list.
    _COMMANDS = (
        ("Add Column", "action_add_column", "Add a new column to the board"),
        ("Edit Column", "action_edit_column", "Edit a column's title and color"),
        ("Delete Column", "action_delete_column", "Delete a column (tasks move to Unsorted)"),
        ("Collapse Column", "action_collapse_column", "Collapse a column to minimize its width"),
        ("Expand Column", "action_expand_column", "Expand a collapsed column to full width"),
        ("Move Tasks to Column", "action_move_to_column",
         "Move the marked task(s) — or the focused card — to a column"),
        ("Clear Selection", "action_clear_marks", "Unmark every marked task"),
        ("Settings", "action_open_settings", "Configure board settings (auto-refresh interval)"),
        ("Sync with Remote", "action_sync_remote", "Push local changes and pull remote changes"),
    )

    def _resolved(self):
        """(display, bound callback, help) for every command — the ONE place
        `_COMMANDS` is turned into callables. Both surfaces go through it."""
        app = self.app
        return [(display, getattr(app, attr), help_text)
                for display, attr, help_text in self._COMMANDS]

    async def discover(self) -> Hits:
        for display, command, help_text in self._resolved():
            yield DiscoveryHit(display=display, command=command, help=help_text)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for display, command, help_text in self._resolved():
            score = matcher.match(display)
            if score > 0:
                yield Hit(score=score, match_display=matcher.highlight(display),
                          command=command, help=help_text)
```

## Step 2 — the task-select modal, extracted onto a shared base

`WorkReportTaskSelectScreen` is exactly the widget this task needs, with a
different row shape. Copying it would make three near-identical
`SelectionList`-in-`#dep_picker_dialog` screens in one file — the same
"refactor duplicates before adding to them" rule Step 1 obeys. Extract the
shape; keep both concrete screens thin.

```python
class TaskSelectScreenBase(ModalScreen):
    """Review a list of tasks in a SelectionList; confirm in DISPLAYED order.

    `space` toggles (SelectionList owns and consumes it), `Enter` confirms via
    `on_key`, Esc / Cancel dismiss `None`. The `None` (cancelled cleanly) vs
    `[]` (confirmed with nothing checked) distinction is load-bearing for every
    caller — they mean different things and neither writes.

    Subclasses supply `TITLE_TEXT` / `LIST_ID` and the three row adapters.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    TITLE_TEXT = ""
    LIST_ID = ""

    def __init__(self, rows: list):
        super().__init__()
        self.rows = list(rows)

    # --- row adapters -------------------------------------------------
    def _row_key(self, row):       # the SelectionList `value`
        raise NotImplementedError
    def _row_label(self, row):     # what the user reads
        raise NotImplementedError
    def _row_value(self, row):     # what `dismiss` hands back
        raise NotImplementedError

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"{self.TITLE_TEXT} — [dim]space to toggle, Enter to confirm, "
                f"Esc to cancel[/]",
                id="dep_picker_title",
            )
            yield SelectionList[str](
                *(Selection(self._row_label(r), value=self._row_key(r),
                            initial_state=True)
                  for r in self.rows),
                id=self.LIST_ID,
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Confirm", variant="primary", id="btn_task_select_save")
                yield Button("Cancel", variant="default", id="btn_task_select_cancel")

    def on_mount(self):
        self.query_one(f"#{self.LIST_ID}", SelectionList).focus()

    def _selected(self) -> list:
        checked = set(self.query_one(f"#{self.LIST_ID}", SelectionList).selected)
        return [self._row_value(r) for r in self.rows if self._row_key(r) in checked]

    @on(Button.Pressed, "#btn_task_select_save")
    def _btn_save(self):
        self.dismiss(self._selected())

    @on(Button.Pressed, "#btn_task_select_cancel")
    def _btn_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)

    def on_key(self, event):
        # SelectionList uses space for toggle and consumes it. Enter is free,
        # so treat it as "confirm selection".
        if event.key == "enter":
            self.dismiss(self._selected())
            event.stop()
```

`WorkReportTaskSelectScreen` becomes a thin subclass. **`tasks` is kept as a
property alias** — `test_board_work_report.py:116` asserts `screen.tasks`, and
that green test must keep passing unchanged (it is the only external reference;
the button ids it never touches are free to be renamed):

```python
class WorkReportTaskSelectScreen(TaskSelectScreenBase):
    """Review/exclude the tasks feeding a work report.

    Rows are ordered `(col_id, task_id, label)` triples grouped by column in
    board order; the displayed sequence IS the reviewed order the launch must
    preserve.
    """
    TITLE_TEXT = "Work report tasks"
    LIST_ID = "work_report_task_list"

    @property
    def tasks(self):
        """Historic alias for `rows` (test_board_work_report.py reads it)."""
        return self.rows

    def _row_key(self, row):    return row[1]              # task_id
    def _row_label(self, row):  return row[2]
    def _row_value(self, row):  return (row[0], row[1])    # (col_id, task_id)


class MoveTaskSelectScreen(TaskSelectScreenBase):
    """Review which tasks a bulk column move will act on (t1243_7).

    Rows are `(filename, label)` pairs in board order; confirm dismisses the
    still-checked FILENAMES in that same order, which is what
    `move_tasks_to_column` consumes (it preserves input order).
    """
    TITLE_TEXT = "Move tasks to column"
    LIST_ID = "move_task_list"

    def _row_key(self, row):    return row[0]              # filename
    def _row_label(self, row):  return row[1]
    def _row_value(self, row):  return row[0]
```

No new CSS: `#dep_picker_dialog`, `#dep_picker_title` and `#detail_buttons` all
already exist, and `ColumnSelectScreen` already styles itself.

## Step 3 — destination columns and board order

Two small `KanbanApp` helpers beside `_work_report_columns` (`:7849`).

```python
def _move_destination_columns(self, filenames=()) -> list:
    """Col-conf dicts offered as a move destination for `filenames`, board order.

    `ColumnSelectScreen` renders `id`/`title`/`color` dicts, so this returns
    confs (not the `(id, title)` pairs `_work_report_columns` builds for the
    SelectionList). Three filters, each matching an existing board contract —
    see Step 0:

    * `unordered` is hand-injected (it is not in `manager.columns`) and only
      while it holds tasks, as `_move_task_lateral` and `action_collapse_column`
      both do.
    * **Collapsed columns are excluded**, matching `_move_task_lateral`, which
      steps OVER a collapsed column and never lands in one. A collapsed
      destination would also swallow the cards on arrival, leaving
      `refresh_columns` a refocus target that is not rendered.
    * A column **every** target already sits in is excluded — picking it would
      be a pure "send to bottom" reorder, not a move. A column only SOME
      targets sit in stays: that is a real consolidation.
    """
    current = {self.manager.task_datas[n].board_col
               for n in filenames if n in self.manager.task_datas}
    redundant = current if len(current) == 1 else set()

    cols = []
    if (self.manager.get_column_tasks("unordered")
            and not self.manager.is_column_collapsed("unordered")):
        cols.append({"id": "unordered", "title": "Unsorted / Inbox", "color": "gray"})
    for col_id in self.manager.column_order:
        conf = self.manager.get_column_conf(col_id)   # None = stale order entry
        if conf and not self.manager.is_column_collapsed(col_id):
            cols.append(conf)
    return [c for c in cols if c["id"] not in redundant]

def _column_title(self, col_id: str) -> str:
    """Display title for a column, including the synthetic `unordered`."""
    if col_id == "unordered":
        return "Unsorted / Inbox"
    conf = self.manager.get_column_conf(col_id)
    return conf["title"] if conf else col_id

def _board_order(self, filenames) -> list:
    """Sort filenames into rendered board order: column, then board index.

    `MarkedSelection.effective()` returns a FILENAME-sorted list precisely
    because it knows nothing about board geometry (t1243_6) — this is the
    re-sort its docstring instructs callers to do. Ordering is part of the
    contract: the destination sequence must match the presented sequence, and
    `move_tasks_to_column` preserves input order.

    The within-column key is `(normalize_board_idx, filename)` — the SAME key
    `get_column_tasks` sorts by, so a reviewed sequence cannot disagree with
    the rendered one.

    Ranks EVERY column, deliberately not `_move_destination_columns()`: a
    target can sit in a collapsed column, or in the one column that list
    filters out as redundant, and it must still sort where it renders.
    """
    rank = {"unordered": 0}
    rank.update({col_id: i + 1
                 for i, col_id in enumerate(self.manager.column_order)})
    last = len(rank)

    def key(name):
        task = self.manager.task_datas.get(name)
        if task is None:
            return (last, 0, name)   # unresolvable sorts last; `_reject_stale`
                                     # stops the flow before it can be moved
        return (rank.get(task.board_col, last),
                normalize_board_idx(task.board_idx), name)

    return sorted(filenames, key=key)
```

## Step 4 — `m`, the chain, and the apply

```python
def action_move_to_column(self) -> None:
    """`m`: move the marked task(s) — or the focused card — to a column."""
    if self._modal_is_active():
        return
    # Re-check the view gate INSIDE the action, not only in check_action: the
    # command palette invokes action_* directly and never consults it.
    if self.base_filter in ("inflight", "bytopic", "bytrail"):
        return

    def to_destination(filenames):
        # Built AFTER the review: the redundant-column filter depends on the
        # confirmed target set, not on the pre-review one.
        dests = self._move_destination_columns(filenames)
        if not dests:
            self.notify("Nowhere to move to — every other column is collapsed, "
                        "and the selection already sits where it is.",
                        severity="warning")
            return
        self.push_screen(
            ColumnSelectScreen(self.manager, "Move to", columns=dests),
            lambda col_id: self._apply_move_to_column(filenames, col_id),
        )

    focused = self._focused_card()
    if focused is not None and focused.is_child and not self.marked:
        # Refuse with a reason — never a silent nothing (the t1243_6 idiom).
        self.notify("Child tasks move with their parent — move the parent instead.",
                    severity="warning")
        return
    focused_name = (focused.task_data.filename
                    if focused is not None and not focused.is_child else None)
    targets = self.marked.effective(focused_name)

    if self.marked:
        # Marks survive a filter pass (t1243_6), so a marked card may be
        # hidden right now. REVIEW before acting — never move what the user
        # cannot see. This is the hidden-but-marked risk t1243_6 assigned here.
        self._review_then(self._board_order(targets), to_destination)
    elif targets:
        # One focused card: unambiguous and visible by construction. No review.
        if self._reject_stale(targets):
            return
        to_destination(targets)
    else:
        # A column placeholder is focused (collapsed, or every card hidden by
        # the filter). Scope the review to that column, read straight from
        # task_datas so filtered-away tasks are exactly what becomes visible.
        col_id = self._get_focused_col_id()
        if col_id is None:
            return
        names = [t.filename for t in self.manager.get_column_tasks(col_id)]
        if not names:
            self.notify(f"No tasks in {self._column_title(col_id)}",
                        severity="warning")
            return
        self._review_then(names, to_destination)

def _reject_stale(self, filenames) -> bool:
    """True (and notifies) when a name no longer resolves to a parent task.

    **Fail closed — never drop the dead names and proceed.** Silently omitting
    them would move the surviving subset of what the user selected: exactly the
    partial application `move_tasks_to_column`'s all-or-nothing contract exists
    to prevent, and the review dialog would not even show what went missing.

    Marks are deliberately **retained**: `r` (`refresh_board`) prunes them and
    reports which ones went, which is what t1243_6 gave
    `MarkedSelection.retain()` a return value for. Clearing here would destroy
    a selection the user may still want after a refresh.
    """
    stale = [n for n in filenames if n not in self.manager.task_datas]
    if not stale:
        return False
    if all(n in self.manager.child_task_datas for n in stale):
        # Structurally unreachable today (every source is parent-only — see
        # `_review_then`), but if a child ever arrives, say the true reason.
        self.notify("Child tasks move with their parent — move the parent instead.",
                    severity="warning")
        return True
    self.notify("Selection is stale — no longer on the board: "
                + ", ".join(stale[:3]) + ("…" if len(stale) > 3 else "")
                + ". Press r to refresh, then retry.", severity="error")
    return True

def _review_then(self, filenames, on_confirm) -> None:
    """Show `filenames` in MoveTaskSelectScreen, then hand the kept ones on.

    Every name is resolvable past `_reject_stale`, so no row is silently
    dropped — what the dialog lists IS the selection. Child rows are excluded
    **structurally**, by the three sources rather than by a filter here:
    `action_toggle_mark` refuses to mark a child, the focused-card path gates
    on `is_child`, and `get_column_tasks` reads `task_datas` (parents only).
    """
    if self._reject_stale(filenames):
        return
    rows = []
    for name in filenames:
        task = self.manager.task_datas[name]
        task_num, task_name = TaskCard._parse_filename(name)
        rows.append((name, f"[{self._column_title(task.board_col)}] "
                           f"{task_num or name} {task_name}".rstrip()))
    # No `if not rows` guard: past `_reject_stale` the row count EQUALS the
    # input count, and every caller already rejects an empty selection. A guard
    # here could never fire, and one that reads like a live check is worse than
    # none (the t1243_6 ghost-arm precedent).

    def on_tasks(selected):
        if selected is None:
            return                                   # Esc — cancelled cleanly
        if not selected:
            self.notify("No tasks selected")         # confirmed with none checked
            return
        on_confirm(selected)

    self.push_screen(MoveTaskSelectScreen(rows), on_tasks)

def _apply_move_to_column(self, filenames, col_id) -> None:
    """Run the batch move and repaint. K writes, input order, K files."""
    if not col_id:
        return                                       # Esc at the column picker
    # Snapshot the SOURCE columns before the move mutates board_col.
    src_cols = {t.board_col for t in
                (self.manager.task_datas.get(n) for n in filenames) if t}
    result = self.manager.move_tasks_to_column(filenames, col_id)
    if result.refused:
        # All-or-nothing: NOTHING was written. `_reject_stale` already screened
        # the selection, so this is the POST-REVIEW window: the user sits in the
        # two modals while the auto-refresh timer (or another session) removes a
        # task, and the confirmed filename list was captured in the closure
        # before that happened. Narrow, but genuinely reachable — and the branch
        # is tested by mutating `task_datas` between the two callbacks.
        names = ", ".join(name for name, _ in result.refused)
        self.notify(f"Move refused, nothing written — no longer on the board: "
                    f"{names}. Press r to refresh.", severity="error")
        return
    # Clear BEFORE the refresh: refresh_board prunes-and-notifies, and an
    # already-empty set drops nothing, so no spurious warning fires. Same
    # ordering rationale as _set_base_filter in t1243_6.
    self.marked.clear()
    self.refresh_columns(src_cols | {col_id},
                         refocus_filename=result.moved[-1],
                         refocus_col_id=col_id)
    self.notify(f"Moved {len(result.moved)} task(s) to {self._column_title(col_id)}")

def action_clear_marks(self) -> None:
    """Palette 'Clear Selection': unmark everything and repaint those cards."""
    if self._modal_is_active():
        return
    if not self.marked:
        self.notify("Nothing marked")
        return
    cleared = set(self.marked.marked)
    self.marked.clear()
    for card in self.query(TaskCard):
        if card.task_data.filename in cleared:
            self._repaint_card_mark(card)
    self.notify(f"Cleared {len(cleared)} mark(s)")
```

**Binding** — appended to `KanbanApp.BINDINGS` beside `space`, shown (the
feature is otherwise undiscoverable; `check_action` hides it where it does not
apply). It self-registers as user-rebindable via `ShortcutsMixin` — no
`shortcut_scopes.py` edit:

```python
Binding("m", "move_to_column", "Move to Col"),
```

`action_clear_marks` is **palette-only** (no binding), so it needs no
`check_action` branch; marks are already cleared on a view switch.

## Step 5 — `check_action` gating

One branch, beside the `toggle_mark` gate (`:6310`):

```python
elif action == "move_to_column":
    # Hidden wherever movement is hidden — the derived views render
    # non-reorderable lanes. (By-Trail move-to-column is t1210_5, which
    # consumes this chain rather than duplicating it.)
    if self.base_filter in ("inflight", "bytopic", "bytrail"):
        return False
    if self.marked:
        return True   # a marked set is movable regardless of what has focus
    if self._get_focused_col_id() is None:
        return False  # neither a card nor a placeholder identifies a source
    focused = self._focused_card()
    if focused is not None and focused.is_child:
        return False  # matches the movement gate: a child is not movable, and
                      # with no marks there is nothing else for `m` to act on
```

---

## Verification — `tests/test_board_move_command.py` (new)

**The model layer is already covered — do not re-test it.**
`tests/test_board_manager_moves.py:150-262` already pins `move_tasks_to_column`
for K writes, input order, append semantics, duplicates, empty input, unknown
names, child ids, and mixed refusals. This module covers the **command** layer
only: the chain, the review gate, the gating, and the palette parity.

Booted with `board_fixture.FixtureBoardTestBase` + `PristineTreeMixin`,
`app.run_test(size=(160, 48))`, `await pilot.pause()` after boot and twice after
a mutating keypress. Opens with a `test_fixture_facts` precondition test so a
reshaped fixture fails loudly instead of going vacuous.

1. **`CommandPaletteParityTests`** — the regression the Step-1 de-dup prevents.
   Drive both real coroutines: collect `discover()`'s displays, and collect
   `search(d)`'s displays for each `d`. Assert both sets equal
   `{d for d, _, _ in _COMMANDS}`, and that every action attribute resolves on
   `KanbanApp`. **Discriminating control:** patch `_COMMANDS` with an extra
   sentinel entry and assert **both** surfaces pick it up — a re-hardcoded
   `search()` would show the sentinel only in `discover()` and fail here.
   (t1377_5 extends this class rather than writing a second guard.)
2. **`MoveChainTests`** — construction spies over the two-stage chain, using
   `test_board_work_report.py`'s `MagicMock`-app pattern (no board state
   mutated). Assert *which* screen was pushed with *which* arguments at each
   stage, for all four rows of the Step-0 table:
   - no marks + focused card → **one** `push_screen`, and it is
     `ColumnSelectScreen` (no review);
   - marks + focused card → `MoveTaskSelectScreen` first, seeded with the
     marked filenames **in board order**, then `ColumnSelectScreen`;
   - no marks + focused placeholder → `MoveTaskSelectScreen` seeded with the
     whole column from `task_datas`, then `ColumnSelectScreen`;
   - marks + focused placeholder → the marked set, not the column.
3. **`MoveOrderingTests`** — `_board_order` sorts by column rank then
   `normalize_board_idx` then filename; a hand-quoted `boardidx: "5"` sorts
   numerically; an unresolvable name sorts last rather than raising.
   **Discriminating control for the full-column ranking:** a target in a
   **collapsed** column, and one in the column `_move_destination_columns`
   filters out as redundant, both sort **where they render** — not lumped at
   the end. (Ranking off the destination list instead would pass every other
   ordering assertion and fail only these two.) Paired with a chain test
   asserting the reviewed row order reaches `move_tasks_to_column` unchanged.
4. **`MoveWriteTests`** — the only real-write class. K marked tasks → exactly
   **K** writes with an **exact changed-path set** (`bf.snapshot` /
   `bf.diff_snapshots`), destination sequence matching the presented sequence.
   Marks are **cleared** afterwards and the glyphs repaint to `☐`. Plus the
   **consolidation** case: targets spanning `c0` and `c1` moved into `c1` →
   still exactly K writes, and the `c1` members land at the bottom in presented
   order (the one path where a target's own column is a legal destination).
5. **`MoveCancellationTests`** — `None` (Esc) and `[]` (nothing checked) are
   distinguished, produce **different** notifications, and **neither writes**
   (assert an empty changed-path set, not merely "no exception"). Same for
   `None` from the column picker.
6. **`MoveStaleSelectionTests`** — the fail-closed guard. Mark two tasks, drop
   **one** from `task_datas`, press `m`: assert **zero** `push_screen` calls
   (no picker at all), the notify **names the stale id**, an **empty**
   changed-path set, and — the key assertion — `app.marked` is **unchanged**,
   still holding both names. Control: the *valid* task must **not** have moved,
   which is the partial-application this guard exists to prevent. Same guard on
   the focused-card path. A child filename injected into the marked set
   produces the **child** message, not the stale one.
7. **`MoveRefusalTests`** — the post-review TOCTOU window, the branch's only
   reachable trigger. Drive the chain to the task-select callback, then delete
   the entry from `task_datas` **between** the review callback and the column
   callback: `move_tasks_to_column` refuses, the notify names the id, and the
   changed-path set is **empty** (all-or-nothing). Deterministic — no timer, no
   sleep. Ordered after `MoveStaleSelectionTests` because it only means
   anything once the pre-review guard is proven to be the earlier gate.
8. **`MoveGatingTests`** —
   `assertIs(app.check_action("move_to_column", None), False)` in `inflight` /
   `bytopic` / `bytrail`, plus absence from `_footer_actions(app)` (the
   `test_board_footer_visibility.py:65` helper). `is True` in `all` with a card
   focused; `False` on a focused child **with no marks**; `True` on a focused
   child **with marks**. `assertIs` against `False`, never `assertFalse` —
   `None` must stay distinguishable.
9. **`MoveDestinationTests`** — one test per Step-0 filter, each with its
   negative half:
   - `unordered` is injected **first** when it has tasks, **omitted** when it
     does not, and **omitted when collapsed**;
   - a **collapsed** configured column is omitted and the same column expanded
     is offered — plus a parity assertion that `_move_task_lateral`'s own
     skip-list and this list agree on the collapsed set;
   - the targets' **shared** column is omitted when *all* targets sit in it,
     and **kept** when they span two columns (the consolidation case);
   - a stale `column_order` entry with no conf is not offered;
   - all columns collapsed → empty list → `action_move_to_column` notifies and
     pushes **no** picker.
10. **`MoveActionGuardTests`** — the palette bypasses `check_action`, so
   `action_move_to_column` must re-guard: call it directly with
   `base_filter="bytopic"` and assert **zero** `push_screen` calls; likewise
   under an active modal. `action_clear_marks` clears and repaints only the
   previously-marked cards.

**Negative controls.** Every guarded behaviour must make the suite exit 1 when
its production line is reverted — **one mutation per test**, verified
individually, not one revert checked against the whole file. Purge
`__pycache__` between runs so a stale bytecode cache cannot make a negative
control pass for the wrong reason.

```bash
~/.aitask/venv/bin/python -m pytest tests/test_board_move_command.py   # fast iteration
~/.aitask/venv/bin/python -m pytest tests/test_board_work_report.py    # base extraction
~/.aitask/venv/bin/python -m pytest tests/test_board_marking.py        # t1243_6 intact
bash tests/run_all_python_tests.sh                                     # full gate, NO args
bash tests/test_shortcuts_registry_coverage.sh                         # `m` self-registers
```

**Do NOT pass a positional test path to `run_all_python_tests.sh`** — it
*widens* the run rather than narrowing it (`CLAUDE.md:58-60`; t1243_6 lost a
tool budget to this). Read **only the last line** for the verdict
(`PYTHON SUITE: PASSED|FAILED`); if piping, use `set -o pipefail`.

**Live acceptance** (a render assertion is not a visibility claim): run
`ait board` in a tmux pane, mark two cards with `send-keys -l ' '` (literal
space — `Space` does not reach a Textual binding), press `m`, and capture the
pane to confirm the review dialog paints, the column picker follows, and the
cards land in the destination column.

---

## Notes for sibling tasks

- **t1210_5** — the shared entry points are `KanbanApp.action_move_to_column`
  (`m`), `MoveTaskSelectScreen`, `_move_destination_columns()` and
  `_board_order()`. Consume them; do **not** build a parallel picker. `m` means
  the same thing in every view — "move the selected task(s) to a column" — with
  per-view semantics gated in `check_action` (By-Trail is currently `False`
  there; t1210_5 flips that branch and supplies its own destination set).
- **t1377_5** — `_COMMANDS` is the single palette source, de-duped here as
  planned. Add "Manage Columns" / "Merge Columns" to that tuple and extend
  `CommandPaletteParityTests`; do not re-add duplicated lists or write a second
  guard. Bind the column-management dialog to `e`, not `m`.
- **t1243_12** (`G`, group membership) — reuse `_review_then`, `_reject_stale`
  and `_board_order` for the same "show the marked set before acting on it,
  and fail closed rather than silently dropping a dead mark" invariant.

## Risk

### Code-health risk: medium
- `TaskSelectScreenBase` re-parents `WorkReportTaskSelectScreen`, a green,
  load-bearing modal, and renames its button ids · severity: medium ·
  → mitigation: **in-task** — `tasks` kept as a property alias; the only
  external references were audited (`test_board_work_report.py` uses `.tasks`,
  `isinstance`, an untyped `query_one(SelectionList)` and key presses — **no**
  button ids, and `test_board_work_report_roundtrip.sh` references none), and
  both work-report test files run before commit
- `getattr(app, attr)` resolves palette actions by **name**, so a typo'd
  attribute now fails at palette-open time rather than at import · severity:
  medium · → mitigation: **in-task** — `CommandPaletteParityTests` asserts every
  `_COMMANDS` action attribute resolves on the real `KanbanApp` class
- `check_action`'s new branch returns `True` early on a non-empty marked set,
  diverging from every other gate in the function (which only ever return
  `False`), so a later reader could "normalize" it away · severity: low ·
  → mitigation: **in-task** — commented at the site and pinned by
  `MoveGatingTests`' focused-child-with-marks case
- `_move_destination_columns` now applies **three** filters and depends on the
  confirmed target set, so it can over-restrict — a user whose only other
  column is collapsed gets an empty picker · severity: medium · → mitigation:
  **in-task** — the empty case notifies with the reason and pushes no dialog,
  and `MoveDestinationTests` has one test per filter *with its negative half*
  plus the all-collapsed case
- A binding, two screens, four helpers and three actions land in a 9986-line
  file that five sibling tasks (t1243_8–12, t1377_*, t1210_5) are still editing ·
  severity: low · → mitigation: **in-task** — additive-only; full Python suite
  plus `test_shortcuts_registry_coverage.sh` before commit

### Goal-achievement risk: low
- The confirmed subdialog rule (review whenever marks exist) contradicts the
  task file's §2 and its Verification bullets, which still describe the
  decomposition-time rule; the task file also still names the removed
  `move_task_col`, and its "subdialog omits child rows" line no longer matches
  the structural exclusion · severity: low · → mitigation: **in-task** — amend
  the task file's §2, §3 and Verification in the same commit so the AC matches
  the implemented behaviour
- The destination set deliberately diverges from "every configured column" on
  three axes (transient `unordered`, collapsed columns, the targets' own
  column). Each is contract parity rather than a preference, but a user who
  expects a plain column list will find entries missing · severity: low ·
  → mitigation: each filter is justified against its existing call site in
  Step 0 and pinned in **both** directions by `MoveDestinationTests`; the
  empty-picker notify states the reason rather than failing silently

`risk_mitigations_planned: true` · `risk_mitigations_confirmed: false` — one
`after` mitigation was proposed (a board-wide decision on whether an emptied
Unsorted column stays a reachable move destination for `m` **and**
`shift+left/right`) and **declined by the user**. Every code-health risk is
already mitigated inside this task, and the Unsorted-parity risk is a deliberate
contract match pinned in both directions by `MoveDestinationTests`. No
`### Planned mitigations` subsection is written, so Step 7 and Step 8d both
no-op.

---

## Final Implementation Notes

- **Actual work done:** three files.
  - `.aitask-scripts/board/aitask_board.py` (+440/−72): `KanbanCommandProvider`
    de-duped onto `_COMMANDS` + `_resolved()`, with the two new palette entries;
    `TaskSelectScreenBase` extracted and `WorkReportTaskSelectScreen` re-parented
    onto it (keeping its `tasks` alias); `MoveTaskSelectScreen`;
    `_move_destination_columns` / `_column_title` / `_board_order`;
    `_reject_stale` / `_review_then` / `action_move_to_column` /
    `_apply_move_to_column` / `action_clear_marks`; `Binding("m", …,
    show=False)`; the `move_to_column` branch in `check_action`; and
    `_focused_card()` reduced to an O(1) attribute read.
  - `tests/test_board_move_command.py` — **new**, 944 lines, 69 tests in 11
    classes.
  - `aitasks/t1243/t1243_7_move_to_column_command.md` — §2/§3/§5 and
    Verification amended so the AC matches the implemented behaviour.

- **Deviations from plan:**
  1. **`m` is `show=False`.** The plan said shown, "the feature is otherwise
     undiscoverable". Live tmux capture disproved the premise's cost: the board
     footer is already full at 200 columns — `space Mark` (t1243_6) took the
     last slot — so a shown `m` renders as a bare key with its label clipped,
     whether the label is "Move to Col" or "Move". A key with no label is worse
     than no key. Discovery is the `?` shortcuts editor (ShortcutsMixin
     registers the binding automatically) and the palette's "Move Tasks to
     Column". Same call as `ctrl+up`/`ctrl+down` and `X`.
  2. **`_focused_card()` was made O(1)** — scope beyond this task, confirmed
     with the user mid-implementation. See "Issues encountered" #1.

- **Issues encountered:**
  1. **This task's `check_action` gate regressed
     `test_board_movement::test_attribution_tier_localises_an_injected_cost`.**
     The full suite went red 3 of 4 runs with the change and passed on a clean
     tree. Diagnosis: `check_action` runs once per binding on every
     `refresh_bindings()` — i.e. on every focus change during a move — and ~10
     of its gates call `_focused_card()`, most of them twice (ghost pre-gate +
     their own branch). Measured on a 60-card fixture board: **27 whole-board
     `query("TaskCard:focus")` walks and 59.08 ms per footer sweep**, all
     pre-existing. This task added the 28th, ~4%, which tipped a benchmark
     already sitting at its fixed 25 ms cross-run threshold — the giveaway that
     it was noise crossing a bar rather than a localisation bug was that a
     *different* neighbour failed each time (`render` 46.2 ms, then `dom_query`
     31.6 ms).
     Two fixes, in order: the gate was collapsed to **one** `_focused_card()`
     call (the first draft called `_get_focused_col_id()` — which queries
     internally — *and* `_focused_card()`), and then, with the user's
     agreement, `_focused_card()` itself became an attribute read. `:focus`
     matches exactly one widget, the screen's focused one, so the whole-board
     query was always redundant; `_focused_placeholder()` has used the O(1)
     idiom all along. Equivalence was verified live in both directions (a
     focused `TaskCard` → the card; a focused `Input` → `None`).
     **Result: 59.08 ms → 0.05 ms per footer sweep, 27 queries → 0**, and the
     suite is 3/3 green (was 1/4). The board is now faster on its hottest path
     than before this task.
  2. **A negative control caught a vacuous test of mine.** The "source columns
     snapshot before the move" mutation passed the suite, because
     `MoveRefusalTests`' success-path stub returned a `MoveResult` without
     mutating `board_col` — so before/after snapshots were indistinguishable.
     The stub now mutates like the real API, and the control discriminates.
     A passing negative control means the test is wrong, not the code.
  3. **Two mock-fidelity bugs** surfaced the same way: `_get_focused_col_id`
     returning `None` regardless of the focused card made the gate look
     stricter than it is, and an unconfigured `_focused_placeholder` MagicMock
     is truthy, which silently disabled the "nothing in focus" case. Both now
     mirror production.

- **Key decisions:**
  - **Review whenever marks exist** (user-confirmed), overriding the task
    file's §2. Marks survive a filter pass by t1243_6's design, so the marked
    set can contain cards the user cannot see; a bare focused card needs no
    review because it is one visible, unambiguous target.
  - **Fail closed on a stale mark**, rather than showing it as a review row.
    Dropping dead names and moving the rest is the partial application
    `move_tasks_to_column`'s all-or-nothing contract exists to prevent, and a
    row that can only ever be unchecked is a dead-end control. Marks are
    **retained** so `r` can prune-and-report them — which is what t1243_6 gave
    `MarkedSelection.retain()` a return value for. This left the
    `_apply_move_to_column` refusal branch reachable only through the
    post-review TOCTOU window, which is exactly how it is now tested (mutate
    `task_datas` between the two callbacks — deterministic, no timer).
  - **Three destination filters, not one.** The plan's first draft claimed
    parity with `_move_task_lateral` while offering every configured column;
    that helper also *skips collapsed columns*. Added, along with excluding a
    column every target already occupies (a "send to bottom" reorder, not a
    move) while keeping it when targets span two columns (real consolidation).
    Consequence caught in the same pass: `_board_order` must rank **every**
    column, not the filtered destination list, or a target in a collapsed or
    redundant column sorts last instead of where it renders.
  - **A shared modal base rather than a third hand-copy** — the same "refactor
    duplicates before adding to them" rule §1 obeys.

- **Upstream defects identified:**
  - `.aitask-scripts/board/aitask_board.py:6216-6223` — `check_action`'s ghost
    pre-gate calls `_focused_card()` for six movement actions and then each
    action's own branch calls it again, so every gated action paid for two
    whole-board DOM walks. Pre-existing and independent of this task (it dates
    from the ghost pre-gate, not from `m`); fixed here only because this task's
    28th call is what made it visible, and the fix was a strict improvement.
    No separate task needed — it is resolved.

- **Notes for sibling tasks:** see the section above. `_focused_card()` is now
  cheap enough to call freely in `check_action`; `FocusedCardCostTests` fails if
  the whole-board query ever returns.
