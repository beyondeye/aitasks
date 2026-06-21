---
priority: high
effort: high
depends: [t1037_2]
issue_type: feature
status: Implementing
labels: [aitask_monitormini, tui, clipboard]
assigned_to: dario-e@beyond-eye.com
anchor: 1037
created_at: 2026-06-21 11:42
updated_at: 2026-06-21 18:29
---

## Context

Consumer UI of t1037. Builds the Textual **concern-picker modal** that shows
the parsed shadow concerns as a checkbox list and, on confirm, produces the
clipboard payload. The trigger/capture wiring that *opens* this modal is the
next sibling (t1037_4); this task delivers a self-contained, testable modal.

Depends on t1037_1 (imports `Concern` and `build_clipboard_payload` from
`.aitask-scripts/monitor/concern_parser.py`). Read the parent t1037 and the
spec `aidocs/framework/shadow_concern_format.md` first.

## Key files to modify

- `.aitask-scripts/monitor/monitor_shared.py` — add `ConcernPickerModal`
  (a `ModalScreen`) here, alongside the existing shared modals
  (`ChooseSiblingModal`, `KillConfirmDialog`, etc.) so both monitor and
  minimonitor can use it. Pattern it on `ChooseSiblingModal` + `_SiblingRow`
  (focusable item rows, `VerticalScroll` list, `.narrow` variant for the
  ~40-col companion pane, OK/Cancel buttons + key handlers).

## Modal requirements

- **Input:** `concerns: list[Concern]` (+ `narrow: bool`).
- **Each row:** a checkbox-style toggle showing `☑/☐` (use the checkbox glyph,
  not a dot — marked = bold yellow; same glyph convention as t1004) plus
  priority badge (color by high/med/low) and the region label; body shown
  truncated/wrapped. Toggle with space/enter on the focused row.
- **Select-all / none** shortcut (e.g. `a` toggles all).
- **Confirm (OK):** dismiss with the list of selected `Concern`s (the app does
  the clipboard write in t1037_4) OR build the payload here via
  `build_clipboard_payload` and dismiss with the string — pick one; recommend
  dismissing with selected `Concern`s and letting the action handler call
  `build_clipboard_payload` + `app.copy_to_clipboard` (keeps the modal pure-UI
  and testable without a clipboard backend).
- **"Copy ALL" fast path** (parent open question): a shortcut that selects all
  and confirms in one step, for the manual-paste fast path with the preamble
  already attached.
- **Cancel/Esc:** dismiss with `None`.
- Add a `.narrow` CSS variant exactly as `ChooseSiblingModal` does.

## Reference files for patterns

- `.aitask-scripts/monitor/monitor_shared.py`: `ChooseSiblingModal`
  (lines ~385-464) and `_SiblingRow` (~324-383) — focus management, key
  handlers (`on_key` up/down/enter), `.narrow` CSS, OK/Cancel buttons,
  `dismiss(payload)`.
- Clipboard prior art: `.aitask-scripts/codebrowser/codebrowser_app.py:145-168`
  (`self.app.copy_to_clipboard(...)` + `self.app.notify(...)`) and
  `.aitask-scripts/lib/agent_command_screen.py:666-672`.
- Checkbox-glyph convention (☑/☐, bold yellow marked): see t1004 work.
- Existing modal tests: `tests/test_brainstorm_node_action_modal.py`,
  `tests/test_shortcut_editor_modal.py`, `tests/test_stale_entry_modal.py`
  (Textual `Pilot` harness shape).

## Implementation plan

1. Add `ConcernPickerModal(ModalScreen)` + a focusable concern row widget to
   `monitor_shared.py`, modeled on `ChooseSiblingModal`/`_SiblingRow`.
2. Implement toggle, select-all/none, OK (dismiss with selected concerns),
   "copy ALL", Cancel.
3. Wire badges/glyphs per the conventions above; add `.narrow` CSS.
4. Write `tests/test_concern_picker_modal.py` (Textual `Pilot`):
   - renders N rows from N concerns;
   - toggling marks/unmarks (assert ☑/☐ + selection set);
   - select-all selects every row;
   - OK dismisses with exactly the selected `Concern`s;
   - "copy ALL" dismisses with all;
   - Cancel/Esc dismisses with `None`.

## Verification steps

- `tests/test_concern_picker_modal.py` passes.
- Read `aidocs/framework/tui_conventions.md` before editing the TUI; follow its
  modal/keybinding rules.
- Manual smoke (optional here; full live flow is the t1037 manual-verification
  sibling): instantiate the modal with sample concerns in a scratch Textual app.

## Notes for sibling tasks

- Document the modal's dismiss contract (returns selected `list[Concern]` vs
  payload string) so t1037_4 wires the right callback. Note the chosen
  select-all / copy-all keybindings so the parent MV checklist can exercise
  them.
