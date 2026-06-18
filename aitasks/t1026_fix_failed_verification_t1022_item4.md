---
priority: medium
effort: medium
depends: [1021]
issue_type: bug
status: Implementing
labels: [verification, bug]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-18 11:17
updated_at: 2026-06-18 15:54
---

## Failed verification item from t1021

> Open a Folded Tasks / Folded Into / Parent relation where the target is archived; confirm it resolves read-only.

### Source

- **Manual-verification task:** `aitasks/t1022_manual_verification_board_archived_relation_dialogs.md` (item #4)
- **Origin feature task:** t1021
- **Origin archived plan:** `aiplans/archived/p1021_board_resolve_archived_tasks_in_cross_repo_children_folded_d.md`

### Commits that introduced the failing behavior

- 83babd9b9 bug: Resolve archived tasks in board cross-repo/children/folded dialogs (t1021)

### Files touched by those commits

- .aitask-scripts/board/aitask_board.py
- tests/test_board_archived_relation_lookup.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1022 item #4.
