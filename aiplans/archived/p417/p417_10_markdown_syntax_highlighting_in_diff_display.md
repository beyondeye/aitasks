---
Task: t417_10_markdown_syntax_highlighting_in_diff_display.md
Parent Task: aitasks/t417_diff_viewer_tui_for_brainstorming.md
Sibling Tasks: aitasks/t417/t417_11_*.md, aitasks/t417/t417_12_*.md
Archived Sibling Plans: aiplans/archived/p417/p417_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Markdown Syntax Highlighting in Diff Display (t417_10)

## Context

The diff viewer renders all content as plain text with only diff-colored backgrounds (green/red/orange for insert/delete/replace). Since it exclusively handles markdown plan files, the content should show markdown formatting — headings bold and colored, **bold** text, *italic*, `inline code`, list bullets styled — while preserving existing diff background colors.

## Files Modified

- `.aitask-scripts/diffviewer/diff_display.py` — Added `MD_STYLES` dict, regex patterns, `_highlight_md_line()` function, integrated into both renderers and `_word_diff_texts()`
- `tests/test_diff_display.py` — Added `TestHighlightMdLine` (13 tests)

## Implementation Steps

### 1. Added themable `MD_STYLES` dictionary

Module-level dict following the same pattern as `TAG_STYLES`. All markdown colors in one place for easy theming:
- `h1`–`h6`: Bold + level-scaled foreground colors (Dracula palette)
- `bold`: Bold style
- `italic`: Italic style
- `code`: Yellow foreground (`#F1FA8C`)
- `bullet`: Bold + pink foreground (`#FF79C6`)

### 2. Added compiled regex patterns

Six module-level compiled patterns: `_MD_HEADING_RE`, `_MD_BOLD_RE`, `_MD_ITALIC_RE`, `_MD_CODE_RE`, `_MD_LIST_RE`, `_MD_OLIST_RE`.

### 3. Added `_highlight_md_line(line: str) -> Text`

Returns a `Rich.Text` with markdown-level styles applied. Headings get whole-line styling with early return. Bold/italic/code use `finditer` spans. List bullets style only the bullet character.

### 4. Integrated into `_word_diff_texts()`

Replaced `Text(main_line)` / `Text(other_line)` with `_highlight_md_line()` calls. Existing dim and tag styles layer on top — matching words keep markdown formatting (dimmed), changed words get full diff color.

### 5. Integrated into `_render_interleaved()`

Replaced `Text(dl.content)` with `_highlight_md_line(dl.content)` for non-word-diff lines. The subsequent `stylize(tag_style)` layers diff background on top.

### 6. Integrated into `_render_side_by_side()`

Replaced `Text(sbl.main_content)` and `Text(sbl.other_content)` with `_highlight_md_line()` calls for non-word-diff lines.

### 7. Added tests

13 tests in `TestHighlightMdLine`: headings (h1, h3, all levels 1-6, heading-no-inline), bold, italic, code, unordered/ordered/star list bullets, plain text, multiple markers, empty line.

## Final Implementation Notes

- **Actual work done:** Added markdown syntax highlighting to the diff viewer with a themable `MD_STYLES` dictionary, integrated into all rendering paths (interleaved, side-by-side, word-diff).
- **Deviations from plan:** None — implementation followed the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Used `MD_STYLES` dict pattern (matching existing `TAG_STYLES`) so all markdown colors are centralized and easily themable. Headings use early return to avoid applying inline styles (bold/code) within heading lines. The `_highlight_md_line()` function is used as a base layer before diff styles are applied on top.
- **Notes for sibling tasks:** `_highlight_md_line()` is exported and tested independently. `MD_STYLES` can be extended with additional markdown elements. The function handles empty strings gracefully.

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
