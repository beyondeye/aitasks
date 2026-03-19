---
Task: t424_diff_viewer_visual_polish.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Diff Viewer Visual Polish (t424)

## Context

Follow-up to t417_10 (markdown syntax highlighting). The diff viewer had overly bright background colors making text hard to read, no comprehensive markdown test files for visual verification, the default directory pointed to `aiplans/`, row spacing was doubled due to trailing newlines, and word-diff lines lacked background context for matching words.

## Files Modified

- `.aitask-scripts/diffviewer/diff_display.py` — Dimmed TAG_STYLES, added `_dim` variants, added `padding=0` to tables, empty-line background fix
- `.aitask-scripts/diffviewer/plan_browser.py` — Changed default `root_dir` to test plans
- `.aitask-scripts/diffviewer/plan_loader.py` — Fixed `splitlines(keepends=True)` → `splitlines()` to remove trailing newlines
- `.aitask-scripts/diffviewer/test_plans/md_cheatsheet_a.md` — New: comprehensive markdown cheatsheet
- `.aitask-scripts/diffviewer/test_plans/md_cheatsheet_b.md` — New: variation with blank lines in diff regions

## Implementation Steps

### 1. Created markdown cheatsheet test plans

Two files covering all markdown syntax: headings h1-h6, bold, italic, code, lists, blockquotes, tables, task lists. Version B has targeted variations to exercise all diff tags plus blank lines in diff regions.

### 2. Dimmed TAG_STYLES background colors

Replaced bright Dracula palette backgrounds with dark muted versions: `#264d26` (green), `#4d2626` (red), `#4d3826` (orange), `#263a4d` (cyan) with light gray foreground.

### 3. Added `_dim` style variants for word-diff matching words

Added `insert_dim`, `delete_dim`, `replace_dim` keys to TAG_STYLES — even dimmer backgrounds for matching words in word-diff lines. Updated `_word_diff_texts()` to accept optional dim style parameters and pass them from both renderers.

### 4. Changed default starting directory

`PlanBrowser.__init__` default changed from `"aiplans/"` to `".aitask-scripts/diffviewer/test_plans/"`.

### 5. Fixed row double-spacing

Root cause: `plan_loader.py` used `splitlines(keepends=True)` which preserved trailing `\n` in each line. Rich Table rendered these as 2-line rows. Changed to `splitlines()`. Also added `padding=0` to both Table constructors.

### 6. Fixed empty line background rendering

Empty content lines (`""`) now rendered as `" "` (single space) so diff background colors show on full-width blank lines.

## Post-Review Changes

### Change Request 1 (2026-03-19)
- **Requested by user:** Word-diff matching words need dimmed background (not just dim text)
- **Changes made:** Added `_dim` style variants to TAG_STYLES, updated `_word_diff_texts()` signature and callers
- **Files affected:** `.aitask-scripts/diffviewer/diff_display.py`

### Change Request 2 (2026-03-19)
- **Requested by user:** Increase brightness of all diff background colors
- **Changes made:** Bumped RGB values ~50% brighter for both regular and dim variants
- **Files affected:** `.aitask-scripts/diffviewer/diff_display.py`

### Change Request 3 (2026-03-19)
- **Requested by user:** Row spacing doubled, empty lines not showing full background
- **Changes made:** Fixed `splitlines(keepends=True)` → `splitlines()` in plan_loader.py. Added `padding=0` to tables. Empty lines render as space. Updated cheatsheet_b with blank lines in diff regions.
- **Files affected:** `.aitask-scripts/diffviewer/plan_loader.py`, `.aitask-scripts/diffviewer/diff_display.py`, `.aitask-scripts/diffviewer/test_plans/md_cheatsheet_b.md`

## Final Implementation Notes

- **Actual work done:** Dimmed diff colors, added word-diff dim variants, created markdown cheatsheet test plans, fixed row spacing bug, changed default directory, fixed empty line rendering.
- **Deviations from plan:** Added 3 features not in original plan: word-diff dim backgrounds, row spacing fix (plan_loader.py), empty line background fix.
- **Issues encountered:** Row double-spacing was caused by `splitlines(keepends=True)` preserving trailing newlines in plan_loader.py — a pre-existing issue that only became apparent when testing visually.
- **Key decisions:** Used `_dim` suffix convention in TAG_STYLES for word-diff matching variants. Made `_word_diff_texts()` parameters optional for backward compatibility. Changed plan_loader to strip line endings since neither the diff engine nor display needs them.
- **Notes for sibling tasks:** TAG_STYLES now includes `_dim` variants. `_word_diff_texts()` has optional `main_dim_style`/`other_dim_style` params. `plan_loader.py` no longer preserves line endings.

## Post-Implementation

Step 9 of the task-workflow: archive task, push changes.
