---
Task: t1243_6_multiselect_marking.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_*.md
Archived Sibling Plans: aiplans/archived/p1243/p1243_*_*.md
Parent Plan: aiplans/p1243_board_task_groups_and_fast_reordering.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-04 10:55
---

# t1243_6 — Multi-select marking

## Context

`ait board` has **no selection state of any kind** today — no marking, no
multi-select, nothing. Every later child in the t1243 decomposition operates on a
marked set: **t1243_7** (`m` — move-to-column) and **t1243_12** (`G` — group
membership). This child lands that primitive and nothing else: `space` toggles a
mark on the focused parent card, the mark renders as a `☑`/`☐` glyph, and the
marked set lives on the app keyed by task filename.

Read `aiplans/p1243_board_task_groups_and_fast_reordering.md` §"Workstream D" for
the design decisions and rejected alternatives. The task file
`aitasks/t1243/t1243_6_multiselect_marking.md` is the spec; this file is the
execution order.

---

## Step 0 — anchor re-verification · **DONE 2026-08-04**

`aitask_board.py` is now **9775 lines** (7378 at t1243 planning, 9043 at
decomposition). Every symbol this plan names was re-located; three claims the
task file makes are **stale** and are corrected below.

### Confirmed

| Claim | Anchor |
|---|---|
| `space` is free | zero `Binding("space"` hits in the whole file; free in `KanbanApp.BINDINGS` (`:5903-5979`) and in every `Screen`/`ModalScreen` |
| `_modal_is_active()` exists | `:7272-7273`, `return isinstance(self.screen, ModalScreen)`, 33 call sites |
| `on_focus`/`on_blur` set the border imperatively | `:2090-2101` — so a CSS-class "marked" border would be stomped on every focus change. **Glyph, not border, stands.** |
| `check_action` hides movement in the three derived views | `:6170-6182` |
| movement actions early-return on `focused.is_child` | `_move_task_lateral` `:8629-8630`, `_move_task_vertical` `:8819`, `_move_task_to_extreme` `:8877+` |
| `.task-title-row` is a `Horizontal` of CSS-classed `Label`s | `:1980-1985` |
| `tests/test_board_marking.py` is free | 29 `test_board_*.py` files, none named that |

### Corrected — three stale premises

1. **`TaskManager.move_task_col` no longer exists.** t1243_3 replaced it with
   `move_tasks_to_column(task_names, new_col)` (`:1574`) — already a **batch**
   API — over `_resolve_parents` (`:1551-1568`), which **refuses** an
   unresolvable name with `("<name>", "not_a_parent_task")` and writes nothing
   (all-or-nothing). So the task file's rationale — *"a marked child handed to
   the persistence API would be silently ignored"* — is **no longer true**: it
   now fails closed with a which-items report. **The v1 decision to exclude
   children still holds** (parent design plan §Workstream D), but the reason is
   now "the board's movement contract is parent-level", not "it would be
   silently dropped".

2. **`check_action` has a ghost-card pre-gate** (`:6088-6096`) that fires
   *before* the movement branch and covers the same six movement actions. The
   task file does not mention ghosts at all. `toggle_mark` **does not join it** —
   ghosts exist only under By-Trail, which the view gate already covers; see
   Step 2 for the reachability argument and Step 4 for the matching action-guard
   decision.

3. **The view attribute is `self.base_filter`** (`:5986`, a plain `str`). There
   is no `view_mode` and no `current_view` anywhere in the file.

### New constraints the task file does not carry

- **`TopicColumn` (`:2227`) mounts base `TaskCard`s.** A glyph added
  unconditionally to `TaskCard.compose` would appear in By-Topic, where `space`
  is gated off. `InFlightTaskCard` (`:2128`) and `TrailTaskCard` (`:2298`)
  **fully override** `compose` and are unaffected.
- **The board has no `TaskCard` CSS rule and zero `:hover` rules**, but it *does*
  have two `:focus` rules using `background: $primary 30%` (`:5762`, `:5764`) —
  the board's own idiom, not brainstorm's `$accent`.
