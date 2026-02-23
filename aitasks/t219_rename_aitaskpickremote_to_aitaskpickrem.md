---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [claudeskills]
created_at: 2026-02-23 09:10
updated_at: 2026-02-23 09:10
---

Rename the aitask-pick-remote skill to aitask-pickrem for brevity. Changes needed: 1) Rename directory .claude/skills/aitask-pick-remote/ to .claude/skills/aitask-pickrem/. 2) Update name field in SKILL.md frontmatter. 3) Update any references in .claude/skills/task-workflow/SKILL.md that point to aitask-pick-remote. 4) No profile changes needed (profiles don't reference skill names).
