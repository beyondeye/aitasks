---
priority: medium
effort: medium
depends: [1377_5]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1243
created_at: 2026-08-07 13:08
updated_at: 2026-08-07 13:08
---

## Failed verification item from t1377_5

> [t1377_5] Add, edit and delete a column through the new dialog and confirm each still works as it did from the command palette

### Source

- **Manual-verification task:** `aitasks/t1377/t1377_7_manual_verification_column_features.md` (item #18)
- **Origin feature task:** t1377_5
- **Origin archived plan:** `aiplans/archived/p1377/p1377_5_board_column_management_dialog.md`

### Commits that introduced the failing behavior

- cf56fae48 feature: Add the board column management dialog (t1377_5)

### Files touched by those commits

- .aitask-scripts/board/aitask_board.py
- tests/test_board_column_dialog.py
- tests/test_board_move_command.py
- tests/test_board_work_report.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1377_7 item #18.
