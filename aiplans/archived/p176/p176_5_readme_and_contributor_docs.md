---
Task: t176_5_readme_and_contributor_docs.md
Parent Task: aitasks/t176_create_web_site.md
Sibling Tasks: (all archived)
Archived Sibling Plans: aiplans/archived/p176/p176_*_*.md
Branch: main (no worktree)
Base branch: main
---

## Context

Child task t176_5 of "Create Web Site" (t176). The Hugo/Docsy website is fully set up. This task: adds README badge, makes `website/content/docs/` the single source of truth, creates installation page, reorganizes doc hierarchy with subpages for sidebar navigation, and updates landing page with platform icons.

## New Documentation Hierarchy

```
docs/
├── _index.md (w:1) — Landing page with brief platform support (Linux/Windows/macOS icons)
├── installation/
│   ├── _index.md (w:10) — Quick Install, upgrade, setup, what gets installed, known issues, auth
│   └── windows-wsl.md (w:20) — Windows/WSL subpage
├── getting-started.md (w:20) — First-time walkthrough
├── board/
│   ├── _index.md (w:30) — Overview + Tutorial
│   ├── how-to.md (w:10) — How-To Guides
│   └── reference.md (w:20) — Feature Reference
├── workflows.md (w:40) — Single page (moderate size)
├── skills/
│   ├── _index.md (w:50) — Overview table
│   ├── aitask-pick.md (w:10)
│   ├── aitask-explore.md (w:20)
│   ├── aitask-fold.md (w:30)
│   ├── aitask-create.md (w:40)
│   ├── aitask-stats.md (w:50)
│   └── aitask-changelog.md (w:60)
├── commands/
│   ├── _index.md (w:60) — Overview table + usage examples
│   ├── setup-install.md (w:10) — ait setup + ait install
│   ├── task-management.md (w:20) — ait create + ait ls + ait update
│   ├── board-stats.md (w:30) — ait board + ait stats
│   └── issue-integration.md (w:40) — ait issue-import + ait issue-update + ait changelog + ait zip-old
├── development/
│   ├── _index.md (w:70) — Architecture, directory layout, libraries, release
│   └── task-format.md (w:10) — Task file format
```

## Plan

### Step 1: Create installation/ section

1. Create `website/content/docs/installation/_index.md` (w:10)
   - Content from README: Quick Install, upgrade, `ait setup`, "What Gets Installed", Platform Support table, Known Issues
   - Content from README "Authentication with Your Git Remote": GitHub, GitLab, Bitbucket auth (moved here, removed from README)
   - Hugo-style relative links

2. Move `installing-windows.md` → `installation/windows-wsl.md` (w:20)

### Step 2: Create Getting Started page

`website/content/docs/getting-started.md` (w:20) — install → setup → create task → board → pick with Claude

### Step 3: Split board.md into board/ subpages

- `_index.md` (w:30) — Overview + Tutorial section
- `how-to.md` (w:10) — 14 How-To Guides
- `reference.md` (w:20) — Feature Reference (shortcuts, config, etc.)
- Remove TOCs, delete original board.md

### Step 4: Split skills.md into skills/ subpages

- `_index.md` (w:50) — Overview table
- Individual skill files: aitask-pick (w:10), aitask-explore (w:20), aitask-fold (w:30), aitask-create (w:40), aitask-stats (w:50), aitask-changelog (w:60)
- Remove TOCs, delete original skills.md

### Step 5: Move task-format under development/

- `development.md` → `development/_index.md` (w:70), remove TOC
- `task-format.md` → `development/task-format.md` (w:10), remove TOC

### Step 6: Split commands.md into commands/ subpages

- `_index.md` (w:60) — Overview table + Usage Examples
- `setup-install.md` (w:10) — ait setup + ait install
- `task-management.md` (w:20) — ait create + ait ls + ait update
- `board-stats.md` (w:30) — ait board + ait stats
- `issue-integration.md` (w:40) — ait issue-import + ait issue-update + ait changelog + ait zip-old
- Remove TOCs, delete original commands.md

### Step 7: Update remaining pages

- `workflows.md` weight → 40, remove TOC
- `_index.md` — Update with brief platform support using icons from dashboardicons.com (Linux, Windows, macOS)

### Step 8: Fix cross-references

Update all internal links across all docs for new Hugo directory structure.

### Step 9: Update README.md

1. Add documentation badge after title
2. Remove "Authentication with Your Git Remote" section (moved to website installation page)
3. Add live site link in Documentation section
4. Update doc links to point to `website/content/docs/` paths

### Step 10: Delete docs/ and create pointer

- Delete all `docs/*.md` (7 doc files + website-development.md)
- Create `docs/README.md` — table linking to each `website/content/docs/` file with descriptions

### Step 11: Create website/README.md

Contributor guide from `docs/website-development.md` content (prerequisites, platform-specific install, local dev, troubleshooting).

### Step 12: Post-Implementation (workflow Step 9)

Archive task and plan files.

## Verification

1. `cd website && hugo server` — sidebar shows correct hierarchy and ordering
2. All internal doc links resolve
3. README.md badge renders, doc links work
4. `docs/README.md` links resolve

## Final Implementation Notes

- **Actual work done:** Complete restructuring of documentation into Hugo/Docsy subpages. Created 27 new files, deleted 17 old files. All flat doc pages (board, commands, skills, workflows, development) split into subdirectories with subpages. New installation section created from README content. New Getting Started page. Workflows also split into 6 subpages (was initially kept as single page but user requested split). README updated with badge, auth section moved to website installation page. `docs/` directory replaced with pointer README.
- **Deviations from plan:** Workflows were initially planned as a single page but were split into 6 subpages per user request during review. Commands were initially planned as single page but were split into 4 subpages per user request during planning.
- **Issues encountered:** None — Hugo builds cleanly with 36 pages.
- **Key decisions:** Used dashboardicons.com CDN SVG icons for platform support on docs landing page. Grouped commands logically: setup+install, task management (create/ls/update), board+stats, issues+utilities. Kept all README sections except auth (moved to installation page).
- **Notes for sibling tasks:** This is the final child task (t176_5), so no sibling notes needed. The `docs/` directory now contains only a pointer README — all documentation lives in `website/content/docs/`. The development guide's "Keeping Documentation in Sync" section was updated to reference the new paths.
