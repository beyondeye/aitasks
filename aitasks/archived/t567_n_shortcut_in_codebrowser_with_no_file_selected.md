---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [codebrowser]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-16 08:27
updated_at: 2026-04-16 09:53
completed_at: 2026-04-16 09:53
---

in ait codebrowser the n shortcut allow to create new task from code file line range: two changes to behavior required: 1) if no line range selected and no file open, then spawn create new task command withot file reference, if file opened but no line range selected then default to full line range). also in tmux options for spawning the ait create bash script, default to spawning in THE SAME TMUX window whe codebrowser is currently running, so that during ait create we can actually see the file
