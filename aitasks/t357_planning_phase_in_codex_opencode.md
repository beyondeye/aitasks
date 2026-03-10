---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [task_workflow]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-10 09:37
updated_at: 2026-03-10 10:58
---

currently the planning phase of the task-workflow skill when executed in opencode (even if in planning mode)  create a very high level plan that is not suitable for discussion and refinement using the user feedback. only when prompted to create a detailed-step-by-step implementation plan thenopen code actual come up with something is suitable for discussion, perhpas need to edit the planning phase in task-workflow to make this more explicit. also need to update the known issue subpage of the installation page in web site that when opencode run interactive skills like aitask-pick it skips task locking at the beginning of the skill so this must be avoided (perhaps add this to the docs of the aitask-pick and similar skills that have the aitask-own.sh script call) better to user opencode in regular mode (not plan mode)
