---
Task: t164_aitask_create2_skill_not_user_facing.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

The `aitask-create2` skill is an internal skill used only by Claude to run `./aiscripts/aitask_create.sh`. It should not appear as a user-invocable slash command. The task is to mark it as non-user-invocable and remove it from user-facing documentation.

## Changes

### 1. Mark skill as non-user-invocable
**File:** `.claude/skills/aitask-create2/SKILL.md`
- Add `user-invocable: false` to the YAML frontmatter (same pattern as `task-workflow/SKILL.md`)

### 2. Remove from docs/skills.md
**File:** `docs/skills.md`
- Remove TOC entry: `- [/aitask-create2](#aitask-create2)`
- Remove overview table row: `| /aitask-create2 | ... |`
- Remove cross-reference sentence from `/aitask-create` section: `Use /aitask-create2 for a faster terminal-native experience.`
- Remove entire `/aitask-create2` section (from `## /aitask-create2` through the `---` separator)

### 3. Update docs/workflows.md reference
- Replace `[/aitask-create2](skills.md#aitask-create2)` with `[/aitask-create](skills.md#aitask-create)` in the "Capturing Ideas Fast" section

## Verification
- [x] Grep for `aitask-create2` across docs/ — no remaining user-facing references
- [x] Skill YAML frontmatter has `user-invocable: false`

## Final Implementation Notes
- **Actual work done:** All three changes implemented as planned. Added `user-invocable: false` to skill frontmatter, removed all user-facing documentation references, and updated the workflows.md cross-reference.
- **Deviations from plan:** None — plan executed exactly as written.
- **Issues encountered:** None.
- **Key decisions:** Changed the workflows.md reference to point to `/aitask-create` instead of removing it entirely, since users still need a way to create tasks from within Claude Code.
