---
Task: t247_replace_raw_ls_with_aitask_query_in_remaining_skills.md
Branch: (current branch, main)
---

## Context

Task t246 created `aiscripts/aitask_query_files.sh` and replaced raw `ls` commands in `aitask-pick` and `task-workflow` skills. Four skills still use raw `ls` commands, which can trigger permission prompts. This task replaces those remaining `ls` calls with `aitask_query_files.sh` subcommands.

## Plan

### 1. Add `active-children` and `all-children` subcommands to `aitask_query_files.sh`
### 2. Update `aitask-pickrem/SKILL.md` — replace 5 ls calls + sibling context
### 3. Update `aitask-pickweb/SKILL.md` — replace 5 ls calls + sibling context
### 4. Update `aitask-fold/SKILL.md` — replace 2 ls calls
### 5. Update `aitask-create/SKILL.md` — replace 2 ls calls using new subcommands
### 6. Add tests for new subcommands in `tests/test_query.sh`

## Final Implementation Notes
- **Actual work done:** Added `active-children` (lists active child files) and `all-children` (lists active + archived child files) subcommands to `aitask_query_files.sh`. Replaced all raw `ls aitasks/` and `ls aiplans/` calls in 4 skill files with structured `aitask_query_files.sh` calls. Added 21 new tests (57 total, all passing).
- **Deviations from plan:** Originally named `list-children`, renamed to `active-children` per user feedback for clarity. Added `all-children` subcommand (combines active + archived results) to fix a latent bug where `aitask-create` would generate duplicate child numbers when all siblings were archived.
- **Issues encountered:** Discovered the original `ls`-based child number calculation in aitask-create didn't account for archived children, risking duplicate numbers. Fixed by using `all-children` instead.
- **Key decisions:** Kept `ls .aitask-data-updated/plan_t<task_id>.md` in pickweb as-is since it's a specific known filename in a web-local temp directory, not worth a dedicated subcommand.
