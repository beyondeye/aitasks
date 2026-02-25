---
Task: t214_3_update_reviewguide_import_skill_multi_platform.md
Parent Task: aitasks/t214_multi_platform_reviewguide_import_and_setup_dedup.md
Sibling Tasks: aitasks/t214/t214_1_*.md, aitasks/t214/t214_2_*.md, aitasks/t214/t214_4_*.md
Archived Sibling Plans: aiplans/archived/p214/p214_1_*.md, aiplans/archived/p214/p214_2_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

## Implementation Plan

### Step 1: Update YAML description (line 3)

Change "GitHub directory" → "repository directory"

### Step 2: Update Step 1 intro text

- Line 10: Example URL can stay as GitHub (it's just an example)
- Line 13: Change AskUserQuestion text: "GitHub directory URL" → "repository directory URL"
- Line 17: Update option description to mention all three platforms

### Step 3: Replace Step 1b: Detect Source Type (lines 21-28)

Replace the 4-item classification with expanded platform-aware detection:
- Local file (unchanged)
- Repository single file (GitHub/GitLab/Bitbucket patterns)
- Repository directory (GitHub/GitLab/Bitbucket patterns)
- Generic URL (unchanged)

### Step 4: Replace Step 1c: Fetch Content (lines 30-61)

Replace GitHub-only fetch with platform-dispatched fetching:
- URL parsing table per platform
- Platform-specific file fetching with fallbacks
- Platform-specific directory listing
- Keep Local file and Generic URL sections unchanged

### Step 5: Update Step 7 Batch Mode (lines 255-294)

- Heading: "GitHub directories" → "repository directories"
- Line 257: "GitHub directory" → "repository directory"
- Line 276: Replace "gh api" with "platform-specific method from Step 1c"
- Line 282: Remove "github" from summary template

### Step 6: Update Notes section (lines 296-308)

- Expand the single GitHub fetching note into per-platform notes
- Add self-hosted instances note

### Step 7: Review and verify

Read the complete updated SKILL.md to ensure consistency and correctness.

## Post-Implementation (Step 9)
Archive task and plan. Push changes.
