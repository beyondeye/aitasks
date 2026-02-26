---
Task: t258_5_update_website_documentation.md
Parent Task: aitasks/t258_automatic_clean_up_of_aiexplains_for_code_browser.md
Sibling Tasks: aitasks/t258/t258_1_*.md, aitasks/t258/t258_2_*.md, aitasks/t258/t258_3_*.md, aitasks/t258/t258_4_*.md
Archived Sibling Plans: aiplans/archived/p258/p258_1_*.md, aiplans/archived/p258/p258_2_*.md, aiplans/archived/p258/p258_3_*.md, aiplans/archived/p258/p258_4_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

## Plan: Update website documentation

### Step 1: Update commands/explain.md

**File:** `website/content/docs/commands/explain.md`

- Add new section for `ait explain-cleanup`:
  - Purpose: remove stale run directories, keeping only newest per source key
  - Modes: `--target DIR`, `--all`, `--dry-run`, `--quiet`
  - Examples
- Update existing `ait explain-runs` section:
  - New `--cleanup-stale` mode
  - Updated display showing dir_key alongside timestamp
  - New `<dir_key>__<timestamp>` naming convention

### Step 2: Update skills/aitask-explain.md

**File:** `website/content/docs/skills/aitask-explain.md`

- Update "Run Management" section:
  - Runs now use `<dir_key>__<timestamp>` naming
  - The dir_key identifies the source directory
  - Stale runs are automatically cleaned up when new data is generated
- Update references to bare timestamp directory names

### Step 3: Update workflows/explain.md

**File:** `website/content/docs/workflows/explain.md`

- In "How It Works" section: mention automatic stale cleanup
- Update run directory naming references
- Mention cleanup at codebrowser startup

### Step 4: Verify

1. `cd website && hugo build --gc --minify` if Hugo is available
2. Review pages for consistent messaging
3. Verify code examples use new naming format

### Step 9: Post-Implementation

Archive task following the standard workflow.

## Post-Review Changes

### Change Request 1 (2026-02-26 17:30)
- **Requested by user:** Update the main commands index page (`docs/commands/_index.md`) with the latest list of commands, and reorganize them into groups matching the documentation structure
- **Changes made:** Reorganized the flat command table into grouped sections (Task Management, TUI, Integration, Reporting, Tools, Infrastructure) matching the documentation page structure. Added missing commands: `ait git`, `ait codebrowser`, `ait explain-cleanup`. Updated usage examples with new commands (`codebrowser`, `git`, `explain-cleanup`, `--cleanup-stale`).
- **Files affected:** `website/content/docs/commands/_index.md`

## Final Implementation Notes

- **Actual work done:** All planned documentation updates completed across 4 files: (1) `commands/explain.md` — updated description, added `--cleanup-stale` option, new naming convention docs, added codebrowser run location, added full `ait explain-cleanup` section with options/examples. (2) `skills/aitask-explain.md` — updated naming from `<timestamp>` to `<dir_key>__<timestamp>` in step-by-step, key capabilities, and run management sections; added auto-cleanup notes; added `--cleanup-stale` to CLI examples. (3) `workflows/explain.md` — added naming convention and auto-cleanup paragraph in "How It Works"; updated "Manage disk usage" tip. (4) `commands/_index.md` — reorganized flat command table into grouped sections matching `ait` help structure; added missing commands (`ait git`, `ait codebrowser`, `ait explain-cleanup`); updated usage examples.
- **Deviations from plan:** Added the commands index page reorganization as a post-review change request from the user. This was not in the original t258_5 task scope but was a natural addition since we were already updating the commands section.
- **Issues encountered:** None. Hugo build passes cleanly.
- **Key decisions:** Organized commands into 6 groups (Task Management, TUI, Integration, Reporting, Tools, Infrastructure) matching the `ait` help text grouping. For `ait git` and `ait codebrowser` which lack dedicated doc pages, linked to the most relevant existing pages (`sync/` and `board-stats/`) without specific anchors.
- **Notes for sibling tasks:** This was the final child task (t258_5). All documentation now reflects the `<dir_key>__<timestamp>` naming convention and automatic stale cleanup behavior introduced in t258_1 through t258_4.
