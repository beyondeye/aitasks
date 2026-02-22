---
Task: t201_userfileselect_not_user_invocable.md
---

## Context

The `user-file-select` skill was designed as a reusable internal component invoked by other skills (aitask-explore, aitask-explain). However, it's missing the `user-invocable: false` frontmatter flag, so Claude Code exposes it as a user-invocable `/user-file-select` command, which it should not be.

## Plan

Add `user-invocable: false` to the YAML frontmatter of `.claude/skills/user-file-select/SKILL.md`.

**Pattern reference:** `.claude/skills/task-workflow/SKILL.md` uses the same flag:
```yaml
---
name: task-workflow
description: ...
user-invocable: false
---
```

### File to modify

- `.claude/skills/user-file-select/SKILL.md` — Add `user-invocable: false` to frontmatter

## Verification

1. Check the frontmatter has the correct field
2. Confirm the skill is no longer listed in Claude Code's system reminder as a user-invocable skill (would require restarting the session to verify)

## Final Implementation Notes
- **Actual work done:** Added `user-invocable: false` to the YAML frontmatter of `.claude/skills/user-file-select/SKILL.md`, matching the pattern used by `task-workflow` and `aitask-create2`
- **Deviations from plan:** None
- **Issues encountered:** None
- **Key decisions:** Used the same frontmatter field (`user-invocable: false`) already established by other internal-only skills in the project
