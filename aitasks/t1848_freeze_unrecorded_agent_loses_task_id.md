---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [frozen, session_persistence]
created_at: 2026-09-21 22:42
updated_at: 2026-09-21 22:42
---

## Problem

Freezing an agent that was never recorded by the SessionStart hook creates a record with no task id and no operation. Such a record can be neither restored (no session id) nor re-picked (no task id). The only things left to do with it are to read it or drop it, even though the task is plainly known.

Observed on 2026-09-21: 4 thinking_app records (306a470c, bcd38690, f4e67f01, 2dd0d10d) with windows `agent-pick-449_4`, `agent-pick-462`, `agent-pick-464`, `agent-pick-53_5` all have `task_id: ""`, `operation: ""`, `codeagent_session_id: ""`, and `started_at == frozen_at`. The record was created at freeze time, not at launch.

## Root cause (verified)

- thinking_app runs framework v0.35.1, the same as this repo, so the code is not older. However, `.claude/settings.json` does not exist there: the SessionStart hook was never installed. `install.sh` (used by `ait upgrade`) only stages the seed at `aitasks/metadata/claude_settings.hooks.json`. The merge into `.claude/settings.json` happens only in `ait setup` (`setup_claude_hooks`), which was not re-run after the upgrade.
- With no hook record, `agent_freeze.py::_resolve_record` falls back to an `upsert` with root/window/pane/session only. Unlike `aitask_session_hook.sh` (step 6), it does **not** derive `operation`/`task_id` from the window name (`^agent-(pick|qa|resume)-([0-9]+(_[0-9]+)?)$`).

## Fix

1. In the freeze fallback path, derive operation/task_id from the window name with the same regex the hook uses (share the pattern, e.g. `monitor_core._TASK_ID_RE`; don't copy it). Pass `--operation` / `--task-id` to the upsert. The store must not overwrite existing non-blank values.
2. Consider a one-shot repair in `reconcile` (or a store verb) that backfills task_id for existing frozen records whose window name encodes one. That would make the 4 existing records re-pickable.
3. Add a test: freeze an unrecorded pane in an `agent-pick-<id>` window → the record has task_id and is re-pickable.

The missing-hook-after-upgrade gap is split into its own task.
