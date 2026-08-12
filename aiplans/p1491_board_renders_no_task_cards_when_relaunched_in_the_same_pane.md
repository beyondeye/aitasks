---
Task: t1491_board_renders_no_task_cards_when_relaunched_in_the_same_pane.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1491 — board swallows every single-key binding at startup

## Context

t1490 (manual verification of t1486) reported that relaunching `ait board` in the
same tmux pane after quitting with `q` renders column headers with **correct task
counts** but **zero task cards** — every column body shows `(empty)`. It was
spawned as t1491 with `followup_kind: upstream_defect`.

**The premise is a misdiagnosis, and I reproduced the real defect instead.**
There is no relaunch bug. The board never quit: `q` was typed into the search box,
and so was the `./ait board` that followed it.

### Root cause (reproduced, with positive and negative controls)

`KanbanApp` never claims startup focus. Textual applies `App.AUTO_FOCUS = "*"`
inside `Screen._compose()` — **before** `KanbanApp.on_mount` runs — and the first
focusable widget in the board's DOM is `Input#search_box`
(`aitask_board.py:7930`, composed ahead of `#board_container` at `:7931`).

Traced live in a real terminal (`Screen.set_focus` instrumented), focus is set
exactly once and never moved again:

```
[  0.024] set_focus -> Input#search_box (from_app_focus=False)
    textual/screen.py:1487  in _compose
    textual/screen.py:1499  in _update_auto_focus
```

Consequences on a freshly launched board, before any Tab/Esc/click:

* every **non-priority** binding is swallowed as text — `q` (Quit,
  `aitask_board.py:7512`), `n`, `r`, `s`, `a/l/f/i/y/z`, `g`, `t`, `e`, `p`, `c`,
  `x`, `m`, `b`, `w`, `o`, `O`, `T`, `X`, `#`, `space`. Only the `priority=True`
  bindings (arrows, `tab`, `escape`, `:7513-7519`) still work, which is why the
  board *feels* functional.
* whatever lands in the box sets `search_filter` (`on_search`, `:8419-8422`), so
  `apply_filter` (`:8572`) hides every card via `set_unit_display` (`:422-441`)
  and re-shows each column's `EmptyColumnPlaceholder` (`:8676-8678`), while
  `ColumnHeader.task_count` — baked in at construction (`:2764`) and never
  touched by `apply_filter` — keeps its **unfiltered** count. That is the
  reported symptom byte for byte.
* `on_resize` (`:7969`) only reflows the filter row, so a resize never repairs it.

Measured evidence (isolated `-L t1491` server, the t1490 8-task fixture, 200x50):

| trial | result |
|---|---|
| fresh board → bare `q` | `pane_current_command` still `python`; search box holds `q` |
| then `Escape` → `q` | `pane_current_command` `bash` — quit works |
| relaunch in the **same pane** after a real quit | all 8 cards render; `(empty)` only in the genuinely empty Backlog |
| `AIT_USE_PYPY=0` (CPython) vs PyPy | **identical failure** — not interpreter-dependent |

### Why no existing test catches it, and why a headless test cannot

`Screen._update_auto_focus` is gated on `self.app.app_focus`, and the widget it
picks differs between drivers. Measured on the same fixture at the same size:

* **real terminal** → `Input#search_box` (the bug)
* **headless `App.run_test()`** → `HorizontalScroll#board_container`; `pilot.press("q")` exits cleanly

So a headless pilot **cannot reproduce the `q`-swallowing symptom**. AC #3's
instinct was right, for a reason it did not state: the pin must run against a real
terminal. A headless pin is still useful for the *positive* contract (see Tests).

## Implementation

All code changes are in `.aitask-scripts/board/aitask_board.py`.

### 1. Factor the board's focus-anchor lookup (near `action_focus_board`, `:9058`)

