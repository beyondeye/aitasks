---
Task: t23_rewrite_clear_old_skill.md
Worktree: none (working in main repository)
Branch: current
---

# Plan: Rewrite aitask-cleanold Skill with Bash Script

## Summary

Rewrite the aitask-cleanold skill to use a dedicated bash script (`aitask_clear_old.sh`) instead of the current multi-step workflow that Claude must execute manually. The script will handle all archiving logic, with the SKILL.md simply invoking the script.

## Files to Create/Modify

1. **Create:** `aitask_clear_old.sh` - New bash script with full archiving logic
2. **Modify:** `.claude/skills/aitask-cleanold/SKILL.md` - Simplify to just invoke the script

## Implementation Steps

### Step 1: Create `aitask_clear_old.sh`

- [x] Create the bash script at repository root with:
  - Archive old task files from `aitasks/archived/` to `old.tar.gz`
  - Archive old plan files from `aiplans/archived/` to `old.tar.gz`
  - Keep the most recent task and plan file uncompressed
  - Verify archive integrity before deleting originals
  - Handle edge cases (no files, corrupted archives, permission errors)

**Flags:**
- `--dry-run` / `-n`: Show what would be archived without making changes
- `--no-commit`: Archive files but skip git commit
- `--verbose` / `-v`: Show detailed progress output
- `--help` / `-h`: Display usage information

### Step 2: Update SKILL.md

- [x] Replace the current 7-step workflow with a simple invocation of the script

## Verification

- [x] Run `./aitask_clear_old.sh --dry-run` to verify it correctly identifies files
- [x] Run `./aitask_clear_old.sh --dry-run --verbose` to see detailed output
- [x] Test `--help` flag shows usage

## Post-Implementation

- [ ] Archive task file t23 (add completion timestamp, move to archived/)
- [ ] Archive this plan file (add completion timestamp, move to archived/)

---
COMPLETED: 2026-02-01 14:43
