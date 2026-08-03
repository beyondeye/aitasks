---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_board, tui]
gates: [risk_evaluated]
anchor: 1210
created_at: 2026-08-03 00:15
updated_at: 2026-08-03 00:15
boardidx: 5120
---

## Origin

Risk-mitigation ("after") follow-up for t1366, created at Step 8d after
implementation landed.

## Risk addressed

Addresses: half-fixed shared sink (confirm-dialog family).

From t1366's plan `## Risk` section, verbatim:

> A third dialog-body id (`#orphan_parent_label`) has no CSS rule at all and
> `#delarch_label` keeps `width: auto`; both stay clipped at 80 cols, and the three
> label-only confirm dialogs remain keyboard-unreachable when their body overflows.
> Pre-existing, deliberately out of scope, but the sink is now half-fixed
> · severity: low

## Goal

t1366 fixed focus visibility and overflow for the seven **focus-driven** pickers
built on `#dep_picker_dialog`, scoping the new behaviour behind a `picker-dialog`
marker class. The confirm-dialog family could not take the same treatment because
of its **shape**, not its styling — so it was left out. This task fixes the shape,
then extends the treatment.

Confirmed with live Textual probes during t1366 (textual 8.2.7):

- `RemoveDepConfirmScreen`, `DeleteConfirmScreen` and `DeleteColumnConfirmScreen`
  put their entire body text inside the `#dep_picker_title` Label, whose only
  sibling is the docked `#detail_buttons` row. With `dock: top` on the title, the
  container's only non-docked child disappears from the flow and `height: auto`
  resolves to **0**: probed on the real `RemoveDepConfirmScreen` at 120x40 the
  dialog collapsed to `height=4`, `content_size.height=0`, with the title drawn
  *below* the buttons and both outside the box. `dock: top` also defeats
  `overflow-y: auto` on those screens (`allow_vertical_scroll` stays False).

Work:

1. Move the body text of the three screens out of `#dep_picker_title` into a
   second `Label` (as `UnlockConfirmScreen` / `ResetTaskConfirmScreen` already do),
   leaving the title as a real title. This makes the family structurally uniform.
2. Give `#delarch_label` and `#orphan_parent_label` `width: 100%` so long bodies
   wrap instead of clipping mid-word at 80 columns. `#orphan_parent_label`
   (`aitask_board.py`, `OrphanParentArchiveScreen.compose`) currently has **no CSS
   rule at all** and renders with bare `Label` defaults — consider folding the
   three body-label ids into one shared selector.
3. Extend the `picker-dialog` treatment (or an equivalent) to the confirm family
   so an overflowing body is reachable, not hard-clipped. Note `Container` has no
   arrow-key bindings, so a scrollable confirm dialog with no focusable body is
   mouse-wheel-only — decide whether that is acceptable or whether the body needs
   to become focusable.
4. Leave the three `SelectionList` screens (`IssueTypeFilterScreen`,
   `WorkReportColumnSelectScreen`, `WorkReportTaskSelectScreen`) out of any blanket
   `overflow-y: auto`: `OptionList` is `height: auto; max-height: 100%` and already
   overlaps the docked buttons by ~2 rows, so an outer scrollbar produces a nested
   double scrollbar and steals ~2 columns. If they are brought in, add a long-list
   test case — `tests/test_board_work_report.py` only drives them with 2-3 options
   and would not catch it.

## Verification

Follow t1366's pattern: assert at **render level** (composited frame), not on
`.classes`/`app.focused`. `ByTrailTestBase._dialog_text(app, widget)` in
`tests/test_board_bytrail_view.py` slices the frame to a widget's columns and
strips box chrome — required for a centred modal, because whole-screen flattening
splices the board rendered on either side into any wrapped dialog phrase.

Each new test must be shown to fail against pre-fix code. Re-run the full board
suite (26 modules, 472 tests) since the CSS sink is shared by 19 modals, and
confirm the seven pickers t1366 already fixed are unchanged.
