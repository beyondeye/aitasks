---
Task: t291_document_new_filtering_features_in_ait_board.md
Branch: main
Base branch: main
---

# Plan: Document View Mode Filtering Features in Board Documentation (t291)

## Context

The ait board recently added three view mode filters (commit `098c50f`, t273): **All**, **Git**, and **Implementing**. These are displayed as `a All │ g Git │ i Impl` in a ViewSelector widget next to the search box. The Git filter relates to t260's PR import feature. This task documents these features across all three board documentation pages.

## Changes

### 1. `website/content/docs/tuis/board/_index.md`

- [x] **1a.** Update layout description (line 27): Change "Search box" to "Filter area" describing both the ViewSelector and search box
- [x] **1b.** Add view mode keys to navigation (after line 45): Add `a / g / i` to the keyboard list

### 2. `website/content/docs/tuis/board/how-to.md`

- [x] **2a.** Add AND-logic note to existing "How to Search and Filter Tasks" (after line 129)
- [x] **2b.** Add new "How to Filter by View Mode" section (after search, before commit)
- [x] **2c.** Add Pull Request to task relationships table (line 228)

### 3. `website/content/docs/tuis/board/reference.md`

- [x] **3a.** Add view mode keyboard shortcuts (`a`, `g`, `i`) to Board Navigation table
- [x] **3b.** Add "PR Platform Indicators" section after Issue Platform Indicators
- [x] **3c.** Add "View Modes" reference section
- [x] **3d.** Update Task Card Anatomy to show PR indicator and contributor
- [x] **3e.** Add `pull_request`, `contributor`, `contributor_email`, `implemented_with` to metadata table
- [x] **3f.** Update Task Detail modal entry to mention PR and contributor

## Verification

1. Run `cd website && hugo build --gc --minify` to verify no broken shortcodes
2. Check all three pages render correctly

## Final Implementation Notes
- **Actual work done:** Documented the three view mode filters (All/Git/Implementing) across all three board documentation pages (_index.md, how-to.md, reference.md). Also documented PR platform indicators, pull_request/contributor/contributor_email/implemented_with metadata fields, and the Pull Request navigable field in the detail dialog.
- **Deviations from plan:** None — all planned changes implemented as designed.
- **Issues encountered:** No `docs/commands/pr-import` page exists yet, so used plain text references to `ait pr-import` instead of Hugo relref links. This is a follow-up for t260_7.
- **Key decisions:** Used plain text for `ait pr-import` references rather than broken relref links. Added `implemented_with` to the metadata table since it was already displayed in the board but undocumented.
