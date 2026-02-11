---
Task: t85_4_fix_skill_references.md
Parent Task: aitasks/t85_universal_install.md
Sibling Tasks: aitasks/t85/t85_5_*.md, aitasks/t85/t85_6_*.md, etc.
Archived Sibling Plans: aiplans/archived/p85/p85_*_*.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

Scripts have been moved from the project root to `aiscripts/` (completed in t85_3). The 5 SKILL.md files in `~/Work/aitasks/skills/` still reference `./aitask_*` and need updating to `./aiscripts/aitask_*`.

## Plan

1. Run bulk sed replacement across all 5 SKILL.md files:
   ```bash
   cd ~/Work/aitasks
   sed -i 's|\./aitask_|./aiscripts/aitask_|g' skills/*/SKILL.md
   ```

2. Verify: confirm 0 old references remain, 27 new references exist

3. Spot-check `skills/aitask-pick/SKILL.md` (largest file, 11 references)

## Files Modified

- `~/Work/aitasks/skills/aitask-cleanold/SKILL.md` (4 refs)
- `~/Work/aitasks/skills/aitask-create/SKILL.md` (3 refs)
- `~/Work/aitasks/skills/aitask-create2/SKILL.md` (4 refs)
- `~/Work/aitasks/skills/aitask-pick/SKILL.md` (11 refs)
- `~/Work/aitasks/skills/aitask-stats/SKILL.md` (5 refs)

## Verification

1. `grep -r '\./aitask_' ~/Work/aitasks/skills/` → 0 matches
2. `grep -r '\./aiscripts/aitask_' ~/Work/aitasks/skills/` → 27 matches
3. Visual spot-check of aitask-pick/SKILL.md

## Post-Implementation (Step 9)

Commit in aitasks repo, archive child task and plan in tubetime repo.

## Final Implementation Notes
- **Actual work done:** Exactly as planned — single sed command replaced all 27 occurrences of `./aitask_` with `./aiscripts/aitask_` across 5 SKILL.md files.
- **Deviations from plan:** None.
- **Issues encountered:** None — clean 1:1 replacement with no double-replace issues.
- **Key decisions:** Used `sed -i` with `|` delimiter to avoid escaping issues with path separators.
- **Notes for sibling tasks:** The SKILL.md files now correctly reference `./aiscripts/aitask_*.sh`. When t85_9 (apply changes to tubetime) runs, the tubetime `.claude/skills/` copies will need to be synced from this repo. The pattern `./aitask_` is fully eliminated from skill files — any future script references should use `./aiscripts/` prefix.
