---
priority: medium
effort: medium
depends: [t417_9]
issue_type: feature
status: Implementing
labels: [tui, brainstorming]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-19 12:03
updated_at: 2026-03-19 17:24
---

## Context

Add markdown-aware syntax highlighting to the diff viewer display. Currently, all diff content is rendered as plain text with only diff-colored backgrounds (green/red/orange for insert/delete/replace). Since the diff viewer exclusively handles markdown plan files, the content should be rendered with markdown formatting — headings bold and colored, **bold** text, *italic*, `inline code`, list bullets styled — while preserving the existing diff background colors.

## Key Files to Modify

- `.aitask-scripts/diffviewer/diff_display.py` — Add a markdown-aware line highlighter and integrate it into `_render_interleaved()` and `_render_side_by_side()` rendering paths

## Key Files for Reference

- `.aitask-scripts/diffviewer/diff_engine.py` — `DiffHunk` data model, understands what content types exist
- `.aitask-scripts/diffviewer/diff_viewer_screen.py` — Screen that hosts the DiffDisplay widget

## Implementation Plan

1. Create a `_highlight_md_line(line: str) -> Rich.Text` function in `diff_display.py` that applies inline markdown formatting:
   - `# Heading` lines → bold + accent color (scale by heading level)
   - `**bold**` → bold style
   - `*italic*` → italic style
   - `` `code` `` → dim background or distinct color
   - `- list item` / `* list item` / `1. item` → styled bullet/number
   - Bare text → no extra styling
   This produces a `Rich.Text` with markdown-level styles but NO diff colors yet.

2. Modify the content rendering in `_render_interleaved()`:
   - For plain lines (non-replace-partner), replace `Text(dl.content)` + `content.stylize(tag_style)` with: first call `_highlight_md_line(dl.content)` to get styled text, then layer the diff background via `content.stylize(tag_style)`.
   - For `_word_diff_texts()` replace-partner lines, apply markdown highlighting to each line before word-diff processing.

3. Apply the same changes to `_render_side_by_side()`.

4. Ensure "equal" lines (dim style) still show markdown formatting — headings should be visible even in equal sections.

## Verification

- Load two markdown plans with headings, bold text, code spans, and lists
- In diff view: equal sections show markdown formatting (headings bold, code highlighted)
- Changed sections show markdown formatting overlaid with diff background colors
- Word-level diff highlighting still works correctly for replace hunks
- Side-by-side and interleaved layouts both render correctly
- No visual regressions in plain-text-only plans
