---
priority: medium
effort: low
depends: [t172_1]
issue_type: refactor
status: Implementing
labels: [aitask_review]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-18 22:05
updated_at: 2026-02-18 23:24
---

## Context

Child task 5 of t172 (rename reviewmode to reviewguide). Updates all task files, plan files, and archived files that reference the old naming. This is lower effort since these are documentation/historical files — the changes are straightforward text replacements.

## Key Files to Modify

### Active Tasks (4 files)

- `aitasks/t169_add_skill_review_import.md` — update reviewmode references
- `aitasks/t170_improve_review_mode_filtering_and_info_display.md` — update reviewmode references
- `aitasks/t171_new_claude_skills_for_code_review_docs.md` — update reviewmode references
- `aitasks/t129/t129_6_document_aitask_review.md` — update reviewmode references

For each file:
- Replace `reviewmode(s)` → `reviewguide(s)` in content
- Replace `aitasks/metadata/reviewmodes/` → `aireviewguides/`
- Replace skill names: `aitask-reviewmode-classify` → `aitask-reviewguide-classify`, `aitask-reviewmode-merge` → `aitask-reviewguide-merge`
- Replace script names: `aitask_reviewmode_scan.sh` → `aitask_reviewguide_scan.sh`
- Update `updated_at` timestamp

### Archived Tasks (~9 files in `aitasks/archived/`)

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

### Archived Plans (~10 files in `aiplans/archived/`)

- `aiplans/archived/p129/p129_3_review_modes_infrastructure.md`
- `aiplans/archived/p129/p129_4_create_aitask_review_skill.md`
- `aiplans/archived/p158_fixes_to_review_skill.md`
- `aiplans/archived/p159_reviewmodes_directory_tree.md`
- `aiplans/archived/p163/p163_1_vocabulary_files_and_install.md`
- `aiplans/archived/p163/p163_2_add_reviewmode_metadata.md`
- `aiplans/archived/p163/p163_3_reviewmode_scan_script.md`
- `aiplans/archived/p163/p163_4_classify_skill.md`
- `aiplans/archived/p163/p163_5_merge_skill.md`

### Active Plans

- `aiplans/p129_dynamic_task_skill.md` — check for reviewmode references

### Approach

For all files, do a systematic search-and-replace:
1. `aitasks/metadata/reviewmodes/` → `aireviewguides/`
2. `seed/reviewmodes/` → `seed/reviewguides/`
3. `aitask-reviewmode-classify` → `aitask-reviewguide-classify`
4. `aitask-reviewmode-merge` → `aitask-reviewguide-merge`
5. `aitask_reviewmode_scan.sh` → `aitask_reviewguide_scan.sh`
6. `.reviewmodesignore` → `.reviewguidesignore`
7. `reviewmode` → `reviewguide` (general, case-sensitive)
8. `reviewmodes` → `reviewguides` (general, case-sensitive)
9. `review mode` → `review guide` (in prose)
10. `review modes` → `review guides` (in prose)

## Verification

1. `grep -ri "reviewmode" aitasks/t169_*.md aitasks/t170_*.md aitasks/t171_*.md aitasks/t129/t129_6_*.md` — 0 results
2. `grep -ri "reviewmode" aitasks/archived/` — 0 results
3. `grep -ri "reviewmode" aiplans/archived/` — 0 results
4. `grep -r "aitasks/metadata/reviewmodes" aitasks/ aiplans/` — 0 results
