---
priority: medium
effort: medium
depends: [t1243_14]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [t1243_3, t1243_4, t1243_5, t1243_6, t1243_7, t1243_8, t1243_9, t1243_10, t1243_11, t1243_12, t1243_13]
anchor: 1243
followup_kind: manual_verification
created_at: 2026-07-28 01:21
updated_at: 2026-08-13 23:06
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1243_3] Move a task right across three columns with shift+right; confirm it lands correctly and that `git status` in .aitask-data shows ONLY that task file modified — no files in the columns it passed through.
- [ ] [t1243_3] Move a task to the top and bottom of a column (ctrl+up / ctrl+down); confirm ordering is correct and only that task file changed.
- [ ] [t1243_3] On a column whose tasks still carry legacy 10/20/30 indices, insert repeatedly between the same two cards until a respace fires; confirm the board stays visually correct and the respace happens once, not on every move.
- [ ] [t1243_4] With a search filter active on a large board, hold shift+up/shift+down; confirm the board feels responsive and cards do not visibly flicker or re-flow.
- [ ] [t1243_4] Move a card laterally, vertically, and to a column extreme; confirm each moved card shows the `*` modified marker immediately. The marker now comes from the write itself, not from a `git status` scan per keypress.
- [ ] [t1243_4] With the board open, commit a task file from another terminal, then move an *unrelated* card. Confirm the committed task keeps a stale `*` until you press `r`. This is the accepted add-only trade-off, not a bug — `r`, a view switch, a detail return, and a board commit all still run the full scan.
- [ ] [t1243_4] With a search filter that hides the focused card's column, move a card; confirm focus is never left stranded on a hidden card.
- [ ] [t1243_4] Filter one column empty, then move a card in a *different* column; confirm the empty column's `(empty)` placeholder does not flicker or change state.
- [ ] [t1243_5] Move a task laterally while its children are expanded; confirm the child rows travel with it, focus stays on the moved card in the destination column, and a search typed afterwards filters correctly.
- [ ] [t1243_5] After a lateral move, press ctrl+left / ctrl+right; confirm column reordering still acts on the correct column.
- [ ] [t1243_6] Press space on several cards; confirm the checkbox glyph toggles, marked cards read as bold yellow, and the marks survive typing a search filter.
- [ ] [t1243_6] Press space on an expanded child card; confirm nothing is marked and the "child tasks move with their parent" message appears.
- [ ] [t1243_6] Switch views (a / l / f / i / y); confirm marks are cleared and the space binding is hidden where movement is hidden.
- [ ] [t1243_7] Mark several tasks, press m, choose a destination column; confirm they arrive in the order they were listed and only those files changed.
- [ ] [t1243_7] Focus an empty column, press m; confirm the task-select subdialog opens scoped to a column, and that Escape (cancel) leaves everything untouched.
- [ ] [t1243_9] Create a group, collapse it, and navigate a column that contains ONLY collapsed groups with arrow keys; confirm focus is never lost and left/right still move between columns.
- [ ] [t1243_9] With a grouped parent whose children are expanded, walk down with the arrow key; confirm the order is header, parent, its children, next member, then the next unit outside the group.
- [ ] [t1243_9] With focus on a group header, press shift+right; confirm the whole group moves. With focus on a member, press shift+right; confirm only that member moves and the notice about leaving the group appears.
- [ ] [t1243_10] Collapse a group, type a search that matches only a member's child task; confirm the collapsed group's header stays visible and shows a match count.
- [ ] [t1243_10] Type a search that matches nothing in a column containing only collapsed groups; confirm the empty-column placeholder appears and focus is not stranded.
- [ ] [t1243_10] Collapse a group, quit and relaunch the board; confirm it is still collapsed. Repeat after renaming the group, after moving it to another column, and after renaming and after deleting its column.
- [ ] [t1243_11] Move a group of several tasks up past a single card; confirm the group moves as a block, the order inside it is preserved, and the card it passed is NOT modified in git status.
- [ ] [t1243_11] Move a group into a column that already contains a group with the same name; confirm they merge, the arriving tasks appear after the residents, and a notice explains the merge.
- [ ] [t1243_12] Rename a group to a name already used in the same column; confirm a confirmation prompt appears and that cancelling changes nothing on disk.
- [ ] [t1243_12] Remove the last member from a group; confirm the group disappears and does not reappear after a board restart.
- [ ] [t1243_12] Open a task's detail screen and set/clear its group from the Board group field; confirm the board reflects it after closing.
- [ ] [t1243_8] CROSS-PC: group a task on machine A and sync; confirm the group appears on machine B.
- [ ] [t1243_8] CROSS-PC: remove a task from its group on machine A; on machine B (unsynced) edit only that task's status; sync both. Confirm the task ends up OUT of the group — the status-only edit must not resurrect the membership.
- [ ] [t1243_13] Read the board documentation page as a new user; confirm every key it documents actually works and no documented behaviour is missing.
