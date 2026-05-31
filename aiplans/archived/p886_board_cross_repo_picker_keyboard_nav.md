---
Task: t886_board_cross_repo_picker_keyboard_nav.md
Base branch: main
plan_verified: []
---

# Plan: Fix keyboard nav in board cross-repo ref picker (t886)

## Context

On the `ait board` TUI, the cross-repo reference picker
(`CrossRepoRefPickerScreen`, `.aitask-scripts/board/aitask_board.py:1893`)
is only keyboard-reachable to its first (auto-focused) item. With ≥2
cross-repo refs, the 2nd+ entries and the **Cancel** button can only be
reached with the mouse. The intended fix is to let **Tab** cycle focus
through the picker's items instead of yanking focus out to the board.

### Root cause (verified by reading the code)

`KanbanApp` registers two App-level `priority=True` bindings
(`aitask_board.py:3577-3578`):

```python
Binding("tab", "focus_search", "Search", show=False, priority=True),
Binding("escape", "focus_board", "Board", show=False, priority=True),
```

Textual checks App `priority=True` bindings before the focused widget, and
they keep firing while a `ModalScreen` is on the stack. Tracing the two
action handlers:

- **`action_focus_search`** (Tab, `:4144`) is **not** modal-aware — it
  unconditionally focuses `#search_box`. So Tab inside the picker jumps to
  the board search input instead of cycling to the next item. **← the bug.**
- **`action_focus_board`** (Escape, `:4152`) **is already modal-aware**
  (`:4154-4159`): when a modal is active it calls `self.screen.dismiss()`.
  That's why Escape already closes the picker fine.

The existing `check_action` guard at `:3641` already disables the board's
`nav_*` (arrow) actions when `len(self.screen_stack) > 1`, letting arrows
fall through to the focused modal widget. There is no equivalent guard for
`focus_search`, so Tab is still hijacked.

## Approach — gate only `focus_search`

Add one guard clause in `KanbanApp.check_action`
(`aitask_board.py:3634`), mirroring the existing `nav_*` blanket guard at
`:3641`: return `False` for `focus_search` whenever a modal screen is on the
stack. Returning `False` marks the priority binding inactive, so Tab falls
through to Textual's default widget focus-cycling **within the active
modal** — which walks the picker's focusable `CrossRepoRefItem` widgets
(`can_focus = True`, `:1868`) and the Cancel `Button`, then Enter on a
focused item opens it via the item's existing `on_key` handler (`:1878`).

This is the documented "blanket" remedy in
`aidocs/tui_conventions.md` ("Priority bindings + `App.query_one` gotcha"):
gate the App's priority binding in `check_action` so the key reaches the
modal — covering the picker and any current/future modal without
per-class enumeration.

### Why NOT also gate `focus_board` (deviation from the task's suggestion)

The task text suggests gating both `focus_search` **and** `focus_board`.
I'm deliberately gating only `focus_search`, because gating `focus_board`
is unnecessary and carries real blast radius:

- **Unnecessary:** Escape already works — `action_focus_board` is modal-aware
  and dismisses the active modal. The bug is purely the Tab key.
- **Risky:** Gating `focus_board` would re-route Escape away from the
  centralized `action_focus_board` dismiss to each modal's *own* escape
  binding. ~20 `ModalScreen`s currently rely on the App's centralized
  Escape→`dismiss()` (no modal defines `handle_escape`, so they all hit the
  bare `dismiss()` branch). Their own `action_cancel`/`action_close_*`
  handlers may `dismiss(False)`/`dismiss(None)` instead of a bare
  `dismiss()`, and `LoadingOverlay` (`:3252`) has **no** escape binding at
  all — gating would silently change its Escape behavior to a no-op. None of
  that is needed to fix this bug, so it stays untouched.

### Exact change

In `KanbanApp.check_action`, immediately after the existing `nav_*` guard
(`aitask_board.py:3641-3642`), add:

```python
# Tab normally jumps to the board search box. While a modal is on the
# stack that yanks focus out of the modal (e.g. the cross-repo ref picker,
# which then only exposes its first item to the keyboard). Gate it so Tab
# falls through to default widget focus-cycling inside the modal. Escape is
# left App-level: action_focus_board is already modal-aware and dismisses
# the active modal.
if action == "focus_search" and len(self.screen_stack) > 1:
    return False
```

