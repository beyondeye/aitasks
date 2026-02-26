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
