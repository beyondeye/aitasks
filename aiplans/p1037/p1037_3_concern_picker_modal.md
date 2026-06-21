---
Task: t1037_3_concern_picker_modal.md
Parent Task: aitasks/t1037_minimonitor_shadow_concern_picker.md
Sibling Tasks: aitasks/t1037/t1037_4_minimonitor_trigger_capture_wiring.md, aitasks/t1037/t1037_5_manual_verification_minimonitor_shadow_concern_picker.md
Archived Sibling Plans: aiplans/archived/p1037/p1037_1_concern_format_spec_and_parser.md, aiplans/archived/p1037/p1037_2_shadow_skill_emit_concern_block.md, aiplans/archived/p1037/p1037_6_richer_concern_block_body_framing.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-21 18:35
---

# Plan: Concern-picker modal (t1037_3)

## Context

This is the consumer-UI child of **t1037** (minimonitor shadow concern picker).
The shadow agent emits a structured, fenced concern block; foundation sibling
**t1037_1** (landed) ships the pure parser `concern_parser.py` exposing
`Concern(priority, region, body)`, `parse_concerns`, `has_concern_block`, and
`build_clipboard_payload`. **t1037_2** (landed) makes the shadow skill emit the
block.

This task delivers a **self-contained, testable Textual modal** —
`ConcernPickerModal` — that renders parsed concerns as a ☑/☐ checkbox list and,
on confirm, dismisses with the user's selected `list[Concern]`. The trigger that
*opens* this modal and writes the clipboard is the next sibling **t1037_4**;
this task keeps the modal pure-UI so it is unit-testable without a clipboard
backend or tmux.

**Verify-path note:** existing plan re-checked against current code on
2026-06-21. All assumptions hold — `ChooseSiblingModal` (monitor_shared.py
385-463) and `_SiblingRow` (324-383) are present as referenced; the parser
contract is locked; the test-host pattern exists. Enriched below with the
concrete import/CSS/test details confirmed during verification.

## Key file to modify

- `.aitask-scripts/monitor/monitor_shared.py` — add `ConcernPickerModal`
  (`ModalScreen`) + a focusable `_ConcernRow(Static)` widget, placed next to
  `ChooseSiblingModal`/`_SiblingRow` so **both** monitor and minimonitor can
  push it. The module already imports everything needed (`ModalScreen`,
  `Container`, `VerticalScroll`, `Button`, `Static`, `Label`, `Binding`,
  `ComposeResult`, `rich.text.Text`).

## Files to create

- `tests/test_concern_picker_modal.py` — Textual `Pilot`/host-App test.

## Design

### `_ConcernRow(Static)` — focusable concern row (model on `_SiblingRow`)

- `can_focus = True`; holds the `Concern` and a `selected: bool` (default
  `False`).
- `render()` →  mark + priority badge + region + truncated body, e.g.
  `f"{mark}  {badge} [dim]{region}[/]  {body}"` where:
  - `mark` = `☑` (bold yellow) when selected else `☐` (per the t1004 checkbox
    convention — checkbox glyph, never a dot; marked = bold yellow).
  - `badge` color by priority: high=red, medium=yellow, low=dim.
  - body is single-line truncated/wrapped (rich handles width; keep `height: 1`
    like `_SiblingRow`, or `height: auto` if wrapping is wanted — start with
    single-line truncation for parity).
- `on_key`: `space`/`enter` → toggle `selected` (call `self.refresh()`);
  `up`/`down` → reuse the `_focus_neighbor(delta)` pattern (copy from
  `_SiblingRow`, filtering on `_ConcernRow`). `prevent_default()` + `stop()` as
  in `_SiblingRow`.
- Expose `concern` and `selected` as read properties so tests/handlers read
  state without poking internals.

### `ConcernPickerModal(ModalScreen)` — model on `ChooseSiblingModal`

