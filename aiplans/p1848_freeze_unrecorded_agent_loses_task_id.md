---
Task: t1848_freeze_unrecorded_agent_loses_task_id.md
Base branch: main
Output branch: main
---

# t1848 — Freezing an unrecorded agent loses its task id

## Context

When the SessionStart hook never recorded an agent (e.g. `.claude/settings.json`
missing after `ait upgrade`), `agent_freeze._resolve_record` falls back to an
`upsert` carrying only root/window/pane/session. Unlike `aitask_session_hook.sh`
step 6, it never derives `operation`/`task_id` from the window name
(`agent-(pick|qa|resume)-<id>`), so the frozen record can be neither resumed (no
session id) nor re-picked (`agent_restore` → `RESTORE_FAILED:…|no_task_id`,
frozenagent shows "(no task)"). Scope is new freezes only: records already
frozen before this fix are not repaired.

Store semantics that shape the fix (`lib/agent_sessions.py`):
- `_apply_upsert_fields`: `operation`/`task_id` — `None` = not supplied, but a
  **blank string overwrites**. So passing values to `upsert` would overwrite an
  existing non-blank value whenever the fallback selects an existing record by
  pane identity.
## Approach

A new blank-only store verb `fill-task`, driven by a freeze-engine helper that
derives the values from the window name via the **shared** regex, run on both
record-resolution paths of a freeze.

### 1. Shared window-name pattern — `.aitask-scripts/monitor/monitor_core.py`

- Change `_TASK_ID_RE` to named groups (same shape, one source of truth):
  `^agent-(?P<operation>pick|qa|resume)-(?P<task_id>\d+(?:_\d+)?)$`
  (only consumer of the group is `task_id_from_window_name`; others merely
  import the name — verified by grep).
- `task_id_from_window_name` → `m.group("task_id")`.
- Add `task_ref_from_window_name(window_name) -> tuple[str, str] | None`
  returning `(operation, task_id)`; pure, import-free, docstring noting it is
  the Python twin of the hook's step 6.
- `aitask_session_hook.sh` comment stays ("Same shape as monitor_core._TASK_ID_RE").

`agent_freeze` imports it directly (`from monitor.monitor_core import
task_ref_from_window_name`, as `agent_frozen_ops` already does for the option
names); it is a pure function never swapped by tests, so the seam rule does not
apply.

### 2. Store verb `fill-task` — `.aitask-scripts/lib/agent_sessions.py`

```python
def fill_task(sf, id, *, operation: str, task_id: str) -> tuple[SessionsFile, str]:
    """Fill a record's BLANK operation / task_id; never overwrite, any state."""
```
- `_require_record(sf, id)`; for each of the two fields: set only if stored is
  blank and the supplied value is non-blank.
- Returns `FILLED:<id>|operation,task_id` (names of fields written) or
  `FILL_NOOP:<id>|unchanged`.
- Needs **no lease** and is not state-gated: it touches only descriptive
  fields — never state, lease, location or captures — and runs under the
  wrapper's mutex like every writer, so no update is lost. (The freeze path
  calls it while the record is still `live`, before `freeze-begin`.)
- CLI dispatch in `main()`: `elif verb == "fill-task": fill_task(sf, _id_arg(rest[0]), operation=_arg(rest,"operation",""), task_id=_arg(rest,"task-id",""))`.

### 3. Wrapper — `.aitask-scripts/aitask_agent_sessions.sh`

- Header verb list: `fill-task <id> [--operation <op>] [--task-id <t>]` with a
  one-line note (blank-only, any state, no lease). Add to `usage()`.
- `cmd_fill_task`: `require_hex_id`, `sessions_lock_or_busy "$WRITE_LOCK_TIMEOUT"`,
  `run_sessions_py fill-task "$id" "$@"`; `case` entry.

### 4. Freeze engine — `.aitask-scripts/lib/agent_freeze.py`

