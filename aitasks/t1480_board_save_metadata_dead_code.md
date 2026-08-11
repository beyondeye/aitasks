---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1243
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-08-10 22:09
updated_at: 2026-08-11 00:10
---

## Context

Two pre-existing pieces of dead/misleading code in
`.aitask-scripts/board/aitask_board.py`, both surfaced while implementing
t1243_10 (group collapse persistence). Neither is a live bug — nothing
misbehaves today — but both read as if they do something they cannot, which is
the kind of thing that misleads the next reader of the save path.

Recorded in `aiplans/archived/p1243/p1243_10_group_collapse_and_filtering.md`
under "Upstream defects identified".

## Defect 1 — the `if user_data:` guard in `save_metadata` is vacuous

`TaskManager.save_metadata` builds:

```python
data = {"columns": ..., "column_order": ..., "settings": self._settings_for_save()}
project_data, user_data = split_config(data, project_keys=..., user_keys=...)
```

`_USER_KEYS` is `{"settings"}` and `data` **always** carries the `"settings"`
key, so `split_config` always returns `user_data == {"settings": {...}}` —
truthy even when `self.settings == {}`. The guard (now inside
`_write_user_layer`, previously inline at `:1321`) therefore never skips.

It reads as "the local file is written only sometimes", which is false, and it
invites a reader to assume a settings-empty board leaves `board_config.local.json`
untouched. Either drop the guard, or make it mean something (e.g. skip when the
serialized user payload is unchanged from disk — a genuinely useful no-op skip).

## Defect 2 — the `auto_refresh_minutes` property setter has zero callers

`TaskManager.auto_refresh_minutes` (property + setter, around `:1329-1334`)
has **no callers for the setter**. `KanbanApp._handle_settings_result` writes
the key through `self.manager.settings.update(result)` instead, bypassing the
property entirely.

Same class as the dead `Task._BOARD_KEYS` assignment that t1243_2 retired by
making validation read it. Either route the settings-dialog write through the
setter, or delete the setter and keep the getter.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — `TaskManager.save_metadata` /
  `_write_user_layer`, and the `auto_refresh_minutes` property pair.

## Verification

- Defect 1: a test pinning the chosen semantics — either that
  `board_config.local.json` is always written (guard dropped), or that an
  unchanged payload issues no write (guard made meaningful), with a negative
  control that fails under the other reading.
- Defect 2: if the setter is kept, a test asserting the settings dialog's write
  goes through it; if deleted, `grep` shows no reference and the suite is green.
- Full suite: `bash tests/run_all_python_tests.sh` (read the last line).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-10T21:09:53Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-11T11:20:03Z status=pass attempt=1 type=human
