---
priority: high
effort: medium
depends: []
issue_type: bug
status: Done
labels: [workflow, codexcli, locking, aitask_pick]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-05 16:02
updated_at: 2026-03-05 22:11
completed_at: 2026-03-05 22:11
---

Update task-workflow and Codex wrapper skills (including all aitask-pick variants) so ownership/lock acquisition is guaranteed before implementation starts. Add a guard that checks whether own/lock was already performed; if not (e.g. due to plan-mode deferral), run own immediately at the beginning of implementation and only then proceed. Cover direct implementation paths and variants embedding task-workflow.