- New best-effort helper `_backfill_task_ref(record_id, facts)`, modelled on
  `_backfill_agent_string` (re-reads the record AS STORED, never raises, warns
  to stderr on failure):
  - `stored = frozen_ops.store_show(record_id)`; return if missing or both
    `operation` and `task_id` already non-blank.
  - `ref = task_ref_from_window_name(stored.get("window") or facts.get("window",""))`;
    return if `None`.
  - `frozen_ops.store("fill-task", record_id, "--operation", op, "--task-id", tid)`;
    success test is the `FILLED:`/`FILL_NOOP:` line prefix, else `WARNING:` line.
- Call it in `_resolve_record` on **both** paths (stamped, and after the fallback
  upsert/stamp), next to `_backfill_agent_string`. Update the docstring.
  (The fallback upsert itself is left without `--operation/--task-id`: sending
  them would overwrite a non-blank value on a pane-identity match.)
- Scope: new freezes only. `reconcile()` is **not** changed — already-frozen
  legacy records are out of scope (user decision).

### 5. Tests

- `tests/test_agent_freeze.py`
  - `_FakeStore`: pass `--operation`/`--task-id` through `upsert` (None when
    absent, like the others) and dispatch `fill-task` to `agent_sessions.fill_task`.
  - New `TaskRefBackfillTests(_FreezeTestCase)` (fixture window is
    `agent-pick-1705`, record created with blank task):
    1. unstamped pane in `agent-pick-1705` → freeze ok, record frozen with
       `task_id == "1705"`, `operation == "pick"`, and immediately re-pickable:
       `agent_restore`'s repick preflight no longer reports `no_task_id`
       (asserted through `agent_restore.build_repick_argv` / the preflight with
       the dry-run command resolution stubbed), while a control record frozen
       without the backfill does report `no_task_id`.
    2. stamped pane with blank task → filled too.
    3. existing non-blank values (`qa`/`999`) are never overwritten.
    4. non-task window (`agent-explore-x`) → stays blank, no `fill-task` call.
    5. negative control: a `fill-task` failure (`fail_verbs`) warns and the
       freeze still succeeds.
- `tests/test_agent_sessions_transitions.py` (or `test_agent_sessions.py`):
  `fill_task` fills blanks only, works from every state, leaves lease/state
  untouched, unknown id raises.
- `tests/test_agent_sessions_contract_call_sites.py`: add `fill-task` to
  `VERB_FN` if the file's checks cover it without a pinned-table row; otherwise
  leave (it transcribes the pinned §C/§D tables).
- `task_id_from_window_name` tests (`tests/test_monitor_completed_status.py`)
  must still pass; add a `task_ref_from_window_name` case there.
- Wrapper: a small end-to-end call of `aitask_agent_sessions.sh fill-task` in an
  existing shell test that already drives the wrapper against a temp
  `AITASKS_AGENT_SESSIONS_FILE` (e.g. `tests/test_agent_sessions_stamp.sh`),
  including a bad-id usage check.

## Verification

- `python3 tests/test_agent_freeze.py`, `python3 tests/test_agent_sessions_transitions.py`,
  `python3 tests/test_agent_sessions_contract_call_sites.py`,
  `python3 tests/test_monitor_completed_status.py`, `python3 tests/test_agent_restore.py`,
  `python3 tests/test_frozenagent_app.py`, the edited shell test.
- `shellcheck .aitask-scripts/aitask_agent_sessions.sh`.
- Full Python suite: `bash tests/run_all_python_tests.sh` (check the last line).

## Step 9

Post-implementation: commit code (`bug: … (t1848)`), then archival per Step 9.

## Risk

### Code-health risk: low
- `fill-task` is a store write outside the lease protocol · severity: low · → mitigation: none needed — descriptive fields only, blank-only, under the store mutex; pinned by the "every state, state/lease untouched" test in the plan.
- `_TASK_ID_RE` gains named groups · severity: low · → mitigation: none needed — shape unchanged, sole group consumer updated, existing window-name tests re-run.

### Goal-achievement risk: low
None identified.
