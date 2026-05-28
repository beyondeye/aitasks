---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: []
created_at: 2026-03-09 14:48
updated_at: 2026-05-28 08:42
completed_at: 2026-05-28 08:42
boardcol: next
boardidx: 80
---

in gemini cli the only reliable way to identify the current model id is to call the cli_tool . need to update the task_workflow to use this method for determining the model id

here is the exact prompt to use: ask the cli_help tool what is my current model id

---

## Closed; migrated to t835_1 (2026-05-28, t812_5)

geminicli support was removed from the aitasks framework in t812. The
underlying concern (reliable model-id detection surface) transfers to
agy (Antigravity CLI) and has been migrated to
**`aitasks/t835/t835_1_identifying_model_id_in_agy.md`** — that task
will research agy's reliable model-id surface (candidates:
`agy --version`, `cli_help`/`cli_info` equivalent, or
`~/.gemini/settings.json`) and wire the chosen method into the Model
Self-Detection Sub-Procedure.
