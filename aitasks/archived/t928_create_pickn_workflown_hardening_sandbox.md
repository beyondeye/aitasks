---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: chore
status: Done
labels: [task_workflow, aitask_pick, testing]
implemented_with: codex/gpt-5
created_at: 2026-06-03 12:26
updated_at: 2026-06-03 13:59
completed_at: 2026-06-03 13:59
---

Create an experimental workflow-hardening sandbox by duplicating the current aitask-pick and task-workflow definitions into new pickn/workflown variants, then apply the proposed enforcement changes there first.

Context:
During t927 execution, two mandatory workflow procedures were skipped in practice:
- Step 9b Satisfaction Feedback Procedure was not run after archival, so the user was not asked for the final 1-5 rating.
- Risk Evaluation Procedure was not run during planning, so the archived plan lacked a ## Risk section and the archived task lacked risk_code_health / risk_goal_achievement fields.

Do not modify the current production aitask-pick or task-workflow behavior in-place for this task. This task must create a parallel experimental flow first so the changes can be tested and reviewed before being merged back into the current procedure definitions.

Required implementation:
1. Create a new aitask-pickn skill that fully duplicates the currently rendered/authoritative aitask-pick behavior, including profile-aware dispatch behavior where applicable.
2. Create a new task-workflown workflow definition that fully duplicates the current task-workflow definition and its referenced procedure files.
3. Wire aitask-pickn to dispatch into task-workflown, not the production task-workflow.
4. Apply the workflow-hardening changes only inside the new pickn/workflown copies:
   - Add a blocking final-response gate for Step 9b Satisfaction Feedback: after archive/push, the workflow must not send a final response until the Satisfaction Feedback Procedure has either asked for and processed a rating or recorded a valid skip reason from satisfaction-feedback.md.
   - Add a mandatory plan requirement that every implementation plan must contain a ## Risk section produced by the Risk Evaluation Procedure, except explicitly documented skip paths such as cross-repo parent plans.
   - Add a pre-implementation Risk Gate before any code edits: verify the approved plan contains ## Risk plus both Code-health and Goal-achievement risk headings; if missing, stop and repair the plan before implementation.
   - Change Step 7 risk-field behavior from silent conditional write to fail-closed behavior: missing ## Risk is an error, not a skip; when present, write risk_code_health and risk_goal_achievement to task frontmatter.
   - Add an archive-time Risk Gate before aitask_archive.sh: verify the plan has ## Risk and the task frontmatter has risk_code_health and risk_goal_achievement; if any are missing, stop and repair before archival.
5. Add or update tests that validate the new pickn/workflown copies exist, dispatch to each other, preserve parity with the current workflow where expected, and include the new gates.
6. Document that pickn/workflown are experimental staging definitions and that no production workflow merge happens in this task.

Acceptance criteria:
- Existing aitask-pick and task-workflow definitions are not modified except for any minimal registry/test fixture references needed to expose the experimental copies.
- New pickn/workflown definitions are complete enough to run independently from the current production workflow.
- Tests demonstrate that Step 9b feedback and risk evaluation cannot be silently skipped in the experimental workflow.
- The task outcome is an experimental, tested copy only. A later follow-up task should merge the finalized wording into the production workflow after review.
