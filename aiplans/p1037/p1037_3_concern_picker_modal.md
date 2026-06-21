---
Task: t1037_3_concern_picker_modal.md
Parent Task: aitasks/t1037_minimonitor_shadow_concern_picker.md
Sibling Tasks: aitasks/t1037/t1037_1_*.md, aitasks/t1037/t1037_2_*.md, aitasks/t1037/t1037_4_*.md
Archived Sibling Plans: aiplans/archived/p1037/p1037_*_*.md
Worktree: (current branch — fast profile)
Branch: (current branch)
Base branch: main
---

# Plan: Concern-picker modal (t1037_3)

Self-contained, testable Textual modal. The trigger that opens it is t1037_4.

## 0. Prerequisite

t1037_1 landed: `from monitor.concern_parser import Concern, build_clipboard_payload`.
Read `aidocs/framework/tui_conventions.md` before editing the TUI.

## 1. Add `ConcernPickerModal` to monitor_shared.py

Place it next to `ChooseSiblingModal` so both monitor and minimonitor can use
it. Model on `ChooseSiblingModal` (~385-464) + `_SiblingRow` (~324-383).

- **Constructor:** `ConcernPickerModal(concerns: list[Concern], narrow: bool=False)`.
- **`compose`:** header (`[bold]Concerns[/]`), context line (`N concerns`), a
  `VerticalScroll` of `_ConcernRow` widgets, help line, OK/Cancel buttons.
  Apply `.narrow` class when `narrow` (companion-pane ~40 cols), same as
  `ChooseSiblingModal`.
- **`_ConcernRow`** (focusable, like `_SiblingRow`): renders
  `☑/☐` mark (checkbox glyph — marked = bold yellow, per t1004 convention) +
  priority badge (color: high=red, medium=yellow, low=dim) + region label +
  truncated/wrapped body. Holds the `Concern` and a `selected: bool`.
  - `on_key`: `space`/`enter` toggles select; `up`/`down` move focus
    (reuse the `_focus_neighbor` pattern).
- **App-level / modal keys:**
  - `a` — toggle select-all/none.
  - OK button / a confirm key — `dismiss(list_of_selected_concerns)`.
  - A "copy ALL" shortcut (e.g. `A` or a second button) — select all then
    confirm in one step.
  - `escape` / Cancel — `dismiss(None)`.
- **Dismiss contract:** return the **selected `list[Concern]`** (NOT the payload
  string). Rationale: keeps the modal pure-UI and unit-testable without a
  clipboard backend; t1037_4's action handler calls `build_clipboard_payload` +
  `app.copy_to_clipboard`. Document this in Final Implementation Notes.
- **CSS:** add `ConcernPickerModal` DEFAULT_CSS + `.narrow` variant mirroring
  `ChooseSiblingModal`'s sizing.

## 2. Tests — tests/test_concern_picker_modal.py

Textual `Pilot` harness (match `tests/test_brainstorm_node_action_modal.py`,
`tests/test_shortcut_editor_modal.py`). Push the modal in a scratch `App`:
1. N concerns → N `_ConcernRow`s rendered.
2. toggle focused row → `selected` flips, glyph ☐↔☑.
3. `a` select-all → every row selected; again → none.
4. OK → dismissed result == exactly the selected `Concern`s, in order.
5. "copy ALL" → result == all concerns.
6. Esc/Cancel → result is `None`.

## 3. Verification

- `tests/test_concern_picker_modal.py` passes.
- Optional scratch-app smoke (full live flow is the t1037 MV sibling).

## 4. Final Implementation Notes (fill at completion)

State the dismiss contract (selected `list[Concern]`) and the final
select-all / copy-all keybindings so t1037_4 wires the callback and the parent
MV checklist exercises them.

See parent t1037 and **Step 9 (Post-Implementation)** for archival/merge.
