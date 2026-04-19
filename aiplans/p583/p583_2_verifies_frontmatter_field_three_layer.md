---
Task: t583_2_verifies_frontmatter_field_three_layer.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_1_*.md, aitasks/t583/t583_3_*.md .. t583_9_*.md
Archived Sibling Plans: aiplans/archived/p583/p583_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t583_2 — `verifies:` Frontmatter Field (3-layer propagation)

## Context

Adds a new `verifies: [task_id, ...]` list frontmatter field. Per CLAUDE.md's "Adding a New Frontmatter Field" rule, new list fields must touch **all three layers** or the board silently drops them.

Independent of t583_1 (no code dependency). Required by t583_3 and t583_7.

## Files to modify

1. `.aitask-scripts/aitask_create.sh` — batch flag `--verifies`, interactive prompt when `issue_type: manual_verification`, emit via `format_yaml_list()`. Mirror `depends:` at ~390, ~470, ~1398.
2. `.aitask-scripts/aitask_update.sh` — `--add-verifies` / `--remove-verifies` / `--set-verifies`. Mirror `depends` at ~335-338, ~442.
3. `.aitask-scripts/aitask_fold_mark.sh` — union folded tasks' `verifies:` into primary (parallel to existing `folded_tasks` handling).
4. `.aitask-scripts/board/aitask_board.py` — add `VerifiesField` widget class in `TaskDetailScreen.compose()` mirroring `DependsField` (~1986-1992).

## Reference precedent

- `depends:` is the direct analogue. Trace via `git grep -n "depends"` limited to the 4 files above.
- `folded_tasks:` is an analogous list field unioned by `aitask_fold_mark.sh`.
- `lib/task_utils.sh` exposes `format_yaml_list()`, `parse_yaml_list()`, `normalize_task_ids()`.

## Implementation order

1. `aitask_create.sh`: add flag, wire into create_task_file() write paths (3 call sites).
2. `aitask_update.sh`: add 3 flags, wire into write_task_file().
3. `aitask_fold_mark.sh`: add union block parallel to folded_tasks handling.
4. `aitask_board.py`: copy DependsField → VerifiesField, swap field name + shell-out flag.
5. Manual smoke test via `aitask_create.sh --batch --type manual_verification --verifies 10,11 ...`.

## Verification

- Create round-trip: `--verifies 10,11` → file has `verifies: [10, 11]`.
- Update add/remove: `--add-verifies 12 --remove-verifies 10` → `[11, 12]`.
- Fold union: two tasks with `verifies:[A,B]` and `[B,C]` → folded primary has `[A,B,C]`.
- Board TUI: `ait board` → detail panel for a manual-verification task shows `verifies` field with edit widget.
- Full unit tests land in t583_6 (`test_verifies_field.sh`).

## Final Implementation Notes

_To be filled in during implementation._
