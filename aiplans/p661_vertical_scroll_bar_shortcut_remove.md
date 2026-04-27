---
Task: t661_vertical_scroll_bar_shortcut_remove.md
Base branch: main
plan_verified: []
---

# Plan: Remove `b` scrollbar-toggle shortcut from `ait monitor`

## Context

In `ait monitor`, the agent preview pane currently exposes a `b` keyboard shortcut that toggles the vertical scrollbar via `action_toggle_scrollbar`. The user reports that toggling the scrollbar OFF makes the preview disappear — likely because setting `scrollbar_size_vertical = 0` interacts badly with the layout / `scrollbar-gutter: stable` rule. More importantly, toggling the scrollbar is no longer considered useful.

**Goal:** Remove the `b` shortcut and the toggle action entirely. The vertical scrollbar should always be visible (the default state — `_show_scrollbar` is initialized to `True`, so removing the toggle naturally leaves the scrollbar always-on, with no CSS or initial-state changes required).

## Files to modify

### 1. `.aitask-scripts/monitor/monitor_app.py`

Remove all four references to the toggle-scrollbar feature:

- **Line 449** — remove the binding entry from `BINDINGS`:
  ```python
  Binding("b", "toggle_scrollbar", "Scrollbar"),
  ```
- **Line 501** — remove the now-unused instance attribute initialization in `__init__`:
  ```python
  self._show_scrollbar: bool = True
  ```
- **Lines 1356–1366** — remove the entire `action_toggle_scrollbar` method:
  ```python
  def action_toggle_scrollbar(self) -> None:
      """Toggle the vertical scrollbar on the preview panel."""
      self._show_scrollbar = not self._show_scrollbar
      try:
          scroll = self.query_one("#preview-scroll", ScrollableContainer)
      except Exception:
          return
      scroll.styles.scrollbar_size_vertical = 1 if self._show_scrollbar else 0
      self.notify(
          f"Scrollbar: {'shown' if self._show_scrollbar else 'hidden'}"
      )
  ```

A repo-wide grep confirmed `_show_scrollbar` and `toggle_scrollbar` are referenced only in this file, so no further code touchpoints. The CSS rule `scrollbar-gutter: stable` for `#preview-scroll` (line 426) stays — it already keeps gutter space reserved so the always-visible scrollbar lays out cleanly.

### 2. `website/content/docs/tuis/monitor/reference.md`

- **Line 44** — remove the `b` row from the Monitor Controls table:
  ```markdown
  | `b` | Toggle the preview scrollbar visibility | Global |
  ```

The surrounding rows (`z` zoom and `t` tail) stay unchanged.

### Out of scope

- The v0.15.1 blog post (`website/content/blog/v0151-...md`) mentions the `b` toggle as a historical release note. Per the project doc convention ("User-facing docs describe the current state only" for live docs; release-note posts are historical), the blog post is **not** edited — it describes a feature shipped in v0.15.1, which was real at that point in time.

## Verification steps

1. **Syntax check** — confirm the edited Python file still parses:
   ```bash
   python3 -c "import ast; ast.parse(open('.aitask-scripts/monitor/monitor_app.py').read())"
   ```

2. **Confirm no orphaned references** remain:
   ```bash
   grep -n "_show_scrollbar\|toggle_scrollbar" .aitask-scripts/monitor/monitor_app.py
   ```
   Expected: no matches.

3. **Manual TUI smoke test** — launch `ait monitor` inside tmux:
   - Footer should no longer show the `b Scrollbar` hint.
   - Pressing `b` should do nothing (or, if the preview zone is active, be forwarded to the focused tmux pane like any other unbound character — which is the desired behavior).
   - The vertical scrollbar should be visible at the right edge of the agent preview pane.
   - Other monitor shortcuts (`z`, `t`, `r`, `j`, etc.) should still function.

## Step 9 (Post-Implementation)

Standard cleanup, archival, and merge per the task-workflow `Step 9` procedure (single-task, no worktree, working on `main`).

## Final Implementation Notes

- **Actual work done:** Removed the `b` keyboard shortcut and its `action_toggle_scrollbar` action from `ait monitor`. Three deletions in `.aitask-scripts/monitor/monitor_app.py` (the `BINDINGS` row, the `_show_scrollbar` instance attribute initialization in `__init__`, and the `action_toggle_scrollbar` method) and one row removal in `website/content/docs/tuis/monitor/reference.md` (the `b` row of the Monitor Controls table). The vertical scrollbar is now always visible via the existing CSS layout (`scrollbar-gutter: stable` on `#preview-scroll`); no CSS or layout changes were needed because `_show_scrollbar` was already initialized to `True` and only the toggle action ever flipped it.
- **Deviations from plan:** None. Implementation matched the plan exactly.
- **Issues encountered:** None.
- **Key decisions:**
  - Left the v0.15.1 blog post (`website/content/blog/v0151-...md`) untouched. It's a historical release note describing what shipped at that point in time; per project doc conventions, only live user-facing docs (the monitor reference page) need updating to reflect the current state.
  - Dropped the `_show_scrollbar` attribute entirely rather than keeping it as a permanently-true flag — no other code reads it, so a renamed/unused attribute would just be dead state.
- **Verification:**
  - `python3 -c "import ast; ast.parse(...)"` — passed.
  - `grep _show_scrollbar\|toggle_scrollbar` on the edited file — no matches (clean removal).
  - Manual TUI smoke test of `ait monitor` is left to the user.
