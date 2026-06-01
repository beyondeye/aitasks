---
Task: t893_up_down_arrows_in_task_detail_dialog.md
Base branch: main
plan_verified: []
---

# Plan: Fix up/down arrow field navigation in board task detail dialog (t893)

## Context

In `ait board`, the task **detail dialog** (`TaskDetailScreen`) lets the user move
between metadata fields (priority/effort/status `CycleField`s, depends, verifies,
children, etc.) with the **up/down arrow keys**. The user reports this stopped
working — the arrows "are apparently captured by the main screen."

**Root cause (a regression).** `KanbanApp` binds `up`/`down`/`left`/`right` as
App-level **`priority=True`** bindings (`aitask_board.py:3580-3583`) routed to
`action_nav_*`. Those nav actions are *modal-aware*: when a modal is on the
stack, `action_nav_up`/`action_nav_down` call `self.screen.focus_previous()` /
`focus_next()` (`aitask_board.py:4193-4211`) — **this is the field-selection
navigation** in the detail dialog. Likewise `action_nav_left`/`action_nav_right`
cycle the focused `CycleField`.

Commit `50e3a375` (t848_4, in-TUI shortcut editor) added a **blanket guard** in
`KanbanApp.check_action` (`aitask_board.py:3641-3642`):

```python
if action in ("nav_up", "nav_down", "nav_left", "nav_right") and len(self.screen_stack) > 1:
    return False
```

Returning `False` for a priority binding makes Textual treat it as inactive, so
the arrow key falls through to the focused modal widget. That is correct for the
new shortcut editor — its `DataTable(cursor_type="row")`
(`shortcut_editor_modal.py:95`) owns up/down for row navigation. But it is
**too broad**: it disables the App's up/down for *every* pushed modal. The
detail dialog's field widgets only self-handle **left/right** (`CycleField.on_key`,
`aitask_board.py:1032-1040`) — they have **no up/down handler**. So up/down now
fall through to a widget that ignores them, and field navigation is dead.

**Wider blast radius (bonus fix).** The same guard also broke the focusable-Static
**picker** modals (`DependencyPickerScreen`, `ChildPickerScreen`,
`FoldedTaskPickerScreen`, `CrossRepoRefPickerScreen`, `FileReferencePickerScreen`,
`ColumnSelectScreen`) and `AgentCommandScreen`, whose items/buttons are navigated
by up/down via the same `focus_previous`/`focus_next` path and have no up/down
`on_key`. They were silently broken too; one fix restores them all.

**Intended outcome.** Up/down again move focus between fields in the detail dialog
(and items in the pickers / buttons in agent-command), while the shortcut editor's
DataTable keeps owning up/down for row navigation, and left/right keep working.

## Approach

