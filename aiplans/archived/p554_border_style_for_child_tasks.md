---
Task: t554_border_style_for_child_tasks.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# p554: Dashed Border for Child Task Cards

## Goal
In `ait board` TUI main screen, distinguish child task cards from parent task cards by using a `dashed` border style for children. The selected (focused) card keeps the `double` border style regardless of parent/child.

## Investigation

The board TUI is implemented in `.aitask-scripts/board/aitask_board.py`. Task cards are rendered by the `TaskCard` class. Border is set in three methods on `TaskCard`:

- `on_mount` (line 733): `self.styles.border = ("solid", self._priority_border_color())` — initial render
- `on_focus` (line 741): `self.styles.border = ("double", "cyan")` — when selected
- `on_blur` (line 745): `self.styles.border = ("solid", self._priority_border_color())` — after losing focus

`self.is_child` is a boolean set in `TaskCard.__init__` (line 610, 614), and is `True` for child cards (set at line 798 when rendering children of an expanded parent).

Textual supports the `dashed` border style — see https://textual.textualize.io/styles/border/.

## Plan

Introduce a small helper method `_idle_border_style(self)` on `TaskCard` that returns `"dashed"` for child tasks and `"solid"` for parent tasks. Use it in both `on_mount` and `on_blur`.

Leave `on_focus` unchanged — the selected card always shows `("double", "cyan")`.

## Files to modify

1. `.aitask-scripts/board/aitask_board.py` — TaskCard class (around lines 726-745)

## Detailed changes

Replace:
```python
    def _priority_border_color(self):
        priority = self.task_data.metadata.get('priority', 'normal')
        if priority == "high": return "red"
        if priority == "medium": return "yellow"
        return "gray"

    def on_mount(self):
        self.styles.border = ("solid", self._priority_border_color())
        ...

    def on_blur(self):
        self.styles.border = ("solid", self._priority_border_color())
```

With:
```python
    def _priority_border_color(self):
        priority = self.task_data.metadata.get('priority', 'normal')
        if priority == "high": return "red"
        if priority == "medium": return "yellow"
        return "gray"

    def _idle_border_style(self):
        return "dashed" if self.is_child else "solid"

    def on_mount(self):
        self.styles.border = (self._idle_border_style(), self._priority_border_color())
        ...

    def on_blur(self):
        self.styles.border = (self._idle_border_style(), self._priority_border_color())
```

## Verification

1. Run `ait board`.
2. Find a parent task with children and expand it (press the expand key).
3. Confirm child task cards render with a **dashed** border, parent cards remain **solid**.
4. Focus a child card — border switches to **double cyan**.
5. Blur the child card — border returns to **dashed** with the priority color.
6. Confirm parent cards still show their priority-colored solid borders.

## Step 9 (Post-Implementation)

After user approval in Step 8, proceed with Step 9 (archive and push) per the shared task-workflow.

## Final Implementation Notes

- **Actual work done:** Added `_idle_border_style()` helper to `TaskCard` returning `"dashed"` for child tasks and `"solid"` for parent tasks. Updated `on_mount` and `on_blur` to call the helper; `on_focus` still sets `("double", "cyan")` unchanged.
- **Deviations from plan:** None.
- **Issues encountered:** None. Syntax check passed; TUI was not launched from the agent (user-verified interactively).
- **Key decisions:** Introduced a tiny helper instead of inlining the conditional in two places — keeps the two idle-state setters in sync if the style rule ever changes.
