---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [execution_profiles]
created_at: 2026-03-16 16:06
updated_at: 2026-03-16 16:06
---

the execution profile selection procedure is common to multiple skills, refactor it to single file in skills/task-workflow/execution-profile-selection.md and use it instead of copying the same procedure into multiple skills. review all existing skills in ./claude/skills and use the new refactored procedure
