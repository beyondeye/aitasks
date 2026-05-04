---
Task: t746_arrows_in_compare_tab_in_brainstorm.md
Base branch: main
plan_verified: []
---

# t746 — Up/down arrow navigation in Compare-tab node-selection dialog

## Context

In `ait brainstorm` → Compare tab, pressing `c` opens `CompareNodeSelectModal`
— a modal with a vertical list of `Checkbox` widgets (one per brainstorm
node) plus `Compare`/`Cancel` buttons.

Currently:
- `Tab` / `Shift+Tab` cycle focus across all focusable widgets (checkboxes
  + buttons).
- `Space` / `Enter` toggle the focused checkbox.
- **Up/Down arrow keys do nothing useful in the list** — focus does not move
  between checkboxes.

The task description explicitly asks for: *"up down arrows to navigate in
shown list of node"*. Space/Enter selection already works.

This pattern is already implemented elsewhere in the same file for the
**Actions wizard** node-selection step (line 3094 hint *"↑↓ Navigate Enter
Select"*) via the `_navigate_rows()` helper called from
`BrainstormApp.on_key()` (lines 1754–1760, 2020–2073). The fix mirrors that
pattern, scoped to the modal.

## Critical file

- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - `CompareNodeSelectModal` (lines 742–784) — the modal to extend.
  - `_navigate_rows()` (lines 2020–2073) — reference implementation for
    arrow-row navigation in the App. Not directly callable from the modal
    (`self.focused` semantics differ between App and ModalScreen), so the
    modal gets its own helper.
  - `_actions_show_node_select()` (line 3094) — reference for the `↑↓
    Navigate` hint label styling.

## Approach

### Change 1 — Add a pure-logic helper

Add a small free function near the existing helpers (e.g., adjacent to
`_sections_intersection` or near the modal class):

```python
def _next_checkbox_index(current: int | None, total: int, direction: int) -> int | None:
    """Compute next focus index for arrow navigation in a checkbox list.

    - current: currently focused checkbox index, or None if none focused
    - total: number of focusable checkboxes
    - direction: +1 (down) or -1 (up)

    Returns the new index, or None if focus should not move (no checkboxes,
    or already at the boundary in the requested direction). Stops at
    boundaries — no wrapping, consistent with `_navigate_rows`.
    """
    if total <= 0:
        return None
    if current is None:
        return 0 if direction == 1 else total - 1
    new_idx = current + direction
    if new_idx < 0 or new_idx >= total:
        return None
    return new_idx
```

This is the only piece that gets unit tested directly.

### Change 2 — Extend `CompareNodeSelectModal`

Add an `on_key` handler and a `_navigate_checkboxes` helper to the modal.
Also add a discoverability hint label to the dialog body, matching the
wizard's hint style:

```python
class CompareNodeSelectModal(ModalScreen):
    """Modal for selecting 2-4 nodes to compare in the dimension matrix."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, node_ids: list[str]):
        super().__init__()
        self.node_ids = node_ids

    def compose(self) -> ComposeResult:
        with Container(id="compare_select_dialog"):
            yield Label("Select 2–4 nodes to compare", id="compare_select_title")
            yield Label(
                "[dim]↑↓ Navigate  Space/Enter Toggle[/dim]",
                id="compare_select_hint",
            )
            with VerticalScroll(id="compare_checkbox_list"):
                for nid in self.node_ids:
                    yield Checkbox(nid, id=f"chk_cmp_{nid}")
            with Horizontal(id="compare_select_buttons"):
                yield Button("Compare", variant="primary", id="btn_compare")
                yield Button("Cancel", variant="default", id="btn_compare_cancel")

    # ... existing _get_selected, confirm, cancel, action_cancel unchanged ...

    def on_key(self, event) -> None:
        if event.key in ("up", "down"):
            direction = 1 if event.key == "down" else -1
            if self._navigate_checkboxes(direction):
                event.prevent_default()
                event.stop()

    def _navigate_checkboxes(self, direction: int) -> bool:
        try:
            container = self.query_one("#compare_checkbox_list", VerticalScroll)
        except Exception:
            return False
        checkboxes = [w for w in container.children
                      if isinstance(w, Checkbox) and w.can_focus]
        if not checkboxes:
            return False
        focused = self.focused
        current = checkboxes.index(focused) if focused in checkboxes else None
        new_idx = _next_checkbox_index(current, len(checkboxes), direction)
        if new_idx is None:
            return False
        checkboxes[new_idx].focus()
        checkboxes[new_idx].scroll_visible()
        return True
```

Notes on behavior choices:

- **No wrapping** at boundaries (consistent with `_navigate_rows`). Up at
  the first checkbox is a no-op; down at the last checkbox is a no-op. Tab
  is still available to reach the buttons.
- **No focus on first refresh**: Textual's default first-focusable selection
  already lands on the first `Checkbox`, so no `call_after_refresh` is
  needed. Up/down behavior when *no* checkbox has focus (e.g., user tabbed
  to a button then pressed up) routes focus back to the first/last
  checkbox via `_next_checkbox_index(None, ...)`.
- **Why `on_key` instead of priority bindings**: matches the existing
  pattern in this file (`BrainstormApp.on_key` line 1633, multiple
  `_navigate_rows` callsites). If empirical testing shows
  `VerticalScroll`'s default scroll behavior consumes the arrow keys before
  `on_key` fires, the fallback is to switch to `Binding("up", "nav_prev",
  show=False, priority=True)` on the modal — but the same pattern works
  for the wizard today, so this is unlikely.

### Change 3 — CSS for the new hint label

Add a small CSS rule near the existing `#compare_select_title` block
(around line 1248):

```css
#compare_select_hint {
    text-align: center;
    width: 100%;
    margin-bottom: 1;
}
```

(`[dim]…[/dim]` markup handles the muted styling; the rule just centers it
to match the title.)

### Change 4 — Test the helper

New test file `tests/test_brainstorm_compare_modal.py` exercising
`_next_checkbox_index` only (consistent with the file-level convention in
`test_brainstorm_wizard_sections.py` — pure-logic helpers tested,
Pilot/end-to-end TUI deferred to manual verification).

```python
"""Tests for compare-modal arrow navigation helper (t746)."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_app import _next_checkbox_index  # noqa: E402


class NextCheckboxIndexTests(unittest.TestCase):
    def test_no_checkboxes_returns_none(self):
        self.assertIsNone(_next_checkbox_index(None, 0, 1))
        self.assertIsNone(_next_checkbox_index(None, 0, -1))
        self.assertIsNone(_next_checkbox_index(0, 0, 1))

    def test_no_focus_down_focuses_first(self):
        self.assertEqual(_next_checkbox_index(None, 5, 1), 0)

    def test_no_focus_up_focuses_last(self):
        self.assertEqual(_next_checkbox_index(None, 5, -1), 4)

    def test_down_increments(self):
        self.assertEqual(_next_checkbox_index(0, 5, 1), 1)
        self.assertEqual(_next_checkbox_index(2, 5, 1), 3)

    def test_up_decrements(self):
        self.assertEqual(_next_checkbox_index(4, 5, -1), 3)
        self.assertEqual(_next_checkbox_index(1, 5, -1), 0)

    def test_down_at_bottom_stays(self):
        self.assertIsNone(_next_checkbox_index(4, 5, 1))

    def test_up_at_top_stays(self):
        self.assertIsNone(_next_checkbox_index(0, 5, -1))

    def test_single_checkbox_no_movement(self):
        self.assertIsNone(_next_checkbox_index(0, 1, 1))
        self.assertIsNone(_next_checkbox_index(0, 1, -1))


if __name__ == "__main__":
    unittest.main()
```

## Verification

1. **Unit test** — runs in <1s, no TUI needed:

   ```bash
   python tests/test_brainstorm_compare_modal.py
   ```

   Expect: all assertions pass.

2. **Lint** — file has been edited:

   ```bash
   shellcheck .aitask-scripts/aitask_*.sh   # unrelated, sanity only
   ```

   No new shell scripts; Python lint only matters if the project runs one
   (no `lint_command` in `project_config.yaml` — skip).

3. **Manual TUI verification** (the load-bearing check):

   - Launch `ait brainstorm` in a project with an existing brainstorm
     session containing ≥3 nodes (or initialize one).
   - Switch to **Compare** tab (`c` key from any other tab).
   - Press `c` again to open the node-selection modal.
   - **Test:**
     - First focus lands on the first checkbox (current behavior).
     - `↓` moves focus to the second checkbox (highlight ring moves).
     - Repeated `↓` advances down the list; at the last item, further `↓`
       is a no-op (no wrap, no error).
     - `↑` moves focus back up; at the first item, further `↑` is a no-op.
     - `Space` and `Enter` still toggle the focused checkbox.
     - `Tab` still cycles into `Compare` / `Cancel` buttons.
     - From a focused button, pressing `↑` jumps focus back to the **last**
       checkbox; `↓` from a focused button jumps to the **first** checkbox.
     - Hint *"↑↓ Navigate  Space/Enter Toggle"* is visible under the
       title.

## Step 9 — Post-Implementation

- Standard archival via `aitask_archive.sh 746`.
- No worktree to clean (Step 5 chose current branch via profile `fast`).
- No build verification configured (`verify_build` absent in
  `project_config.yaml`).

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Added
  `_next_checkbox_index()` free function before `CompareNodeSelectModal`,
  added `on_key()` and `_navigate_checkboxes()` methods to the modal, added
  a hint `Label` (`#compare_select_hint`) under the dialog title, added a
  matching CSS rule for `#compare_select_hint`, and created
  `tests/test_brainstorm_compare_modal.py` with 8 unit tests for the
  index helper. All 8 new tests pass; existing
  `test_brainstorm_init_failure_modal.py` (10) and
  `test_brainstorm_wizard_sections.py` (16) still pass.
- **Deviations from plan:** None.
- **Issues encountered:** Source file uses Python `\uXXXX` escape sequences
  (e.g. `–`, `↑`) for non-ASCII characters in string literals
  rather than literal UTF-8. Edits preserved the existing convention.
- **Key decisions:** Kept the `on_key` approach (matching the existing
  `BrainstormApp.on_key` pattern in the same file) rather than priority
  bindings — the empirical-test fallback noted in the plan was not needed.
  No-wrap boundary behavior matches `_navigate_rows` for consistency.
- **Upstream defects identified:** None.

