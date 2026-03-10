---
priority: medium
effort: medium
depends: [2]
issue_type: feature
status: Implementing
labels: [codeagent, ait_settings]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-08 11:19
updated_at: 2026-03-10 22:30
---

## Context

This is child task 3 of t303. It adds the Satisfaction Feedback Procedure call to task-workflow (covering aitask-pick, aitask-explore, aitask-pr-import, aitask-fold, aitask-review) and to skills with their own finalization (aitask-wrap, aitask-web-merge).

## Key Files to Modify

- `.claude/skills/task-workflow/SKILL.md` — add Step 9b after archival push, add `skill_name` to context variables table
- `.claude/skills/aitask-pick/SKILL.md` — set `skill_name: "pick"` in handoff context variables
- `.claude/skills/aitask-explore/SKILL.md` — set `skill_name: "explore"` in handoff
- `.claude/skills/aitask-pr-import/SKILL.md` — set `skill_name: "pr-import"` in handoff
- `.claude/skills/aitask-fold/SKILL.md` — set `skill_name: "fold"` in handoff
- `.claude/skills/aitask-review/SKILL.md` — set `skill_name: "review"` in handoff
- `.claude/skills/aitask-wrap/SKILL.md` — add feedback after Step 5
- `.claude/skills/aitask-web-merge/SKILL.md` — add feedback after completion

## Reference Files for Patterns

- `.claude/skills/task-workflow/procedures.md` — Satisfaction Feedback Procedure (created in t303_2)
- `.claude/skills/task-workflow/SKILL.md` — current context variables table and Step 9 flow
- `.claude/skills/aitask-pick/SKILL.md` — current handoff section (Step 3)

## Implementation Plan

### 1. Update context variables table in task-workflow/SKILL.md

Add row:
```markdown
| `skill_name` | string | Name of the calling skill for feedback tracking (e.g., `pick`, `explore`, `pr-import`) |
```

### 2. Add Step 9b to task-workflow/SKILL.md

After the `./ait git push` at the end of Step 9, add:

```markdown
### Step 9b: Satisfaction Feedback

Execute the **Satisfaction Feedback Procedure** (see `procedures.md`) with `skill_name` from the context variables.
```

### 3. Update each calling skill's handoff

In each skill's "Hand Off to Shared Workflow" section, add `skill_name` to the context variable list:

- **aitask-pick:** `- **skill_name**: "pick"`
- **aitask-explore:** `- **skill_name**: "explore"`
- **aitask-pr-import:** `- **skill_name**: "pr-import"`
- **aitask-fold:** `- **skill_name**: "fold"`
- **aitask-review:** `- **skill_name**: "review"`

### 4. Add feedback to aitask-wrap

Add after the existing final step:
```markdown
### Step 6: Satisfaction Feedback

Execute the **Satisfaction Feedback Procedure** (see `.claude/skills/task-workflow/procedures.md`) with `skill_name` = `"wrap"`.
```

### 5. Add feedback to aitask-web-merge

Add after the completion step:
```markdown
### Step X: Satisfaction Feedback

Execute the **Satisfaction Feedback Procedure** (see `.claude/skills/task-workflow/procedures.md`) with `skill_name` = `"web-merge"`.
```

### 6. Note about pickrem and pickweb

These skills explicitly skip feedback (no interactive prompts available). Add a note to their SKILL.md files:
```markdown
**Note:** Satisfaction feedback is not collected in this skill (non-interactive mode).
```

## Verification Steps

- Each calling skill sets `skill_name` in its handoff context variables
- task-workflow Step 9b references the correct procedure
- aitask-wrap and aitask-web-merge have the feedback step in the correct position
- Walk through a complete aitask-pick flow and verify feedback would be asked at the end
