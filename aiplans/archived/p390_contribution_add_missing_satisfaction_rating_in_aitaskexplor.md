---
Task: t390_contribution_add_missing_satisfaction_rating_in_aitaskexplor.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

When a user runs `/aitask-explore` and selects "Save for later" at the decision point (Step 4), the workflow ends without collecting satisfaction feedback. The Satisfaction Feedback Procedure only runs via task-workflow Step 9b, which is only reached when continuing to implementation. This means valuable feedback data for model selection is lost for the "Save for later" path.

Contribution from beyondeye (issue #7). Folded task t379.

## Plan

### 1. Edit `.claude/skills/aitask-explore/SKILL.md` (line ~211)

In Step 4's "Save for later" path, add a line to execute the Satisfaction Feedback Procedure between the user notification and the workflow end:

**Current (lines 210-212):**
```markdown
**If "Save for later":**
- Inform user: "Task t\<N\>_\<name\>.md is ready. Run `/aitask-pick <N>` when you want to implement it."
- End the workflow.
```

**After:**
```markdown
**If "Save for later":**
- Inform user: "Task t\<N\>_\<name\>.md is ready. Run `/aitask-pick <N>` when you want to implement it."
- Execute the **Satisfaction Feedback Procedure** (see `.claude/skills/task-workflow/procedures.md`) with `skill_name` = `"explore"`.
- End the workflow.
```

This matches the exact diff from the contribution.

### 2. Step 9 (Post-Implementation)

No other changes needed. The contribution is a clean single-line addition.

## Final Implementation Notes
- **Actual work done:** Added single line to `.claude/skills/aitask-explore/SKILL.md` at line 212, exactly matching the contributed diff
- **Deviations from plan:** None — implemented exactly as planned
- **Issues encountered:** None
- **Key decisions:** Only the Claude Code version needed updating; the OpenCode version of aitask-explore doesn't have a "Save for later" path