- **New bindings self-register.** `KanbanApp._shortcuts_scope = "board"`
  (`:5656`) and `ShortcutsMixin.__init__` pipes `BINDINGS` through
  `register_app_bindings` (`lib/shortcuts_mixin.py:83-93`), so `space` becomes
  user-rebindable and appears in the `?` editor **automatically** — no
  `shortcut_scopes.py` edit. `tests/test_shortcuts_registry_coverage.sh` must
  stay green.
- The `space`-binding uniqueness guard (`tests/test_monitor_agent_marks.py:266`)
  iterates **`MiniMonitorApp`/`MonitorApp` only** — the board is out of its
  scope.
- **t1243_5 rebuilds card widgets** on a lateral move (`_transplant_block`, via
  the single construction path `KanbanColumn.task_block` `:2845`). A transplanted
  card is a **new widget object**, so per-widget mark state would be destroyed.
  App-level state keyed by filename is therefore **required**, not merely tidy.

---

## Design decisions — confirmed with the user 2026-08-04

1. **Hover pair only.** Add `TaskCard:hover` + `TaskCard:focus:hover`; do **not**
   add a `TaskCard:focus` background. Focus keeps its existing imperative
   double-cyan border, so no focused card changes appearance. `:focus:hover` uses
   `$primary 30%` — the board's own focus idiom — so a hovered focused card never
   flips to gray.
2. **Prune on refresh, clear on view switch.** `refresh_board` reaches the
   *auto-refresh timer*, so clearing there would silently discard a selection
   with no user action. It **prunes** to still-present parent filenames instead.