No other files need changing. The `focus_search` binding is `show=False`,
so the footer is unaffected. Base-board Tab→search (advertised in the
`#search_box` placeholder, `:3712`) is preserved because the guard only
fires when a modal is pushed.

## Files to modify

- `.aitask-scripts/board/aitask_board.py` — one guard clause in
  `check_action` (~`:3642`).
- `tests/test_board_picker_tab_nav.py` — **new** regression test (Pilot-based,
  mirroring `tests/test_board_view_filter.py`'s `KanbanApp().run_test()`
  pattern).

## Verification

1. **Automated regression test** (new file, run with
   `python3 -m pytest tests/test_board_picker_tab_nav.py -v`):
   - Spin up `KanbanApp` via `app.run_test(size=(160,48))`.
   - Baseline: with no modal, assert
     `app.check_action("focus_search", None)` is **not** `False` (Tab→search
     still active on the base board).
   - Push `CrossRepoRefPickerScreen([("repoA","1"),("repoB","2")])`, pause.
   - Assert `app.check_action("focus_search", None) is False` (gate active
     while modal on stack).
   - Press Tab a couple of times and assert focus stays inside the modal —
     `app.focused` is a `CrossRepoRefItem` (or the Cancel `Button`), and is
     **not** the `#search_box` Input; `isinstance(app.screen,
     CrossRepoRefPickerScreen)` remains true.
2. **Lint:** `shellcheck` is N/A (Python). Confirm no syntax regression by
   importing the module / running the existing board tests
   (`python3 -m pytest tests/test_board_view_filter.py -v`).
3. **Manual smoke (optional, matches the task repro):** open `ait board` on a
   task carrying ≥2 cross-repo refs, focus the card, press `#`, then Tab —
   focus should cycle ref→ref→Cancel→ref within the popup; Enter opens the
   focused ref; Escape still closes the picker.

## Notes / follow-ups

- Arrow-key navigation inside the picker is still not added (the items are
  plain focusable `Static`s). Tab cycling is the standard modal nav and fully
  resolves the reported bug. Converting the list to an `OptionList`/`ListView`
  for arrow support is a larger, optional enhancement — out of scope for this
  low-effort fix; can be a follow-up if desired.
- Per CLAUDE.md, the board is the Claude-Code source of truth; this is a
  Python TUI change with no skill/`.md.j2` surface, so no cross-agent port is
  required.
- Step 9 (Post-Implementation): commit on current branch, no worktree
  (profile `fast`), then archive via `aitask_archive.sh 886`.

## Final Implementation Notes

- **Actual work done:** Added one guard clause in `KanbanApp.check_action`
  (`.aitask-scripts/board/aitask_board.py`, just after the existing `nav_*`
  guard): `if action == "focus_search" and len(self.screen_stack) > 1: return
  False`. Added a new Pilot-based regression test
  `tests/test_board_picker_tab_nav.py` (2 tests).
- **Deviations from plan:** None. Implemented exactly the recommended
  "gate only `focus_search`" approach; did **not** gate `focus_board` (the
  task text suggested both) because Escape already works via the modal-aware
  `action_focus_board`, and gating it would re-route Escape across ~20 modals
  with no benefit — rationale captured in the plan's "Why NOT also gate
  `focus_board`" section.
- **Issues encountered:** `pytest` is not installed in `~/.aitask/venv`; ran
  the test via `python3 -m unittest` (the runner `tests/run_all_python_tests.sh`
  has this exact fallback). Textual 8.2.7. Both new tests verified to FAIL
  with the fix removed (focus stays stuck on the picker's first item — the
  reported symptom) and PASS with it; existing `tests/test_board_view_filter.py`
  (9 tests) still green.
- **Key decisions:** Used the documented "blanket" `check_action` remedy from
  `aidocs/tui_conventions.md` ("Priority bindings + `App.query_one` gotcha")
  rather than per-modal bindings, so the fix covers every current/future
  pushed modal, not just the cross-repo picker.
- **Upstream defects identified:** None.