`action_focus_board` already walks `_get_visible_col_ids()` → `_column_focus_target()`
for its leftmost anchor. Extract that loop so startup focus and Escape share one
site rather than duplicating it:

```python
    def _first_board_focus_target(self):
        """Leftmost column's focus anchor (card / group header / placeholder), or None."""
        for col_id in self._get_visible_col_ids():
            target = self._column_focus_target(col_id)
            if target is not None:
                return target
        return None
```

Rewrite `action_focus_board`'s tail to `target = self._first_board_focus_target()`
/ `if target is not None: target.focus()`. Its modal branch is unchanged.

### 2. Claim startup focus for the board (`KanbanApp.on_mount`, `:7941`)

```python
        self._apply_filter_reflow()
        # Startup focus (t1491). Textual applies AUTO_FOCUS="*" in
        # Screen._compose — BEFORE this hook — and the first focusable widget in
        # the DOM is `#search_box`, so on a real terminal every non-priority
        # single-key binding (`q` included) is swallowed as search text until the
        # user presses Esc/Tab or clicks, and whatever lands there filters the
        # whole board to `(empty)` while the headers keep unfiltered counts.
        # Deferred for the same reason `apply_filter` is: refresh_board mounts
        # the columns asynchronously, so the anchors are not queryable yet.
        self.call_after_refresh(self._claim_startup_focus)
```

### 3. New `_claim_startup_focus` (beside `_first_board_focus_target`)

```python
    def _claim_startup_focus(self) -> None:
        """Move startup focus off `#search_box` and onto the board (t1491).

        Runs once, from `on_mount`. Unconditional apart from the modal guard:
        nothing else has legitimately claimed focus this early, and the widget
        AUTO_FOCUS picked differs by driver (`#search_box` on a real terminal,
        `#board_container` headless) — so a "steal only from an Input" predicate
        would silently no-op on one of them.

        A board with no anchor at all (no columns) clears focus instead: an
        unfocused screen still routes keys to the App bindings, which is what
        `q` needs.
        """
        if self._modal_is_active():
            return
        target = self._first_board_focus_target()
        if target is not None:
            target.focus()
        elif self.screen is not None:
            self.screen.set_focus(None)
```

### 4. Harden: make a filter-emptied column distinguishable (`EmptyColumnPlaceholder`, `:2598`)

**Scope justification.** This is a second, separately visible UI change and does
not fix the crash-shaped defect above. It is in scope deliberately: an
indistinguishable `(empty)` is *why* this bug survived a full verification run and
was filed as a nonexistent relaunch bug. Without it the same stray filter reads
the same way next time. It lands as its **own commit** (see Commits) so the
root-cause fix stays narrowly reviewable, and it is behind no behavioural change
other than the placeholder's label.

**No count in the label.** An earlier draft said `(N hidden by filter)`. There is
no consistent N:

| column shape | mounted filter units | parent tasks hidden |
|---|---|---|
| ungrouped cards | 1 per task | 1 per task |
| expanded group, all filtered | N cards **+ 1 header** | N |
| collapsed group | **1 header only** | `len(header.members)` |
| expanded parent | 1 parent card **+ 1 per child** (`task_block:4004,4012`) | 1 |

"Rendered rows" and "hidden tasks" therefore diverge in three of four shapes, and
neither matches `ColumnHeader`'s count (`:3947`), which counts **parent tasks
only**. A number would have to be reconciled against that header on every shape.
It is also redundant: the placeholder is shown **only** when nothing in the column
is visible (`:8676-8678`), so the count could only ever equal the header's own
count already displayed one row above. The label carries the one bit the header
cannot: *why* the body is empty.

```python
class EmptyColumnPlaceholder(Static):
    EMPTY_LABEL = "(empty)"
    FILTERED_LABEL = "(hidden by filter)"

    def __init__(self, col_id: str):
        super().__init__(self.EMPTY_LABEL, classes="empty-placeholder")
        self.column_id = col_id

    def set_filtered(self, filtered: bool) -> None:
        """`(hidden by filter)` when a filter emptied the column, `(empty)` when
        it truly holds nothing (t1491).

        Deliberately carries no count: rendered rows and hidden tasks diverge
        across grouped / collapsed / expanded-parent columns, and the only number
        that would be correct is the one `ColumnHeader` already shows.

        Label only — identity, `column_id` and focusability are untouched, so
        every focus path keyed off this widget (`_column_focus_target`,
        `action_focus_board`, `_refocus_column`, `apply_filter`'s rescue) is
        unaffected."""
        self.update(self.FILTERED_LABEL if filtered else self.EMPTY_LABEL)
