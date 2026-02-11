---
Task: t53_1_add_issue_metadata_field_to_bash_scripts.md
Parent Task: aitasks/t53_import_gh_issue_as_task.md
Sibling Tasks: aitasks/t53/t53_2_*.md, aitasks/t53/t53_3_*.md, aitasks/t53/t53_4_*.md, aitasks/t53/t53_5_*.md
Branch: main
Base branch: main
---

# Plan: Add `issue` metadata field to bash scripts

## Context

Add a new `issue` metadata field (stores full URL to issue page) to the three bash task management scripts: `aitask_update.sh`, `aitask_create.sh`, and `aitask_ls.sh`. This is the foundation for the GitHub issue import feature (t53).

## Changes Made

### aitask_update.sh
- Added `BATCH_ISSUE`/`BATCH_ISSUE_SET` batch mode variables
- Added `CURRENT_ISSUE` to parsing variables with reset
- Added `--issue` CLI argument parsing
- Added `issue)` case to `parse_yaml_frontmatter()`
- Added `issue` as 14th positional parameter to `write_task_file()`
- `issue:` field written between `assigned_to` and `created_at` (only if non-empty)
- Updated all 4 call sites of `write_task_file()`
- Added save/restore of `CURRENT_ISSUE` in `handle_child_task_completion()`
- Added `has_update` check for `BATCH_ISSUE_SET` in batch mode
- Added `new_issue` computation in batch mode
- Added issue display to interactive summary
- Added help text for `--issue` option

### aitask_create.sh
- Added `BATCH_ISSUE` variable
- Added `--issue` CLI argument parsing
- Added `issue` as 11th parameter to both `create_task_file()` and `create_child_task_file()`
- `issue:` field written between `labels` (or `assigned_to`) and `created_at` (only if non-empty)
- Updated batch mode call sites for both regular and child task creation
- Updated help text

### aitask_ls.sh
- Added `issue_text` variable
- Added `issue)` case to `parse_yaml_frontmatter()`
- Reset `issue_text=""` in `parse_task_metadata()`
- Added issue info to verbose output: `Issue: <url>`

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned. All three scripts updated with the new `issue` field.
- **Deviations from plan:** None significant.
- **Issues encountered:** None. The pattern for adding optional fields was well-established by `boardcol`/`boardidx`/`assigned_to`.
- **Key decisions:** Field is written between `assigned_to` and `created_at` in YAML output, consistent with the "optional metadata before timestamps" convention.
- **Notes for sibling tasks:**
  - The `issue` field stores a full URL (e.g., `https://github.com/owner/repo/issues/123`)
  - Field position in YAML: after `labels`/`children_to_implement`/`assigned_to`, before `created_at`/`updated_at`/`boardcol`/`boardidx`
  - For `aitask_create.sh`, the `--issue` argument works in batch mode. No interactive mode support was added (not needed for the import workflow).
  - The `aitask_board.py` (t53_2) doesn't need these bash changes since it uses `yaml.safe_load()` which parses all fields automatically.
  - The import script (t53_3) should use `--issue URL` when calling `aitask_create.sh --batch`.
