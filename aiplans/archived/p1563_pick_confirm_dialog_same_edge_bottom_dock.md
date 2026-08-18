---
Task: t1563_pick_confirm_dialog_same_edge_bottom_dock.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1563 — Undock `TaskPickConfirmDialog`'s footer off the confirm row's edge

## Context

`TaskPickConfirmDialog` (`.aitask-scripts/monitor/monitor_shared.py`) docks
**two sibling widgets to the same bottom edge** of `#task-detail-dialog`:
`#pick-confirm-row` (`dock: bottom; height: auto`) and, later in DOM order,
`#task-detail-footer` (`dock: bottom; height: 1`, inherited from the
`TaskDetailDialog` base and redundantly restated in the subclass).

Under Textual 8.2.7 same-edge docked siblings do not stack — unequal heights
produce **overlapping** regions and the later-in-DOM widget wins. This is the
same bug class as t1499 (minimonitor top chrome) and t1278 (board
`#filter_area`).

**Confirmed on a composited frame**, not inferred. Probing the real dialog via
the existing `_ConfirmHost` fixture, `confirm_row.bottom > footer.y` holds in
**all 8** size × variant combinations probed. In the wide (`narrow=False`)
variant it destroys visible content — at 80×24 the buttons' bottom border row
is painted over by `q/Esc: cancel`:

```
 row 17: '  ▔▔▔▔▔▔▔▔▔▔ ▔▔▔▔▔▔▔▔▔▔ ▔▔▔▔▔▔▔▔▔▔   '   <- top border
 row 18: '   Launch anyway  Move to column  Cancel  '   <- labels
 row 19: '  q/Esc: cancel                       '   <- footer OVER the bottom border
```

In the narrow variant (the only one production uses — `minimonitor_app.py:1912`
is the single call site and always passes `narrow=True`) the overwritten row
happens to be the last button's dead bottom *margin*, so nothing legible is lost
**today**. That is luck, not design: the geometry is wrong, one row of the
confirm row is destroyed every frame, and the next control added to the row
starts eating a real label.

**Outcome:** at most one docked widget per edge, the confirm row's rendered
geometry no longer overlapped, and a render-level regression guard so this
cannot silently return. Building that guard also surfaced a second, independent
footer defect in the same block — the narrow plan hint is truncated mid-word —
which is fixed here too (see below), because the guard cannot assert a complete
footer while it ships broken.

## Approach

Wrap the confirm row and the footer in **one** docked container, per the
`aidocs`/t1499 rule ("wrap the group in ONE docked container rather than adding
a second `dock:` sibling"). This preserves the visual order (controls above the
hint line, both pinned at the bottom) and preserves the **load-bearing property**
documented at `monitor_shared.py:1508-1513` — the body scroll gives up space,
not the controls — because the wrapper itself is what docks.

Undocking the footer costs one row that the overlap previously stole. It is
repaid under `.narrow` by dropping the dead trailing margin below the last
stacked button — the very row the footer paints over today. Measured across
9 size × variant combinations, this lands **content visibility identical to the
current baseline at every size** (including the pre-existing 40×16 clip of the
eligibility warnings, which is unchanged).

### Files to modify

**1. `.aitask-scripts/monitor/monitor_shared.py` — `TaskPickConfirmDialog`**

`DEFAULT_CSS` (`:1486-1521`): introduce the docked wrapper, undock the confirm
row, and override the base's footer dock.

```css
/* The ONE docked widget on this edge (t1563). #pick-confirm-row and
   #task-detail-footer used to dock: bottom individually; Textual 8.2.7 gives
   same-edge docked siblings overlapping regions and the later-in-DOM widget
   wins, so the footer painted over the confirm row's last row every frame.
   NEVER re-add `dock:` to either child — dock this wrapper instead. Same bug
   class as t1499 (minimonitor top chrome) and t1278 (board #filter_area). */
TaskPickConfirmDialog #pick-bottom-dock {
    dock: bottom;
    width: 100%;
    height: auto;
}
TaskPickConfirmDialog #pick-confirm-row {
    width: 100%;
    height: auto;
    margin: 1 0 0 0;
}
/* The base docks this to the dialog; here it flows inside the wrapper. */
TaskPickConfirmDialog #task-detail-footer { dock: none; }
```

Keep the existing "Docked, not in normal flow…" comment, retargeted to
`#pick-bottom-dock` — the rationale it records (a flow-laid confirm row
overflows *below* the dialog at ~20 rows) is still exactly why the wrapper is
docked.

In the `.narrow` block, reclaim the dead trailing margin:

