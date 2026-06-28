---
priority: medium
effort: low
depends: []
issue_type: test
status: Done
labels: [tests, task_workflow]
implemented_with: codex/gpt5_5
created_at: 2026-06-28 10:30
updated_at: 2026-06-28 10:39
completed_at: 2026-06-28 10:39
---

Remove obsolete geminicli/Gemini CLI expectations from task-workflow test fixtures now that geminicli is no longer a supported code agent.

The cleanup keeps the fixtures aligned with the supported agent set: claudecode, codex, and opencode.
