---
Task: t347_consolidate_aitask_create_skill.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Plan

Consolidate aitask-create and aitask-create2 skills into a single skill by:

1. Adding batch mode documentation (from aitask-create2) to aitask-create SKILL.md
2. Deleting the aitask-create2 skill directory
3. Updating CLAUDE.md skill count (13 → 21, correcting stale count)
4. Updating website docs to mention batch mode

## Final Implementation Notes

- **Actual work done:** Merged batch mode instructions into aitask-create, deleted aitask-create2, updated skill count and website docs
- **Deviations from plan:** Initially included terminal fzf interactive mode reference in the skill; removed per user feedback since fzf interactive mode won't work inside a code agent context. Also expanded batch mode flags to include the full set from `--help` output (status, assigned-to, issue, finalize, finalize-all, silent) beyond what aitask-create2 originally documented.
- **Issues encountered:** The CLAUDE.md skill count was already stale (said 13, actual was 22). Updated to 21 (post-deletion count).
- **Key decisions:** Left historical references to aitask-create2 in CHANGELOG.md and aiexplains/ untouched. No changes needed in .gemini/, .agents/, .opencode/ (no references existed).

## Post-Review Changes

### Change Request 1 (2026-03-09 18:30)
- **Requested by user:** Check batch mode usage is up-to-date, remove fzf interactive mode reference from skill
- **Changes made:** Removed "Terminal-Interactive Mode (fzf)" subsection from SKILL.md, verified all batch flags against `--help` output and added missing ones (--status, --assigned-to, --issue, --finalize, --finalize-all, --silent), simplified website docs to remove fzf mention
- **Files affected:** .claude/skills/aitask-create/SKILL.md, website/content/docs/skills/aitask-create.md
