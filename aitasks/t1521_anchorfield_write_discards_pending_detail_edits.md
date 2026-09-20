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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_7** id=2026-09-20T06:11:35Z.b5a7a06d71ca210c62214300 from=t1794_7 from_verified=yes at=2026-09-20T06:11:35Z base=4b76a992b8ec9a170c4238d08214cf4f640c47b0 base_branch=main dirty=yes host=omg16
>
> | t1794_7 moved the whole task editor out of `aitask_board.py` into the new
> | `.aitask-scripts/board/board_detail_screen.py` (landed as commit
> | `refactor: Extract the task editor into board_detail_screen.py (t1794_7)`), so
> | every file/line anchor in this task's body is stale. The defect itself is
> | unchanged — the code moved verbatim.
> | 
> | New locations (as of that commit):
> | 
> | - the defect: `board_detail_screen.py:553` `AnchorField._apply` → its
> |   `_reload_detail_screen(...)` call on success (was `aitask_board.py:4899-4910`;
> |   `AnchorField` is at `:512`)
> | - `TaskDetailScreen.__init__` re-seeding `_original_values` /
> |   `_current_values`: `board_detail_screen.py:1455-1461`
> | - `FollowupKindField._apply` (the same immediate-write + reload idiom, added by
> |   t1468_8): `board_detail_screen.py:774`
> | - `_reload_detail_screen`, `CycleField`, `_update_save_button` and every other
> |   field widget: same module
> | 
> | Two things that change how a fix is written, not what it fixes:
> | 
> | 1. `board_detail_screen.py` must not import `aitask_board` (t1794 contract C1).
> |    The three board helpers the screen needs — task types, user email, tmux
> |    session — arrive as required keyword-only callables, and the board binds them
> |    in `aitask_board.make_task_detail_screen()`. If a fix needs a fourth board
> |    value, inject it the same way rather than importing.
> | 2. Tests construct the screen through `ab.make_task_detail_screen(task, manager)`
> |    — a bare `ab.TaskDetailScreen(task)` now raises `TypeError`. A stub of
> |    anything the screen or a field calls (`subprocess`, `_reload_detail_screen`,
> |    …) must patch `ab.board_detail_screen`; the board's re-exports are inert
> |    there.
> | 
> | Advisory only — this is one session's report about the tree at the commit above,
> | not an instruction about how to fix t1521.
