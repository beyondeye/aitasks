---
Task: t76_brief_task_summery_when_starting_ai_pick.md
Worktree: (working on current branch)
Branch: main
Base branch: main
---

# Plan: t76 - Brief task summary when starting AI pick

## Context

When `/aitask-pick` is invoked with an explicit task number, the workflow currently jumps from finding the task file straight to Step 3 (Assign Task) without showing the user what the task is about. The user has no opportunity to confirm they picked the correct task before the workflow proceeds to set status to Implementing, ask for email, etc.

## Change

Modify **Step 0** in `.claude/skills/aitask-pick/SKILL.md` to add a confirmation sub-step after finding the task file (for both Format 1 without children and Format 2 child tasks).

### Specific edits

**File:** `.claude/skills/aitask-pick/SKILL.md`

**For Format 1 (parent task, no children):**

After "If no children → proceed to **Step 3**", add confirmation sub-step.

**For Format 2 (child task):**

After "Skip directly to Step 3", add the same confirmation sub-step with parent context.

### Wording template

```markdown
- **Show task summary and confirm:**
  - Read the task file content
  - Generate a brief 1-2 sentence summary of the task description
  - Use `AskUserQuestion`:
    - Question: "Is this the correct task? Brief summary: <summary of task>"
    - Header: "Confirm task"
    - Options: "Yes, proceed" / "No, abort"
  - If "Yes, proceed" → continue to Step 3
  - If "No, abort" → fall back to Step 1
```

## Verification

- Read the modified SKILL.md to verify correct placement
- Manual test: invoke `/aitask-pick <number>` and confirm summary appears

## Final Implementation Notes
- **Actual work done:** Added confirmation sub-steps to both Format 1 (parent task, no children) and Format 2 (child task) in Step 0 of `.claude/skills/aitask-pick/SKILL.md`. Each sub-step reads the task file, generates a brief summary, and uses `AskUserQuestion` to confirm before proceeding.
- **Deviations from plan:** None. Implementation matched the plan exactly.
- **Issues encountered:** Initially left a redundant "Skip directly to Step 3" line in the Format 2 section after adding the confirmation flow; removed it in a follow-up edit.
- **Key decisions:** For child tasks, the confirmation summary includes the parent task name for additional context. The "No, abort" option falls back to Step 1 (normal task selection) rather than exiting entirely.

## Post-Implementation

Follow Step 8 from the aitask-pick workflow for archival.
