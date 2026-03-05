---
priority: high
effort: medium
depends: []
issue_type: documentation
status: Done
labels: [documentation, codexcli, workflow, aitask_pick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-05 16:06
updated_at: 2026-03-05 22:50
completed_at: 2026-03-05 22:50
---

Update website docs for all skills that embed task-workflow (including all aitask-pick variants) to document that when using the Codex codeagent, after implementation the user must explicitly tell the agent to continue the remaining workflow steps (review/finalization/archive). This is due to AskUserQuestion not being available outside plan mode in Codex.