```

### 5. Drive the label from `apply_filter` (`:8572`)

The decision needs exactly one extra bit per column — *did this column mount any
filter unit at all* — which is immune to the counting ambiguity above. Accumulate
it beside the existing `cols_with_visible`, in **both** the unit loop (`:8626`)
and the group-header loop (`:8656`), for every unit regardless of visibility:

```python
        cols_with_visible = set()
        cols_with_units = set()      # mounted a unit this pass, visible or not
        ...
            cols_with_units.add(unit.column_id)
            set_unit_display(unit, v)
            if v:
                cols_with_visible.add(unit.column_id)
```

and label the placeholder before flipping it (`:8676-8678`):

```python
        for placeholder in self._filter_placeholders(cols):
            show = placeholder.column_id not in cols_with_visible
            if show:
                placeholder.set_filtered(placeholder.column_id in cols_with_units)
            set_unit_display(placeholder, show)
```

This is correct on every shape in the table: a collapsed-group-only column mounts
a header and is therefore `filtered`; a genuinely empty column mounts nothing and
stays `(empty)`; a column that mounts only child cards is `filtered`. A collapsed
*column* never reaches here at all — `compose` returns after
`CollapsedColumnPlaceholder` (`:3958`), so no `EmptyColumnPlaceholder` exists and
`_filter_placeholders` yields none.

A scoped pass only relabels placeholders in `cols`, matching the existing scoping
contract. `_recompose_column` rebuilds the placeholder with the default label and
is already followed by a scoped `apply_filter({col_widget.col_id})` (`:11235`),
so the label re-derives there for free.

### 6. Correct the task's Problem and acceptance criteria

`aitasks/t1491_board_renders_no_task_cards_when_relaunched_in_the_same_pane.md`
describes a relaunch bug that does not exist. Rewrite `## Problem`,
`## Reproduction` and `## Acceptance criteria` against the confirmed root cause
(startup focus on `#search_box`; `q` and every other non-priority key swallowed;
a stray filter renders as an indistinguishable `(empty)`), keeping the original
report as a "Reported as" note so the provenance survives. AC #3 becomes: a live
tmux pin that presses bare `q` on a fresh board and asserts the pane returns to
the shell, then relaunches in the same pane and asserts card presence.

## Tests

### `tests/test_board_startup_focus.py` — headless, normal pool

Sibling pattern: `tests/test_board_empty_column_focus.py` (`enter_fixture_tree` +
`run_test(size=(160, 48))` + a `_settle(pilot)` helper).

1. **Startup focus is a board anchor.** After boot, `app.screen.focused` is a
   `TaskCard` / `GroupHeader` / `EmptyColumnPlaceholder`, not `Input` and not
   `HorizontalScroll`. **Fails today** — today it is `HorizontalScroll#board_container`.
2. **`q` quits.** `await pilot.press("q")`; assert the app is no longer running.
   *State honestly in the docstring that this half already passes headless* — it
   is a guard against a future regression, not a reproduction of this bug.