- **Constructor:** `ConcernPickerModal(concerns: list[Concern], narrow: bool = False)`.
- **`DEFAULT_CSS` (own — load-bearing):** per
  `aidocs/framework/tui_conventions.md` ("Modals pushed by multiple Apps must
  carry their own DEFAULT_CSS"), define the full dialog CSS here — dialog size,
  header/context/list/help/buttons, the `_ConcernRow:focus` accent
  (`background: $accent 30%`) **and** a `_ConcernRow:focus:hover` rule keeping a
  focused+hovered row a shade of the focus accent (never gray hover — per
  established TUI convention), plus the `ConcernPickerModal.narrow
  #concern-dialog { width: 90%; min-width: 30; }` variant mirroring
  `ChooseSiblingModal`.
- **`compose`:** add `narrow` class when `self._narrow`; `Container` dialog with
  header (`[bold]Concerns[/]`), context line (`f"{len(concerns)} concern(s)"`),
  `VerticalScroll` of `_ConcernRow`s, a help line documenting the keys, and an
  OK/Cancel button row. Mirror `ChooseSiblingModal.compose` structure/ids.
- **`on_mount`:** focus the first `_ConcernRow` (as `ChooseSiblingModal` does).
- **Keys / actions:**
  - `BINDINGS`: `Binding("escape", "dismiss_dialog", "Close", show=False)`;
    `Binding("a", "toggle_all", "Select all/none")`;
    `Binding("A", "copy_all", "Copy ALL")`. Prefer `Binding`+`action_*` (with
    short labels) over `on_key`-only for modal-level shortcuts, per the
    footer-visibility convention; row navigation stays `on_key` on the row
    (matches `_SiblingRow`).
  - `action_toggle_all`: if any row unselected → select all, else deselect all;
    `refresh` rows.
  - OK button / confirm → `dismiss([row.concern for row in rows if
    row.selected])`.
  - `action_copy_all` (`A`) → select all then immediately
    `dismiss(all_concerns)` (the manual-paste fast path; preamble is attached
    by t1037_4 via `build_clipboard_payload`).
  - `escape` / Cancel → `dismiss(None)`.
- **Dismiss contract (LOCKED for t1037_4):** returns the **selected
  `list[Concern]`** (NOT a payload string). Rationale: keeps the modal pure-UI
  and unit-testable without a clipboard backend; t1037_4's action handler calls
  `build_clipboard_payload(selected)` + `app.copy_to_clipboard(...)` +
  `notify(...)`. OK with an empty selection dismisses with `[]` (caller decides
  whether to no-op/toast). Document this in Final Implementation Notes.

## Tests — `tests/test_concern_picker_modal.py`

Follow `tests/test_kill_confirm_dialog.py` exactly for harness shape:
- `REPO_ROOT = Path(__file__).resolve().parent.parent`; `sys.path.insert` for
  `.aitask-scripts` (so `from monitor.monitor_shared import ConcernPickerModal`
  resolves the `monitor` package) **and** `.aitask-scripts/monitor` (so
  `from concern_parser import Concern` resolves, matching
  `test_concern_parser.py`).
- A small host `App` whose `on_mount` pushes `ConcernPickerModal(sample_concerns)`,
  driven via `App.run_test()` `Pilot` (async, `unittest` + `asyncio` like
  `test_kill_confirm_dialog.py`). Capture the dismiss result via the
  `push_screen` callback or `screen.dismiss` wrapper.

Cases:
1. N concerns → N `_ConcernRow`s rendered; first is focused.
2. toggle focused row (`space`) → `selected` flips; `render()` shows ☑ then ☐.
3. `a` select-all → every row `selected`; press again → none selected.
4. OK with a subset selected → dismissed result == exactly those `Concern`s,
   in original order.
5. `A` (copy ALL) → result == all concerns (regardless of prior toggles).
6. `escape` / Cancel → result is `None`.

Run via `bash tests/run_all_python_tests.sh` (or
`python3 -m unittest tests.test_concern_picker_modal`).

## Verification

- `tests/test_concern_picker_modal.py` passes.
- Re-read `aidocs/framework/tui_conventions.md` modal rules before editing
  (own-DEFAULT_CSS, focus styling, footer-visible bindings) — already done in
  planning; honor them in the implementation.
- Optional scratch-App smoke; the full live flow (shadow → minimonitor →
  picker → paste) is the t1037 manual-verification sibling (t1037_5), not this
  task.

## Notes for sibling tasks (fill final values at completion)

- Restate the dismiss contract (selected `list[Concern]`) and the final
  keybindings (`a` = select-all/none, `A` = copy-all, `space`/`enter` = toggle,
  `Esc` = cancel) so t1037_4 wires the callback and the t1037_5 MV checklist
  exercises them.

## Risk

### Code-health risk: low
- Purely additive: one new modal class + one new row widget in
  `monitor_shared.py` (alongside existing peers) and one new test file. No
  existing code path, signature, or call site is modified; nothing imports the
  new class yet (t1037_4 wires it). Blast radius is contained to additions ·
  severity: low · → mitigation: covered in-task by the modal unit tests.

### Goal-achievement risk: low
- The dismiss contract (return `list[Concern]`, not a payload string) is a
  cross-task interface t1037_4 depends on; a mismatch would force rework there ·
  severity: low · → mitigation: contract is documented in the plan, asserted by
  the OK/copy-all tests, and recorded in Final Implementation Notes for t1037_4.
- "copy ALL" semantics (select-all-then-confirm in one keystroke) is a parent
  open question; chosen here as `A`. Low risk of churn if the parent later
  prefers a button · severity: low · → mitigation: keybinding documented for
  the MV sibling; trivially changeable.

See parent t1037 and **Step 9 (Post-Implementation)** for archival/merge.
