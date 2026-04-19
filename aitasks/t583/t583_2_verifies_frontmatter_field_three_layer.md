---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [framework, skill, task_workflow, verification]
created_at: 2026-04-19 08:29
updated_at: 2026-04-19 08:29
---

## Context

Second child of t583. Adds a new `verifies: [task_id, ...]` list frontmatter field used by manual-verification tasks to declare which feature siblings they validate. Independent of t583_1 (no code dependency). Required by t583_3 (follow-up helper disambiguates via this list) and t583_7 (generation integration populates it).

Per CLAUDE.md's "Adding a New Frontmatter Field" rule, a new list field must touch 3 layers: create/update scripts, fold_mark union, board TaskDetailScreen widget. Missing any layer means the board silently drops the field.

## Key Files to Modify

- `.aitask-scripts/aitask_create.sh` — add `--verifies t1,t2,t3` batch flag; interactive prompt visible only when `issue_type: manual_verification`; emit via `format_yaml_list()`.
- `.aitask-scripts/aitask_update.sh` — add `--add-verifies`, `--remove-verifies`, `--set-verifies`; parse via `parse_yaml_list()` + `normalize_task_ids()`.
- `.aitask-scripts/aitask_fold_mark.sh` — union folded tasks' `verifies:` into the primary at fold time.
- `.aitask-scripts/board/aitask_board.py` — add `VerifiesField` widget class in `TaskDetailScreen.compose()` mirroring `DependsField`.

## Reference Files for Patterns

- `depends:` field is the closest precedent. Trace:
  - `aitask_create.sh` ~lines 390, 470, 1398 (`depends: $deps_yaml` via `format_yaml_list()`).
  - `aitask_update.sh` ~lines 335-338 (parse), ~442 (write).
  - `aitask_board.py` ~lines 1986-1992 (`DependsField` widget).
- `folded_tasks:` is another existing list field — `aitask_fold_mark.sh` already unions it; add `verifies:` alongside.
- `lib/task_utils.sh` — `format_yaml_list()`, `parse_yaml_list()`, `normalize_task_ids()`.

## Implementation Plan

1. **`aitask_create.sh`:**
   - Add `--verifies` to batch flag parsing; default empty.
   - In the write paths (`create_task_file()` at ~line 360+ and helpers at ~440+, ~1370+), emit `verifies: $verifies_yaml` line via `format_yaml_list()` whenever the list is non-empty.
   - Interactive prompt: if `issue_type == manual_verification` and stdin is a TTY, ask for comma-separated task IDs.

2. **`aitask_update.sh`:**
   - Add three new batch flags: `--add-verifies`, `--remove-verifies`, `--set-verifies`.
   - Parse/normalize input; pass through to `write_task_file()`.
   - Mirror the `depends` handling at lines 335-338 and 442.

3. **`aitask_fold_mark.sh`:**
   - Locate where `folded_tasks` is unioned (search the script for `folded_tasks` assembly).
   - Add a parallel block that unions `verifies:` from all folded tasks into the primary.
   - Deduplicate and normalize IDs.

4. **`aitask_board.py` `TaskDetailScreen`:**
   - Copy `DependsField` class; rename to `VerifiesField`; swap the flag name in the shell-out (`--set-verifies`) and the metadata key (`verifies`).
   - Wire into `compose()` method alongside `DependsField`.

## Verification Steps

- Create a manual-verification task with `./.aitask-scripts/aitask_create.sh --batch --type manual_verification --name test --verifies 10,11 --desc test --commit`. Inspect the resulting file — `verifies: [10, 11]` present.
- Update: `./.aitask-scripts/aitask_update.sh --batch <id> --add-verifies 12 --remove-verifies 10`. Inspect: `verifies: [11, 12]`.
- Fold two tasks (both with `verifies:` set) into a third. Confirm the third's `verifies:` is the union.
- Launch `ait board`, pick the manual-verification task, inspect detail panel — `verifies` field appears as editable list.

## Step 9 reminder

Standard post-implementation flow. Commit: `feature: Add verifies frontmatter field (t583_2)`.
