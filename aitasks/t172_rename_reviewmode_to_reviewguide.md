---
priority: high
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [aitask_review, claudeskills]
children_to_implement: [t172_1, t172_2]
created_at: 2026-02-18 22:00
updated_at: 2026-02-18 22:40
---

Rename all references in the repository from "reviewmode" to "reviewguide" and restructure the directory layout. This is a comprehensive refactoring touching ~50 files and ~330 occurrences.

## Key Changes

1. **Rename terminology**: reviewmode(s) → reviewguide(s) everywhere (filenames, content, variable names, function names, comments)
2. **Move installed directory**: `aitasks/metadata/reviewmodes/` → `aireviewguides/` (project root) — the installed reviewguides should live at the root for easier access
3. **Move seed directory**: `seed/reviewmodes/` → `seed/reviewguides/`
4. **Rename skill directories**: `aitask-reviewmode-classify` → `aitask-reviewguide-classify`, `aitask-reviewmode-merge` → `aitask-reviewguide-merge`
5. **Rename script**: `aitask_reviewmode_scan.sh` → `aitask_reviewguide_scan.sh`
6. **Rename ignore file**: `.reviewmodesignore` → `.reviewguidesignore`
7. **Update install.sh**: fix all paths, function names, and the destination directory (now `aireviewguides/` instead of `aitasks/metadata/reviewmodes/`)
8. **Update all skills and scripts**: fix internal references
9. **Update active task files**: fix references in pending tasks
10. **Update archived tasks/plans**: fix references for historical consistency

## Scope Inventory

| Category | Files | Notes |
|----------|-------|-------|
| Skill dirs to rename | 2 | aitask-reviewmode-classify, aitask-reviewmode-merge |
| Skill files to update | 3 | classify, merge, review SKILL.md files |
| Scripts to rename/update | 3 | aitask_reviewmode_scan.sh, aitask_review_detect_env.sh, aitask_setup.sh |
| install.sh | 1 | ~22 references, function renames, path changes |
| Seed directory | 1 dir + 13 files | rename dir, update .reviewmodesignore |
| Metadata directory | 1 dir + 13 files | move to aireviewguides/ at root |
| Active tasks | 4 | t169, t170, t171, t129_6 |
| Archived tasks | ~9 | t129_3, t129_4, t158, t159, t163 series |
| Archived plans | ~10 | p129, p158, p159, p163 series |
| Tests | 2 | test_setup_git.sh, test_t167_integration.sh |
