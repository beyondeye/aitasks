---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, tui, trails]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
implemented_with: claudecode/opus5
created_at: 2026-08-02 10:23
updated_at: 2026-08-02 23:12
---

## Symptom

In `ait board`'s By-Trail view, pressing `s` opens the trail-selection modal
(`TrailSelectScreen`). Pressing ↑/↓ appears to do nothing: no option highlights,
nothing visibly moves. The dialog reads as if it does not support keyboard
navigation at all.

## Root cause (confirmed with live Textual Pilot probes)

The keyboard *mechanics* are already correct — this is a **rendering** defect,
not a binding defect. Verified against the real `KanbanApp` booted on the
`tests/lib/board_fixture.py` tree:

- ↑/↓ **do** move focus. The board binds `up`/`down` with `priority=True`
  (`aitask_board.py:5571-5572`) → `action_nav_up`/`action_nav_down`
  (`:6870-6903`), which detect `_modal_is_active()` and call
  `screen.focus_previous()` / `focus_next()`. Probe: focus walked
  `art:alpha → art:beta → art:alpha`.
- Enter confirms (`TrailSelectItem.on_key`, `:2290`) and Esc cancels
  (`TrailSelectScreen` binding, `:2302`). Probe: `down` then `enter` dismissed
  with `'art:beta'`.

### 1. Focus is invisible (primary defect)

`TrailSelectItem.on_focus` adds the CSS class `dep-item-focused`
(`:2284-2288`), but the app CSS defines a rule for that class **only** for two
sibling types:

```
DepPickerItem.dep-item-focused   { background: $primary 20%; border-left: thick $accent; }  # :5462
ChildPickerItem.dep-item-focused { background: $primary 20%; border-left: thick $accent; }  # :5464
```

`TrailSelectItem` matches neither selector, so the class is inert. **Probe
evidence:** the composited frame
(`screen._compositor.render_strips(...)`) is *byte-identical* before and after
pressing `down`, while `items[0].classes` → `frozenset()` and
`items[1].classes` → `frozenset({'dep-item-focused'})`. Focus moved; the
terminal showed nothing.

Seven item classes add `dep-item-focused`; only two are styled. Unstyled:
`GateChoiceItem` (`:2178`), `TrailSelectItem` (`:2260`),
`FoldedTaskPickerItem` (`:3796`), `FileReferenceItem` (`:3853`),
`ColumnSelectItem` (`:5215`).

### 2. The dialog silently clips its own list

`#dep_picker_dialog` (`:5444-5451`) is `height: auto; max-height: 50%` with no
overflow rule, and `Container` does not scroll. **Probe with 10 trails at
100×30:**

- `dialog.region` height **15** vs `dialog.virtual_size` height **25**;
  `allow_vertical_scroll=False`, `show_vertical_scrollbar=False`.
- Trails 06–10 never render. The `Cancel` button lands at `y=31` — below a
  30-row terminal — so it is unreachable by eye or mouse.
- 12 × `down` wrapped focus around through every off-screen row and the button
  with zero feedback, leaving focus on an invisible row that Enter would
  activate.

Rows are **2 lines tall** here (title line + wrapped `owner · scope ·
freshness · updated`), and grow further with `also references:` overlap
sub-lines — so `TrailSelectItem` cannot reuse the `height: 1` rule the two
styled siblings use.

### 3. The hint label under-documents and truncates

The title reads `Select trail — Enter to activate, Esc to cancel` (`:2312`) and
never mentions ↑/↓. The sibling `TopicSortModeScreen` already sets the house
style: `Topic sort order — ↑/↓ to move, Enter to apply, Esc to cancel`
(`:2133`). At 80 columns the trail label is clipped mid-word to
`Esc to c` (the dialog is `width: 60%`).

## Scope — fix at the shared sink

Confirmed with the user: fix the CSS/scroll gap once, at the shared
`#dep_picker_dialog` / `.dep-item-focused` sink, rather than patching
`TrailSelectScreen` alone. The same two defects reach every picker built on
that dialog id: `GateChoiceScreen` (`:2201`), `FoldedTaskPickerScreen`
(`:3825`), `FileReferencePickerScreen` (`:3878`), `ColumnSelectScreen`
(`:5243`), plus `DependencyPickerScreen` / `ChildPickerScreen` (styled, but
still non-scrolling).

## Acceptance criteria

1. In the By-Trail trail selector, the focused row is **visibly distinct** in
   the composited frame — asserted at render level, not by inspecting
   `.classes` or `app.focused` (see the render-level TUI verification
   convention). A `down` press must change the frame.
2. The focus style is applied via a rule that covers **every** item type using
   `dep-item-focused`, not a new per-type duplicate. Multi-line rows
   (`TrailSelectItem` with overlap sub-lines) must render fully — the shared
   rule cannot assume `height: 1`.
3. `#dep_picker_dialog` scrolls when its content exceeds `max-height`: with
   N rows tall enough to overflow, focusing the last row scrolls it into view,
   and the `Cancel` button is reachable. No focusable widget may sit outside
   the rendered region.
4. The trail-selector hint mentions ↑/↓ and fits the dialog width at 80
   columns without mid-word truncation (verify at the narrow width, not only
   at 100+).
5. Regression tests live with the By-Trail Pilot tests
   (`tests/test_board_bytrail_view.py`, `ByTrailPilotTests`) and use the
   `board_fixture` harness. Each new test must be shown to **fail** against
   the current code (prove the harness discriminates) before the fix lands.
6. At least one sibling picker (e.g. `ColumnSelectScreen` or
   `GateChoiceScreen`) is covered too, proving the fix landed at the shared
   sink rather than on the trail path only.

## Notes / non-goals

- Do **not** convert `TrailSelectScreen` to the `TopicSortModeScreen`
  selection-model pattern (screen-owned index + `check_action` fall-through).
  Focus-based navigation already works; only its visibility and the container
  overflow are broken. A rewrite would be a larger, riskier change than the
  defect warrants — but if the implementer finds the selection model is
  genuinely required (e.g. to make scroll-into-view tractable), raise it
  explicitly at planning time rather than switching silently.
- `TrailSelectItem.on_key` (`:2290`) does not call `event.stop()` /
  `prevent_default()` on Enter, unlike `DepPickerItem` (`:3457-3463`) and
  `ColumnSelectItem` (`:5227-5231`). The probe observed **no** leak to the
  App-level `Binding("enter", "view_details")` after dismiss, so this is not a
  reported defect — but it is a latent inconsistency worth tidying while in
  the file. `GateChoiceItem` (`:2193`) has the same shape.
- Read `aidocs/framework/tui_conventions.md` before editing.

## Related (not folded)

- **t1365** — By-Trail discovery misses a newly created trail. Same modal,
  different layer: t1365 is about *which* trails the list contains
  (`_open_trail_select` rescan), this task is about how the list *renders* and
  responds to the keyboard. No dependency either way.

## Reproduction probes

Both probes booted the real `KanbanApp` via `board_fixture.FixtureBoardTestBase`
and pushed `TrailSelectScreen` with synthetic `TrailInfo` rows:

- 3 trails @ 80×24 → frame identical across `down`; `classes` moved.
- 10 trails @ 100×30 → `region.height=15` vs `virtual_size.height=25`;
  `#btn_dep_cancel` at `y=31`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-02T20:12:24Z status=pass attempt=1 type=human
