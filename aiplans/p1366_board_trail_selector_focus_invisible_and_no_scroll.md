---
Task: t1366_board_trail_selector_focus_invisible_and_no_scroll.md
Worktree: (none — current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1366 — Board trail selector: invisible focus + non-scrolling dialog

## Context

In `ait board`'s By-Trail view, `s` opens `TrailSelectScreen`. ↑/↓ appear to do
nothing. The task's diagnosis is correct and I re-confirmed every claim against
the real `KanbanApp` booted on `tests/lib/board_fixture.py`.

> **Re-checked at HEAD `2c6e237bf`, after t1365 landed.** t1365 ("By-Trail
> discovery misses a newly created trail") touched only the *discovery* layer —
> `dedupe_trail_records`, `load_trail_blob`, `run_trail_drift`, `TaskManager`,
> `_open_trail_select` — and left `TrailSelectScreen`, `TrailSelectItem`,
> `#dep_picker_dialog` and `dep-item-focused` untouched, exactly as the task's
> "Related (not folded)" note predicted. All four defects reproduce byte-for-byte
> on the new HEAD; every line anchor below is re-derived from it, and the working
> tree is now clean.

- **Focus moves, the frame does not.** After `down`: focus index `1`, classes
  `[[], ['dep-item-focused'], []]`, and the composited frame is **byte-identical**.
  `TrailSelectItem` adds `dep-item-focused`, but the only rules for that class are
  `DepPickerItem.dep-item-focused` / `ChildPickerItem.dep-item-focused`. **Five of
  the seven** focusable row classes have *no* focus indicator at all today.
- **The dialog clips itself.** `#dep_picker_dialog` is `height: auto; max-height: 50%`
  with no overflow rule and `Container` does not scroll (`allow_vertical_scroll: False`).
  At 80×24 with just **3** trails the `Cancel` button is already off-dialog.
- **The hint clips mid-word.** `Label` defaults to `width: auto`, so the title
  overflows the 42-col content box and renders `…Esc to c`. It never mentions ↑/↓.

The id `#dep_picker_dialog` is shared by **19** `ModalScreen`s, so the fix must land
at the shared sink — but not *all* 19 want the same behaviour (see Design).

## Design

### 1. `PickerItem` base class — one focus rule for every row type

Add a shared base and reparent the seven focusable row classes onto it. Each keeps
its own `__init__` / `render` / `on_key` / `on_click`; only `can_focus`,
`on_focus`, `on_blur` move up.

```python
class PickerItem(Static):
    """Focusable row inside a `#dep_picker_dialog` modal.

    Owns the focus-visibility contract for every picker row so a new row type
    cannot ship without a highlight (t1366). `CrossRepoRefItem` is deliberately
    NOT a subclass: its styling lives in `CrossRepoRefPickerScreen.DEFAULT_CSS`,
    and App-level CSS outranks widget `DEFAULT_CSS`, so reparenting it would
    make the rules below silently beat its own.
    """

    can_focus = True

    def on_focus(self):
        self.add_class("dep-item-focused")

    def on_blur(self):
        self.remove_class("dep-item-focused")
```

Reparent (drop each class's now-duplicate `can_focus`/`on_focus`/`on_blur` — leaving
them would double-dispatch):

| Class | line |
|---|---|
| `GateChoiceItem` | 2377 |
| `TrailSelectItem` | 2459 |
| `DepPickerItem` | 3640 |
| `ChildPickerItem` | 3939 |
| `FoldedTaskPickerItem` | 3995 |
| `FileReferenceItem` | 4052 |
| `ColumnSelectItem` | 5414 |

Define `PickerItem` just above `GateChoiceItem` (~line 2377) — every subclass is
defined after it. (`CrossRepoRefItem`, 3782, is the 8th class with this shape and
stays out — see the docstring above.)

CSS (replacing the four per-type rules at 5660–5663):

```
    PickerItem { height: auto; width: 100%; padding: 0 1; }
    PickerItem.dep-item-focused { background: $primary 20%; outline-left: thick $accent; }
    DepPickerItem { height: 1; }
    ChildPickerItem { height: 1; }
```

- Textual type selectors match the whole MRO (`dom.py:592` builds `_css_type_names`
  from `_css_bases`), so one `PickerItem` rule styles all seven — verified live.
- **`outline-left`, not `border-left`.** Outline paints over the content area and
  does not resize it. Measured on a 2-line row: `border-left` → content width
  85 focused / 86 blurred (reflow, row-height jump on the multi-line trail rows);
  `outline-left` → 86 / 86. This is what lets AC2's "cannot assume `height: 1`" hold.
- `padding: 0 1` is load-bearing, not cosmetic: it gives the outline a blank column
  so no glyph is covered. Cost: a uniform +1 column indent on the five rows that had
  no rule before.
- **Source order matters** — `DepPickerItem { height: 1; }` must come *after*
  `PickerItem { height: auto; … }`; both are specificity `(0,0,1)`, so order decides.
- `query(DepPickerItem)` still narrows to that exact class (`dom.py:1415` filters by
  `selector.__name__`), so `tests/test_board_detail_nested_actions.py:145` is unaffected.

### 2. Scroll + pinned hint — scoped to the picker family via a marker class

`overflow-y: auto` and a docked title must **not** go on all 19 screens. Verified
against the real classes:

- Global `dock: top` **collapses** the three label-only confirm dialogs
  (`RemoveDepConfirmScreen`, `DeleteConfirmScreen`, `DeleteColumnConfirmScreen`):
  their only flow child is the title, so `height: auto` resolves to **0**. Probe on
  the real `RemoveDepConfirmScreen`: dialog `height=4`, `content_size.height=0`,
  title rendered *below* the buttons, both outside the box.
- Global `overflow-y: auto` gives the three `SelectionList` screens a nested
  double scrollbar (`OptionList` is `height: auto; max-height: 100%`, which already
  overlaps the docked buttons by 2 rows).

So the new behaviour rides a `picker-dialog` marker class applied alongside the id:

```
    #dep_picker_dialog.picker-dialog { overflow-y: auto; }
    .picker-dialog #dep_picker_title { width: 100%; dock: top; }
```

Change `with Container(id="dep_picker_dialog"):` →
`with Container(id="dep_picker_dialog", classes="picker-dialog"):` in exactly the
seven focus-driven pickers the task enumerates:

`GateChoiceScreen` (2414), `TrailSelectScreen` (2510), `DependencyPickerScreen` (3698),
`ChildPickerScreen` (3981), `FoldedTaskPickerScreen` (4037),
`FileReferencePickerScreen` (4089), `ColumnSelectScreen` (5456).

`TopicSortModeScreen` (2330) is excluded on purpose (`TopicSortModeItem.can_focus = False`;
selection lives on the screen, so `set_focus`'s scroll-into-view never fires) — add a
one-line comment saying so. The remaining 11 screens are untouched.

> **Deviation from the answered question, stated explicitly:** you chose "Pin it
> (dock: top)". It is still pinned — but scoped to the picker family rather than
> applied globally, because global docking provably breaks three confirm dialogs.

Scroll-into-view then comes for free: `Screen.set_focus` calls `scroll_to_center`
when the container permits scrolling (`screen.py:1138-1145`).

### 3. Hint text (AC4)

`TrailSelectScreen.compose`, line 2511:

```python
yield Label(
    "Select trail — [dim]↑/↓ move · Enter open · Esc cancel[/]",
    id="dep_picker_title",
)
```

Verified at 80 cols: wraps to 2 centred lines, fully rendered, no truncation.
(Compact `·`-separated rather than `TopicSortModeScreen`'s comma phrasing because the
docked header costs list rows; the longer form needs 3.)

### 4. Latent tidy the task flags

Add `event.prevent_default()` / `event.stop()` to `TrailSelectItem.on_key` (2489) and
`GateChoiceItem.on_key` (2392), matching `DepPickerItem` (3656-3663) and
`ColumnSelectItem` (5426-5430). No observed leak — consistency only.

## Files to modify

- `.aitask-scripts/board/aitask_board.py` — all source changes above.
- `tests/test_board_bytrail_view.py` — regression tests (AC5 names this file and
  `ByTrailPilotTests` as their home).

The concurrent session's work has landed (t1243_3, t1294, t1269, t1365) and the tree
is clean, so the earlier "stage only my own hunks" hazard is gone. Still check
`git status` / `git diff --cached` before staging at Step 8 — another session may
start again mid-task.

## Tests — `ByTrailPilotTests` (`tests/test_board_bytrail_view.py`)

Add one helper to `ByTrailTestBase`, beside the existing `_screen_rows`:

```python
    @staticmethod
    def _dialog_text(app, widget) -> str:
        """Composited frame sliced to `widget`'s columns, chrome stripped.

        Whole-screen flattening interleaves the board rendered on either side of
        a centred modal, so a phrase that wraps inside the dialog is split by
        board text and no assertion can match it.
        """
        r = widget.region
        rows = [s.text for s in
                app.screen._compositor.render_strips(app.screen.size)]
        raw = " ".join(row[r.x:r.right] for row in rows[r.y:r.bottom])
        return " ".join(
            "".join(" " if "▀" <= c <= "▟" else c for c in raw).split())
```

Four tests, each verified to fail against current code:

1. `test_trail_select_focus_is_visible_in_frame` — 3 trails **with overlap
   sub-lines** @ 80×24. Capture frame, `press("down")`, capture again; assert the
   frames differ **and** the `└ also references:` sub-line is on the frame (AC1 +
   the multi-line half of AC2). Ground truth alongside: focused row's
   `styles.background` ≠ an unfocused sibling's, and blurring restores it.
   *Pre-fix: frames byte-identical.*
2. `test_trail_select_dialog_scrolls_and_cancel_is_reachable` — 10 trails @ 100×30.
   Assert `allow_vertical_scroll`; focus the last row → `screen.can_view_entire`;
   focus `#btn_dep_cancel` → `can_view_entire` and `"Cancel"` in `_dialog_text`.
   *Pre-fix: `allow_vertical_scroll` False.*
3. `test_trail_select_hint_fits_80_cols` — 10 trails @ 80×24; assert
   `"Select trail — ↑/↓ move · Enter open · Esc cancel" in _dialog_text(app, dialog)`.
   *Pre-fix: no ↑/↓ at all, and the hint clips to `Esc to c`.*
4. `test_gate_choice_focus_is_visible_in_frame` (AC6) — `GateChoiceScreen` with two
   gates; frame changes on `down`. Proves the fix landed at the shared sink.
   *Pre-fix: frames byte-identical.*

Settle with `pilot.pause()` ×5 + `pilot.wait_for_scheduled_animations()` before every
render assertion — the scroll-into-view is both deferred (`call_later`) and animated.

## Verification

1. **Prove the harness discriminates (AC5).** Add the tests *first*, run them against
   unmodified source, record the four failures:
   ```bash
   ~/.aitask/venv/bin/python -m pytest tests/test_board_bytrail_view.py::ByTrailPilotTests -v
   ```
2. Apply the source changes; re-run the same command — all pass.
3. Full file, to catch collateral in the other 15 By-Trail classes:
   ```bash
   ~/.aitask/venv/bin/python -m pytest tests/test_board_bytrail_view.py -v
   ```
4. Neighbours that touch the shared sink:
   ```bash
   ~/.aitask/venv/bin/python -m pytest tests/test_board_detail_nested_actions.py \
     tests/test_board_work_report.py tests/test_board_picker_tab_nav.py \
     tests/test_board_topic_group.py tests/test_shortcut_scopes.py -v
   ```
5. **Live eyes.** `ait board` → `z` (By-Trail) → `s`: ↑/↓ visibly highlight, the hint
   is pinned and readable at 80 cols, a long list scrolls and `Cancel` is reachable.
   Also open a confirm dialog (delete a task, then cancel) to confirm it is unchanged.
6. Full suite before commit — read only the last line:
   ```bash
   bash tests/run_all_python_tests.sh
   ```

## Step 9 (Post-Implementation)

Current-branch mode: no worktree/branch to merge or clean up. Verify build/gates, then
archive with `./.aitask-scripts/aitask_archive.sh 1366`.

## Risk

### Code-health risk: medium
- Blast radius: 7 class reparentings + 7 `compose()` edits + a CSS block shared by
  19 modals. Scoping the new behaviour behind `.picker-dialog` keeps 12 of the 19
  bit-identical, and the two globally-applied changes (`PickerItem` styling, the
  base class) are additive — but a mistake here reaches the whole modal layer
  · severity: medium · → mitigation: none — accepted (each of the 19 shapes was
  probed; the untouched-confirm-dialog assertion is part of the verification run)
- The `PickerItem`/`DepPickerItem` height override depends on CSS **source order**
  (equal specificity); a later reorder of the CSS block silently restores `height: auto`
  on the two `height: 1` rows · severity: low · → mitigation: none — accepted
- A third dialog-body id (`#orphan_parent_label`) has no CSS rule at all and
  `#delarch_label` keeps `width: auto`; both stay clipped at 80 cols, and the three
  label-only confirm dialogs remain keyboard-unreachable when their body overflows.
  Pre-existing, deliberately out of scope, but the sink is now half-fixed
  · severity: low · → mitigation: confirm_dialog_body_label_split

### Planned mitigations
- timing: after | name: confirm_dialog_body_label_split | type: enhancement | priority: low | effort: medium | addresses: half-fixed shared sink (confirm-dialog family) | desc: Move the body text of RemoveDepConfirmScreen / DeleteConfirmScreen / DeleteColumnConfirmScreen out of #dep_picker_title into a second Label so the dialogs stop collapsing under dock:top, then extend the width:100% + overflow-y:auto treatment to the confirm family including #delarch_label and the unstyled #orphan_parent_label.

### Goal-achievement risk: low
- Every acceptance criterion was demonstrated end-to-end on the real `KanbanApp`
  before this plan was written — AC1 frame-change, AC2 multi-line sub-line render,
  AC3 scroll + reachable `Cancel`, AC4 untruncated pinned hint, AC6 sibling picker —
  and the assertion helper itself was proven to work. The failing baseline was then
  re-confirmed at HEAD `2c6e237bf` after t1365 landed. `None identified.`

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, in the planned order.
  1. Tests first, in `ByTrailPilotTests` (`tests/test_board_bytrail_view.py`), plus
     three helpers on `ByTrailTestBase`: `_dialog_text` (composited frame sliced to a
     widget's columns, block-drawing chrome collapsed), `_settle` (pauses +
     `wait_for_scheduled_animations`), `_mk_trail_info`.
  2. `PickerItem(Static)` added above `GateChoiceItem`; all seven row classes
     (`GateChoiceItem`, `TrailSelectItem`, `DepPickerItem`, `ChildPickerItem`,
     `FoldedTaskPickerItem`, `FileReferenceItem`, `ColumnSelectItem`) reparented and
     their duplicated `can_focus`/`on_focus`/`on_blur` deleted — exactly one
     `add_class("dep-item-focused")` site remains in the file.
  3. CSS: two per-type focus rules → `PickerItem { height: auto; width: 100%;
     padding: 0 1; }` + `PickerItem.dep-item-focused { background: $primary 20%;
     outline-left: thick $accent; }`, with `DepPickerItem`/`ChildPickerItem
     { height: 1; }` kept *after* them as sizing-only overrides.
  4. `picker-dialog` marker class added to the seven focus-driven pickers, carrying
     `overflow-y: auto` and `width: 100%; dock: top` on the title.
  5. Trail hint → `Select trail — ↑/↓ move · Enter open · Esc cancel`;
     `event.prevent_default()`/`event.stop()` added to `TrailSelectItem.on_key` and
     `GateChoiceItem.on_key`.

- **Deviations from plan:** None in the delivered code. The *design* deviated from
  the answered planning question during planning itself (recorded in the plan body):
  the user chose "pin the hint with `dock: top`", but applying it globally to all 19
  `#dep_picker_dialog` modals was proven to collapse the three label-only confirm
  dialogs to `content_height = 0` with the title drawn below the buttons. The hint is
  still pinned — scoped to the picker family via the `picker-dialog` marker.

- **Issues encountered:**
  - `outline-left` vs `border-left` — `border-left` steals a content column
    (measured 85 focused / 86 blurred), which reflows and changes the height of the
    multi-line trail rows. `outline-left` paints over the content area without
    resizing it (86 / 86). This is what makes AC2's "cannot assume `height: 1`" hold.
  - **The first live-terminal verification produced a false negative.** `ait board`
    boots with focus in the search `Input`, so the scripted `z`/`s` were typed as
    text (the search box read `zs`), the modal never opened, and the two captured
    frames were identical — which looks exactly like the unfixed defect. Fixed by
    sending `Escape` first and adding a guard that asserts "Select trail" is on the
    frame before the comparison is trusted. A capture-based check needs a
    did-the-thing-open assertion or it silently reports harness failure as defect.
  - `pytest` is not installed in `~/.aitask/venv`; used
    `python -m unittest tests.<module>` throughout.

- **Key decisions:**
  - Shared **base class** rather than a bare `.dep-item-focused` CSS selector: the
    padding that keeps the focus bar off the first glyph needs a shared selector
    anyway, and the base makes a future picker row styled by construction.
  - **Scoped** marker class rather than applying the new behaviour at the raw
    `#dep_picker_dialog` id: 19 modals share that id and only ~7 want scrolling.
    Keeps 12 dialogs bit-identical (verified: `vscroll=False`, `width: auto` titles).
  - `TopicSortModeScreen` excluded with an inline comment — its items are
    `can_focus = False`, so focus-driven scroll-into-view would never fire.

- **Upstream defects identified:**
  - `.aitask-scripts/board/aitask_board.py:3638 — OrphanParentArchiveScreen's body label uses id `orphan_parent_label`, which has no CSS rule anywhere in the file; it renders with bare `Label` defaults (`width: auto`) and is clipped horizontally at narrow widths.`
  - `.aitask-scripts/board/aitask_board.py:5635 — `#delarch_label` (DeleteArchiveConfirmScreen's body) keeps `width: auto`, so a long ARCHIVED/DELETED listing is clipped mid-word at 80 columns rather than wrapping.`
  - `.aitask-scripts/board/aitask_board.py:3432,3467,5310 — RemoveDepConfirmScreen / DeleteConfirmScreen / DeleteColumnConfirmScreen put their entire body text inside `#dep_picker_title`, whose only sibling is the docked button row. That shape makes the dialog's `height: auto` resolve to 0 under `dock: top`, and leaves overflowing bodies reachable by mouse wheel only. Covered by the planned mitigation `confirm_dialog_body_label_split`.`

- **Verification:** 4 new tests fail against unmodified source and pass after the fix;
  `ByTrailPilotTests` 11/11; `test_board_bytrail_view` 93/93; all 26 board test
  modules 472 passed / 1 skipped; unscoped-dialog isolation probed directly; and a
  real 80×24 tmux capture of `./ait board` → `z` → `s` shows the focus bar moving,
  the hint pinned and unclipped, the scrollbar thumb moving, and the Cancel button
  scrolling into view.
