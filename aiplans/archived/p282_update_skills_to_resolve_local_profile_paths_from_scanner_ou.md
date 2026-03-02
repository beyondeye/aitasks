---
Task: t282_update_skills_to_resolve_local_profile_paths_from_scanner_ou.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

## Context

The profile scanner (`aitask_scan_profiles.sh`) outputs `local/<filename>` for user-local profiles. Skills that read profile files after scanner output need the scanner-returned path to correctly resolve local profiles. The `cat aitasks/metadata/profiles/<filename>` pattern was already correct in most skills, but `task-workflow/SKILL.md` Step 3b couldn't re-read profiles because no filename was stored in context variables.

## Plan

1. Add `active_profile_filename` context variable to `task-workflow/SKILL.md`
2. Update Step 3b to use `cat aitasks/metadata/profiles/<active_profile_filename>`
3. Update handoff sections in 5 calling skills to pass `active_profile_filename`

## Files Changed

- `.claude/skills/task-workflow/SKILL.md` — Added context variable + updated Step 3b
- `.claude/skills/aitask-pick/SKILL.md` — Added `active_profile_filename` to handoff
- `.claude/skills/aitask-explore/SKILL.md` — Added `active_profile_filename` to handoff
- `.claude/skills/aitask-fold/SKILL.md` — Added `active_profile_filename` to handoff
- `.claude/skills/aitask-review/SKILL.md` — Added `active_profile_filename` to handoff
- `.claude/skills/aitask-pr-review/SKILL.md` — Added `active_profile_filename` to handoff

## Final Implementation Notes
- **Actual work done:** Added `active_profile_filename` as a new context variable that carries the scanner-returned filename (including `local/` prefix for user-scoped profiles) from calling skills through to task-workflow's Step 3b profile refresh. Updated Step 3b to use this filename for profile re-reads.
- **Deviations from plan:** None — implementation matched plan exactly.
- **Issues encountered:** None.
- **Key decisions:** `aitask-pickrem` and `aitask-pickweb` were not modified because they are self-contained (don't hand off to task-workflow for Step 3b) and already use the scanner-returned filename correctly inline.
