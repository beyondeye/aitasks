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

## Final Implementation Notes
- **Actual work done:** All 7 steps implemented as planned. Added `ANNOTATION_COLORS` palette, `_build_annotation_gutter()`, `set_annotations()`, `toggle_annotations()` to `code_viewer.py`. Extended `_rebuild_display()` to 3-column table. Added `t` keybinding, `_update_code_annotations()` helper, and `action_toggle_annotations()` to `codebrowser_app.py`. Wired annotation updates into both `_load_explain_data` and `_refresh_explain_data` workers.
- **Deviations from plan:** Step 5 (refactor to `_rebuild_display()`) was already done by t195_3 — no refactor needed, just extended the existing method. Added `_update_code_annotations()` helper in the app (not in original plan) to centralize the logic for extracting file-specific annotations from the explain data dict and passing them to the code viewer. Annotations are cleared (`self._annotations = []`) in `load_file()` to avoid stale annotations showing when switching files before explain data loads.
- **Issues encountered:** None. The `_rebuild_display()` method from t195_3 was perfectly set up for extension as noted in t195_3's sibling notes.
- **Key decisions:** Used `hash(task_id) % len(ANNOTATION_COLORS)` for color assignment — deterministic across sessions for the same task ID. The 3rd column always exists in the table (width=12) even when annotations are hidden — renders empty `Text()` objects to maintain consistent column structure.
- **Notes for sibling tasks:** `set_annotations()` triggers `_rebuild_display()` only when `_show_annotations` is True; `toggle_annotations()` always triggers rebuild. The `_update_code_annotations()` method in the app converts from the dict-based `_current_explain_data` to file-specific annotations using relative path lookup. t195_6 (cursor navigation) should be aware that `_rebuild_display()` now builds 3 columns — cursor highlighting will need to account for this. t195_8 (rendering hardening) should test annotation gutter with edge cases (overlapping ranges, very long task ID lists, files with 0 annotations).
