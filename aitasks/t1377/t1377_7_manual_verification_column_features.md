---
priority: medium
effort: medium
depends: [t1377_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1377_2, 1377_3, 1377_5, 1377_6]
anchor: 1243
created_at: 2026-08-04 10:02
updated_at: 2026-08-04 10:02
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1377_2] In a real ~40-column minimonitor companion pane, press p, enter a task number, and confirm the detail dialog shows THREE buttons (OK/Launch anyway, Move to column…, Cancel) fully readable and not clipped
- [ ] [t1377_2] Choosing the pick path launches the agent exactly as before — same launch dialog, same window naming, no behaviour change
- [ ] [t1377_2] Choosing "Move to column…" opens the column picker; ↑/↓ navigate, Enter selects, Esc cancels, and the task's current column is visibly marked
- [ ] [t1377_2] After a move, ait board shows the task at the BOTTOM of the destination column on next refresh (not at an arbitrary position)
- [ ] [t1377_2] The moved task's updated_at in its frontmatter is UNCHANGED (a layout write must not stamp it)
- [ ] [t1377_2] Multi-session: follow an agent belonging to a DIFFERENT project and confirm the move writes into that project's tree, not the local one
- [ ] [t1377_2] Kill the wrapper script mid-move (or point it at a bad path) and confirm minimonitor shows a warning and stays responsive — no traceback, no hang
- [ ] [t1377_3] The column picker's "＋ New column…" row opens a title-entry modal that is fully readable at 40 columns
- [ ] [t1377_3] Submitting an empty or whitespace-only title keeps the modal open with a warning and creates nothing
- [ ] [t1377_3] Creating a column with an emoji/non-ASCII title yields a usable slug id and the column appears in ait board
- [ ] [t1377_3] After creating a column from minimonitor, board_config.local.json is unchanged and board_config.json gained ONLY the new column (no settings block leaked in)
- [ ] [t1377_5] In ait board, press e and confirm the column-management dialog opens and is listed in the footer
- [ ] [t1377_5] The e binding is HIDDEN in the In-Flight, By-Topic and By-Trail views
- [ ] [t1377_5] Reorder columns in the dialog, quit and relaunch the board, and confirm the new order persisted
- [ ] [t1377_5] Merge two columns into a third: all tasks arrive at the bottom of the destination in their original relative order, and both sources disappear from the board
- [ ] [t1377_5] Merging a COLLAPSED source column removes its collapsed state; a collapsed DESTINATION stays collapsed
- [ ] [t1377_5] Merge with "Unsorted / Inbox" as the source: its tasks move and the board does not error
- [ ] [t1377_5] Add, edit and delete a column through the new dialog and confirm each still works as it did from the command palette
- [ ] [t1377_5] Ctrl+P palette still lists every column command, and typing a partial name still finds it (discover and search parity)
- [ ] [t1377_6] Read the updated board and minimonitor doc pages against the shipped behaviour and confirm no statement is stale
