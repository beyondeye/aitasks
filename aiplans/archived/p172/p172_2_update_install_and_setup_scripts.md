---
Task: t172_2_update_install_and_setup_scripts.md
Parent Task: aitasks/t172_rename_reviewmode_to_reviewguide.md
Sibling Tasks: aitasks/t172/t172_3_*.md, aitasks/t172/t172_4_*.md, aitasks/t172/t172_5_*.md
Archived Sibling Plans: aiplans/archived/p172/p172_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Child task 2 of t172 (rename reviewmode to reviewguide). After t172_1 physically moved/renamed all directories and files, this task updates the two installation scripts (`install.sh` and `aiscripts/aitask_setup.sh`) to reference the new paths and names.

## Plan

### 1. Update `install.sh` (~25 changes)

**Function renames:**
- `install_seed_reviewmodes()` → `install_seed_reviewguides()` (definition + call site)

**Path changes in vocabulary install functions (reviewtypes, reviewlabels, reviewenvironments):**
- `seed/reviewmodes/<file>` → `seed/reviewguides/<file>`
- `aitasks/metadata/reviewmodes/<file>` → `aireviewguides/<file>`
- Comments referencing old paths

**Path changes in main reviewguides install function:**
- `seed/reviewmodes` → `seed/reviewguides`
- `aitasks/metadata/reviewmodes` → `aireviewguides`
- `.reviewmodesignore` → `.reviewguidesignore`

**User-facing messages:**
- "Installing review modes..." → "Installing review guides..."

### 2. Update `aiscripts/aitask_setup.sh` (~25 changes)

**Function renames:**
- `setup_review_modes()` → `setup_review_guides()` (definition + call site)

**Path variables:**
- `seed_dir` from `seed/reviewmodes` → `seed/reviewguides`
- `dest_dir` from `aitasks/metadata/reviewmodes` → `aireviewguides`

**Comments and user-facing strings:**
- All "review mode(s)" → "review guide(s)"
- `.reviewmodesignore` → `.reviewguidesignore`
- fzf prompts/headers referencing review modes

### 3. Update `.reviewguidesignore` file content (both locations)

- `aireviewguides/.reviewguidesignore` line 1 comment
- `seed/reviewguides/.reviewguidesignore` line 1 comment

## Verification

1. `shellcheck install.sh` — no new warnings
2. `shellcheck aiscripts/aitask_setup.sh` — no new warnings
3. `grep -c "reviewmode" install.sh` — should return 0
4. `grep -c "reviewmode" aiscripts/aitask_setup.sh` — should return 0
5. `grep -c "aitasks/metadata/reviewmodes" install.sh` — should return 0
6. `grep "aireviewguides" install.sh` — should show new destination paths

## Final Implementation Notes

- **Actual work done:** All changes executed exactly as planned across 4 files (install.sh, aitask_setup.sh, and both .reviewguidesignore files). 54 insertions, 54 deletions — pure renames with no logic changes.
- **Deviations from plan:** None — plan was followed exactly.
- **Issues encountered:** None.
- **Key decisions:** None needed — straightforward text replacements.
- **Notes for sibling tasks:**
  - `install.sh` and `aiscripts/aitask_setup.sh` now fully use `aireviewguides/` as the destination path (not `aitasks/metadata/reviewguides/`)
  - Function names updated: `install_seed_reviewguides()`, `setup_review_guides()`
  - The `.reviewguidesignore` files in both `aireviewguides/` and `seed/reviewguides/` now have updated content (comment header references "reviewguides" not "reviewmodes")
  - All user-facing strings changed from "review mode(s)" to "review guide(s)"
  - No shellcheck regressions — only pre-existing info-level warnings remain

## Post-Implementation

Step 9 from task-workflow: archive task and plan via `aitask_archive.sh 172_2`.
