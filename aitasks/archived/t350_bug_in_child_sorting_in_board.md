---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
implemented_with: opencode/openai_gpt_5_3_codex
created_at: 2026-03-09 16:57
updated_at: 2026-03-09 17:06
completed_at: 2026-03-09 17:06
---

when a parent task with more that 10 children is expanded in ait board, the children are sorted wrongly: for example for task t259, the children are shown in the order: 10, 11,1,2,3,4,5,6,7,8,9. this is not the desired behavior the sorting shold be 1,2,3,4,5,6,7,8,9,10,11
