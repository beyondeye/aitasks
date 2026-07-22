---
priority: medium
effort: medium
depends: [1209]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1209]
created_at: 2026-07-22 11:23
updated_at: 2026-07-22 11:23
boardidx: 100
boardcol: tests
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1209

## Verification Checklist

- [ ] Create/keep a board column with no tasks; arrow onto it — a dim "(empty)" row takes focus
- [ ] ctrl+left / ctrl+right move the empty column, and focus stays on it after each move
- [ ] X collapses/expands the empty column; it stays focused across the toggle
- [ ] Collapse a populated column and reorder it with ctrl+arrow (previously impossible)
- [ ] Type a no-match string in the search box: every column shows "(empty)" and focus moves off the hidden card; clear it and focus returns to a card
- [ ] Press r (and wait for an auto-refresh tick) while an empty/collapsed column is focused — focus is preserved
- [ ] Expand a parent with children, then filter to no matches — no bare "↳" connector row survives
- [ ] Move a task between columns / up / down — focus still follows the card (partial-refresh regression check)
- [ ] TODO: verify .aitask-scripts/board/aitask_board.py end-to-end in tmux