```css
/* Repays the row the footer no longer steals (t1563): the last stacked
   button's bottom margin is a separator with nothing after it. */
TaskPickConfirmDialog.narrow #pick-buttons Button:last-of-type { margin: 0; }
```

`compose` (`:1590-1631`): nest the existing `#pick-confirm-row` container and
the `#task-detail-footer` `Static` inside `with Container(id="pick-bottom-dock"):`.
Same widgets, same ids, same order, same dismissal contract.

**Second, separate defect found while verifying the footer** — the footer's plan
hint is truncated mid-word in the narrow variant. `q/Esc: cancel  p: switch
plan/task` is 34 columns; the narrow footer is 30 and `height: 1`, so it renders
`q/Esc: cancel  p: switch` at **every** narrow size (40×16 … 40×50). The `p`
affordance is therefore invisible in minimonitor whenever the task has a plan —
which is the common case. This is **pre-existing**, identical in baseline and
fixed, and was hidden because `_task_info` hardcodes `plan_content=None`, so no
existing narrow test ever renders the long form. Fix it in the same `compose`,
since the guard being added must be able to assert a complete footer:

```python
plan_hint = ""
if self._info.plan_content:
    # 34 cols does not fit the 30-col narrow footer, and `height: 1` clips
    # rather than wraps — the hint rendered as "p: switch" (t1563).
    plan_hint = ("  [dim]p: plan/task[/]" if self._narrow
                 else "  [dim]p: switch plan/task[/]")
```

Measured: `q/Esc: cancel  p: plan/task` = 27 of 30 columns, complete at every
narrow size. The wide variant keeps the full wording. `TaskDetailDialog`'s own
footer is untouched — the base has no narrow variant.

**Test fixture support (`tests/test_minimonitor_pick_by_number.py`):** add an
optional `plan_content: str | None = None` parameter to `_task_info` and to
`_ConfirmHost.__init__`, threaded into the `TaskInfo`. Defaults keep all 111
existing tests unchanged.

**2. `tests/test_minimonitor_pick_by_number.py` — new `BottomDockGeometryTests`**

Extend the existing file rather than adding one: `_ConfirmHost`, `_screen_text`,
`_flat` and `_assert_controls_inside` already live there. Follow the t1499 idiom
in `tests/test_minimonitor_top_chrome_render.py` (pairwise
`earlier.y + earlier.height <= later.y`, assertions on
`screen._compositor.render_strips()`).

Assert on the widget that **loses** the overlap — the confirm row, earlier in
DOM — never on the footer, which survives the fault intact:

- `test_confirm_row_and_footer_do_not_overlap` — sweep
  `((40,16),(40,20),(40,24),(40,30),(40,50))` × `narrow=True` and
  `((80,24),(80,30),(120,40))` × `narrow=False`, each **with and without**
  `plan_content`, using `subTest`; assert
  `confirm_row.y + confirm_row.height <= footer.y`, and that both are
  descendants of `#pick-bottom-dock`.
- `test_footer_is_contained_and_visible_at_the_tightest_size` — at `(40, 16)`,
  `narrow=True`, with and without plan content. Non-overlap alone is satisfied
  by a footer pushed *below* the viewport, which would lose the cancel hint
  entirely, so assert three things the inequality cannot: the footer region is
  inside `#task-detail-dialog` on **both** axes; `0 <= footer.y < len(strips)`;
  and the strip **at `footer.y`** contains `q/Esc: cancel` (the exact row, not
  the whole frame — a frame-wide `assertIn` would be satisfied by a stray
  match).
- `test_footer_does_not_paint_the_confirm_rows_last_row` — render-level: the
  strip at `confirm_row.bottom - 1` must not contain `q/Esc: cancel`.
- `test_button_bottom_border_survives_in_the_wide_variant` — at `(80, 24)`,
  `narrow=False`, the strip at `pick_buttons.bottom - 1` contains the `▁`
  bottom-border glyph (the row the footer destroys today).
- `test_narrow_content_visibility_matches_baseline` — at `(40, 20)` and
  `(40, 24)`, `narrow=True`, every probe string reaches the frame:
  `t1310 is Done`, `blocked by t1200`, `kill followed agent`, `keeps t77`,
  `Launch anyway`, `Move to column`, `Cancel`, `q/Esc: cancel`. This is what
  pins the margin reclaim as load-bearing; without it the fix silently costs a
  warning line at 40×20.
