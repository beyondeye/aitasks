---
priority: high
effort: medium
depends: [t195_3, t195_4]
issue_type: feature
status: Done
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-25 12:18
updated_at: 2026-02-25 22:49
completed_at: 2026-02-25 22:49
---

## Context

This is child task 5 of t195 (Python Code Browser TUI). It adds the task annotation overlay — a gutter on the right side of the code viewer that shows which aitask originated each code section. This is the core feature that differentiates the codebrowser from a regular code viewer.

The annotation data comes from `ExplainManager` (t195_4) as a list of `AnnotationRange` objects, each mapping a line range to task IDs. The code viewer (t195_3) already renders a Rich Table with line numbers and code — this task adds the third column for annotations.

## Key Files to Modify

- **`aiscripts/codebrowser/code_viewer.py`** (MODIFY):
  - Extend `load_file()` to create a 3-column Rich Table (line numbers, code, annotations) instead of 2-column
  - Add `set_annotations(annotations: list[AnnotationRange])`: populates the annotation gutter
  - Add `_build_annotation_gutter() -> list[Text]`: maps line ranges to per-line annotation text
  - Color-code task IDs: assign colors from a palette cycling through task IDs
  - Third column styling: right-aligned or left-aligned, distinct color, slightly dimmer than code
  - Toggle visibility: `show_annotations` flag, `t` key binding toggles between showing/hiding the gutter
  - Handle missing annotations: show empty gutter when no data is available
- **`aiscripts/codebrowser/codebrowser_app.py`** (MODIFY):
  - Wire explain data to code viewer: when `_load_explain_data()` completes, call `code_viewer.set_annotations()`
  - Add `t` keybinding: `Binding("t", "toggle_annotations", "Toggle annotations")`
  - `action_toggle_annotations()`: toggles gutter visibility and rebuilds display

## Reference Files for Patterns

- `aiscripts/codebrowser/annotation_data.py` (from t195_1): `AnnotationRange` dataclass — `start_line`, `end_line`, `task_ids`, `commit_hashes`, `commit_messages`
- `aiscripts/codebrowser/code_viewer.py` (from t195_3): Current 2-column Rich Table rendering
- `aiscripts/codebrowser/explain_manager.py` (from t195_4): `get_cached_data()` returns `FileExplainData` with `annotations: list[AnnotationRange]`
- `aiscripts/board/aitask_board.py` (lines 407-551): `TaskCard` rendering — pattern for building Rich `Text` objects with multiple styles

## Implementation Plan

1. Define annotation color palette in `code_viewer.py`:
   ```python
   ANNOTATION_COLORS = ["cyan", "green", "yellow", "magenta", "blue", "red", "bright_cyan", "bright_green"]
   ```
   - Assign colors by cycling: task_id hash % len(palette) or first-seen order

2. Add `_build_annotation_gutter(self) -> list[Text]`:
   - Create a list of `Rich.Text` objects, one per source line (initialized empty)
   - For each `AnnotationRange`: for lines in `[start_line, end_line]`, set the annotation text to the task ID(s) joined by `,` (e.g., `t42`, `t42,t130`)
   - Apply color based on first task ID in the range
   - Return the list

3. Modify `load_file()`:
   - Change Table from 2 columns to 3:
     - Column 3: annotation (style varies per task, width=12, no_wrap=True, justify="left")
   - Initially render empty annotations (third column all empty strings)
   - Store `self._annotations: list[AnnotationRange] = []`

4. Add `set_annotations(annotations: list[AnnotationRange])`:
   - Store `self._annotations = annotations`
   - If `self._show_annotations`: rebuild display with populated gutter
   - Else: do nothing (annotations stored but not displayed)

5. Add `_rebuild_display()` method (refactor from `load_file()`):
   - Builds the Rich Table from stored `_lines`, `_annotations`, `_show_annotations`
   - Called by `load_file()`, `set_annotations()`, and toggle

6. Add toggle:
   - `self._show_annotations: bool = True`
   - `toggle_annotations()`: flip flag, call `_rebuild_display()`

7. Wire in `codebrowser_app.py`:
   - In `_load_explain_data()` completion callback: `self.code_viewer.set_annotations(data.annotations)`
   - Add `t` binding and `action_toggle_annotations()`

## Verification Steps

1. Select a file that has been modified by tasks — annotation gutter should show task IDs (e.g., `t42`, `t130_2`)
2. Different tasks should have different colors
3. Line ranges should be correctly mapped (check against `reference.yaml` data)
4. Press `t` — annotations should hide; press again — they reappear
5. Select a file with no explain data yet — gutter should be empty, no errors
6. Select a file that was never modified by any task — gutter should be empty
7. File info bar should still show explain timestamp correctly