3. **Glyph exactly where `space` acts** — the t1383 precedent ("present exactly
   when `space` would act"). No inert `☐` on a row the key refuses.

---

## Step 1 — `MarkedSelection`

New class in `.aitask-scripts/board/aitask_board.py` (per the task file's "Key
files"), dependency-free so it unit-tests without a running app.

```python
class MarkedSelection:
    """Board multi-select state: the set of marked task filenames.

    Mirrors `brainstorm/utils.py::NodeSelection`'s documented rule — SINGLE-item
    operations act on the cursor, MULTI-item operations act on the marked set.
    The board already *has* a cursor (the focused `TaskCard`), so this holds only
    the marked set and `effective()` takes the cursor as an argument.

    Keyed by `Task.filename`, the board's durable card identity — the same key
    `expanded_tasks` (`:5990`) and `_refocus_card` (`:6603`) already use. A
    filename key is what survives the widget churn that `_transplant_block`,
    `_recompose_column` and `refresh_board` inflict on card objects.
    """

    def __init__(self, marked=None):
        self.marked: set[str] = set(marked) if marked else set()

    def __contains__(self, filename) -> bool:
        return filename in self.marked

    def __len__(self) -> int:
        return len(self.marked)

    def toggle(self, filename) -> bool:
        """Flip `filename`; return its NEW marked state."""
        if filename in self.marked:
            self.marked.discard(filename)
            return False
        self.marked.add(filename)
        return True

    def clear(self) -> None:
        self.marked.clear()

    def retain(self, filenames) -> set[str]:
        """Drop every mark not in `filenames`; return the dropped set.

        Returns *which* marks were dropped rather than a bare count so a caller
        can report them; `refresh_board` uses it to survive a task archived by
        another session without discarding the rest of the selection.
        """
        keep = set(filenames)
        dropped = self.marked - keep
        self.marked &= keep
        return dropped

    @property
    def cardinality(self) -> int:
        return len(self.marked)

    def effective(self, focused_filename=None) -> list[str]:
        """Targets an operation runs on: the marked set, else the focused card.

        Sorted for determinism. Callers that need *board* order (t1243_7's
        `move_tasks_to_column` preserves input order) must re-sort by
        `(board_col, board_idx)` themselves — this class knows nothing about
        board geometry.
        """
        if self.marked:
            return sorted(self.marked)
        return [focused_filename] if focused_filename else []
```

Instantiate beside the existing app-level sets, next to `expanded_tasks`
(`:5990`): `self.marked = MarkedSelection()`.

## Step 2 — the `space` binding and its gate

**Binding** — appended to `KanbanApp.BINDINGS`, shown (the feature is otherwise
undiscoverable; `check_action` hides it where it does not apply):

```python
Binding("space", "toggle_mark", "Mark"),
```

**`check_action`** — **one** edit: a branch beside the movement gate.

Do **not** add `"toggle_mark"` to the ghost pre-gate at `:6088-6096`. Ghost cards
are mounted **only** by `TrailColumn` (`:2404`), which is mounted **only** on the
By-Trail render path (`:7786`) — so `is_ghost` implies `base_filter == "bytrail"`,
which the branch below already hides. Adding it would be unreachable code that
reads like a live guard.

```python
elif action == "toggle_mark":
    # Marking feeds bulk column moves (t1243_7) and group membership
    # (t1243_12) — both parent-level column operations. In-Flight / By-Topic /
    # By-Trail render derived, non-reorderable lanes, so there is nothing there
    # to mark. False (not None) so the footer HIDES it, matching the movement
    # gate above.
    if self.base_filter in ("inflight", "bytopic", "bytrail"):
        return False
```

**Deliberately NOT gated on `focused.is_child`** — unlike movement, where hiding
is right, a child card keeps the binding so the action can *explain* the refusal
(Step 4). This is the one place the mark gate diverges from the movement gate,
and the divergence is intentional.

## Step 3 — the glyph, structurally scoped

Module-level constants, mirroring `brainstorm_dag_display.py:58-66`:

```python
# Board multi-select mark (t1243_6). The t1004 checkbox convention — ☑/☐, never
# a dot, marked = bold yellow — which `monitor/monitor_shared.py:152` records as
# meaning "selected for this action", exactly the sense here. Rendered as a
# CSS-classed `Label` rather than Rich markup because that is how `.task-number`
# / `.task-modified` already work in this same title row.
MARK_CHECKED = "☑"
MARK_UNCHECKED = "☐"
```

**Markability is a constructor flag, not a runtime lookup.** `TaskCard.__init__`
gains `markable: bool = False`; only `KanbanColumn.task_block` (`:2845`) passes
`markable=True`, and only for the parent card:

```python
yield TaskCard(task, self.manager, column_id=self.col_id, markable=True)
```

Everything else defaults to `False` and is excluded **structurally** rather than
by an invariant that a future caller could forget: the child card at `:2853`,
`TopicColumn`'s cards at `:2227`, and `TrailGhostCard`. `InFlightTaskCard` /
`TrailTaskCard` override `compose` and never reach this code.

`__init__` also mirrors the flag onto a CSS class. **This assignment is
load-bearing for Step 6** — the hover selectors key on `.markable-card`, and
without it they would match nothing and `MarkScopeTests` would fail:

```python
def __init__(self, task, manager=None, is_child=False, column_id="",
             markable: bool = False):
    super().__init__()
    ...
    self.markable = markable
    if markable:
        # The hover rules in KanbanApp.CSS select `.markable-card`, not the
        # `TaskCard` type — see Step 6 for why. Set only when True so every
        # other card kind stays class-free.
        self.add_class("markable-card")
```

`markable` is appended **last with a default**, which is what keeps the three
subclasses class-free without touching them: `InFlightTaskCard` (`:2124`),
`TrailTaskCard` (`:2290-2292`) and `TrailGhostCard` (`:2342`) all call
`super().__init__(...)` without it — verified, not assumed. The child card at
`:2853` likewise omits it. So exactly one construction site in the whole file
produces a `.markable-card`.

`TaskCard.compose` (`:1980`) prepends one label inside `.task-title-row`:

```python
with Horizontal(classes="task-title-row"):
    if self.markable:
        marked = self._is_marked()
        yield Label(MARK_CHECKED if marked else MARK_UNCHECKED,
                    classes="task-mark task-marked" if marked else "task-mark")
    if task_num:
        ...
```

with

```python
def _is_marked(self) -> bool:
    """Live read of the app's marked set — never a build-time freeze.

    `compose` derives the glyph from app state on every (re)build, so a card
    remounted by `_transplant_block` / `_recompose_column` / `refresh_board`
    paints the correct glyph for free. `_repaint_card_mark` handles the other
    direction: a toggle on an already-mounted card.
    """
    return self.markable and self.task_data.filename in self.app.marked
```

## Step 4 — the action, and child refusal with a reason

```python
def action_toggle_mark(self) -> None:
    """`space`: toggle the focused parent card's mark."""
    # Textual does not dispatch App BINDINGS under a ModalScreen (see
    # monitor_shared.py:389-394), and SelectionList modals own `space` for their
    # own toggling — but the house idiom guards anyway, and a test pins it.
    if self._modal_is_active():
        return
    # Re-check the view gate inside the action, not only in check_action: a
    # binding gate is not an action guard.
    if self.base_filter in ("inflight", "bytopic", "bytrail"):
        return
    card = self._focused_card()
    if card is None:
        return
    if card.is_child:
        # Refuse with a reason — never a silent nothing. This is the ONE
        # reachable non-markable card in the kanban views.
        self.notify("Child tasks move with their parent — mark the parent instead.",
                    severity="warning")
        return
    if not getattr(card, "markable", False):
        # Unreachable today: every non-child card `KanbanColumn` mounts is
        # markable, and the derived views (the only source of In-Flight / Trail /
        # ghost cards) returned above. Fail closed rather than marking something
        # the parent-only persistence API would refuse.
        return
    self.marked.toggle(card.task_data.filename)
    self._repaint_card_mark(card)
```

**No ghost arm.** `_focused_card()` (`:7124`) resolves `query("TaskCard:focus")`,
which does catch ghosts — but a ghost only exists under `base_filter ==
"bytrail"`, so the view gate above returns first. A ghost-specific `notify` would
be dead code, and the guard-order fact is recorded here so a later reader does
not "restore" it.

```python
def _repaint_card_mark(self, card) -> None:
    """Repaint ONE card's glyph in place — no recompose, no board-wide query.

    Scoped to the card's own subtree deliberately: t1243_4 measured a whole-board
    `query(TaskCard)` at ~6.8 ms, and only one card changes per keypress.
    """
    labels = card.query(".task-mark")
    if not labels:
        return
    marked = card.task_data.filename in self.marked
    labels.first().update(MARK_CHECKED if marked else MARK_UNCHECKED)
    labels.first().set_class(marked, "task-marked")
```

## Step 5 — lifecycle

| Site | Anchor | Behaviour |
|---|---|---|
| `_set_base_filter` | `:6949`, right after `self.base_filter = name` | `self.marked.clear()` — a view switch discards the selection. Placed **before** `refresh_board` so re-mounted cards paint unmarked. Sits next to the existing `expanded_tasks` / `_view_auto_expanded` per-view handling (`:6957-6961`), the precedent for this. |
| `refresh_board` | `:6490`, early — before the mount loop | Prune, never clear — and **report what it dropped** (below). Survives the auto-refresh timer; drops a task archived by another session. |
| `apply_filter` | `:6714` | **untouched.** Filtering is a view operation, not a selection operation; marks survive it. |
| `refresh_column` / `refresh_columns` / `_transplant_block` | — | **untouched.** The glyph is re-derived from the app set at `compose`. |

**The prune must not be silent.** `retain` returns *which* marks it dropped
precisely so the caller can report them, and the whole reason prune was chosen
over clear was to stop an unattended timer tick from quietly shrinking the
user's selection. Discarding the return value would reintroduce that exact
failure at a smaller scale:

```python
dropped = self.marked.retain(self.manager.task_datas.keys())
if dropped:
    self.notify(f"Unmarked {len(dropped)} task(s) no longer on the board: "
                + ", ".join(sorted(dropped)[:3])
                + ("…" if len(dropped) > 3 else ""),
                severity="warning")
```

It fires only when something was actually removed, so the common refresh — and
every timer tick on a stable board — stays silent. Ordering makes it
self-limiting: `_set_base_filter` clears **before** calling `refresh_board`, so a
view switch prunes an already-empty set and never notifies; likewise the
`on_mount` boot refresh.

`_set_base_filter` already calls `refresh_bindings()` (`:7016`), so the footer
picks up the `check_action` change on a view switch for free.

## Step 6 — CSS

Four rules appended to `KanbanApp.CSS`, beside the existing `.task-number` /
`.task-modified` block (`:5718-5719`):

```css
.task-mark { width: auto; margin: 0 1 0 0; color: #6272A4; }
.task-marked { color: yellow; text-style: bold; }

/* `.markable-card` is set in TaskCard.__init__ — see Step 3. Without that
   assignment these two rules match nothing.
   Scoped to .markable-card, NOT bare `TaskCard`. A Textual type selector matches
   the whole MRO, so `TaskCard:hover` would also restyle InFlightTaskCard (:2121),
   TrailTaskCard (:2285) and the read-only TrailGhostCard (:2331) — a hover
   affordance in three views this task does not touch, on cards whose glyph and
   action are structurally excluded. Keeping the visual change coextensive with
   the feature is the same smallest-blast-radius call as skipping :focus. */
TaskCard.markable-card:hover { background: $surface-lighten-1; }
/* Focused + hovered stays in the focus family, never the gray hover
   (:hover would otherwise override :focus at equal specificity).
   $primary 30% is the board's own focus idiom — .collapsed-placeholder:focus. */
TaskCard.markable-card:focus:hover { background: $primary 30%; }
```

The conditional-class shape (`task-mark` / `task-mark task-marked`) is a direct
copy of the `task-number` / `task-number task-modified` pattern two lines above
it in the same `compose`.

---

## Verification — `tests/test_board_marking.py` (new)

Booted with `board_fixture.FixtureBoardTestBase` + `PristineTreeMixin`,
`app.run_test(size=(160, 48))`, `await pilot.pause()` after boot and **twice**
after a mutating keypress. Opens with a `test_fixture_facts` precondition test so
a reshaped fixture fails loudly instead of going vacuous.

1. **`MarkedSelectionUnitTests`** — pure model: `toggle` returns the new state
   and round-trips; `retain` returns the *dropped* set and keeps the rest;
   `clear`; `cardinality`; `effective` falls back to the focused filename, and
   returns `[]` with neither.
2. **`MarkGlyphRenderTests`** — render-level, on the `.task-mark` `Label`:
   `render().plain == "☐"` initially; `== "☑"` after `space`, with
   `"task-marked"` in its classes; back to `"☐"` on the second press. Each
   positive paired with its negative (`assertNotIn` the other glyph).
   **Discriminating controls:** a child card and a `TopicColumn` card have **no**
   `.task-mark` label at all.
3. **`MarkGatingTests`** — `assertIs(app.check_action("toggle_mark", None), False)`
   in `inflight` / `bytopic` / `bytrail` plus absence from `_footer_actions(app)`
   (the `test_board_footer_visibility.py:65` helper); `is True` and present in
   `all`. `assertIs` against `False`, never `assertFalse` — `None` must be
   distinguishable.
4. **`MarkModalInertTests`** — push a modal, press `space`, assert the marked set
   is unchanged.
5. **`MarkRefusalTests`** — focus a child card, press `space`: the set is
   unchanged **and** `notify` fired with the child reason (spy on `app.notify`).
   **No ghost test** — a ghost is unreachable behind the By-Trail view gate
   (Step 4); By-Trail is covered by `MarkGatingTests` instead. Add one test that
   *pins the unreachability* rather than asserting dead behaviour: assert every
   `is_ghost` card class is mounted only by `TrailColumn`, so a future view that
   mounts ghosts elsewhere fails here and forces the guard to be reconsidered.
6. **`MarkScopeTests`** — the `markable-card` class is what the hover rules key
   on, so assert it directly: **present** on a kanban parent card, **absent** on
   a child card, an `InFlightTaskCard`, a `TopicColumn` card and a
   `TrailGhostCard`. This is the regression assertion that keeps the hover
   restyle coextensive with the feature.
7. **`MarkLifecycleTests`** — marks **survive** a search-filter pass (type into
   `#search_box`, assert the mark and the glyph persist); marks are **cleared**
   by `_set_base_filter("locked")`; `refresh_board` **prunes** a bogus filename
   while keeping a real one **and notifies**, naming the dropped file; a stable
   refresh with no drops **does not** notify (the control that stops the warning
   firing on every timer tick); a mark **survives a lateral move**
   (`shift+right`) and the *rebuilt* card still renders `☑` — the t1243_5
   transplant interaction.
8. **`MarkNarrowWidthTests`** — the glyph takes 2 columns from a `width: 1fr`
   title, so the assertion must be **screen-level**, not label-level: a
   `Label.render().plain` stays fully populated even when its parent clips it to
   nothing, which would make a non-empty-text assertion vacuous. Boot
   `wide_topology(n, tall_titles=True)` (`board_fixture.py:311`, whose
   `_TALL_SLUG` exists for exactly this) at a narrow width, composite the screen
   with `"\n".join(strip.text for strip in app.screen._compositor.render_strips())`
   (the `test_concern_picker_modal.py:80-84` helper), locate the line bearing the
   glyph, and assert **that same line** also carries the task number and the
   title's first word. Control: the marked card's `.task-title` `Label` has a
   non-zero `region.width` at that terminal size.

**Negative controls.** Every guarded behaviour must make the suite exit 1 when
its production line is reverted — **one mutation per test**, verified
individually, not one revert checked against the whole file.

```bash
bash tests/run_all_python_tests.sh tests/test_board_marking.py   # single module
bash tests/run_all_python_tests.sh                               # full suite
bash tests/test_shortcuts_registry_coverage.sh                   # binding registry
```

Read **only the last line** for the verdict (`PYTHON SUITE: PASSED|FAILED`); if
piping, use `set -o pipefail` or check `${PIPESTATUS[0]}`. Do **not** use a `-k`
filter — without pytest installed the runner falls back to `unittest`, where
`-k "A or B"` runs zero tests and exits 0.

**Live acceptance** (a render assertion is not a visibility claim): run
`ait board` in a tmux pane, `space` on a card, and capture the pane to confirm
the `☑` actually paints and the title row does not reflow.

---

## Notes for sibling tasks

- **t1243_7 / t1243_12:** the marked set is `app.marked` (`MarkedSelection`), keyed
  by filename. `effective(focused_filename)` implements "marked set, else focused
  card" and returns a **filename-sorted** list — re-sort by
  `(board_col, board_idx)` before handing it to `move_tasks_to_column`, which
  preserves input order.
- **Hidden-but-marked is a real edge, and it is t1243_7's.** Marks deliberately
  survive a filter pass, so a marked card that `apply_filter` has hidden
  (`styles.display == "none"`) is an invisible participant in a later bulk
  action. t1243_7's task-select subdialog is what makes that set visible again
  before it is acted on — do not let the `m` command act on `effective()` without
  showing it.
- `move_tasks_to_column` already **fails closed** on a child id with
  `("<name>", "not_a_parent_task")` — a which-items report, not a silent skip.
  Surface it rather than filtering children out beforehand.

## Risk

### Code-health risk: medium
- The glyph prepends a label to `.task-title-row` on **every parent card in the
  kanban views**, taking 2 columns from a `width: 1fr` title — a visible layout
  change to the board's most-seen surface · severity: medium · → mitigation:
  **screen-level** narrow-width test (`MarkNarrowWidthTests`, in-task; a
  label-level text assertion would pass vacuously under clipping) + live tmux
  capture
- The hover restyle is scoped by a CSS class rather than by the `TaskCard` type
  selector, because a Textual type selector matches the whole MRO and would have
  silently restyled three views this task does not touch · severity: low ·
  → mitigation: `MarkScopeTests` asserts `markable-card` presence/absence across
  all five card kinds
- `TaskCard.__init__` gains a parameter and `compose` gains a branch in a
  9775-line load-bearing file that three sibling tasks are still editing ·
  severity: low · → mitigation: additive-only, defaulted parameter; full suite
  before commit
- `check_action` gains a branch whose gate deliberately diverges from the
  movement gate beside it (no `is_child` arm), which a later reader could
  "fix" · severity: low · → mitigation: the divergence is commented at the site
  and pinned by `MarkRefusalTests`

### Goal-achievement risk: low
- Marks survive filtering by design, so a bulk command could act on cards the
  user cannot see · severity: medium · → mitigation: owned by **t1243_7**'s
  task-select subdialog; recorded above under "Notes for sibling tasks" rather
  than spawned as a new task, since t1243_7 already carries it

`risk_mitigations_planned: true` · `risk_mitigations_confirmed: false` — two
`after` mitigations were proposed (a card-title width-budget audit and a
marked-but-hidden-card guard) and **declined by the user**, because both material
risks are already handled: the width risk inside this task by
`MarkNarrowWidthTests` plus a live tmux capture, and the hidden-card risk by
**t1243_7**'s task-select subdialog. Spawning either would duplicate scope that
is already decomposed. No `### Planned mitigations` subsection is written, so
Step 7 and Step 8d both no-op.
