---
Task: t172_5_update_tasks_and_archives.md
Parent Task: aitasks/t172_rename_reviewmode_to_reviewguide.md
Archived Sibling Plans: aiplans/archived/p172/p172_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

This is the final child task of t172 (rename reviewmode to reviewguide). Previous siblings renamed directories, scripts, skill files, and install scripts. This task updates all task files, plan files, and archived files that still reference the old "reviewmode" naming.

## Plan

### Step 1: Batch sed replacements on all target files

Use `sed -i` with ordered replacements on all target files. Order matters — path-specific replacements must come before general word replacements.

**Replacement order:**
1. `aitasks/metadata/reviewmodes/` → `aireviewguides/` (path restructure)
2. `seed/reviewmodes/` → `seed/reviewguides/`
3. `.reviewmodesignore` → `.reviewguidesignore`
4. `aitask-reviewmode-classify` → `aitask-reviewguide-classify`
5. `aitask-reviewmode-merge` → `aitask-reviewguide-merge`
6. `aitask_reviewmode_scan.sh` → `aitask_reviewguide_scan.sh`
7. `reviewmodes` → `reviewguides` (general)
8. `reviewmode` → `reviewguide` (general)
9. `Review Modes` → `Review Guides`
10. `Review Mode` → `Review Guide`
11. `review modes` → `review guides`
12. `review mode` → `review guide`

**Target files (25 files across 4 groups):**

Active tasks (4):
- `aitasks/t169_add_skill_review_import.md`
- `aitasks/t170_improve_review_mode_filtering_and_info_display.md`
- `aitasks/t171_new_claude_skills_for_code_review_docs.md`
- `aitasks/t129/t129_6_document_aitask_review.md`

Archived tasks (10):
- `aitasks/archived/t129/t129_3_review_modes_infrastructure.md`
- `aitasks/archived/t129/t129_4_create_aitask_review_skill.md`
- `aitasks/archived/t158_fixes_to_review_skill.md`
- `aitasks/archived/t159_reviewmodes_directory_tree.md`
- `aitasks/archived/t163_review_modes_consolidate.md`
- `aitasks/archived/t163/t163_1_vocabulary_files_and_install.md`
- `aitasks/archived/t163/t163_2_add_reviewmode_metadata.md`
- `aitasks/archived/t163/t163_3_reviewmode_scan_script.md`
- `aitasks/archived/t163/t163_4_classify_skill.md`
- `aitasks/archived/t163/t163_5_merge_skill.md`

Archived plans (10):
- `aiplans/archived/p129/p129_3_review_modes_infrastructure.md`
- `aiplans/archived/p129/p129_4_create_aitask_review_skill.md`
- `aiplans/archived/p158_fixes_to_review_skill.md`
- `aiplans/archived/p159_reviewmodes_directory_tree.md`
- `aiplans/archived/p163/p163_1_vocabulary_files_and_install.md`
- `aiplans/archived/p163/p163_2_add_reviewmode_metadata.md`
- `aiplans/archived/p163/p163_3_reviewmode_scan_script.md`
- `aiplans/archived/p163/p163_4_classify_skill.md`
- `aiplans/archived/p163/p163_5_merge_skill.md`
- `aiplans/archived/p167_framework_files_not_committed_with_ait_setup.md`

Active plans (1):
- `aiplans/p129_dynamic_task_skill.md`

**Excluded (t172 family — they document the rename itself):**
- `aitasks/t172_rename_reviewmode_to_reviewguide.md`
- `aitasks/t172/t172_5_update_tasks_and_archives.md`
- `aitasks/archived/t172/*`
- `aiplans/archived/p172/*`

### Step 2: Update `updated_at` timestamps on active task files

For the 4 active task files, update the `updated_at` frontmatter to current date/time.

### Step 3: Verification

Run the verification commands from the task description:
1. `grep -ri "reviewmode" aitasks/t169_*.md aitasks/t170_*.md aitasks/t171_*.md aitasks/t129/t129_6_*.md` — 0 results
2. `grep -ri "reviewmode" aitasks/archived/` — 0 for non-t172 files
3. `grep -ri "reviewmode" aiplans/archived/` — 0 for non-p172 files
4. `grep -r "aitasks/metadata/reviewmodes" aitasks/ aiplans/` — 0 results (excluding t172 family)

### Step 4: Step 9 — Post-Implementation

Archive task, commit, push.

## Final Implementation Notes

- **Actual work done:** Applied 12 sed replacement patterns across 25 files (4 active tasks, 10 archived tasks, 10 archived plans, 1 active plan). Updated `updated_at` timestamps on 4 active task files.
- **Deviations from plan:** Initial sed pass missed mixed-case variants (`REVIEWMODES_DIR`, `Reviewmodes`, `Reviewmode`, `Review modes` with capital R). Required 2 additional targeted sed passes to catch all case variants.
- **Issues encountered:** The original replacement list only covered lowercase forms. Uppercase shell variable names (`REVIEWMODES_DIR`) and title-case prose forms (`Reviewmode`, `Review modes`) needed separate handling.
- **Key decisions:** (1) Excluded t172 family files (parent, siblings, current task) since they document the rename itself — updating them would create nonsensical text like "rename reviewguide to reviewguide". (2) Included `aiplans/archived/p167_framework_files_not_committed_with_ait_setup.md` which wasn't in the original task file list but contained "review modes" references.
- **Notes for sibling tasks:** This is the final child task — no subsequent siblings. For future similar bulk renames: always grep case-insensitively first to identify ALL case variants before writing sed patterns.