- `test_narrow_footer_hint_is_complete_with_plan_content` — the case no existing
  test covers. With `plan_content` set, sweep `(40,16),(40,20),(40,50)` ×
  `narrow=True`: the strip at `footer.y` contains **both** `q/Esc: cancel` and
  the complete `p: plan/task`, and `assertNotIn("p: switch", row)` — the
  truncated long form is what ships today, so without that negative half the
  test passes on the broken string. Paired wide case at `(80, 24)`,
  `narrow=False`: the full `p: switch plan/task` is present. Also assert
  `assertNotIn("…", row)` per the existing ellipsis idiom.
- `test_negative_control_footer_redocked` — patch `DEFAULT_CSS` replacing
  `#task-detail-footer { dock: none; }` with `dock: bottom;`, assert the patched
  CSS actually differs, and assert `test_confirm_row_and_footer_do_not_overlap`'s
  assertion raises `AssertionError`. One mutation, reaching the probed
  assertion, with the failing test named in the docstring.

Existing `NarrowRenderTests` (including `test_negative_control_without_narrow_css`,
which strips `.narrow` rules — the new one-line rule is stripped cleanly by
`_drop_narrow_rules`) must stay green.

## Verification

1. `~/.aitask/venv/bin/python tests/test_minimonitor_pick_by_number.py` — 111
   tests green today; must stay green plus the new cases.
2. `~/.aitask/venv/bin/python tests/test_minimonitor_top_chrome_render.py` —
   sibling guard, unaffected.
3. `bash tests/run_all_python_tests.sh` — read the **last** line only
   (`PYTHON SUITE: PASSED|FAILED`); do not pipe without `pipefail`.
4. Negative control must fail for the right reason: temporarily restore
   `dock: bottom` on the footer and confirm
   `test_confirm_row_and_footer_do_not_overlap` fails on the confirm-row
   assertion (not on a query or a size error).
5. Live eyeball in a real terminal: `ait minimonitor`, press `p`, and enter
   **a task that has a plan file** (so the footer carries the plan hint).
   Confirm the three stacked buttons render with no clipped row and the footer
   reads `q/Esc: cancel  p: plan/task` in full — not `p: switch`. Repeat with a
   task that has no plan to confirm the short footer is unchanged.

## Risk

### Code-health risk: low

- The `#pick-bottom-dock` wrapper inserts a DOM level between
  `#task-detail-dialog` and `#pick-confirm-row`; any selector or query assuming
  the confirm row is a *direct* child of the dialog would break. A repo-wide
  grep finds `#pick-confirm-row` / `#task-detail-footer` referenced nowhere
  outside `monitor_shared.py`. · severity: low · → mitigation: covered by the
  existing 111-test suite in Verification step 1.
- Reclaiming the last stacked button's bottom margin changes the `.narrow`
  spacing contract; a fourth button added later inherits the reclaim on the new
  last button, which is the intended behavior. · severity: low · → mitigation:
  pinned by `test_narrow_content_visibility_matches_baseline`.
- This is the **third** instance of one bug class — t1278 (board
  `#filter_area`), t1499 (minimonitor top chrome), t1563 — each found only after
  shipping, because the fault is silent. Fixing this dialog leaves any other
  same-edge docked pair in the repo undiscovered. · severity: medium ·
  → mitigation: t1572
- The plan-hint fix changes **user-visible wording** in the narrow variant
  (`p: switch plan/task` → `p: plan/task`), which is scope beyond the declared
  dock defect. It is included because the requested "assert the complete footer
  remains visible" guard cannot be written against a string that ships
  truncated. The wide wording is unchanged and the `p` binding itself is
  untouched. · severity: low · → mitigation: pinned by
  `test_narrow_footer_hint_is_complete_with_plan_content`, which asserts both
  variants' wording explicitly.

### Goal-achievement risk: low

- The user-visible win in the **production** (narrow) path is structural: the
  row the footer destroys there today is dead margin, so nobody currently sees a
  missing label. Observable content loss is in the wide variant, which no call
  site uses. If the expectation was a visible minimonitor repair, the honest
  outcome is "prevents the next control from being eaten", not "restores
  something you were missing". · severity: low · → mitigation: stated here; the
  wide-variant border test makes the content-loss claim concrete.

### Planned mitigations
- timing: after | name: sweep_same_edge_dock_siblings | type: chore | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: code-health — the same-edge dock bug class recurs (t1278, t1499, t1563) and is silent | desc: audit every Textual screen under .aitask-scripts/ for two or more siblings sharing a dock: edge, fix any found, and add a guard so the class stops recurring | created: t1572

## Implementation notes

Implemented as planned. One deviation, in the negative control only.

**The planned mutation did not reach the fault.** Re-docking *only* the footer
(`dock: none` → `dock: bottom`) leaves the geometry clean at both 40×20 and
80×24: inside `#pick-bottom-dock` the footer becomes the single docked child and
the confirm row simply flows above it. A control built on it passes, proving
nothing — which is what the first run showed (`AssertionError not raised`).

