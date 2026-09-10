---
priority: medium
effort: medium
depends: [219]
issue_type: documentation
status: Done
archived_reason: superseded
labels: [website, claudeskills, documentation]
created_at: 2026-02-23 09:04
updated_at: 2026-09-10 22:07
completed_at: 2026-09-10 22:07
boardcol: backlog
boardidx: 40
---


Add documentation for the new aitask-pickrem skill to the website. Include: 1) Skill reference page describing the workflow, arguments, and profile-driven configuration. 2) Document all remote-specific profile fields (done_task_action, orphan_parent_action, complexity_action, review_action, issue_action, abort_plan_action, abort_revert_status) with their values and defaults. 3) Document profile customization options and how to create custom remote profiles. 4) Explain that EnterPlanMode/ExitPlanMode are still interactive (planning step is supported). Reference: .claude/skills/aitask-pickrem/SKILL.md for the complete skill specification.
After las test this task is delayed until t227 is completed

## Closed as obsolete (2026-09-10)

Covered by t235 (81f8fadba): `skills/aitask-pickrem.md` documents the workflow, arguments, every remote-specific profile field and the interactive ExitPlanMode approval. Not tracked anywhere after this closure: that page's profile YAML sample (~59-75) no longer matches `aitasks/metadata/profiles/remote.yaml`, and the standard-fields table lacks `rendered_gates`.
