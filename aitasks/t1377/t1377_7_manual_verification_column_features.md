---
priority: medium
effort: medium
depends: [t1377_6]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1377_2, t1377_3, t1377_5, t1377_6]
assigned_to: dario-e@beyond-eye.com
anchor: 1243
created_at: 2026-08-04 10:02
updated_at: 2026-08-07 13:08
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1377_2] In a real ~40-column minimonitor companion pane, press p, enter a task number, and confirm the detail dialog shows THREE buttons (OK/Launch anyway, Move to column…, Cancel) fully readable and not clipped — PASS 2026-08-07 13:07 auto: live 40x45 tmux minimonitor pane -- detail dialog rendered OK / Move to column / Cancel, all readable, unclipped
- [x] [t1377_2] Choosing the pick path launches the agent exactly as before — same launch dialog, same window naming, no behaviour change — PASS 2026-08-07 13:07 auto: OK path opened AgentCommandScreen (Profile/Agent/Command, window name agent-pick-7); t1377_2 diff left _launch_pick untouched (only tuple unpack widened)
- [x] [t1377_2] Choosing "Move to column…" opens the column picker; ↑/↓ navigate, Enter selects, Esc cancels, and the task's current column is visibly marked — PASS 2026-08-07 13:07 auto: picker opened; Up/Down moved focus (Edited->Backlog->Zulu Lane), Enter moved the task, Esc cancelled with no write, current column marked with a dot
- [x] [t1377_2] After a move, ait board shows the task at the BOTTOM of the destination column on next refresh (not at an arbitrary position) — PASS 2026-08-07 13:07 auto: seam move of t3 -> backlog gave idx 1224 vs residents 100/200; live board refresh (r) rendered t3 last in Backlog
- [x] [t1377_2] The moved task's updated_at in its frontmatter is UNCHANGED (a layout write must not stamp it) — PASS 2026-08-07 13:07 auto: updated_at stayed 2026-08-01 10:00 across seam move AND a real minimonitor move
- [x] [t1377_2] Multi-session: follow an agent belonging to a DIFFERENT project and confirm the move writes into that project's tree, not the local one — PASS 2026-08-07 13:07 auto: two projects, same task id 7 in both; companion beside projB agent with own root projA -> picker listed B-Todo/B-Doing and the write landed in projB; projA decoy byte-identical
- [x] [t1377_2] Kill the wrapper script mid-move (or point it at a bad path) and confirm minimonitor shows a warning and stays responsive — no traceback, no hang — PASS 2026-08-07 13:07 auto: wrapper deleted -> toast 'ERROR:cannot run ...'; wrapper rigged to exit 3 on move -> toast 'Move failed: boom...'; no traceback in scrollback, p reopened after each
- [x] [t1377_3] The column picker's "＋ New column…" row opens a title-entry modal that is fully readable at 40 columns — PASS 2026-08-07 13:07 auto: '+ New column...' opened 'New Board Column' modal, fully readable at 40 cols with stacked Create/Cancel
- [x] [t1377_3] Submitting an empty or whitespace-only title keeps the modal open with a warning and creates nothing — PASS 2026-08-07 13:07 auto: empty and whitespace-only submits both kept the modal open with a 'Title is required' toast; board_config.json column list unchanged
- [x] [t1377_3] Creating a column with an emoji/non-ASCII title yields a usable slug id and the column appears in ait board — PASS 2026-08-07 13:07 auto: '🚀 Spät Lane' -> slug spt_lane (protocol-safe); column rendered in ait board with the moved task in it
- [x] [t1377_3] After creating a column from minimonitor, board_config.local.json is unchanged and board_config.json gained ONLY the new column (no settings block leaked in) — PASS 2026-08-07 13:07 auto: created from minimonitor -- board_config.local.json byte-identical, project file gained only the new column + order entry, top-level keys stayed [column_order, columns]
- [x] [t1377_5] In ait board, press e and confirm the column-management dialog opens and is listed in the footer — PASS 2026-08-07 13:07 auto: live board footer row 3 shows 'e Columns'; pressing e opened 'Manage columns' listing all columns with counts + Add/Edit/Delete/Merge
- [x] [t1377_5] The e binding is HIDDEN in the In-Flight, By-Topic and By-Trail views — PASS 2026-08-07 13:07 auto: 'e Columns' present in All view footer, absent in In-Flight, By-Topic and By-Trail; pressing e in By-Trail opened nothing (check_action False = hidden AND undispatched)
- [x] [t1377_5] Reorder columns in the dialog, quit and relaunch the board, and confirm the new order persisted — PASS 2026-08-07 13:07 auto: shift+Down moved Now below Next, persisted immediately, survived quit and relaunch (column_order ['next','now','backlog'])
- [x] [t1377_5] Merge two columns into a third: all tasks arrive at the bottom of the destination in their original relative order, and both sources disappear from the board — PASS 2026-08-07 13:07 auto: merge_columns(['alpha','beta'],'dest') on real files -> 8024/9048/10072/11096 all below resident 7000, per-source relative order kept, both sources gone from columns and column_order
- [x] [t1377_5] Merging a COLLAPSED source column removes its collapsed state; a collapsed DESTINATION stays collapsed — PASS 2026-08-07 13:07 auto: collapsed ['alpha','dest'] before merge -> ['dest'] after; collapsed source cleared, collapsed destination retained
- [x] [t1377_5] Merge with "Unsorted / Inbox" as the source: its tasks move and the board does not error — PASS 2026-08-07 13:07 auto: merge_columns(['unordered'],'dest') moved both unsorted tasks to the bottom, no error, board_config.json left valid
- [fail] [t1377_5] Add, edit and delete a column through the new dialog and confirm each still works as it did from the command palette — FAIL 2026-08-07 13:08 follow-up t1454
- [x] [t1377_5] Ctrl+P palette still lists every column command, and typing a partial name still finds it (discover and search parity) — PASS 2026-08-07 13:07 auto: palette search 'olum' returned all 8 column commands incl. Merge Columns; discover()/search() both iterate the single _COMMANDS via _resolved(); CommandPaletteParityTests 5 passed
- [fail] [t1377_6] Read the updated board and minimonitor doc pages against the shipped behaviour and confirm no statement is stale — FAIL 2026-08-07 13:08 follow-up t1455
