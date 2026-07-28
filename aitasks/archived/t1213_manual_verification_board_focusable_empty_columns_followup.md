---
priority: medium
effort: medium
depends: [1209]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1209]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-22 11:23
updated_at: 2026-07-28 11:30
completed_at: 2026-07-28 11:30
boardcol: tests
boardidx: 100
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1209

## Verification Checklist

- [x] Create/keep a board column with no tasks; arrow onto it — a dim "(empty)" row takes focus — PASS 2026-07-28 11:28 auto: tmux board, Empty(0) column renders dim '(empty)'; right-arrow focuses it (bg accent rgb(12,48,76) vs default rgb(18,18,18))
- [x] ctrl+left / ctrl+right move the empty column, and focus stays on it after each move — PASS 2026-07-28 11:28 auto: ctrl+left moved zz_empty to index 0, two ctrl+right moves to index 2; column_order updated on disk and accent bg stayed on '(empty)' after each
- [x] X collapses/expands the empty column; it stays focused across the toggle — PASS 2026-07-28 11:28 auto: X collapsed Empty to the '···' placeholder (accent bg) and X expanded it back to '(empty)' (accent bg) -- focus held across both
- [x] Collapse a populated column and reorder it with ctrl+arrow (previously impossible) — PASS 2026-07-28 11:28 auto: collapsed populated Left(2) with X (focus moved to its '···'), ctrl+right reordered it to ['zz_right','zz_left','zz_empty'] with focus retained
- [x] Type a no-match string in the search box: every column shows "(empty)" and focus moves off the hidden card; clear it and focus returns to a card — PASS 2026-07-28 11:28 auto: search 'zzznomatchzzz' -> all 3 columns show '(empty)', no card rows render; Esc focuses a placeholder, not a hidden card. Cleared filter -> focus back on a card (double-border t3)
- [x] Press r (and wait for an auto-refresh tick) while an empty/collapsed column is focused — focus is preserved — PASS 2026-07-28 11:28 auto: r preserved focus on both '(empty)' and collapsed '···'; separate 1-min auto_refresh instance re-globbed a new task (Right 2->3, no keypress) with focus still on '(empty)'
- [x] Expand a parent with children, then filter to no matches — no bare "↳" connector row survives — PASS 2026-07-28 11:28 auto: expanded parent t1 (2 '↳' child rows visible), then no-match filter -> 0 '↳' and 0 child-card glyphs remain
- [x] Move a task between columns / up / down — focus still follows the card (partial-refresh regression check) — PASS 2026-07-28 11:28 auto: shift+down, shift+right (cross-column), shift+up all kept focus on the moved card; moving the last card out turned Right into '(empty)' with focus following the card
- [x] TODO: verify .aitask-scripts/board/aitask_board.py end-to-end in tmux — PASS 2026-07-28 11:28 auto: full e2e in tmux (200x50) against a sandbox TASK_DIR -- nav/reorder/collapse/search/move/refresh, no traceback in pane history; tests/test_board_empty_column_focus.py 12/12 OK
