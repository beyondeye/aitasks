---
Task: t417_4_diff_display_widget.md
Parent Task: aitasks/t417_diff_viewer_tui_for_brainstorming.md
Sibling Tasks: aitasks/t417/t417_1_*.md through t417_3_*.md, aitasks/t417/t417_5_*.md through t417_7_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Diff Display Widget (t417_4)

## 1. Create `diff_display.py`

File: `.aitask-scripts/diffviewer/diff_display.py`

Follow the `CodeViewer` pattern from `.aitask-scripts/codebrowser/code_viewer.py`.

### Class Structure

```python
class DiffDisplay(VerticalScroll):
    """Widget that renders diff hunks with color coding and keyboard navigation."""

    class CursorMoved(Message):
        def __init__(self, line: int) -> None:
            super().__init__()
            self.line = line

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._diff: PairwiseDiff | None = None
        self._multi_diff: MultiDiffResult | None = None
        self._cursor_line: int = 0
        self._flat_lines: list[_DisplayLine] = []  # flattened for cursor nav
        self._active_comparison_idx: int = 0
```

### `_DisplayLine` Helper

```python
@dataclass
class _DisplayLine:
    """One rendered line in the display."""
    main_lineno: int | None
    other_lineno: int | None
    tag: str
    content: str
    source_plan: str = ""
```

### Rendering

`_render_diff() -> Rich.Table`:
- Build a Rich `Table` with columns: main_lineno (4 chars, right-aligned, dim), other_lineno (4 chars, right-aligned, dim), gutter (1 char), content (remaining width)
- For each `_DisplayLine`:
  - Apply Rich Style based on tag:
    - `equal`: `Style(dim=True)`
    - `insert`: `Style(color="white", bgcolor="dark_green")`
    - `delete`: `Style(color="white", bgcolor="dark_red")`
    - `replace`: `Style(color="white", bgcolor="dark_goldenrod")`
    - `moved`: `Style(color="white", bgcolor="dark_cyan")`
  - Gutter char: `' '` equal, `'+'` insert, `'-'` delete, `'~'` replace, `'>'` moved
  - Cursor line gets additional highlight: `Style(bold=True)`
- Mount the Table as a `Static` child widget (same pattern as CodeViewer)

### `load_diff(diff: PairwiseDiff)`

1. Store `self._diff = diff`
2. Flatten hunks into `_flat_lines`:
   - For each hunk, expand main_lines and other_lines into _DisplayLine objects
   - For `equal`: one line per matched pair (both line numbers)
   - For `insert`: other_lines only (main_lineno=None)
   - For `delete`: main_lines only (other_lineno=None)
   - For `replace`: interleave main (as delete) then other (as insert) lines
   - For `moved`: other_lines with both line numbers
3. Reset cursor to 0
4. Call `_render_diff()` and update display

### `load_multi_diff(result: MultiDiffResult, active_idx: int = 0)`

1. Store result and active_idx
2. Load the active comparison as a regular diff via `load_diff()`
3. For unified overlay mode: merge all pairwise diffs, interleaving hunks by position, adding `source_plan` to gutter

### `set_active_comparison(idx: int)`

Switch which comparison is displayed without recomputing diffs.

### Keyboard Navigation

```python
BINDINGS = [
    Binding("up", "cursor_up", "Up", show=False),
    Binding("down", "cursor_down", "Down", show=False),
    Binding("page_up", "page_up", "Page Up", show=False),
    Binding("page_down", "page_down", "Page Down", show=False),
    Binding("home", "cursor_home", "Home", show=False),
    Binding("end", "cursor_end", "End", show=False),
]
```

Each action: update `_cursor_line`, scroll viewport, post `CursorMoved`, re-render current line highlight.

### Empty State

If all hunks are `equal`, display centered message: "No differences found between the plans."

## 2. Plan Identifier Colors (for multi-diff gutter)

```python
PLAN_COLORS = [
    ("A", "#FF5555"),  # Red
    ("B", "#50FA7B"),  # Green
    ("C", "#8BE9FD"),  # Cyan
    ("D", "#FFB86C"),  # Orange
    ("E", "#BD93F9"),  # Purple
]
```

In multi-diff mode, the gutter shows the plan letter in its assigned color instead of the +/-/~ indicator.

## 3. Verification

- Instantiate widget, call `load_diff()`: renders without crash
- Visual check: insert lines green, delete red, replace yellow, equal dim
- Cursor moves with up/down, viewport follows
- `load_multi_diff()` with 2 comparisons: gutter shows A/B identifiers
- Empty diff: shows "No differences found" message
- Large diff (100+ lines): no performance degradation

## Final Implementation Notes

- **Actual work done:** Created `diff_display.py` with `DiffDisplay(VerticalScroll)` class following the CodeViewer pattern. Implemented `_DisplayLine` dataclass, `_flatten_hunks()` module-level helper, `load_diff()`, `load_multi_diff()`, `set_active_comparison()`, `_render_diff()` with Rich Table, keyboard navigation (up/down/page_up/page_down/home/end), and `CursorMoved` message. Added plan identifier gutter colors for multi-diff mode. Added empty-state handling.
- **Deviations from plan:** `CursorMoved` message includes `total` field (matching CodeViewer pattern) rather than just `line`. The `_flatten_hunks()` function is module-level rather than a method, for easier testing. Binding strings use `pageup`/`pagedown` (Textual convention) rather than `page_up`/`page_down`. Line number columns use width 5 (matching CodeViewer) rather than 4. No viewport windowing — plan diffs are unlikely to exceed 2000 lines, so the simpler approach was used. Unified overlay mode for multi-diff (item 3 in `load_multi_diff`) was deferred — the per-comparison switching approach is sufficient for now.
- **Issues encountered:** None.
- **Key decisions:** `replace` hunks are flattened as delete lines + insert lines (main first, then other) for clarity. Moved hunks use `other_lines` as display content with both line numbers when available. Module-level `_all_equal()` helper detects identical-plan case cleanly.
- **Notes for sibling tasks:** `DiffDisplay` exposes `load_diff(PairwiseDiff)` and `load_multi_diff(MultiDiffResult, active_idx)` as its public loading API. The `CursorMoved` message includes `line` (1-indexed) and `total`. The widget's Static child has id `"diff_display"`. `set_active_comparison(idx)` switches between comparisons in multi-diff mode. The multi-diff gutter uses `PLAN_COLORS` (A-E) — if more than 5 comparisons are needed, extend this list.

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
