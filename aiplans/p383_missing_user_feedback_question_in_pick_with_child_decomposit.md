---
Task: t383_missing_user_feedback_question_in_pick_with_child_decomposit.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

When `aitask-pick` decomposes a task into child tasks and the user selects "Stop here", the Satisfaction Feedback Procedure is never executed. The feedback should be collected to track model performance even for decomposition-only sessions.

## Implementation Plan

### 1. Add `feedback_collected` guard variable to context table (SKILL.md)

Add a new row to the context requirements table for `feedback_collected: boolean`, initialized to `false`, set to `true` after feedback runs.

### 2. Add feedback call to "Stop here" path (planning.md)

In the child task checkpoint "Stop here" handler, execute the Satisfaction Feedback Procedure before ending the workflow.

### 3. Update "Stop here" note in SKILL.md

Update the Step 6 summary note to mention that feedback is collected on the "Stop here" path.

### 4. Add guard to Satisfaction Feedback Procedure (procedures.md)

Add a guard check at the top of the procedure: skip if `feedback_collected` is `true`, otherwise set it to `true` before proceeding. Prevents double execution.

## Final Implementation Notes
- **Actual work done:** All 4 changes implemented as planned across 3 files (SKILL.md, planning.md, procedures.md)
- **Deviations from plan:** User manually refined the SKILL.md line 244 wording to be more explicit ("Satisfaction Feedback Procedure (see procedures.md) with skill_name from context variables" instead of "(as instructed in planning.md)")
- **Issues encountered:** User flagged potential double-execution risk; addressed by adding the `feedback_collected` guard variable
- **Key decisions:** Guard variable approach chosen over prose-only disambiguation to provide a programmatic guarantee against double execution
