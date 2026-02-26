---
priority: medium
effort: medium
depends: [t195_5]
issue_type: test
status: Done
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-25 12:19
updated_at: 2026-02-26 10:01
completed_at: 2026-02-26 10:01
---

## Context

This is child task 8 of t195 (Python Code Browser TUI) — a risk mitigation follow-up for Risk 1 (Rich Table alignment). After the core code viewer and annotation overlay are built, this task hardens the rendering against edge cases that could break the visual alignment between line numbers, code, and annotations.

## Key Files to Modify

- **`aiscripts/codebrowser/code_viewer.py`** (MODIFY):
  - Handle long lines: add `no_wrap=True` on code column, implement horizontal scroll or truncation with `...` indicator at terminal width
  - Handle tab characters: normalize tabs to spaces (configurable tab width, default 4)
  - Handle unicode/emoji: ensure Rich Table column widths account for wide characters
  - Handle binary files: detect non-text files, show "Binary file — cannot display" message instead of garbled content
  - Handle empty files: show "(empty file)" message
  - Handle files with only whitespace: display normally
  - Handle very long lines (>500 chars): truncate with `...` to prevent layout breakage
  - Add `overflow: hidden` CSS on code display to prevent horizontal overflow

## Reference Files for Patterns

- `aiscripts/codebrowser/code_viewer.py` (from t195_3, t195_5): Current `_rebuild_display()` and Rich Table construction
- `aiscripts/aitask_explain_extract_raw_data.sh` (lines 28-31): Binary file detection pattern using `file -b --mime-encoding`
- Rich `Table` API: `Column(no_wrap=True, overflow="ellipsis")` for overflow handling

## Implementation Plan

1. Add binary file detection in `load_file()`:
   - Check file encoding: `subprocess.run(["file", "-b", "--mime-encoding", str(file_path)])` — if output contains "binary", show message instead of content
   - Alternative: try `file_path.read_text()`, catch `UnicodeDecodeError`, show binary message

2. Add tab normalization:
   - `self._tab_width: int = 4`
   - In `load_file()`, replace `\t` with spaces: `line.expandtabs(self._tab_width)`

3. Handle long lines:
   - Set `no_wrap=True` on the code column in the Rich Table
   - Add `max_width` parameter: if line exceeds terminal width minus gutter widths, truncate with `...`
   - Or use Rich `Text.truncate()` method

4. Handle edge cases in `load_file()`:
   - Empty file (0 bytes): show `Static("(empty file)")`, don't build table
   - File read error (permissions, deleted): show error message, don't crash

5. Test with problematic files:
   - Create test files with: very long lines, tabs, unicode, emoji, mixed line endings, null bytes
   - Verify rendering doesn't break

## Verification Steps

1. Open a binary file (e.g., a .png or compiled .pyc) — should show "Binary file" message, not garbled content
2. Open a file with very long lines (200+ chars) — should not break layout, lines truncated or scrollable
3. Open a file with tab characters — tabs rendered as consistent spaces
4. Open an empty file — shows "(empty file)" message
5. Open a file with unicode characters — renders correctly, columns stay aligned
6. Open a file with emoji — no crash, reasonable display
7. Annotation gutter stays aligned in all above cases
