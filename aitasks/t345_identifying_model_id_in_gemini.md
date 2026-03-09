---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: []
created_at: 2026-03-09 14:48
updated_at: 2026-03-09 14:48
boardidx: 110
boardcol: next
---

in gemini cli the only reliable way to identify the current model id is to call the cli_tool . need to update the task_workflow to use this method for determining the model id

here is the exact prompt to use: ask the cli_help tool what is my current model id
