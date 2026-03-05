---
priority: medium
effort: medium
depends: [222]
issue_type: feature
status: Ready
labels: [board, statistics, plotting]
created_at: 2026-03-05 15:28
updated_at: 2026-03-05 15:28
---

Integrate triggering task statistics plotting from `ait board` directly.

Goal:
- Add a board action/command that runs the stats plotting workflow (currently exposed via `ait stats --plot`) without leaving the board workflow.

Expected scope:
- Define where the action lives in board UX (command palette, keybinding, or task detail action).
- Trigger stats plot mode and handle environments where `plotext` is missing (clear user guidance, no crash).
- Reuse the existing stats command interface rather than duplicating stats logic inside board.
- Document UX behavior and error handling.

Validation:
- Manual validation from board on systems with and without `plotext` installed.
- Ensure existing board functionality remains unchanged.