3. **Placeholder relabel — one case per column shape.** Set
   `app.search_filter = "zzz-no-such-task"`, call `app.apply_filter()`, settle,
   then assert on `placeholder.render().plain` (render level, not the model):

   | fixture column | expected |
   |---|---|
   | ungrouped cards, all filtered out | `(hidden by filter)` |
   | **expanded** group, all members filtered out | `(hidden by filter)` |
   | **collapsed** group, no member cards mounted | `(hidden by filter)` |
   | genuinely empty column (no tasks) | `(empty)` |

   The two group rows are the cases a count-based label got wrong, and they are
   the reason they are pinned explicitly rather than folded into one assertion.
   Also assert the un-filtered board (empty `search_filter`) leaves the empty
   column at `(empty)` — the off-transition, so the filtered assertion cannot
   pass vacuously.

   `tests/lib/board_fixture.py`'s `RICH_TOPOLOGY` / `FixtureTask` already model
   groups; extend the topology if it lacks a collapsed group, and seed
   `settings["collapsed_groups"]` with `board_groups.group_key(col, slug)` —
   never a hand-built f-string.

### `tests/test_board_startup_focus_live.py` — live tmux, serial carve-out

This is the pin that actually fails on today's code with the reported symptom.
Modelled on `tests/test_board_header_row_live.py` (per-PID `-L` socket,
`AITASKS_TMUX_SOCKET` exported into the child, `kill-server` teardown, boot budget
that **fails** rather than skips; `SkipTest` only when tmux/session/pane is
unavailable). Raw `tmux` is legal here — `tests/test_no_raw_tmux.sh` scans only
`.aitask-scripts/`.

Fixture: an isolated project built in `setUpClass` — a `.aitask-scripts` **symlink**
to `REPO_ROOT/.aitask-scripts` (13 MB; `ait` cds to its own dir, so cwd and
therefore `TASK_DIR="aitasks"` still resolve inside the fixture), a copy of `ait`,
and a synthetic `aitasks/` with a handful of tasks split across two configured
columns plus one deliberately empty column. Metadata payload follows
`tests/lib/board_fixture.py::_write_common`: `board_config.json`,
`board_config.local.json` with `auto_refresh_minutes: 0`, `project_config.yaml`,
and `gates.yaml` copied from `.aitask-scripts/gates_reference.yaml`.

The pane runs an interactive shell (**no** command argument to `new-session`) so
keys can be sent, unlike `test_board_header_row_live.py`.

Sequence and assertions:

1. `send-keys "./ait board" Enter`; poll `capture-pane` for `Task filter`; assert
   a known card title is present.
2. `send-keys q`; poll `#{pane_current_command}` until it leaves the interpreter.
   **Assert it returns to the shell within the budget** — today it stays `python`.
   On failure, attach the capture *and* the search-box line so the FAIL message
   carries the root cause, not just a timeout.
3. `send-keys "./ait board" Enter`; poll; assert the known card title is present
   again and that `(empty)` appears exactly once (the deliberately empty column) —
   the AC's relaunch clause, now passing for the right reason.

Add `test_board_startup_focus_live.py` to `SERIAL_CARVE_OUT` in
`tests/run_all_python_tests.sh:80` (a hardcoded basename array — no glob, no
marker). Two board boots under a loaded xdist pool would otherwise flake the
wall-clock budget.

**Negative control** (one mutation, isolated copy): revert *only* the
`call_after_refresh(self._claim_startup_focus)` line and confirm the live test
fails at step 2 with the `(empty)`-everywhere capture attached. A passing
negative control means the pin is wrong.

## Verification

```bash
# unit / integration
bash tests/run_all_python_tests.sh --test-dir tests            # read only the last line
bash tests/run_all_python_tests.sh tests/test_board_startup_focus.py
python tests/test_board_startup_focus_live.py                  # live, ~2 board boots

# real entry point, real terminal — the acceptance surface
#   launch board in an isolated pane, press bare `q`, assert the shell is back;
#   relaunch in the same pane, assert cards render.
```

Manual checks against the live board (isolated `-L` socket, isolated fixture):

