---
Task: t240_rename_own_script.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Rename aitask_own.sh → aitask_pick_own.sh (t240)

## Context

The `aitask_own.sh` script handles task ownership claiming (lock, status update, commit, push) and remote sync. It's specifically designed for the aitask-pick workflow, not a general-purpose script. Renaming it to `aitask_pick_own.sh` makes this relationship explicit.

## Changes

### 1. Rename the script file
- `aiscripts/aitask_own.sh` → `aiscripts/aitask_pick_own.sh`
- Update internal references within the script (header comments, usage text)

### 2. Update skill files (7 files)
All `./aiscripts/aitask_own.sh` → `./aiscripts/aitask_pick_own.sh`:

- `.claude/skills/aitask-pick/SKILL.md` (1 ref: --sync)
- `.claude/skills/task-workflow/SKILL.md` (7 refs: ownership claiming + force)
- `.claude/skills/aitask-pickrem/SKILL.md` (4 refs: sync + ownership)
- `.claude/skills/aitask-pickweb/SKILL.md` (2 refs: lock comparison notes)
- `.claude/skills/aitask-explore/SKILL.md` (1 ref: --sync)
- `.claude/skills/aitask-fold/SKILL.md` (1 ref: --sync)
- `.claude/skills/aitask-review/SKILL.md` (1 ref: --sync)

### 3. Update other scripts
- `aiscripts/aitask_lock.sh` line 17: comment referencing caller

### 4. Update settings files
- `.claude/settings.local.json` (2 refs: Bash permissions)
- `seed/claude_settings.local.json` (1 ref: Bash permissions)

### 5. Update test files
- `tests/test_lock_force.sh` (~10 refs: script path + comments)
- `tests/test_sed_compat.sh` (1 ref: comment)

### 6. Update documentation
- `aidocs/sed_macos_issues.md` (1 ref: portability table)
- `website/content/docs/skills/aitask-pickweb.md` (1 ref: comparison table)

## Verification

1. `bash -n aiscripts/aitask_pick_own.sh` — syntax check
2. `shellcheck aiscripts/aitask_pick_own.sh` — lint
3. `grep -r "aitask_own" . --include="*.sh" --include="*.md" --include="*.json" | grep -v archived` — confirm no stale references remain
4. `bash tests/test_lock_force.sh` — run the ownership test
5. `bash tests/test_sed_compat.sh` — run sed compat test (has a comment ref)

## Final Implementation Notes
- **Actual work done:** Renamed `aiscripts/aitask_own.sh` → `aiscripts/aitask_pick_own.sh` via `git mv`, then updated all 14 files containing references (7 skill files, 2 settings files, 2 test files, 1 script comment, 2 documentation files).
- **Deviations from plan:** None — straightforward find-and-replace across all identified files.
- **Issues encountered:** None.
- **Key decisions:** Used `replace_all` for each file to ensure no references were missed.

## Step 9 Reference
Post-implementation: archive task and plan per task-workflow Step 9.