Refine the over-broad guard so that **up/down fall through to the focused modal
widget only when that widget actually owns vertical navigation** (the shortcut
editor's `DataTable`); for every other modal, up/down drive the App's
modal-aware `action_nav_up`/`action_nav_down` (`focus_previous`/`focus_next`).
Left/right behavior is left exactly as today.

This restores the *pre-t848_4* design: `check_action` already has
widget-specific fall-through guards for `Input`, `SelectionList`, `SelectOverlay`
and screen-specific ones for `TuiSwitcherOverlay`, `SectionViewerScreen`
(`aitask_board.py:3651-3670`). Those guards were rendered dead by the blanket
guard short-circuiting first; removing the blanket up/down clause makes them live
again, and we add `DataTable` to that same family.

### Change — `KanbanApp.check_action` (`.aitask-scripts/board/aitask_board.py`)

Replace the single blanket clause (lines 3641-3642):

```python
if action in ("nav_up", "nav_down", "nav_left", "nav_right") and len(self.screen_stack) > 1:
    return False
```

with a split that keeps left/right identical and narrows up/down to
arrow-owning widgets:

```python
# Lateral nav (left/right) always falls through to the focused modal
# widget while a modal is on the stack — e.g. CycleField.on_key cycles its
# options, and Input moves its text cursor. The board's column nav is
# board-only.
if action in ("nav_left", "nav_right") and len(self.screen_stack) > 1:
    return False
# Vertical nav (up/down) falls through only when the focused modal widget
# owns row/line navigation itself — currently the shortcut editor's
# DataTable. For every other modal (TaskDetailScreen metadata fields, the
# task/dep/child pickers built from focusable Static items, AgentCommandScreen
# buttons) up/down must reach action_nav_up/down, which moves focus between
# widgets via focus_previous/next. Widget-specific fall-throughs (Input,
# SelectionList, SelectOverlay) and screen-specific ones (TuiSwitcherOverlay,
# SectionViewerScreen) are handled by the guards below.
if action in ("nav_up", "nav_down") and len(self.screen_stack) > 1 \
        and isinstance(self.app.focused, DataTable):
    return False
```

Add the import: `DataTable` is not currently imported in `aitask_board.py`
(it lives in the separate `shortcut_editor_modal.py`). Add it to the existing
`from textual.widgets import ...` line (`aitask_board.py:39`).

The existing per-widget / per-screen guards at lines 3651-3670 are unchanged and
now correctly handle their cases for up/down.

### Why this is safe (blast-radius summary)

| Modal (pushed in board) | Focused widget | up/down after fix |
|---|---|---|
| `TaskDetailScreen` | CycleField / Static fields | App `focus_previous/next` — **FIXED** |
| pickers (dep/child/folded/xrepo/file/column) | focusable `Static` items | App `focus_previous/next` — **FIXED** |
| `AgentCommandScreen` | Button | App `focus_previous/next` — restored; Input handled by Input guard |
| `ShortcutEditorModal` | `DataTable` | falls through — **preserved** |
| `TuiSwitcherOverlay` | ListView | existing TuiSwitcher guard |
| `IssueTypeFilterScreen` | `SelectionList` | existing SelectionList guard |
| Select dropdown | `SelectOverlay` | existing SelectOverlay guard |
| `SectionViewerScreen` | own | existing SectionViewer guard |
| confirm dialogs / Input modals | Button / Input | App focus nav (buttons) / Input guard (text cursor) |

Left/right are unchanged (still blanket fall-through), so `CycleField` cycling and
`Input` cursor movement keep working exactly as today. Main-screen behavior is
unchanged: the `Input`/`SelectionList`/`SelectOverlay` guards carry no
`screen_stack` condition and already fire on the base board.

## Files to modify

- `.aitask-scripts/board/aitask_board.py`
  - line 39: add `DataTable` to the `textual.widgets` import.
  - lines 3641-3642 (`KanbanApp.check_action`): replace the blanket nav guard
    with the left/right + up/down-DataTable split above.

## Verification

1. **Automated regression test (new).** Add `tests/test_board_detail_arrow_nav.py`
   mirroring the Pilot harness in `tests/test_board_picker_tab_nav.py`
   (real `KanbanApp` via `app.run_test`). Cases:
   - Push a `TaskDetailScreen`; assert `app.check_action("nav_up", None)` and
     `("nav_down", None)` are **not** `False` (App nav stays active), and that
     pressing `down`/`up` changes `app.focused` between detail field widgets while
     the screen stays a `TaskDetailScreen`.
   - Assert left/right still gated off (`check_action(...) is False`) so
     `CycleField` keeps handling them.
   - Optionally push the shortcut editor (`ShortcutEditorModal`) and assert
     `check_action("nav_up", None) is False` while its `DataTable` is focused
     (DataTable keeps owning up/down).
   - Run: `python3 -m pytest tests/test_board_detail_arrow_nav.py -v`
2. **Existing guard tests still pass:**
   `python3 -m pytest tests/test_board_picker_tab_nav.py -v`
   and `bash tests/run_all_python_tests.sh` (board-related subset).
3. **Manual smoke test:** `ait board` → focus a card → `Enter` to open the detail
   dialog → press ↓/↑ and confirm focus moves between metadata fields; ←/→ still
   cycle priority/effort/status; open a dependency picker and confirm ↓/↑ move
   between items; open the shortcut editor (`?`) and confirm ↓/↑ still move the
   DataTable row cursor.
4. **Lint:** `shellcheck` not applicable (Python-only change). No new TUI scope or
   binding added, so no shortcut-manifest / goldens regeneration required.

## Notes

- Pure board-TUI Python change — no skill/`.md.j2`/golden touchpoints, no new
  frontmatter field, no install-flow change.
- Per the TUI conventions doc (`aidocs/tui_conventions.md`, "Priority bindings +
  App.query_one gotcha" → arrow-key sub-note), this is the documented
  `priority=True` modal arrow-key interaction; the fix follows the doc's intent of
  letting arrows fall through *only* to widgets that own them.
- See **Step 9 (Post-Implementation)** in the task-workflow for cleanup, archival,
  and (since this runs on the current branch) the merge step is a no-op.
