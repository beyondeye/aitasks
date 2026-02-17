---
Task: t144_1_rename_clear_old_to_zip_old.md
Parent Task: aitasks/t144_ait_clear_old_rewrite.md
Sibling Tasks: aitasks/t144/t144_2_tar_gz_fallback_resolve_functions.md, aitasks/t144/t144_3_rewrite_selection_logic.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

Child 1 of t144 (ait clear_old rewrite). Rename `aitask_clear_old.sh` → `aitask_zip_old.sh` and update all references. Pure rename, no logic changes. Siblings t144_2 and t144_3 depend on this completing first.

## Implementation Steps

### 1. Git mv the script file
```bash
git mv aiscripts/aitask_clear_old.sh aiscripts/aitask_zip_old.sh
```
Update line 3 comment: `aitask_clear_old.sh` → `aitask_zip_old.sh`

### 2. Git mv the skill directory
```bash
git mv .claude/skills/aitask-cleanold .claude/skills/aitask-zipold
```
Update SKILL.md: name, description, all script references.

### 3. Update `ait` dispatcher
- Line 30: `clear-old` → `zip-old`
- Line 109: `clear-old` → `zip-old`, `aitask_clear_old.sh` → `aitask_zip_old.sh`

### 4. Update `docs/commands.md`
All `clear-old` → `zip-old`

### 5. Update `docs/skills.md`
All `aitask-cleanold` → `aitask-zipold`, `aitask_clear_old.sh` → `aitask_zip_old.sh`

### 6-7. Update settings JSON files
`aitask_clear_old.sh` → `aitask_zip_old.sh` in both seed/claude_settings.local.json and aitasks/metadata/claude_settings.seed.json

### 8. Update test file
`aitask_clear_old.sh` → `aitask_zip_old.sh` in tests/test_terminal_compat.sh

## Verification

- `bash -n aiscripts/aitask_zip_old.sh`
- `./ait zip-old --help`
- `./ait zip-old --dry-run`
- `bash tests/test_terminal_compat.sh`

## Final Implementation Notes

- **Actual work done:** All 8 steps completed exactly as planned. Renamed script file, skill directory, and updated all 8 files with references.
- **Deviations from plan:** None — straightforward rename with no surprises.
- **Issues encountered:** None.
- **Key decisions:** The `ait zip-old --help` output already shows the new script name (`aitask_zip_old.sh`) because the help text is generated from `$0`.
- **Notes for sibling tasks:** The rename is complete. t144_2 and t144_3 task files already reference `aitask_zip_old.sh` (they were written expecting this rename). The script's internal logic (selection functions, archive functions) is unchanged — t144_3 will rewrite the selection logic.
