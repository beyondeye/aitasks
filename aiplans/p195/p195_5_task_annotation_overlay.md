---
Task: t195_5_task_annotation_overlay.md
Parent Task: aitasks/t195_python_codebrowser.md
Sibling Tasks: aitasks/t195/t195_3_*.md, aitasks/t195/t195_4_*.md, aitasks/t195/t195_6_*.md
Archived Sibling Plans: aiplans/archived/p195/p195_*_*.md
Branch: main
Base branch: main
---

# Plan: t195_5 — Task Annotation Overlay

## Steps

### 1. Define color palette in `code_viewer.py`
```python
ANNOTATION_COLORS = ["cyan", "green", "yellow", "magenta", "blue", "red", "bright_cyan", "bright_green"]
```
Assign colors by task_id hash or first-seen order.

### 2. Add `_build_annotation_gutter() -> list[Text]`
- Initialize list of `Rich.Text` objects (one per line, all empty)
- For each `AnnotationRange`: set annotation text to task IDs joined by `,`
- Apply color from palette based on first task_id

### 3. Extend Rich Table to 3 columns
- Column 3: annotation (width=12, no_wrap=True, justify="left")
- Initially empty when no annotations loaded

### 4. Add `set_annotations(annotations: list[AnnotationRange])`
- Store annotations, rebuild display if `_show_annotations` is True

### 5. Refactor to `_rebuild_display()`
- Extract table building from `load_file()` into shared method
- Called by: `load_file()`, `set_annotations()`, toggle

### 6. Add toggle
- `self._show_annotations: bool = True`
- When False: 3rd column renders empty
- `t` binding in app: `action_toggle_annotations()`

### 7. Wire in app
- On explain data ready: `code_viewer.set_annotations(data.annotations)`
- `t` key toggles

## Verification
- Files with task history show colored task IDs in gutter
- Different tasks get different colors
- `t` hides/shows annotations
- No annotations data → empty gutter, no errors
