---
priority: low
effort: low
depends: []
issue_type: feature
status: Ready
labels: [aitask_board, brainstorming]
created_at: 2026-04-09 11:11
updated_at: 2026-04-09 11:11
---

When launching brainstorm from the board TUI via tmux, detect if an existing tmux window is already running `ait brainstorm` for the specified task number. If found, switch to that window instead of starting a new one. This prevents duplicate brainstorm sessions for the same task.

Check tmux windows for a matching window name pattern (e.g., `brainstorm-<num>`) and use `tmux select-window` to switch to it if found.
