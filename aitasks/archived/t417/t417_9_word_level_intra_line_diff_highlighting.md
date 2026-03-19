---
priority: medium
effort: medium
depends: [t417_8]
issue_type: feature
status: Done
labels: [tui, brainstorming]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-19 09:50
updated_at: 2026-03-19 11:27
completed_at: 2026-03-19 11:27
---

## Context

The side-by-side diff view (t417_8) highlights entire lines as changed when they differ. When two lines are mostly identical but differ by a few words, the entire line gets the `replace` tag color (orange), making it hard to spot the actual differences. This task adds word-level (intra-line) diff highlighting so only the specific changed spans within each line are highlighted, while unchanged portions use a dimmer background.

## Key Files to Modify

- `.aitask-scripts/diffviewer/diff_display.py` — Modify `_render_side_by_side()` to apply word-level highlighting for `replace` rows. Add a helper function that uses `difflib.SequenceMatcher` to find changed spans within paired lines.

## Reference Files for Patterns

- `.aitask-scripts/diffviewer/diff_display.py` — Current `_render_side_by_side()` method builds Rich `Text` objects per cell; word-level diffs would use `Text.stylize(style, start, end)` to apply styles to specific character ranges
- `.aitask-scripts/diffviewer/diff_engine.py` — `DiffHunk` stores whole lines; the intra-line diff is a visualization-only concern (no engine changes needed)
- Python stdlib `difflib.SequenceMatcher` — Can diff character sequences within a pair of lines to find matching blocks

## Implementation Plan

1. Add a helper function `_word_diff_texts(main_line: str, other_line: str, base_style: Style) -> tuple[Text, Text]`:
   - Use `difflib.SequenceMatcher(None, main_line, other_line)` to get matching blocks
   - For matching spans: apply a dimmer version of the base style (e.g., just dim text, no background)
   - For differing spans: apply the full `replace` tag style
   - Return two `Text` objects (main and other) with per-span styling

2. In `_render_side_by_side()`, when processing `replace` rows where both `main_content` and `other_content` are non-empty:
   - Call `_word_diff_texts()` to get styled Text objects
   - Use these instead of the plain styled Text objects

3. Consider whether to also apply word-level highlighting in the interleaved view (for sequential delete+insert pairs from replace hunks) — this may be a follow-up enhancement

## Verification

- Launch diff viewer with test plans, toggle to side-by-side (v)
- In replace lines: only changed words should be highlighted with the full replace color
- Unchanged portions within replace lines should appear dimmer
- Equal, insert, delete, moved lines should be unaffected
- Cursor navigation still works correctly
- Run existing tests: `python -m unittest tests.test_diff_display -v`
