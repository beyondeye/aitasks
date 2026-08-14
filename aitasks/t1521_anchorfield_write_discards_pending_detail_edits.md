---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui]
gates: [risk_evaluated]
anchor: 1468
followup_kind: upstream_defect
created_at: 2026-08-14 16:19
updated_at: 2026-08-14 16:19
---

## Origin

Spawned from t1468_8 during Step 8b review.

## Upstream defect

- `aitask_board.py:4899-4910` — `AnchorField._apply` calls
  `_reload_detail_screen` on success, which pushes a **fresh**
  `TaskDetailScreen` whose `__init__` re-seeds `_original_values` from disk, so
  any pending unsaved `CycleField` edit (priority / effort / status /
  issue_type) is **silently discarded** with no warning and `#btn_save` returns
  to `disabled`. Pre-existing; out of scope for t1468_8, which guarded only its
  own row.

## Diagnostic context

`TaskDetailScreen` hosts **two persistence models**:

- the four `CycleField`s are **deferred** — an edit lands in `_current_values`,
  lights `#btn_save` via `_update_save_button`, and is written only on Save;
- `AnchorField` (and, since t1468_8, `FollowupKindField`) write **immediately**
  through `aitask_update.sh` and then call `_reload_detail_screen`, which does
  `task.load()` + `app.replace_screen_with_detail(task)` — a brand-new screen.

Reproduce: open a task detail, cycle Priority (Save lights up), focus the
`Anchor:` row, press Enter and set an anchor. The screen reloads and the
pending priority change is gone.

t1468_8 verified this mechanism for its own field and guarded against it; the
`Anchor:` row one line above is still exposed.

## Suggested fix

Consult the field-agnostic predicate t1468_8 added —
`TaskDetailScreen.has_unsaved_edits()` — and refuse to open `AnchorEditScreen`
while it is true, mirroring `FollowupKindField`: push a `blocked` flag from
`_update_save_button`, change the row hint to name the remedy, and notify on
Enter instead of opening the editor. See `FollowupKindField.set_blocked` /
`on_key` for the shape, and `FollowupKindDirtyGuardTests` in
`tests/test_board_detail_followup_kind.py` for the test pattern (it pins both
edges of the toggle and carries a negative control).