The fix's real invariant is **one docked widget per edge**, not "the footer is
undocked", so the control now restores the pre-fix arrangement: `dock: bottom`
on **both** wrapper children. Measured to reproduce the overlap in both variants.
Split into `_redock_both_children_css()` plus two controls — one on the region
arithmetic, one on the composited-frame check — because a single control that
trips only one of the two independent assertions leaves the other unpinned.

`_check_no_overlap` is deliberately callable **without** `subTest`: `subTest`
absorbs an `AssertionError` into the result object instead of raising, so a
control wrapped around a subTest-using test can never observe its own injection.

**Result:** `tests/test_minimonitor_pick_by_number.py` 111 → 120 tests, all
green; `tests/test_minimonitor_top_chrome_render.py` (t1499) 13 green; full
`bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED (runner=pytest,
exit=0)`.

## Post-Review Changes

### Change Request 1 (2026-08-18 10:37)
- **Requested by user:** The `.narrow` block comment at `monitor_shared.py:1527`
  still named `#pick-confirm-row { dock: bottom }` as load-bearing, although the
  fix deliberately removed that dock and made `#pick-bottom-dock` the single
  docked widget. As written it could talk a later maintainer into restoring the
  child's dock — the exact change that recreates this overlap class. Retarget it
  to `#pick-bottom-dock`, as the plan intended.
- **Changes made:** Confirmed the staleness (the plan retargeted the
  "Docked, not in normal flow…" comment but missed this second reference).
  Retargeted the `.narrow` comment to `#pick-bottom-dock` and added an explicit
  "do not move the dock onto `#pick-confirm-row`" warning naming t1563, so the
  comment now argues against the regression instead of for it. Swept the repo
  for other stale `pick-confirm-row` + `dock` references — none; every remaining
  mention is a live selector, the negative control's mutation string, or the new
  warning. Re-ran the file: 120 tests green.
- **Files affected:** `.aitask-scripts/monitor/monitor_shared.py`

## Final Implementation Notes

- **Actual work done:** `TaskPickConfirmDialog` now wraps `#pick-confirm-row`
  and `#task-detail-footer` in a single docked `#pick-bottom-dock` container, so
  exactly one widget docks to the dialog's bottom edge. The `.narrow` variant
  reclaims the last stacked button's dead trailing margin
  (`Button:last-of-type { margin: 0 }`), which repays the row the overlap used
  to steal. The narrow footer's plan hint was shortened to `p: plan/task`.
  `tests/test_minimonitor_pick_by_number.py` gained `plan_content` threading
  through `_task_info` / `_ConfirmHost` and a 9-test `BottomDockGeometryTests`
  class; the file went 111 → 120 tests.
- **Deviations from plan:** One, in the negative control. The planned mutation
  (re-dock the footer only) does **not** reproduce the fault — inside the
  wrapper the footer becomes the single docked child and the confirm row flows
  above it, so the geometry stays clean and the control passed. The control now
  restores the pre-fix arrangement instead — `dock: bottom` on **both** wrapper
  children — and is split in two, one against the region arithmetic and one
  against the composited-frame check, since a control that trips only one of two
  independent assertions leaves the other unpinned. This also clarified the real
  invariant: *one docked widget per edge*, not "the footer is undocked".
- **Issues encountered:** `subTest` absorbs an `AssertionError` into the result
  object rather than raising it, so a negative control wrapped around a
  subTest-using test can never observe its own injection. The probed assertion
  was extracted into `_check_no_overlap`, callable without `subTest`.
- **Key decisions:** Wrapper over undocking the footer into flow — it preserves
  the visual order and keeps the load-bearing "the body scroll gives up space,
  not the controls" property with the dock on the wrapper. The narrow margin
  reclaim was chosen over dropping `#pick-confirm-row`'s top separator margin:
  measured across 9 size × variant combinations, it lands content visibility
  identical to the pre-fix baseline at every size, and the reclaimed row was
  genuinely dead space. The plan-hint shortening is narrow-only; the wide
  variant keeps the full wording.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_shared.py:1334 — TaskDetailDialog (the
    read-only i/I surface, pushed from minimonitor_app.py:3741) clips its footer
    to "q/Esc: close  p: switch" at 40 columns. Same root cause as the hint
    defect fixed here (a 33-column string in a 30-column `height: 1` footer),
    but in the base class, which has no `.narrow` variant and is shared with the
    full monitor — so it was left out of scope. Verified on a composited frame
    at 40x24 and 40x20; correct at 80x24.
