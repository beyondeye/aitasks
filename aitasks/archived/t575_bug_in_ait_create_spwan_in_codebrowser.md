---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [codebrowser, aitask-create]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-16 12:37
updated_at: 2026-04-16 12:50
completed_at: 2026-04-16 12:50
---

when spawning ait create from codebrowser tui for a selection of line in file detail, we have the ait create spwan in tmux in the same windows of codebrowser. the problem is that the resolved window can become wrong if some windows are clsosed open: the resolving of the window is not dynamic
