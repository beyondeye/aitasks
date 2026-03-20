---
Task: t417_13_more_differ_visual_tweeks.md
Parent Task: aitasks/t417_diff_viewer_tui_for_brainstorming.md
Sibling Tasks: aitasks/t417/t417_11_*.md, aitasks/t417/t417_12_*.md
Archived Sibling Plans: aiplans/archived/p417/p417_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Diff Viewer Visual Tweaks (t417_13)

## Context

The diff viewer renders line numbers in a plain dim style without background colors, making them visually disconnected from the colored diff content. Additionally, colorblind users cannot distinguish insert (green) from delete (red) blocks by color alone. The task adds: (1) tag-colored backgrounds on line numbers, (2) "-"/"+" gutter labels on line numbers for accessibility, (3) two-space padding between line numbers and content.

## Files Modified

- `.aitask-scripts/diffviewer/diff_display.py` — All three visual changes in both renderers

## Implementation Steps

### 1. Add `_styled_lineno()` helper (module-level, after `_highlight_md_line`)

```python
def _styled_lineno(lineno: int | None, tag: str, prefix: str = "") -> Text:
    """Line number with tag background color and optional gutter prefix."""
    if lineno is None:
        return Text("")
    tag_style = TAG_STYLES.get(tag, Style())
    style = Style(dim=True, bgcolor=tag_style.bgcolor) if tag_style.bgcolor else Style(dim=True)
    text = f"{prefix}{lineno}" if prefix else str(lineno)
    return Text(text, style=style)
```

The column-level `style="dim"` remains on line number columns; the per-cell Style adds `bgcolor` from the tag. Right-alignment ensures `-42` and `42` digit-align correctly (the prefix occupies what was blank space).

### 2. Update `_render_interleaved()` — line numbers

Replace lines 378-380 (line number creation):

```python
# Gutter prefix on line numbers for colorblind accessibility
main_prefix = "-" if dl.tag == "delete" else ""
other_prefix = "+" if dl.tag == "insert" else ""
main_num = _styled_lineno(dl.main_lineno, dl.tag, main_prefix)
other_num = _styled_lineno(dl.other_lineno, dl.tag, other_prefix)
```

In interleaved mode, replace hunks are already flattened to delete+insert lines, so the tag-based prefixes work directly.

### 3. Update `_render_interleaved()` — content padding

Add 2 to the content column's left padding. Change the content column definition (line 368):

```python
table.add_column(no_wrap=True, width=content_width, padding=(0, 0, 0, 2))
```

Adjust `content_width` calculation (line 352) to subtract the 2 extra padding chars:

```python
content_width = max(20, available - LINENO_WIDTH * 2 - GUTTER_WIDTH - 4 - 2)
```

### 4. Update `_render_side_by_side()` — line numbers

Replace left line number (lines 454-458):

```python
main_prefix = "-" if sbl.tag in ("delete", "replace") else ""
main_num = _styled_lineno(sbl.main_lineno, sbl.tag, main_prefix)
```

Replace right line number (lines 493-496):

```python
other_prefix = "+" if sbl.tag in ("insert", "replace") else ""
other_num = _styled_lineno(sbl.other_lineno, sbl.tag, other_prefix)
```

### 5. Update `_render_side_by_side()` — content padding

Add left padding to both content columns. Change main content column (line 439):

```python
table.add_column(header=self._main_label, no_wrap=True, width=content_each, padding=(0, 0, 0, 2))
```

Change other content column (line 444):

```python
table.add_column(header=self._other_label, no_wrap=True, width=content_each, padding=(0, 0, 0, 2))
```

Adjust `content_each` calculation (line 426) to subtract 4 (2 padding × 2 content columns):

```python
content_each = max(10, (available - LINENO_WIDTH * 2 - GUTTER_WIDTH - 4 - 4) // 2)
```

### 6. Add tests

Add `TestStyledLineno` class to `tests/test_diff_display.py`:
- `test_insert_line_has_plus_prefix` — insert lineno text starts with "+"
- `test_delete_line_has_minus_prefix` — delete lineno text starts with "-"
- `test_equal_line_no_prefix` — equal lineno has no prefix
- `test_insert_has_bgcolor` — insert lineno style has insert bgcolor
- `test_delete_has_bgcolor` — delete lineno style has delete bgcolor
- `test_equal_is_dim_no_bgcolor` — equal lineno is dim with no bgcolor
- `test_none_lineno_returns_empty` — None lineno → empty Text

## Verification

1. Run tests: `python -m pytest tests/test_diff_display.py -v`
2. Visual check: `python -m .aitask-scripts.diffviewer.diffviewer_app` — load two test plans, verify:
   - Line numbers have colored backgrounds matching their diff content
   - Delete lines show "-N" in the line number column
   - Insert lines show "+N" in the line number column
   - Content text has visible spacing from line numbers
   - Both interleaved and side-by-side layouts look correct

## Post-Review Changes

### Change Request 1 (2026-03-20 07:50)
- **Requested by user:** Remove +/- prefix from line numbers (keep colored backgrounds only). Also, `Table.add_column()` does not support `padding` kwarg — fix the crash.
- **Changes made:** (1) Removed gutter prefix logic from both renderers — line numbers now only get tag-colored backgrounds. (2) Replaced per-column `padding=(0,0,0,2)` with `Text.assemble("  ", content)` to prepend 2-space padding in both layouts. In interleaved, content_width calc accounts for `CONTENT_PAD=2`.
- **Files affected:** `.aitask-scripts/diffviewer/diff_display.py`

## Final Implementation Notes

- **Actual work done:** Added `_styled_lineno()` helper that applies tag bgcolor to line numbers. Updated both `_render_interleaved()` and `_render_side_by_side()` to use it. Added 2-space content padding via `Text.assemble()` in both layouts. Added 7 tests for `_styled_lineno()`.
- **Deviations from plan:** (1) User dropped the +/- gutter prefix requirement after first review — line numbers now have colored backgrounds only. (2) Rich's `Table.add_column()` does not support per-column `padding`, so padding is applied by prepending "  " to content Text objects via `Text.assemble()`. (3) Interleaved gutter width stayed at 1 (not widened to 3 as in interim approach).
- **Issues encountered:** `Table.add_column()` crashed with `padding` kwarg — not supported in Rich. Fixed by using `Text.assemble()` for padding.
- **Key decisions:** Used `Style(dim=True, bgcolor=tag_style.bgcolor)` to keep line numbers dim while adding background color. The column-level `style="dim"` still applies as base. `_styled_lineno()` helper keeps prefix parameter for potential future use even though currently unused.
- **Notes for sibling tasks:** `_styled_lineno()` is a module-level helper exported from `diff_display.py`. It accepts `(lineno, tag, prefix)` and returns a Rich Text with dim + tag bgcolor. Both renderers now use `Text.assemble("  ", content)` for padding — any future renderer should follow the same pattern.

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
