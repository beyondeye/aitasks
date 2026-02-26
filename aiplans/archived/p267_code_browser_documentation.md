---
Task: t267_code_browser_documentation.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Codebrowser Documentation (t267)

## Context

The codebrowser is a Textual-based TUI (`ait codebrowser`) for browsing project files with syntax highlighting and task annotations from the explain data pipeline. It currently has no dedicated documentation page. The task requires: writing documentation modeled after the Board docs, creating a new TUIs parent section, moving Board under TUIs, and ensuring no broken references.

## Implementation Steps

### 1. Copy images to website static directory

- [x] Copy 3 SVG screenshots from `imgs/` to `website/static/imgs/`

### 2. Create TUIs parent section

- [x] Create `website/content/docs/tuis/_index.md` (weight: 30)
- [x] Emphasize workflow positioning (Board = beginning, Code Browser = end)
- [x] Add aliases for old board URLs redirect coverage

### 3. Move Board docs under TUIs

- [x] `git mv website/content/docs/board/ website/content/docs/tuis/board/`
- [x] Change weight from 30 to 10 (ordering within TUIs section)
- [x] Fix footer relref to use absolute path

### 4. Create Codebrowser documentation (3 files)

- [x] `website/content/docs/tuis/codebrowser/_index.md` — Overview + tutorial with 3 screenshots
- [x] `website/content/docs/tuis/codebrowser/how-to.md` — 6 how-to guides
- [x] `website/content/docs/tuis/codebrowser/reference.md` — Keyboard shortcuts, annotation pipeline, env vars

### 5. Fix all broken references (10 files)

- [x] getting-started.md — board link + Next footer
- [x] overview.md — TUI reference updated to mention both TUIs
- [x] task-consolidation.md — 2 board links
- [x] terminal-setup.md — board link
- [x] capturing-ideas.md — board link
- [x] lock.md — board link
- [x] sync.md — board link
- [x] board-stats.md — board link
- [x] task-format.md — board link
- [x] commands/_index.md — codebrowser anchor link

### 6. Add `ait codebrowser` section to `commands/board-stats.md`

- [x] Added `## ait codebrowser` section with description, usage, requirements, and link to full docs
- [x] Updated page title to "Board, Code Browser & Stats"

### 7. Add codebrowser cross-links to explain docs

- [x] `skills/aitask-explain.md` — Added "Visual Browsing" section
- [x] `workflows/explain.md` — Added "Visual Exploration with the Code Browser" section
- [x] `commands/explain.md` — Added codebrowser reference in run directory description

### 8. Verify build

- [x] `hugo build --gc --minify` passes (82 pages, 5 aliases)
- [x] `hugo build --gc` passes and all pages render correctly with static-img shortcode

## Final Implementation Notes

- **Actual work done:** All 8 plan steps implemented as designed. Created TUIs parent section, moved Board docs, wrote 3 new codebrowser documentation pages (overview, how-to, reference), fixed 10+ broken references across the site, added cross-links to explain docs.
- **Deviations from plan:** None significant. Removed binary files, viewport, layout anatomy, annotation color scheme, and responsive layout sections from codebrowser docs per user feedback (too technical/internal for user-facing docs).
- **Issues encountered:** User reported static-img shortcode stopped working for Board after the move. Investigation revealed the old `/docs/board/` URL was redirecting to `/docs/tuis/` (the parent page with no images) instead of `/docs/tuis/board/`. The aliases redirect to the TUIs section-level page, not the board subpage — this is a cosmetic issue since users navigating via the sidebar will land on the correct page. Also discovered that `hugo --minify` strips inline `<style>` and `<script>` from shortcode output — this is a pre-existing issue unrelated to our changes.
- **Key decisions:** Used Hugo aliases on the TUIs `_index.md` for old board URL redirects. Changed board-stats.md title to "Board, Code Browser & Stats" to reflect the added codebrowser section.
