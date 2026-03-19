---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [tui, brainstorming]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-19 21:57
updated_at: 2026-03-19 22:10
---

## Context

Follow-up to t417_10 (markdown syntax highlighting). Three improvements needed for the diff viewer TUI:

1. **Markdown cheatsheet test plans** — Add two markdown files in `.aitask-scripts/diffviewer/test_plans/` that serve as comprehensive markdown syntax cheatsheets (headings, bold, italic, code blocks, inline code, lists, links, blockquotes, horizontal rules, etc.). The second file should have small variations so diffs between them exercise all markdown rendering paths.

2. **Dim diff background colors** — The current `TAG_STYLES` in `diff_display.py` use overly bright Dracula palette colors as backgrounds (`#50FA7B` green, `#FF5555` red, `#FFB86C` orange, `#8BE9FD` cyan). Text on these bright backgrounds is hard to read. Replace with much dimmer/darker versions of the same hues that still clearly indicate insert/delete/replace/moved but allow text to remain readable.

3. **Default starting directory** — Change the `PlanBrowser` default `root_dir` from `"aiplans/"` to the test plans directory (`.aitask-scripts/diffviewer/test_plans/`) so the TUI opens in a useful location for visual testing.

## Key Files to Modify

- `.aitask-scripts/diffviewer/diff_display.py` — Update `TAG_STYLES` background colors to dimmer values
- `.aitask-scripts/diffviewer/plan_browser.py` — Change default `root_dir` parameter in `PlanBrowser.__init__`
- `.aitask-scripts/diffviewer/test_plans/md_cheatsheet_a.md` — New file: comprehensive markdown cheatsheet
- `.aitask-scripts/diffviewer/test_plans/md_cheatsheet_b.md` — New file: variation of cheatsheet for diff testing

## Key Files for Reference

- `.aitask-scripts/diffviewer/test_plans/plan_alpha.md` — Existing test plan format reference
- `.aitask-scripts/diffviewer/diffviewer_app.py` — App entry point
- `.aitask-scripts/diffviewer/plan_manager_screen.py` — Instantiates PlanBrowser

## Implementation Plan

1. Create `md_cheatsheet_a.md` with full markdown syntax examples: h1-h6 headings, **bold**, *italic*, `inline code`, fenced code blocks, ordered/unordered lists, nested lists, blockquotes, horizontal rules, links, tables
2. Create `md_cheatsheet_b.md` as a variant with: different heading text, modified bold/italic spans, changed list items, added/removed sections — designed so diffing A vs B exercises all diff tags (equal, insert, delete, replace)
3. Update `TAG_STYLES` in `diff_display.py` to use dimmer background colors (e.g., `#1a3a1a` dark green instead of `#50FA7B`, `#3a1a1a` dark red instead of `#FF5555`, etc.) with light foreground text
4. Change `PlanBrowser.__init__` default `root_dir` from `"aiplans/"` to `".aitask-scripts/diffviewer/test_plans/"`

## Verification

- Launch the diff viewer TUI: it opens in the test_plans directory
- Load md_cheatsheet_a.md and md_cheatsheet_b.md
- Diff view shows markdown formatting (headings colored, bold/italic visible, code highlighted)
- Diff backgrounds are dim enough that text is readable on all change types
- Both interleaved and side-by-side layouts render correctly
- Word-level diff highlighting still works