* fresh launch → the leftmost card is focused (double-cyan border), `q` quits
  with no prior Tab/Esc/click;
* `Tab` still focuses the search box, `Esc` still returns to the board;
* typing a non-matching search renders `(N hidden by filter)`, not `(empty)`;
* at a **narrow** terminal (80 cols) the relabelled placeholder is still readable
  inside a 40-cell column (`(hidden by filter)` is 18 cells);
* a modal opened at startup is not stolen from (`_modal_is_active` guard);
* `shellcheck` is not needed (no shell changes).

## Commits

Two code commits, so the root-cause fix is reviewable without the UI change
mixed in. Both carry the task's `issue_type` (`bug`) and the `(t1491)` tag that
`aitask_issue_update.sh` keys on:

1. `bug: Claim board startup focus so single-key bindings fire (t1491)` — steps
   1–3 + `tests/test_board_startup_focus.py` (focus + `q` cases) +
   `tests/test_board_startup_focus_live.py` + the `SERIAL_CARVE_OUT` entry.
2. `bug: Distinguish a filter-emptied board column from an empty one (t1491)` —
   steps 4–5 + the placeholder-relabel test cases.

The task-file correction (step 6) goes in the usual `ait:`-prefixed task/plan
commit via `./ait git`, never mixed with code.

## Follow-ups (not in scope)

* No other TUI sets `AUTO_FOCUS`, and monitor / codebrowser / brainstorm /
  settings each have their own `on_mount`. Whether any shares this defect is an
  audit worth its own task — surface it at Step 8b (upstream defect).
* `/home/ddt/Work/aitasks/importlib.util` is a 24 MB untracked ImageMagick/
  PostScript file sitting in the repo root under a stdlib module name. Unrelated
  to this task; flag it to the user rather than deleting it unasked.

## Step 9 (Post-Implementation)

Merge into the branch recorded in this plan's `Output branch:` header, run the
declared gates via `./ait gates run 1491`, then archive with
`./.aitask-scripts/aitask_archive.sh 1491`.

## Risk

### Code-health risk: low
- The placeholder relabel touches a widget four focus paths key off
  (`_column_focus_target`, `action_focus_board`, `_refocus_column`,
  `apply_filter`'s focus rescue); a change to its identity or display semantics
  would break column focus. Confined to the rendered label — `column_id`,
  `can_focus` and the `display` writes are untouched · severity: low ·
  → mitigation: none needed (covered by `tests/test_board_empty_column_focus.py`,
  which already pins every anchor case, plus the new render-level assertions)
- The relabel is a second, independently visible UI change riding along with a
  bug fix, which widens what a reviewer must judge. Bounded by splitting it into
  its own commit and by pinning one case per column shape rather than a single
  aggregate assertion · severity: low · → mitigation: none needed
- The `filtered` bit is derived inside `apply_filter`, the board's measured hot
  path (~13 ms whole-board pass). The addition is one `set.add` per unit already
  being iterated, and the label write happens only for a column actually showing
  a placeholder · severity: low · → mitigation: none needed
- Startup focus now lands on a card instead of the search Input, changing the
  first keystroke's destination for every existing board user. This is the state
  `Escape` already produced, and the search box's own placeholder ("Tab to focus")
  documents it as intended · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The task's stated goal ("fix the relaunch bug") rests on a misdiagnosis, so
  delivering the correct fix means rewriting its acceptance criteria (step 6). The
  premise is disproved by a positive control — a relaunch after a *real* quit
  renders all cards — so the rewrite is evidence-backed, not a judgement call ·
  severity: low · → mitigation: none needed
- A headless pin cannot reproduce the symptom, so the regression guarantee rests
  on the live tmux test and its boot budget. Mitigated by the negative control and
  by the serial carve-out that keeps the budget honest · severity: low ·
  → mitigation: none needed

No mitigations proposed: both dimensions are `low` and every identified risk is
already covered by the plan's own verification.
