---
Task: t417_9_word_level_intra_line_diff_highlighting.md
Parent Task: aitasks/t417_diff_viewer_tui_for_brainstorming.md
Sibling Tasks: aitasks/t417/t417_7_*.md
Archived Sibling Plans: aiplans/archived/p417/p417_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Word-Level Intra-Line Diff Highlighting (t417_9)

## Context

Both diff views (side-by-side and interleaved) highlighted entire lines for `replace` hunks. When two lines differ by only a few words, the full-line coloring made it hard to spot actual differences. This task adds word-level highlighting to both views so only changed spans get the full color, while unchanged portions appear dimmer.

## Files Modified

- `.aitask-scripts/diffviewer/diff_display.py` — Added `_word_diff_texts()` helper, `replace_partner` field on `_DisplayLine`, word-level diff in both renderers, scroll position preservation on layout toggle, file name column headers in side-by-side view
- `.aitask-scripts/diffviewer/diff_viewer_screen.py` — Updated info bar to exclude file names when in side-by-side mode
- `tests/test_diff_display.py` — Added `TestWordDiffTexts` (7 tests) and `TestFlattenHunksReplacePartner` (4 tests)

## Implementation Steps

### 1. Added `_word_diff_texts()` helper function

Tokenizes lines by whitespace-delimited words using `re.finditer(r"\S+", ...)`, diffs the word lists with `difflib.SequenceMatcher`, applies dim style to matching words and tag style to changed words. Takes separate `main_style` and `other_style` params so interleaved mode can use red/green while side-by-side uses orange/orange.

### 2. Added `replace_partner` field to `_DisplayLine`

New optional field stores the paired line content from replace hunks, enabling word-level diff in interleaved mode.

### 3. Updated `_flatten_hunks()` replace handling

Pairs main/other lines row-by-row: each delete line stores its corresponding insert line as `replace_partner` and vice versa. Unpaired lines (uneven hunk lengths) get `None`.

### 4. Modified `_render_interleaved()` for word-level diffs

When a line has a `replace_partner`, computes word-level diff using `_word_diff_texts()` with delete-red and insert-green styles.

### 5. Modified `_render_side_by_side()` for word-level diffs

For replace rows where both sides have content, uses `_word_diff_texts()` with the replace-orange style on both sides.

### 6. Added scroll position preservation on layout toggle

`set_layout()` now captures the first visible line's line number before switching, finds the equivalent position in the new layout, and scrolls to it.

### 7. Added file name column headers in side-by-side view

Side-by-side Rich Table now shows file names as bold column headers above each pane. Info bar in `diff_viewer_screen.py` omits file names when in side-by-side mode to avoid duplication.

## Post-Review Changes

### Change Request 1 (2026-03-19 10:50)
- **Requested by user:** Word-level diff was finding subword character matches — needed true word-boundary tokenization
- **Changes made:** Rewrote `_word_diff_texts()` to tokenize by whitespace-delimited words instead of character sequences. Uses `re.finditer(r"\S+", ...)` and diffs word lists, not characters.
- **Files affected:** `.aitask-scripts/diffviewer/diff_display.py`, `tests/test_diff_display.py`

### Change Request 2 (2026-03-19 10:55)
- **Requested by user:** Preserve scroll position when toggling between interleaved and side-by-side layouts
- **Changes made:** Updated `set_layout()` to capture the first visible line's reference line number, find the equivalent in the new layout, and scroll to it
- **Files affected:** `.aitask-scripts/diffviewer/diff_display.py`

### Change Request 3 (2026-03-19 11:00)
- **Requested by user:** Show file names above each pane in side-by-side mode instead of in the info bar
- **Changes made:** Added `_main_label`/`_other_label` to DiffDisplay, populated from PairwiseDiff paths. Side-by-side table uses Rich Table column headers. Info bar updated to exclude file names in side-by-side mode.
- **Files affected:** `.aitask-scripts/diffviewer/diff_display.py`, `.aitask-scripts/diffviewer/diff_viewer_screen.py`

## Final Implementation Notes

- **Actual work done:** Added word-level intra-line diff highlighting to both interleaved and side-by-side views, scroll position preservation on layout toggle, and file name column headers in side-by-side view.
- **Deviations from original plan:** (1) Extended to interleaved view (not just side-by-side). (2) Used word-level tokenization instead of character-level. (3) Added scroll position preservation and file name headers as post-review enhancements.
- **Issues encountered:** Initial character-level SequenceMatcher found subword matches (e.g., partial word overlap) which was confusing. Switched to word-level tokenization to match user expectations.
- **Key decisions:** Used `re.finditer(r"\S+")` for tokenization — simple whitespace splitting that treats punctuation as part of adjacent words. The entire character range from first changed word to last changed word in a group is highlighted (including inter-word whitespace).
- **Notes for sibling tasks:** `_word_diff_texts()` is a reusable helper exported for testing. `DiffDisplay` now stores `_main_label`/`_other_label` from loaded diffs, populated via `os.path.basename()`. The `set_layout()` method now preserves scroll position using line number mapping.

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
