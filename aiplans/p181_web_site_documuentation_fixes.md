---
Task: t181_web_site_documuentation_fixes.md
Worktree: (current directory)
Branch: main
Base branch: main
---

## Context

After moving documentation from `docs/` to `website/content/docs/` (Hugo/Docsy site), several issues remain:
1. The documentation map in `docs/README.md` is incomplete
2. The docs main page has platform icons that should be removed
3. Missing "Overview" section on the website docs
4. README.md documentation links point to repo files instead of the website

## Plan

### 1. Complete the documentation map in `docs/README.md`

**File:** `docs/README.md`

Add all missing subpages to the table. Currently missing 16 entries:

**Workflows** (6 missing):
- `capturing-ideas.md` — Quickly capture task ideas without breaking your flow
- `github-issues.md` — Round-trip workflow between GitHub issues and aitasks
- `task-decomposition.md` — Breaking complex tasks into manageable child subtasks
- `follow-up-tasks.md` — Creating rich follow-up tasks during implementation
- `parallel-development.md` — Working on multiple tasks simultaneously
- `terminal-setup.md` — Multi-tab terminal workflow and monitoring

**Skills** (6 missing):
- `aitask-pick.md` — Select and implement the next task
- `aitask-explore.md` — Explore codebase interactively, then create a task
- `aitask-create.md` — Create a new task file interactively
- `aitask-fold.md` — Identify and merge related tasks
- `aitask-stats.md` — View task completion statistics
- `aitask-changelog.md` — Generate a changelog entry

**Commands** (4 missing):
- `setup-install.md` — ait setup and ait install commands
- `task-management.md` — ait create, ait ls, and ait update commands
- `board-stats.md` — ait board and ait stats commands
- `issue-integration.md` — ait issue-import, ait issue-update, ait changelog, ait zip-old

### 2. Remove platform icons from docs main page

**File:** `website/content/docs/_index.md`

Remove the entire `## Platform Support` section (lines 12-30) with the HTML/SVG icon markup.

### 3. Create new "Overview" documentation page

**New file:** `website/content/docs/overview.md`

Create a new standalone documentation page with content adapted from `README.md`:
- "The Challenge" (lines 13-16)
- "Core Philosophy" (lines 18-21)
- "Key Features & Architecture" (lines 23-52)

Frontmatter: `weight: 5` (before Installation at weight 10) to make it the first item in the sidebar. Title: "Overview". Content should be cleaned up for the website context (proper markdown formatting, links pointing to website pages not repo files).

No need to add a link to this page in `README.md` — the README already contains this same content directly.

### 4. Fix README.md documentation links to point to website

**File:** `README.md`

In the Documentation section (lines 121-137), change subsection links from repo file paths to website URLs.

Also fix other repo file links scattered throughout README.md:
- Line 45: Board Documentation link
- Line 62: Windows guide link
- Line 77: Windows/WSL guide link
- Line 91: `ait setup` link
- Line 102: Windows/WSL Installation Guide link
- Line 119: Claude Code Permissions link

## Final Implementation Notes

- **Actual work done:** All 4 planned fixes implemented plus an additional fix to the website homepage Quick Install section (clarified both `curl` and `ait setup` should be run in the project directory).
- **Deviations from plan:** Added website homepage Quick Install fix (not originally planned). Overview page created as standalone `overview.md` rather than inline in `_index.md` (per user feedback during planning).
- **Issues encountered:** None.
- **Key decisions:** Used Hugo `relref` shortcode in overview.md for the Board Documentation link to keep it portable within the Hugo site.

## Post-Review Changes

### Change Request 1 (2026-02-19)
- **Requested by user:** Add "next page" navigation links to each main documentation page
- **Changes made:** Added `**Next:** [Page Title](relref)` links with horizontal rule separator at the bottom of 7 main doc pages: Overview → Installation → Getting Started → Board → Workflows → Skills → Commands → Development
- **Files affected:** `website/content/docs/overview.md`, `website/content/docs/installation/_index.md`, `website/content/docs/getting-started.md`, `website/content/docs/board/_index.md`, `website/content/docs/workflows/_index.md`, `website/content/docs/skills/_index.md`, `website/content/docs/commands/_index.md`

### Change Request 2 (2026-02-19)
- **Requested by user:** Clarify Quick Install instructions on website homepage — both commands should run in the project directory
- **Changes made:** Updated `website/content/_index.md` to say "Run these commands in your project directory:" and show both `curl` and `ait setup` together
- **Files affected:** `website/content/_index.md`

## Step 9 Reference

Post-implementation: archive task/plan, push.
